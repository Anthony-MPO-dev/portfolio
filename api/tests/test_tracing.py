"""Slow request tracing: one line per slow request, with its route, status and the time each adapter took, and never
the visitor's IP, path, query or text."""

import inspect
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
    def __init__(self, before=0.0, between=0.0):
        self.before, self.between, self.made = before, between, []

    def lookup(self, key):
        time.sleep(self.before)
        return [key]

    def stream(self, text):
        def chunks():
            time.sleep(self.before)
            for n, word in enumerate(text.split()):
                if n:
                    time.sleep(self.between)
                yield word

        self.made.append(chunks())
        return self.made[-1]

    def broken(self, text):
        raise ValueError(f"bad input: {text}")

    def __call__(self, token):
        return token == "ok"


def api(slow_ms, **slow):
    lines: list[str] = []
    tracer = make_tracer(slow_ms, emit=lines.append)
    adapter = traced(Slow(**slow), "redis", tracer)
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

    @app.get("/api/worker/next")
    def poll():
        return {"job": None}

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
    found = logged(lines)
    assert (found["route"], found["status"]) == ("GET /api/items/{item}", 200)
    assert [s["name"] for s in found["spans"]] == ["redis.lookup", "redis"]
    assert found["first_ms"] <= found["ms"] and len(found["trace"]) == 32
    assert not any(leak in lines[0] for leak in ("abc", "email", "203.0.113.9", "testclient"))


def test_a_fast_request_logs_nothing():
    client, lines = api(slow_ms=10_000)
    client.get("/api/items/abc")
    assert lines == []


def test_a_streamed_reply_is_timed_until_its_last_chunk_with_the_first_one_marked():
    client, lines = api(slow_ms=0, before=0.05)
    assert client.post("/api/chat").text == "mysecretquestion"
    (stream,) = logged(lines)["spans"]
    assert stream["name"] == "redis.stream" and stream["ms"] >= 50 and 50 <= stream["first_ms"] <= stream["ms"]
    assert "secret" not in lines[0]


def test_a_streamed_reply_is_slow_by_its_first_chunk_not_by_its_length():
    client, lines = api(slow_ms=150, between=0.1)  # first chunk at once, the whole reply in about 200 ms
    client.post("/api/chat")
    assert lines == []
    client, lines = api(slow_ms=150, before=0.2)  # first chunk after 200 ms
    client.post("/api/chat")
    assert logged(lines)["first_ms"] >= 150


def test_a_failing_adapter_keeps_its_error_and_logs_only_the_error_type():
    client, lines = api(slow_ms=0)
    assert client.get("/api/fail").status_code == 500
    found = logged(lines)
    assert found["status"] == 500 and found["spans"] == [{"name": "redis.broken", "ms": found["spans"][0]["ms"],
                                                          "error": "ValueError"}]  # fmt: skip
    assert "secret" not in lines[0] and "bad input" not in lines[0]


def test_the_worker_long_polls_are_not_traced():
    client, lines = api(slow_ms=0)
    client.get("/api/worker/next")
    assert lines == []


def test_a_method_the_visitor_made_up_is_logged_as_other():
    client, lines = api(slow_ms=0)
    client.request("BREWCOFFEE", "/api/items/abc")
    assert logged(lines)["route"] == "OTHER /api/items/{item}" and "BREW" not in lines[0]


def test_an_unknown_path_is_logged_as_unmatched_not_by_its_path():
    client, lines = api(slow_ms=0)
    client.get("/wp-admin/secret-path")
    assert logged(lines)["route"] == "GET unmatched" and "secret-path" not in lines[0]


def test_the_wrapped_adapter_still_raises_passes_attributes_and_unwraps():
    real = Slow()
    adapter = traced(real, "redis", make_tracer(0, emit=lambda line: None))
    with pytest.raises(ValueError, match="bad input"):
        adapter.broken("x")
    assert adapter.before == 0.0 and adapter.lookup.__name__ == "lookup" and inspect.unwrap(adapter) is real


def test_closing_a_stream_closes_the_real_one_even_before_its_first_chunk():
    lines: list[str] = []
    tracer = make_tracer(0, emit=lines.append)
    real = Slow()
    adapter = traced(real, "model", tracer)
    with tracer.start_as_current_span("POST /api/chat"):
        adapter.stream("a b").close()  # the visitor left before the first chunk
        chunks = adapter.stream("a b")
        assert next(chunks) == "a"
        chunks.close()
    assert [inspect.getgeneratorstate(g) for g in real.made] == [inspect.GEN_CLOSED] * 2
    assert [s["name"] for s in logged(lines)["spans"]] == ["model.stream", "model.stream"]


def test_an_adapter_call_outside_a_request_is_not_traced():
    lines: list[str] = []
    adapter = traced(Slow(), "embed", make_tracer(0, emit=lines.append))
    assert adapter("ok") is True and list(adapter.stream("a b")) == ["a", "b"]  # e.g. the facts embedded at startup
    assert lines == []


def test_unfinished_traces_are_capped_so_memory_stays_bounded():
    processor = SlowTraces(0, emit=lambda line: None, max_pending=3)
    provider = TracerProvider()
    provider.add_span_processor(processor)
    tracer = provider.get_tracer("test")
    sampled = trace.TraceFlags(trace.TraceFlags.SAMPLED)
    for n in range(1, 11):  # child spans of requests whose root never ends
        parent = trace.NonRecordingSpan(trace.SpanContext(trace_id=n, span_id=n, is_remote=False, trace_flags=sampled))
        tracer.start_span("child", context=trace.set_span_in_context(parent)).end()
    assert len(processor.pending) == 3
