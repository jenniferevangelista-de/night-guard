"""Open-model bake-off through Backboard (one API key, many open-weight models), on the same 70 fictional test chats.

Same system prompt, same JSON contract, same scoring as every other evaluation (guard/scoring.py): an answer that
does not follow the app's schema is an error, never a catch. Raw answers are saved per case.

  .venv\\Scripts\\python train\\backboard_bakeoff.py            (all models below)
  .venv\\Scripts\\python train\\backboard_bakeoff.py google/gemma-3-27b-it
Needs BACKBOARD_API_KEY in .env. Only fictional test chats are sent.
"""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "train"))
from guard.detector import SYSTEM, _format_chat, postprocess, valid_schema  # noqa: E402
from guard.env import load_env  # noqa: E402
from guard.scoring import summarize  # noqa: E402

load_env()
API = "https://app.backboard.io/api/threads/messages"
MODELS = [  # open-weight models, all reached through Backboard's OpenRouter provider
    "google/gemma-3-27b-it",
    "meta-llama/llama-3.3-70b-instruct",
    "qwen/qwen-2.5-72b-instruct",
    "mistralai/mistral-small-3.1-24b-instruct",
]


def parse(text):
    s, e = text.find("{"), text.rfind("}")
    try:
        return json.loads(text[s:e + 1])
    except Exception:
        return None


def ask(model, row):
    body = {"content": "Chat:\n" + _format_chat(row["messages"]) + "\n\nReturn the JSON.", "system_prompt": SYSTEM,
            "llm_provider": "openrouter", "model_name": model, "json_output": True, "memory": "off", "stream": False}
    t0 = time.time()
    for attempt in range(3):
        try:
            r = httpx.post(API, headers={"X-API-Key": os.environ["BACKBOARD_API_KEY"]}, json=body, timeout=120)
            if r.status_code == 429:
                time.sleep(3 * (attempt + 1)); continue
            r.raise_for_status()
            content = r.json().get("content", "")
            return content, time.time() - t0, None
        except Exception as e:
            err = type(e).__name__
            time.sleep(2)
    return "", time.time() - t0, err


def run(model):
    rows = [json.loads(l) for l in (ROOT / "eval" / "conversations.jsonl").open(encoding="utf-8")]
    with ThreadPoolExecutor(4) as ex:
        answers = list(ex.map(lambda r: ask(model, r), rows))
    cases, pairs, ok = [], [], 0
    for row, (content, lat, err) in zip(rows, answers):
        raw = parse(content) if content else None
        valid = valid_schema(raw)
        ok += valid
        res = postprocess(raw, row["messages"], row["lang"], model=model)
        if err:
            res["analysis_status"] = "unavailable"
        pairs.append((row["id"], row["label"], row["signals"], res))
        cases.append({"id": row["id"], "label": row["label"], "schema_ok": valid, "error": err, "latency_s": round(lat, 2),
                      "status": res["analysis_status"], "severity": res["severity"],
                      "signals": sorted(s["id"] for s in res["signals"]), "raw_output": content})
    out = {"model": model, "via": "Backboard (llm_provider=openrouter)", "n": len(rows), "schema_valid": ok,
           "avg_latency_s": round(sum(c["latency_s"] for c in cases) / len(cases), 2),
           "summary": summarize(pairs), "cases": cases}
    tag = model.split("/")[-1]
    (ROOT / "train" / f"backboard_{tag}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    s = out["summary"]
    print(f"{model:45} schema {ok}/70  coverage {s['coverage']}  risky {s['risky_flagged']}  FA {s['false_alarms']}  "
          f"P/R {s['signal_precision']}/{s['signal_recall']}  {out['avg_latency_s']}s")


if __name__ == "__main__":
    if not os.environ.get("BACKBOARD_API_KEY"):
        sys.exit("Add BACKBOARD_API_KEY=... to .env first.")
    for m in (sys.argv[1:] or MODELS):
        run(m)
