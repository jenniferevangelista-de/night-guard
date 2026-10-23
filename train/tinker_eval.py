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

MODEL = "Qwen/Qwen3-8B"
RENDERER = "qwen3_disable_thinking"


def parse_json(text):
    text = text.strip()
    s, e = text.find("{"), text.rfind("}")
    try:
        return json.loads(text[s:e + 1])
    except Exception:
        return {"signals": [], "summary": "(unparseable)"}


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
        res = postprocess(parse_json(content), row["messages"], row["lang"], model=model_path or MODEL)
        return row, res, time.time() - t0

    results = await asyncio.gather(*[one(r) for r in rows])
    tp = fp = fn = tn = stp = sfp = sfn = 0
    mistakes = []
    for row, res, _ in results:
        flagged, risky = res["severity"] != "none", row["label"] == "risky"
        got, exp = {s["id"] for s in res["signals"]}, set(row["signals"])
        if risky and flagged: tp += 1
        elif risky: fn += 1; mistakes.append(("MISSED", row["id"], sorted(got)))
        elif flagged: fp += 1; mistakes.append(("FALSE ALARM", row["id"], sorted(got)))
        else: tn += 1
        stp += len(got & exp); sfp += len(got - exp); sfn += len(exp - got)
    out = {
        "model": model_path or MODEL, "n": len(rows),
        "recall": tp / max(1, tp + fn), "false_alarm_rate": fp / max(1, fp + tn),
        "signal_precision": stp / max(1, stp + sfp), "signal_recall": stp / max(1, stp + sfn),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn, "mistakes": mistakes,
    }
    print(json.dumps(out, indent=2))
    tag = "finetuned" if model_path else "base"
    (ROOT / "train" / f"tinker_eval_{tag}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else None))
