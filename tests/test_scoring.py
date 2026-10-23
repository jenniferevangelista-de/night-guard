"""F01: an unreadable or unavailable analysis is an error, never a detection or a true negative."""
from guard.scoring import outcome, summarize


def test_error_is_not_detection():
    assert outcome("risky", {"severity": "unknown", "analysis_status": "invalid_output"}) == "error_risky"
    assert outcome("risky", {"severity": "none", "analysis_status": "unavailable"}) == "error_risky"


def test_error_is_not_true_negative():
    assert outcome("safe", {"severity": "none", "analysis_status": "unavailable"}) == "error_safe"
    assert outcome("safe", {"severity": "unknown", "analysis_status": "invalid_output"}) == "error_safe"


def test_valid_outcomes():
    assert outcome("risky", {"severity": "high", "analysis_status": "ok"}) == "tp"
    assert outcome("risky", {"severity": "none", "analysis_status": "ok"}) == "fn"
    assert outcome("safe", {"severity": "low", "analysis_status": "partial"}) == "fp"
    assert outcome("safe", {"severity": "none", "analysis_status": "ok"}) == "tn"


def test_summary_reports_coverage_and_errors():
    cases = [
        ("r1", "risky", ["secrecy"], {"severity": "high", "analysis_status": "ok", "signals": ["secrecy"]}),
        ("r2", "risky", ["secrecy"], {"severity": "unknown", "analysis_status": "invalid_output", "signals": []}),
        ("s1", "safe", [], {"severity": "none", "analysis_status": "unavailable", "signals": []}),
        ("s2", "safe", [], {"severity": "none", "analysis_status": "ok", "signals": []}),
    ]
    s = summarize(cases)
    assert s["coverage"] == "2/4"
    assert s["errors"] == {"risky": 1, "safe": 1}
    assert s["risky_flagged"].startswith("1/1")
    assert s["false_alarms"].startswith("0/1")
    assert s["signal_precision"] == 1.0 and s["signal_recall"] == 1.0  # errors excluded from signal metrics


def test_kuririn_002_all_unavailable_is_not_70_catches():
    cases = [(f"r{i}", "risky", ["secrecy"], {"severity": "unknown", "analysis_status": "unavailable", "signals": []})
             for i in range(36)] + \
            [(f"s{i}", "safe", [], {"severity": "unknown", "analysis_status": "unavailable", "signals": []})
             for i in range(34)]
    s = summarize(cases)
    assert s["counts"]["tp"] == 0 and s["counts"]["tn"] == 0 and s["coverage"] == "0/70"
