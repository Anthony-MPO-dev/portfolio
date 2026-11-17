"""Slow request tracing with OpenTelemetry, in the API process, with no collector and no paid service (pattern 17).

Responsibility: one root span per HTTP request (TraceRequests) and one child span per adapter call (traced, wired in
app.main, so no use case changes); a streamed reply is timed until its last chunk, with the first one marked. When a
request takes TRACE_SLOW_MS or more, SlowTraces writes one log line: `slow_request {json}` with the route template,
status, total ms, each adapter call (name, ms, ms to the first chunk, error type) and the trace id. Nothing else
leaves a span: never the IP, path, query, headers, visitor text or an error message. Traces whose request never
ends are capped, so memory stays bounded.
Public API: make_tracer, SlowTraces, TraceRequests, traced.
Used by: app.main.
Depends on: opentelemetry-sdk.
Tests: tests/test_tracing.py.
"""

import json
import logging
import threading
from collections.abc import Callable, Iterator
from functools import wraps

from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor, TracerProvider

log = logging.getLogger(__name__)
FIRST = "first chunk"


def _ms(start: int, end: int) -> int:
    return round((end - start) / 1_000_000)


class SlowTraces(SpanProcessor):
    def __init__(self, slow_ms: int, emit: Callable[[str], None], max_pending: int = 1000):
        self.slow_ms, self.emit, self.max_pending = slow_ms, emit, max_pending
        self.pending: dict[int, list[tuple[int, dict]]] = {}  # trace id -> (start, child record)
        self.lock = threading.Lock()

    def on_end(self, span: ReadableSpan) -> None:
        start, end = span.start_time or 0, span.end_time or 0
        trace_id = span.context.trace_id if span.context else 0
        if span.parent is not None:
            record = {"name": span.name, "ms": _ms(start, end)}
            if first := next((e.timestamp for e in span.events if e.name == FIRST), None):
                record["first_ms"] = _ms(start, first)
            if error := (span.attributes or {}).get("error.type"):
                record["error"] = error
            with self.lock:
                if trace_id not in self.pending and len(self.pending) >= self.max_pending:
                    del self.pending[next(iter(self.pending))]
                self.pending.setdefault(trace_id, []).append((start, record))
            return
        with self.lock:
            children = self.pending.pop(trace_id, [])
        if _ms(start, end) < self.slow_ms:
            return
        attributes = span.attributes or {}
        line = {
            "route": span.name,
            "status": attributes.get("http.response.status_code", 0),
            "ms": _ms(start, end),
            "spans": [record for _, record in sorted(children, key=lambda child: child[0])][:40],
            "trace": f"{trace_id:032x}",
        }
        self.emit("slow_request " + json.dumps(line))


def make_tracer(slow_ms: int, emit: Callable[[str], None] | None = None, max_pending: int = 1000) -> trace.Tracer:
    """Its own provider, not the global one: libraries that trace themselves (the Anthropic SDK can record the
    conversation) stay off."""
    provider = TracerProvider()
    provider.add_span_processor(SlowTraces(slow_ms, emit or log.warning, max_pending))
    return provider.get_tracer("portfolio-api")


class TraceRequests:
    """Pure ASGI middleware: the root span, named after the route template ("POST /api/chat"), never the path."""

    def __init__(self, app, tracer: trace.Tracer):
        self.app, self.tracer = app, tracer

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        status = 0

        async def send_status(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        with self.tracer.start_as_current_span("request", record_exception=False) as span:
            try:
                await self.app(scope, receive, send_status)
            except Exception:
                status = status or 500
                raise
            finally:
                route = getattr(scope.get("route"), "path", None) or "unmatched"
                span.update_name(f"{scope['method']} {route}")
                span.set_attribute("http.response.status_code", status)


def _failed(span: trace.Span, error: BaseException) -> None:
    span.set_attribute("error.type", type(error).__name__)  # the type only: a message can carry visitor text
    span.set_status(trace.StatusCode.ERROR)


class traced:  # noqa: N801 (reads as a function at the wiring site)
    """Wraps an adapter: inside a request, each method call (or the call itself, for a callable) is a child span named
    "<name>.<method>". Results, errors and attributes pass through unchanged; a returned iterator is timed until it
    ends or is closed, and closing it closes the real one."""

    def __init__(self, target, name: str, tracer: trace.Tracer):
        self._target, self._name, self._tracer = target, name, tracer

    def __getattr__(self, attr: str):
        value = getattr(self._target, attr)
        if not callable(value) or attr.startswith("_"):
            return value
        return wraps(value)(lambda *args, **kwargs: self._run(f"{self._name}.{attr}", value, args, kwargs))

    def __call__(self, *args, **kwargs):
        return self._run(self._name, self._target, args, kwargs)

    def _run(self, name: str, fn, args, kwargs):
        if not trace.get_current_span().is_recording():  # outside a request (startup, the purge): no span
            return fn(*args, **kwargs)
        span = self._tracer.start_span(name, record_exception=False)
        try:
            result = fn(*args, **kwargs)
        except BaseException as error:
            _failed(span, error)
            span.end()
            raise
        if isinstance(result, Iterator):
            return _timed(span, result)
        span.end()
        return result


def _timed(span: trace.Span, items: Iterator):
    first = True
    try:
        for item in items:
            if first:
                span.add_event(FIRST)
                first = False
            yield item
    except GeneratorExit:
        raise
    except BaseException as error:
        _failed(span, error)
        raise
    finally:
        close = getattr(items, "close", None)
        if close:
            close()
        span.end()
