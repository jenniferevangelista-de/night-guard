"""Re-score saved Tinker answers with the current schema rules (no new model calls).

  python train/rescore_tinker.py base_70 v1_70 v2_70
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "train"))
from guard.detector import postprocess  # noqa: E402
from guard.scoring import summarize  # noqa: E402
from tinker_eval import parse_json  # noqa: E402

rows = {r["id"]: r for r in (json.loads(l) for l in (ROOT / "eval" / "conversations.jsonl").open(encoding="utf-8"))}
for tag in sys.argv[1:]:
    p = ROOT / "train" / f"tinker_eval_{tag}.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    strict_pairs, lenient_pairs, ok = [], [], 0
    for c in d["cases"]:
        row = rows[c["id"]]
        s_raw, valid = parse_json(c["raw_output"]); l_raw, _ = parse_json(c["raw_output"], lenient=True)
        s = postprocess(s_raw, row["messages"], row["lang"]); l = postprocess(l_raw, row["messages"], row["lang"])
        ok += valid
        c["schema_ok"] = valid
        c["strict"] = {k: s.get(k) for k in ("severity", "analysis_status", "malformed_items")}
        c["strict_signals"] = sorted(x["id"] for x in s["signals"]); c["lenient_signals"] = sorted(x["id"] for x in l["signals"])
        strict_pairs.append((row["id"], row["label"], row["signals"], s)); lenient_pairs.append((row["id"], row["label"], row["signals"], l))
    d["format_ok"] = ok
    d["strict"], d["lenient"] = summarize(strict_pairs), summarize(lenient_pairs)
    d["rescored"] = "re-scored from saved raw outputs with the current schema rules (no new model calls)"
    p.write_text(json.dumps(d, indent=2), encoding="utf-8")
    print(tag, ok, {k: d[m][k] for m in ("strict",) for k in ("coverage", "risky_flagged", "false_alarms", "signal_precision", "signal_recall")},
          "lenient", {k: d["lenient"][k] for k in ("coverage", "risky_flagged", "false_alarms", "signal_precision", "signal_recall")})
