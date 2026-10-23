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
from guard.detector import SYSTEM, _format_chat, postprocess, valid_schema  # noqa: E402
from guard.scoring import summarize  # noqa: E402
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
        return None, False
    ok = valid_schema(data)  # the app's full schema: id, int message_index, str quote, str summary
    sigs = data.get("signals", []) if isinstance(data, dict) else []
    if lenient and isinstance(data, dict) and isinstance(sigs, list):
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
        return row, strict, lenient, ok, time.time() - t0, content

    results = await asyncio.gather(*[one(r) for r in rows])
    out = {
        "model": model_path or MODEL,
        "n": len(rows),
        "format_ok": sum(1 for r in results if r[3]),
        "avg_latency_s": round(sum(r[4] for r in results) / len(results), 2),
        "strict": score([(r[0], r[1]) for r in results]),
        "lenient": score([(r[0], r[2]) for r in results]),
        "cases": [{"id": r[0]["id"], "label": r[0]["label"], "schema_ok": r[3], "raw_output": r[5],
                   "strict": {k: r[1].get(k) for k in ("severity", "analysis_status", "malformed_items")},
                   "strict_signals": sorted(s["id"] for s in r[1]["signals"]),
                   "lenient_signals": sorted(s["id"] for s in r[2]["signals"])} for r in results],
    }
    print(json.dumps({k: v for k, v in out.items() if k != "cases"}, indent=2))
    tag = sys.argv[2] if len(sys.argv) > 2 else ("finetuned" if model_path else "base")
    (ROOT / "train" / f"tinker_eval_{tag}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


def score(pairs):
    """Same rule as every other evaluation (guard/scoring.py): unreadable output is an error, not a flag."""
    return summarize((row["id"], row["label"], row["signals"], res) for row, res in pairs)


if __name__ == "__main__":
    # usage: tinker_eval.py [model_path|base] [output_tag]
    mp = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "base" else None
    asyncio.run(main(mp))
