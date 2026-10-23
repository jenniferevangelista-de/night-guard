"""F03: a malformed model answer never becomes "no risk"."""
from guard.detector import postprocess, valid_schema

CHAT = [{"from": "them", "name": "Alex_17", "text": "send me a photo of you, just us"},
        {"from": "me", "text": "why"}]


def test_unreadable_output_is_unknown():
    for raw in (None, "oops", {}, {"signals": "x"}):
        r = postprocess(raw, CHAT)
        assert r["analysis_status"] == "invalid_output" and r["severity"] == "unknown"


def test_only_malformed_items_is_invalid_not_none():
    r = postprocess({"signals": [{"signal_id": "photo_request"}, {"id": "made_up", "message_index": 0, "quote": "x"}],
                     "summary": ""}, CHAT)
    assert r["analysis_status"] == "invalid_output" and r["severity"] == "unknown"
    assert r["malformed_items"] == 2


def test_partial_keeps_valid_items():
    r = postprocess({"signals": [{"id": "photo_request", "message_index": 0, "quote": "send me a photo"},
                                 {"id": "photo_request", "message_index": "0", "quote": "x"}], "summary": ""}, CHAT)
    assert r["analysis_status"] == "partial" and r["severity"] == "high"


def test_valid_empty_answer_is_none():
    r = postprocess({"signals": [], "summary": "fine"}, CHAT)
    assert r["analysis_status"] == "ok" and r["severity"] == "none"


def test_child_message_is_never_flagged():
    r = postprocess({"signals": [{"id": "photo_request", "message_index": 1, "quote": "why"}], "summary": ""}, CHAT)
    assert r["signals"] == []


def test_valid_schema_is_strict():
    assert valid_schema({"signals": [{"id": "secrecy", "message_index": 0, "quote": "x"}], "summary": ""})
    assert not valid_schema({"signals": [{"signal_id": "secrecy", "message_index": 0, "quote": "x"}], "summary": ""})
    assert not valid_schema({"signals": [{"id": "secrecy", "message_index": True, "quote": "x"}], "summary": ""})
    assert not valid_schema({"signals": []})  # summary missing


def test_kuririn_002_minimal_cases():
    """Exact inputs from the round-002 review (F03 and F07)."""
    chat = [{"from": "them", "text": "don't tell your parents"}]
    for raw in ({"signals": [{"id": "secrecy"}], "summary": "synthetic"},
                {"signals": [{"id": "unsupported", "message_index": 0, "quote": "don't tell"}], "summary": "synthetic"}):
        r = postprocess(raw, chat)
        assert (r["severity"], r["analysis_status"]) == ("unknown", "invalid_output")
    assert not valid_schema({}) and not valid_schema({"signals": [{"id": "unsupported"}]})
