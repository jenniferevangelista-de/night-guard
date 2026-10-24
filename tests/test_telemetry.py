"""F09: the Sentry scrubber keeps only allowlisted fields; chat text never leaves."""
from guard.telemetry import _allow

MARK = "ZZ_FICTIONAL_CHAT_MARKER_42"


def test_scrubber_drops_chat_text_everywhere():
    event = {
        "event_id": "1", "level": "error", "message": f"user said {MARK}",
        "request": {"data": MARK}, "user": {"email": MARK}, "breadcrumbs": [{"message": MARK}],
        "tags": {"q": MARK}, "server_name": "my-pc", "extra": {"quote": MARK, "severity": "high"},
        "contexts": {"trace": {"data": {"prompt": MARK, "model": "gemma"}}, "custom": {"x": MARK}},
        "exception": {"values": [{"type": "ValueError", "value": MARK,
                                  "stacktrace": {"frames": [{"function": "f", "vars": {"t": MARK}}]}}]},
        "spans": [{"op": "gen_ai.chat", "data": {"gen_ai.prompt": MARK, "latency_s": 4.2}, "tags": {"t": MARK}}],
        "new_field_from_future_sdk": MARK,
    }
    out = _allow(event)
    assert MARK not in repr(out)
    assert out["extra"] == {"severity": "high"}
    assert out["spans"][0]["data"] == {"latency_s": 4.2}
    assert out["exception"]["values"][0]["type"] == "ValueError"


def test_own_fixed_messages_are_kept():
    assert _allow({"message": "night-guard: model unavailable"})["message"] == "night-guard: model unavailable"


def test_regression_span_fields_are_allowlisted():
    m = "SYNTHETIC_PRIVATE_CHAT_MARKER"
    out = _allow({"spans": [{"op": "gen_ai.chat", "description": m, "future_field": m, "data": {"prompt": m}},
                            {"op": "gen_ai.chat", "description": "chat gemma4:e4b", "data": {"latency_s": 4.1}}],
                  "contexts": {"trace": {"op": "gen_ai.invoke_agent", "description": m, "extra_field": m}}})
    assert m not in repr(out)
    assert out["spans"][1]["description"] == "chat gemma4:e4b"
