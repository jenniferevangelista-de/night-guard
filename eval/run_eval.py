"""Runs the local detector on the fictional test set and prints honest metrics.

Usage (from project root):  .venv\\Scripts\\python -m eval.run_eval
Writes eval/last_results.json with the summary AND one line per case (fictional data only).
Errors (unreadable/unavailable analyses) are reported separately; they never count as detections.
"""

import json
import sys
from pathlib import Path

from guard.detector import MODEL, analyze
from guard.scoring import outcome, summarize

ROOT = Path(__file__).parent
rows = [json.loads(l) for l in (ROOT / "conversations.jsonl").open(encoding="utf-8")]
limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(rows)

cases, per_case, lat = [], [], []
for row in rows[:limit]:
    res = analyze(row["messages"], lang=row["lang"])
    lat.append(res.get("latency_s", 0))
    got = sorted(s["id"] for s in res["signals"])
    o = outcome(row["label"], res)
    cases.append((row["id"], row["label"], row["signals"], res))
    per_case.append({"id": row["id"], "label": row["label"], "expected": row["signals"], "got": got,
                     "severity": res["severity"], "analysis_status": res.get("analysis_status"),
                     "outcome": o, "latency_s": res.get("latency_s")})
    print(f"{row['id']:>4} {row['label']:>5} -> {res['severity']:<7} {res.get('analysis_status',''):<14} {o:<11} {got}"
          f"  ({res.get('latency_s')}s)", flush=True)

s = summarize(cases)
print("\n=== Night Guard eval (fictional data) ===")
print(f"model: {MODEL}   conversations: {s['n']}   coverage (valid analyses): {s['coverage']}")
print(f"risky flagged: {s['risky_flagged']}")
print(f"false alarms:  {s['false_alarms']}")
print(f"signal precision: {s['signal_precision']:.0%}   signal recall: {s['signal_recall']:.0%}   (valid analyses only)")
print(f"avg latency: {sum(lat) / max(1, len(lat)):.1f}s")
if s["mistakes"]:
    print("\nMistakes / errors:")
    for m in s["mistakes"]:
        print("  ", m)

(ROOT / "last_results.json").write_text(json.dumps(
    {"model": MODEL, "summary": s, "avg_latency_s": sum(lat) / max(1, len(lat)), "cases": per_case},
    indent=2), encoding="utf-8")
