"""One scoring rule for every evaluation (local, Temporal, Tinker).

A case only counts as flagged or clear when the analysis was valid. An unreadable or unavailable
analysis is an ERROR: it is never a detection (risky) and never a true negative (safe).
Coverage (valid analyses / all cases) is reported next to the metrics.
"""

FLAG = {"low", "medium", "high"}
VALID_STATUS = {"ok", "partial"}


def outcome(label, result):
    """label: 'risky' | 'safe'; result: dict with severity, analysis_status, signals (ids or dicts)."""
    valid = result.get("analysis_status", "ok") in VALID_STATUS and result.get("severity") != "unknown"
    if not valid:
        return "error_risky" if label == "risky" else "error_safe"
    flagged = result.get("severity") in FLAG
    if label == "risky":
        return "tp" if flagged else "fn"
    return "fp" if flagged else "tn"


def signal_ids(result):
    return {s["id"] if isinstance(s, dict) else s for s in result.get("signals", [])}


def summarize(cases):
    """cases: iterable of (case_id, label, expected_signal_ids, result). Returns a JSON-friendly summary."""
    c = {"tp": 0, "fn": 0, "fp": 0, "tn": 0, "error_risky": 0, "error_safe": 0}
    stp = sfp = sfn = 0
    mistakes = []
    n = 0
    for cid, label, expected, res in cases:
        n += 1
        o = outcome(label, res)
        c[o] += 1
        if o in ("fn", "fp", "error_risky", "error_safe"):
            mistakes.append([o, cid, res.get("severity"), res.get("analysis_status", "ok"), sorted(signal_ids(res))])
        if o in ("tp", "fn", "fp", "tn"):  # signal metrics only over valid analyses
            got, exp = signal_ids(res), set(expected)
            stp += len(got & exp); sfp += len(got - exp); sfn += len(exp - got)
    risky_valid, safe_valid = c["tp"] + c["fn"], c["fp"] + c["tn"]
    return {
        "n": n,
        "coverage": f"{n - c['error_risky'] - c['error_safe']}/{n}",
        "errors": {"risky": c["error_risky"], "safe": c["error_safe"]},
        "risky_flagged": f"{c['tp']}/{risky_valid} valid ({c['error_risky']} errors)",
        "false_alarms": f"{c['fp']}/{safe_valid} valid ({c['error_safe']} errors)",
        "signal_precision": round(stp / max(1, stp + sfp), 3),
        "signal_recall": round(stp / max(1, stp + sfn), 3),
        "counts": c,
        "mistakes": mistakes,
    }
