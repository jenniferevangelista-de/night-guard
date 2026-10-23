"""Temporal activities: the parts that touch Ollama and the disk."""

import json
from pathlib import Path

from temporalio import activity
from temporalio.exceptions import ApplicationError

from guard.detector import analyze

ROOT = Path(__file__).resolve().parent.parent


@activity.defn
def check_conversation(row: dict) -> dict:
    """Run the local detector on one fictional chat (Ollama + Gemma)."""
    attempt = activity.info().attempt
    activity.logger.info("checking %s (attempt %s)", row["id"], attempt)
    res = analyze(row["messages"], lang=row["lang"])
    if res.get("analysis_status") == "unavailable":
        # Model down (e.g. Ollama crashed): fail the activity so Temporal's retry policy kicks in.
        raise ApplicationError(f"model unavailable for {row['id']}", type="ModelUnavailable", non_retryable=False)
    # invalid_output is permanent for the same input at temperature 0: recorded as an error case, not retried.
    return {
        "id": row["id"],
        "label": row["label"],
        "expected": row["signals"],
        "got": sorted({s["id"] for s in res["signals"]}),
        "severity": res["severity"],
        "analysis_status": res.get("analysis_status", "ok"),
        "latency_s": res["latency_s"],
        "attempt": attempt,
        "model": res["model"],
    }


@activity.defn
def save_report(report: dict) -> str:
    out = ROOT / "eval" / "temporal_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return str(out)
