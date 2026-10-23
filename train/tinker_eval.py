"""Evaluate a Tinker model (base or fine-tuned) on the held-out fictional eval set.

  base:        .venv\\Scripts\\python train\\tinker_eval.py
  fine-tuned:  .venv\\Scripts\\python train\\tinker_eval.py tinker://<run>/sampler_weights/final
"""

import asyncio
import json
import sys
import time
from pathlib import Path

import tinker
from tinker import types
from tinker_cookbook import renderers
from tinker_cookbook.tokenizer_utils import get_tokenizer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from guard.detector import SYSTEM, _format_chat, postprocess  # noqa: E402
from guard.env import load_env  # noqa: E402

load_env()

MODEL = "Qwen/Qwen3-8B"
RENDERER = "qwen3_disable_thinking"


ID_ALIASES = ("id", "signal_id", "signal", "type", "category", "name")


def parse_json(text, lenient=False):
    """strict: the app's exact schema. lenient: also accept common key variants."""
    text = text.strip()
    s, e = text.find("{"), text.rfind("}")
    try:
        data = json.loads(text[s:e + 1])
    except Exception:
        return {"signals": [], "summary": "(unparseable)"}, False
    sigs = data.get("signals", []) if isinstance(data, dict) else []
    ok = isinstance(sigs, list) and all(isinstance(x, dict) and "id" in x for x in sigs)
    if lenient and isinstance(sigs, list):
        fixed = []
        for x in sigs:
            if isinstance(x, dict):
                key = next((k for k in ID_ALIASES if k in x), None)
                if key:
                    fixed.append({**x, "id": x[key]})
        data["signals"] = fixed
    return data, ok


async def main(model_path=None):
    rows = [json.loads(l) for l in (ROOT / "eval" / "conversations.jsonl").open(encoding="utf-8")]
    sc = tinker.ServiceClient()
    client = sc.create_sampling_client(base_model=MODEL, model_path=model_path)
    renderer = renderers.get_renderer(RENDERER, get_tokenizer(MODEL))
    params = types.SamplingParams(max_tokens=400, temperature=0.0, stop=renderer.get_stop_sequences())

    async def one(row):
        convo = [{"role": "system", "content": SYSTEM},
                 {"role": "user", "content": "Chat:\n" + _format_chat(row["messages"]) + "\n\nReturn the JSON."}]
        t0 = time.time()
        r = await client.sample_async(prompt=renderer.build_generation_prompt(convo), num_samples=1, sampling_params=params)
        msg, _ = renderer.parse_response(r.sequences[0].tokens)
        content = renderers.format_content_as_string(msg["content"]) if not isinstance(msg["content"], str) else msg["content"]
        strict_raw, ok = parse_json(content)
        lenient_raw, _ = parse_json(content, lenient=True)
        strict = postprocess(strict_raw, row["messages"], row["lang"], model=model_path or MODEL)
        lenient = postprocess(lenient_raw, row["messages"], row["lang"], model=model_path or MODEL)
        return row, strict, lenient, ok, time.time() - t0

    results = await asyncio.gather(*[one(r) for r in rows])
    out = {
        "model": model_path or MODEL,
        "n": len(rows),
        "format_ok": sum(1 for r in results if r[3]),
        "avg_latency_s": round(sum(r[4] for r in results) / len(results), 2),
        "strict": score([(r[0], r[1]) for r in results]),
        "lenient": score([(r[0], r[2]) for r in results]),
    }
    print(json.dumps({k: v for k, v in out.items()}, indent=2))
    tag = "finetuned" if model_path else "base"
    (ROOT / "train" / f"tinker_eval_{tag}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


def score(pairs):
    tp = fp = fn = tn = stp = sfp = sfn = 0
    mistakes = []
    for row, res in pairs:
        # "unknown" = unreadable output: the app can't act on it, so it is not a flag.
        flagged = res["severity"] in ("low", "medium", "high")
        risky = row["label"] == "risky"
        got, exp = {s["id"] for s in res["signals"]}, set(row["signals"])
        if risky and flagged: tp += 1
        elif risky: fn += 1; mistakes.append(("MISSED", row["id"], sorted(got)))
        elif flagged: fp += 1; mistakes.append(("FALSE ALARM", row["id"], sorted(got)))
        else: tn += 1
        stp += len(got & exp); sfp += len(got - exp); sfn += len(exp - got)
    return {
        "risky_flagged": f"{tp}/{tp + fn}", "false_alarms": f"{fp}/{fp + tn}",
        "signal_precision": round(stp / max(1, stp + sfp), 3), "signal_recall": round(stp / max(1, stp + sfn), 3),
        "mistakes": mistakes,
    }


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else None))
