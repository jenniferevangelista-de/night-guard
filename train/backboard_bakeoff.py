"""Open-model bake-off through Backboard (one API key, many open-weight models), on the same 70 fictional test chats.

Same system prompt, same JSON contract, same scoring as every other evaluation (guard/scoring.py): an answer that
does not follow the app's schema is an error, never a catch. Raw answers are saved per case.

  .venv\\Scripts\\python train\\backboard_bakeoff.py            (all models below)
  .venv\\Scripts\\python train\\backboard_bakeoff.py google/gemma-3-27b-it
Needs BACKBOARD_API_KEY in .env. Only fictional test chats are sent.
"""

import json
import argparse
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

# Official contract: https://docs.backboard.io/api-reference/threads/send-message
API = "https://app.backboard.io/api/threads/messages"
MODELS = [  # open-weight models, all reached through Backboard's OpenRouter provider
    "google/gemma-3-27b-it",
    "meta-llama/llama-3.3-70b-instruct",
    "qwen/qwen-2.5-72b-instruct",
    "mistralai/mistral-small-3.1-24b-instruct",
]


class BackboardConfigError(RuntimeError):
    """An authentication, billing, endpoint or request error must stop the run."""


def parse(text):
    s, e = text.find("{"), text.rfind("}")
    try:
        return json.loads(text[s:e + 1])
    except Exception:
        return None


def ask(model, row):
    key = os.environ.get("BACKBOARD_API_KEY", "").strip()
    if not key:
        raise BackboardConfigError("Add BACKBOARD_API_KEY=... to .env first.")
    # Omitting both IDs creates a fresh thread and assistant for EACH case.
    # Never send a previous response's IDs: that would mix evaluation history.
    body = {"content": "Chat:\n" + _format_chat(row["messages"]) + "\n\nReturn the JSON.", "system_prompt": SYSTEM,
            "llm_provider": "openrouter", "model_name": model, "json_output": True, "memory": "off",
            "web_search": "off", "stream": False}
    t0 = time.perf_counter()
    err = "RequestFailed"
    for attempt in range(3):
        try:
            r = httpx.post(API, headers={"X-API-Key": key}, json=body, timeout=120)
            if 400 <= r.status_code < 500 and r.status_code not in (408, 425, 429):
                # Do not print response bodies or request headers (may contain secrets).
                raise BackboardConfigError(f"Backboard HTTP {r.status_code}; check API key, credit, endpoint and model.")
            if r.status_code in (408, 425, 429) or r.status_code >= 500:
                err = f"HTTP_{r.status_code}"
            else:
                r.raise_for_status()
                try:
                    data = r.json()
                except ValueError:
                    raise BackboardConfigError("Backboard returned an invalid JSON response.") from None
                if not isinstance(data, dict):
                    raise BackboardConfigError("Backboard returned an unexpected response shape.")
                if data.get("status") not in (None, "COMPLETED"):
                    return "", time.perf_counter() - t0, "BackboardRunFailed"
                content = data.get("content")
                if not isinstance(content, str):
                    raise BackboardConfigError("Backboard response is missing text content.")
                return content, time.perf_counter() - t0, None
        except httpx.RequestError as e:
            err = type(e).__name__
        if attempt < 2:
            time.sleep(3 * (attempt + 1))
    return "", time.perf_counter() - t0, err


def run(model, limit=None):
    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1")
    with (ROOT / "eval" / "conversations.jsonl").open(encoding="utf-8") as source:
        rows = [json.loads(line) for line in source if line.strip()]
    total = len(rows)
    rows = rows[:limit] if limit is not None else rows
    if not rows:
        raise ValueError("Evaluation dataset is empty")
    # Probe the first real case before launching concurrent requests. Permanent
    # errors abort immediately; later batches leave at most four calls in flight.
    answers = [ask(model, rows[0])]
    with ThreadPoolExecutor(4) as ex:
        for start in range(1, len(rows), 4):
            answers.extend(ex.map(lambda row: ask(model, row), rows[start:start + 4]))
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
    out = {"model": model, "via": "Backboard (llm_provider=openrouter)", "n": len(rows), "dataset_n": total,
           "evaluation": "smoke" if limit is not None else "full", "schema_valid": ok,
           "avg_latency_s": round(sum(c["latency_s"] for c in cases) / len(cases), 2),
           "summary": summarize(pairs), "cases": cases}
    tag = model.split("/")[-1]
    suffix = f"_smoke_{limit}" if limit is not None else ""
    (ROOT / "train" / f"backboard_{tag}{suffix}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    s = out["summary"]
    print(f"{model:45} schema {ok}/{len(rows)}  coverage {s['coverage']}  risky {s['risky_flagged']}  FA {s['false_alarms']}  "
          f"P/R {s['signal_precision']}/{s['signal_recall']}  {out['avg_latency_s']}s")
    return out


def export_summary(results, limit=None):
    lines = ["# Backboard model comparison", "",
             "Smoke test only; not the full benchmark." if limit is not None else "Full fictional-chat benchmark.", "",
             "| Model | Cases | Schema | Coverage | Risky flagged | False alarms | Signal precision | Signal recall | Avg s |",
             "| --- | ---: | --- | --- | --- | --- | ---: | ---: | ---: |"]
    for result in results:
        s = result["summary"]
        model = result["model"].replace("|", "\\|")
        lines.append(f"| {model} | {result['n']} | {result['schema_valid']}/{result['n']} | {s['coverage']} | "
                     f"{s['risky_flagged']} | {s['false_alarms']} | {s['signal_precision']} | {s['signal_recall']} | "
                     f"{result['avg_latency_s']} |")
    suffix = f"_smoke_{limit}" if limit is not None else ""
    path = ROOT / "train" / f"backboard{suffix}_summary.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", nargs="*", help="OpenRouter model IDs (default: the four configured models)")
    parser.add_argument("--limit", type=int, help="Smoke test: only the first N fictional cases per model")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    load_env()  # CLI only: importing this module and unit tests never read .env.
    if not os.environ.get("BACKBOARD_API_KEY", "").strip():
        print("Add BACKBOARD_API_KEY=... to .env first.", file=sys.stderr)
        return 1
    results = []
    try:
        for model in args.models or MODELS:
            results.append(run(model, limit=args.limit))
            export_summary(results, limit=args.limit)
    except BackboardConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
