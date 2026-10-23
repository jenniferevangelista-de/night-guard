"""Runs the detector on the fictional test set and prints honest metrics.

Usage (from project root):  .venv\\Scripts\\python -m eval.run_eval
"""

import json
import sys
from collections import Counter
from pathlib import Path

from guard.detector import MODEL, analyze

ROOT = Path(__file__).parent
rows = [json.loads(l) for l in (ROOT / "conversations.jsonl").open(encoding="utf-8")]
limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(rows)

tp = fp = fn = tn = 0
sig_tp = sig_fp = sig_fn = 0
lat = []
mistakes = []
per_signal = Counter()

for row in rows[:limit]:
    res = analyze(row["messages"], lang=row["lang"])
    lat.append(res["latency_s"])
    # Any signal shows the child a tip, so "flagged" = anything above none.
    flagged = res["severity"] != "none"
    risky = row["label"] == "risky"
    got = {s["id"] for s in res["signals"]}
    exp = set(row["signals"])

    if risky and flagged: tp += 1
    elif risky: fn += 1; mistakes.append(("MISSED", row["id"], res["severity"], sorted(got), sorted(exp)))
    elif flagged: fp += 1; mistakes.append(("FALSE ALARM", row["id"], res["severity"], sorted(got), sorted(exp)))
    else: tn += 1

    sig_tp += len(got & exp); sig_fp += len(got - exp); sig_fn += len(exp - got)
    for s in exp - got: per_signal[f"missed:{s}"] += 1
    for s in got - exp: per_signal[f"extra:{s}"] += 1
    print(f"{row['id']:>4} {row['label']:>5} -> {res['severity']:<6} {sorted(got)}  ({res['latency_s']}s)", flush=True)

n = tp + fp + fn + tn
print("\n=== Night Guard eval (fictional data) ===")
print(f"model: {MODEL}   conversations: {n}")
print(f"risky caught (recall):      {tp}/{tp+fn} = {tp/max(1,tp+fn):.0%}")
print(f"false alarms on safe chats: {fp}/{fp+tn} = {fp/max(1,fp+tn):.0%}")
print(f"signal precision: {sig_tp/max(1,sig_tp+sig_fp):.0%}   signal recall: {sig_tp/max(1,sig_tp+sig_fn):.0%}")
print(f"avg latency: {sum(lat)/len(lat):.1f}s")
if mistakes:
    print("\nMistakes:")
    for m in mistakes: print("  ", m)
if per_signal:
    print("\nSignal-level diffs:", dict(per_signal))

(ROOT / "last_results.json").write_text(json.dumps({
    "model": MODEL, "n": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    "signal_precision": sig_tp/max(1,sig_tp+sig_fp), "signal_recall": sig_tp/max(1,sig_tp+sig_fn),
    "avg_latency_s": sum(lat)/len(lat), "mistakes": mistakes,
}, indent=2), encoding="utf-8")
