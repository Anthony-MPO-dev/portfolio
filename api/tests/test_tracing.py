"""Slow request tracing: one line per slow request, with its route, status and the time each adapter took, and never
the visitor's IP, path, query or text."""

import json
import time

import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from app.tracing import SlowTraces, TraceRequests, make_tracer, traced


class Slow:
    def __init__(self, seconds=0.0):
        self.seconds = seconds

    def lookup(self, key):
        time.sleep(self.seconds)
        return [key]

    def stream(self, text):
        time.sleep(self.seconds)
        yield from text.split()

    def broken(self, text):
        raise ValueError(f"bad input: {text}")

    def __call__(self, token):
        return token == "ok"


def api(slow_ms, adapter_seconds=0.0):
    lines: list[str] = []
    tracer = make_tracer(slow_ms, emit=lines.append)
    adapter = traced(Slow(adapter_seconds), "redis", tracer)
    app = FastAPI()

    @app.get("/api/items/{item}")
    def item(item: str):
        return {"found": adapter.lookup(item), "human": adapter("ok")}

    @app.post("/api/chat")
    def chat():
        return StreamingResponse(adapter.stream("my secret question"), media_type="text/plain")

    @app.get("/api/fail")
    def fail():
        adapter.broken("my secret question")

    app.add_middleware(TraceRequests, tracer=tracer)
    return TestClient(app, raise_server_exceptions=False), lines


def logged(lines):
    assert len(lines) == 1, lines
    prefix, _, body = lines[0].partition(" ")
    assert prefix == "slow_request"
    return json.loads(body)


def test_a_slow_request_logs_its_route_status_and_each_adapter_call():
    client, lines = api(slow_ms=0)
    assert client.get("/api/items/abc?email=x@y.z", headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 200
    trace = logged(lines)
    assert (trace["route"], trace["status"]) == ("GET /api/items/{item}", 200)
    assert [s["name"] for s in trace["spans"]] == ["redis.lookup", "redis"]
    assert all(s["ms"] >= 0 for s in trace["spans"]) and trace["ms"] >= 0 and len(trace["trace"]) == 32
    assert not any(leak in lines[0] for leak in ("abc", "email", "203.0.113.9", "testclient"))


def test_a_fast_request_logs_nothing():
    client, lines = api(slow_ms=10_000)
    client.get("/api/items/abc")
    assert lines == []


def test_a_streamed_reply_is_timed_until_its_last_chunk_with_the_first_one_marked():
    client, lines = api(slow_ms=0, adapter_seconds=0.05)
    assert client.post("/api/chat").text == "mysecretquestion"
    (stream,) = logged(lines)["spans"]
    assert stream["name"] == "redis.stream" and stream["ms"] >= 50 and 50 <= stream["first_ms"] <= stream["ms"]
    assert "secret" not in lines[0]


def test_a_failing_adapter_keeps_its_error_and_logs_only_the_error_type():
    client, lines = api(slow_ms=0)
    assert client.get("/api/fail").status_code == 500
    trace = logged(lines)
    assert trace["status"] == 500 and trace["spans"] == [{"name": "redis.broken", "ms": trace["spans"][0]["ms"],
                                                          "error": "ValueError"}]  # fmt: skip
    assert "secret" not in lines[0] and "bad input" not in lines[0]


def test_the_wrapped_adapter_still_raises_and_closes_like_the_real_one():
    tracer = make_tracer(0, emit=lambda line: None)
    adapter = traced(Slow(), "redis", tracer)
    with pytest.raises(ValueError, match="bad input"):
        adapter.broken("x")
    chunks = adapter.stream("a b c")
    assert next(chunks) == "a"
    chunks.close()  # the visitor left: the real generator is closed too
    assert adapter.seconds == 0.0  # plain attributes pass through


def test_an_adapter_call_outside_a_request_is_not_traced():
    lines: list[str] = []
    adapter = traced(Slow(), "embed", make_tracer(0, emit=lines.append))
    assert adapter("ok") is True and list(adapter.stream("a b")) == ["a", "b"]  # e.g. the facts embedded at startup
    assert lines == []


def test_an_unknown_path_is_logged_as_unmatched_not_by_its_path():
    client, lines = api(slow_ms=0)
    client.get("/wp-admin/secret-path")
    assert logged(lines)["route"] == "GET unmatched" and "secret-path" not in lines[0]


def test_unfinished_traces_are_capped_so_memory_stays_bounded():
    processor = SlowTraces(0, emit=lambda line: None, max_pending=3)
    provider = TracerProvider()
    provider.add_span_processor(processor)
    tracer = provider.get_tracer("test")
    for n in range(1, 11):  # child spans of requests whose root never ends
        sampled = trace.TraceFlags(trace.TraceFlags.SAMPLED)
        parent = trace.NonRecordingSpan(trace.SpanContext(trace_id=n, span_id=n, is_remote=False, trace_flags=sampled))
        tracer.start_span("child", context=trace.set_span_in_context(parent)).end()
    assert len(processor.pending) == 3
