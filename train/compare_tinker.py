"""Print base / v1 / v2 Tinker results on the same test set (run from the project root)."""
import json
from pathlib import Path

for tag in ["base_70", "v1_70", "v2_70"]:
    p = Path("train") / f"tinker_eval_{tag}.json"
    if not p.exists():
        print(tag, "missing")
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    s, l = d["strict"], d["lenient"]
    print(f"{tag:8} format {d['format_ok']}/{d['n']} | strict: risky {s['risky_flagged']} false {s['false_alarms']} "
          f"prec {s['signal_precision']} rec {s['signal_recall']} | lenient: risky {l['risky_flagged']} "
          f"false {l['false_alarms']} rec {l['signal_recall']} | {d['avg_latency_s']}s")
    if tag == "v2_70":
        print("   v2 mistakes:", [m[:2] for m in s["mistakes"]])
