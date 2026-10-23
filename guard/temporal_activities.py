"""Temporal activities: the parts that touch Ollama and the disk."""

import json
from pathlib import Path

from temporalio import activity

from guard.detector import analyze

ROOT = Path(__file__).resolve().parent.parent


@activity.defn
def check_conversation(row: dict) -> dict:
    """Run the local detector on one fictional chat (Ollama + Gemma)."""
    attempt = activity.info().attempt
    activity.logger.info("checking %s (attempt %s)", row["id"], attempt)
    res = analyze(row["messages"], lang=row["lang"])
    return {
        "id": row["id"],
        "label": row["label"],
        "expected": row["signals"],
        "got": sorted({s["id"] for s in res["signals"]}),
        "severity": res["severity"],
        "latency_s": res["latency_s"],
        "attempt": attempt,
        "model": res["model"],
    }


@activity.defn
def save_report(report: dict) -> str:
    out = ROOT / "eval" / "temporal_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return str(out)
