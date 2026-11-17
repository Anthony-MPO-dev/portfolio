"""Slow request tracing with OpenTelemetry, in the API process, with no collector and no paid service (pattern 17).

Responsibility: one root span per HTTP request (TraceRequests; the worker's long polls are left out) and, inside a
request, one child span per adapter call (traced, wired in app.main, so no use case changes); a returned iterator (the
model's streamed reply) is timed from the call to its last chunk, with the first one marked. A request is slow when
its first byte (the wait the visitor feels: the first chunk of a streamed reply, or the whole of a JSON one) takes
TRACE_SLOW_MS or more; SlowTraces then writes one log line, `slow_request {json}`: the route template, status, total
ms, ms to the first byte, the first MAX_SPANS adapter calls (name, ms, ms to the first chunk, error type) and the trace
id. Nothing else leaves a span: never the IP, path, query, headers, visitor text or an error message. Traces whose
request never ends are capped, so memory stays bounded. A stream closed after its request ended (the visitor left) is
dropped with that cap.
Public API: make_tracer, SlowTraces, TraceRequests, traced, MAX_SPANS.
Used by: app.main.
Depends on: opentelemetry-sdk.
Tests: tests/test_tracing.py.
"""

import json
import logging
import threading
import time
from collections.abc import Callable, Iterator
from functools import wraps

from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor, TracerProvider

log = logging.getLogger(__name__)
FIRST = "first chunk"
MAX_SPANS = 40  # adapter calls per log line: a request makes a handful, a runaway loop shouldn't flood the log
METHODS = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}  # anything else is OTHER: the visitor picks it


def _ms(start: int, end: int) -> int:
    return round((end - start) / 1_000_000)


def _first(span: ReadableSpan) -> int | None:
    return next((e.timestamp for e in span.events if e.name == FIRST), None)


class SlowTraces(SpanProcessor):
    def __init__(self, slow_ms: int, emit: Callable[[str], None], max_pending: int = 1000):
        self.slow_ms, self.emit, self.max_pending = slow_ms, emit, max_pending
        self.pending: dict[int, list[tuple[int, dict]]] = {}  # trace id -> (start, adapter call)
        self.lock = threading.Lock()

    def on_end(self, span: ReadableSpan) -> None:
        start, end, first = span.start_time or 0, span.end_time or 0, _first(span)
        trace_id = span.context.trace_id if span.context else 0
        if span.parent is not None:
            call = {"name": span.name, "ms": _ms(start, end)}
            if first:
                call["first_ms"] = _ms(start, first)
            if error := (span.attributes or {}).get("error.type"):
                call["error"] = error
            with self.lock:
                if trace_id not in self.pending and len(self.pending) >= self.max_pending:
                    del self.pending[next(iter(self.pending))]
                self.pending.setdefault(trace_id, []).append((start, call))
            return
        with self.lock:
            calls = self.pending.pop(trace_id, [])
        if _ms(start, first or end) < self.slow_ms:
            return
        line = {
            "route": span.name,
            "status": (span.attributes or {}).get("http.response.status_code", 0),
            "ms": _ms(start, end),
            "first_ms": _ms(start, first or end),
            "spans": [call for _, call in sorted(calls, key=lambda c: c[0])][:MAX_SPANS],
            "trace": f"{trace_id:032x}",
        }
        self.emit("slow_request " + json.dumps(line))


def make_tracer(slow_ms: int, emit: Callable[[str], None] | None = None) -> trace.Tracer:
    """Its own provider, not the global one, so libraries that trace themselves stay off."""
    provider = TracerProvider()
    provider.add_span_processor(SlowTraces(slow_ms, emit or log.warning))
    return provider.get_tracer("portfolio-api")


class TraceRequests:
    """Pure ASGI middleware: the root span, named after the route template ("POST /api/chat"), never the path."""

    def __init__(self, app, tracer: trace.Tracer, skip: tuple[str, ...] = ("/api/worker/",)):
        self.app, self.tracer, self.skip = app, tracer, skip

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"].startswith(self.skip):
            return await self.app(scope, receive, send)
        status, first = 0, True
        with self.tracer.start_as_current_span("request", record_exception=False, set_status_on_exception=False) as span:

            async def send_traced(message):
                nonlocal status, first
                if message["type"] == "http.response.start":
                    status = message["status"]
                elif message["type"] == "http.response.body" and first:
                    span.add_event(FIRST)
                    first = False
                await send(message)

            try:
                await self.app(scope, receive, send_traced)
            except Exception:
                status = status or 500
                raise
            finally:
                method = scope["method"] if scope["method"] in METHODS else "OTHER"
                span.update_name(f"{method} {getattr(scope.get('route'), 'path', None) or 'unmatched'}")
                span.set_attribute("http.response.status_code", status)


def _failed(span: trace.Span, error: BaseException) -> None:
    span.set_attribute("error.type", type(error).__name__)  # the type only: a message can carry visitor text
    span.set_status(trace.StatusCode.ERROR)


class traced:  # noqa: N801 (reads as a function at the wiring site)
    """Wraps an adapter: inside a request, each method call (or the call itself, for a callable) is a child span named
    "<name>.<method>". Results, errors and attributes pass through unchanged, and `__wrapped__` is the adapter."""

    def __init__(self, target, name: str, tracer: trace.Tracer):
        self.__wrapped__, self._name, self._tracer = target, name, tracer

    def __getattr__(self, attr: str):
        value = getattr(self.__wrapped__, attr)
        if not callable(value) or attr.startswith("_"):
            return value
        return wraps(value)(lambda *args, **kwargs: self._run(f"{self._name}.{attr}", value, args, kwargs))

    def __call__(self, *args, **kwargs):
        return self._run(self._name, self.__wrapped__, args, kwargs)

    def _run(self, name: str, fn, args, kwargs):
        if not trace.get_current_span().is_recording():  # outside a request (startup, the purge): no span
            return fn(*args, **kwargs)
        span = self._tracer.start_span(name)
        try:
            result = fn(*args, **kwargs)
        except BaseException as error:
            _failed(span, error)
            span.end()
            raise
        if isinstance(result, Iterator):
            return _Timed(span, result)
        span.end()
        return result


class _Timed:
    """An adapter's iterator, timed from the call to its last chunk (a consumer may stop reading at the last one and
    close it later); closing it, even before the first chunk, closes the real one."""

    def __init__(self, span: trace.Span, items: Iterator):
        self.span, self.items, self.last, self.done = span, items, None, False

    def __iter__(self):
        return self

    def __next__(self):
        try:
            item = next(self.items)
        except StopIteration:
            self.close()
            raise
        except Exception as error:
            _failed(self.span, error)
            self.close()
            raise
        if self.last is None:
            self.span.add_event(FIRST)
        self.last = time.time_ns()
        return item

    def close(self) -> None:
        if self.done:
            return
        self.done = True
        try:
            if close := getattr(self.items, "close", None):
                close()
        finally:
            self.span.end(end_time=self.last)

    __del__ = close
