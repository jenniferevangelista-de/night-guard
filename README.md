# 🛡️🌙 Night Guard

**Helps kids understand what happened in an online chat, and choose how to ask for help.**
Runs on the child's own computer with **Gemma** (Google's open-weight model) through Ollama.
Chats never leave the device.

> Existing tools watch kids. Night Guard watches out *for* them.

## What it does

| Screen | What happens |
|---|---|
| **Something felt off** | Paste a chat. Before showing results, Night Guard asks *"did anything feel off to you?"*, then highlights the exact phrases that match common pressure tricks (secrecy, moving to another app, free-stuff links, password requests…) with a calm one-line explanation. If nothing is found, it says so, and reminds the child that their feeling still counts. |
| **Practice** | Short, pre-reviewed fictional scenarios (fake moderator, free Robux link, "don't tell your parents"). Choose a reply, then see why it works or not. |
| **Tell someone** | Pick which quotes to share, and Gemma drafts a short, editable message to a trusted adult ("I didn't do anything wrong, but I need help"). Nothing is sent automatically. |

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

## Limits

Night Guard is a learning and support tool, not a guarantee of safety. It can miss things and can raise false alarms. It does not replace trusted adults or platform reporting tools.

## Prior art and credit

- [Bark](https://www.bark.us/) monitors for parents and sends alerts (cloud, paid).
- [Apple Communication Safety](https://support.apple.com/en-us/105069) blurs photos and videos on-device and offers the child help options.
- [Roblox Sentinel](https://about.roblox.com/newsroom/2026/08/roblox-open-source-safety-models-roost) is open-source platform-side detection.

Night Guard's angle is different: **child-facing, explain-don't-spy, and help-seeking.**

## License

MIT
