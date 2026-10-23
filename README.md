# 🛡️🌙 Night Guard

**Helps kids understand what happened in an online chat, and choose how to ask for help.**
Runs on the child's own computer with **Gemma** (Google's open-weight model) through Ollama.
Chats never leave the device.

> Existing tools watch kids. Night Guard watches out *for* them.

**Try the online demo:** https://night-guard-demo.onrender.com
(fictional examples only; it runs the Tinker fine-tuned model in the cloud so anyone can try it. The real app runs
on the child's computer with Gemma. Free instance: the first visit after a quiet period takes ~50 s to wake up.)

## What it does

| Screen | What happens |
|---|---|
| **Something felt off** | Paste a chat. Before showing results, Night Guard asks *"did anything feel off to you?"*, then highlights the exact phrases that match common pressure tricks (secrecy, moving to another app, free-stuff links, password requests…) with a calm one-line explanation. If nothing is found, it says so, and reminds the child that their feeling still counts. |
| **Practice** | Short, pre-reviewed fictional scenarios (fake moderator, free Robux link, "don't tell your parents"). Choose a reply, then see why it works or not. |
| **Tell someone** | Pick which quotes to share, and Gemma drafts a short, editable message to a trusted adult ("I didn't do anything wrong, but I need help"). Nothing is sent automatically. |
| **Family** | Kids don't always recognize a bad intention, so parents set **family rules**: which signals are shared with them automatically (default: photo requests, meeting in person, password requests, secrecy, and any high-risk combination). The child is always told when that happens. Parents see the risk type, the app and the flagged phrase, never the whole chat. |

### The gap no platform covers

Instagram supervision, Discord Family Center, TikTok Family Pairing and Roblox parental controls each protect **their own app**. The classic pressure path starts in a game and moves to a private app. Night Guard records where each check happened, so the family sees:

> ⚠️ Same contact seen in more than one app: **Alex_17 (Roblox → Instagram)**

**The lazy part:** the tutor repeats less as you learn. Lessons you already know collapse to a single ✓ line, so the guard gets lazier as the kid gets wiser.

## Privacy model

- Analysis and message drafting run **locally** (Ollama + `gemma4:e4b`).
- No chat text is stored. Learning progress lives in the browser's localStorage.
- Cloud services used by the project only ever touch **fictional test data** (evaluation, scenarios, hosting the demo).

## Results (fictional test set, 60 chats: 30 safe, 30 risky)

Baseline `gemma4:e4b`, zero-shot, on an RTX 4050 laptop GPU:

| Metric | Value |
|---|---|
| Risky chats flagged | 30/30 (100%) |
| False alarms on safe chats | 4/30 (13%) |
| Signal precision / recall | 89% / 87% |
| Avg latency | 3.8 s |

The false alarms are deliberate hard cases: an in-game "secret" about a hidden chest, a classmate saying "see you at school", a birthday "how old r u now". All conversations are **fictional**, written for testing; no real children's data is used.

## Run it

```bash
ollama pull gemma4:e4b
python -m venv .venv && .venv/Scripts/pip install fastapi uvicorn httpx
.venv/Scripts/python -m uvicorn guard.server:app --port 8765
# open http://localhost:8765
```

Evaluate: `python eval/make_dataset.py && python -m eval.run_eval`

## Fine-tuning with Tinker

Gemma runs locally, but Tinker doesn't serve Gemma, so the fine-tuning experiment uses **Qwen3-8B** on
[Tinker](https://thinkingmachines.ai/tinker/): LoRA rank 16, 800 fictional training chats (no sentence shared with the
test set), 2 epochs, ~740k training tokens. Same 60-chat held-out test set.

| | Qwen3-8B base | **Qwen3-8B + Tinker LoRA** |
|---|---|---|
| Answers in the app's JSON format | 6 to 28 / 60 (varies by run) | **60 / 60** |
| Risky chats the app can act on | **0 / 30** | **30 / 30** |
| False alarms | 2 / 30 (lenient parsing) | **1 / 30** |
| Signal recall | 67% to 76% (lenient parsing) | **82%** |
| Signal precision | 88% to 90% (lenient parsing) | 88% |
| Latency on Tinker | 2.0 to 2.6 s | 4.8 to 6.6 s |

The base model understands the risk but invents field names (`signal_id` instead of `id`), so the app can't use its
answers. "Lenient parsing" guesses the renamed fields to give the base model a fair comparison. The fine-tuned model
follows the format every time and finds more signals. Trade-off: it was slower on Tinker's sampler.
Scripts: `train/make_train.py`, `train/tinker_sft.py`, `train/tinker_eval.py`.

## Durable evaluation with Temporal

Evaluating a local model on a laptop is fragile: Ollama crashes, the GPU runs out of memory, the lid gets closed.
The evaluation runs as a [Temporal](https://temporal.io) workflow where **each conversation is one activity with automatic retries**
(`guard/temporal_flow.py`, `guard/temporal_activities.py`).

Crash test: Ollama was killed on purpose at conversation 11 of 60. The workflow paused, retried 6 times with backoff
while the model was down, and resumed at conversation 12 when Ollama came back. No conversation was lost or re-run.

```bash
temporal server start-dev --db-filename .temporal.db
python -m eval.temporal_worker          # terminal 1
python -m eval.temporal_run             # terminal 2 (re-attaches if already running)
python -m eval.temporal_run --status    # progress, e.g. 23/60
```

## Limits

Night Guard is a learning and support tool, not a guarantee of safety. It can miss things and can raise false alarms. It does not replace trusted adults or platform reporting tools.

## Prior art and credit

- [Bark](https://www.bark.us/) monitors for parents and sends alerts (cloud, paid).
- [Apple Communication Safety](https://support.apple.com/en-us/105069) blurs photos and videos on-device and offers the child help options.
- [Roblox Sentinel](https://about.roblox.com/newsroom/2026/08/roblox-open-source-safety-models-roost) is open-source platform-side detection.

Night Guard's angle is different: **child-facing, explain-don't-spy, and help-seeking.**

## License

MIT
