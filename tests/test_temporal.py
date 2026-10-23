"""F02: when the model is down, the Temporal activity fails so the retry policy runs (no silent "safe")."""
import pytest
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from guard import temporal_activities as ta

ROW = {"id": "s01", "label": "safe", "lang": "en", "signals": [], "messages": [{"from": "them", "text": "gg"}]}


def test_unavailable_model_raises_retryable_error(monkeypatch):
    monkeypatch.setattr(ta, "analyze", lambda *a, **k: {"analysis_status": "unavailable", "severity": "unknown",
                                                         "signals": [], "latency_s": 0, "model": "x"})
    with pytest.raises(ApplicationError) as e:
        ActivityEnvironment().run(ta.check_conversation, ROW)
    assert e.value.type == "ModelUnavailable" and not e.value.non_retryable


def test_valid_answer_is_returned_with_status(monkeypatch):
    monkeypatch.setattr(ta, "analyze", lambda *a, **k: {"analysis_status": "ok", "severity": "none",
                                                         "signals": [], "latency_s": 1.0, "model": "x"})
    out = ActivityEnvironment().run(ta.check_conversation, ROW)
    assert out["analysis_status"] == "ok" and out["severity"] == "none"
