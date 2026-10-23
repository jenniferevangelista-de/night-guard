# 🛡️🌙 Night Guard

**Helps kids understand what happened in an online chat, and choose how to ask for help.**
Runs on the child's own computer with **Gemma** (Google's open-weight model) through Ollama.
Chats never leave the device.

> Existing tools watch kids. Night Guard watches out *for* them.

**Try the online demo:** https://night-guard-demo.onrender.com
(fictional examples only; it runs the Tinker fine-tuned model in the cloud so anyone can try it. The real app runs
on the child's computer with Gemma. Free instance: the first visit after a quiet period takes ~50 s to wake up.)

> ## 🚧 Next step: mobile apps and in-game chat
> Today, on a **Windows computer**, Night Guard reacts **on its own, as messages arrive**: a Chrome extension
> watches web chats (Discord web, WhatsApp Web, experimental), and a **screen guard** uses Gemma's vision to read the
> chat inside **installed apps** like the Roblox and Discord apps, all on-device.
> **It does not yet protect phones.** On **Android**, the plan is an app that reads message notifications
> (the same permission parental tools use there) and runs the detector on-device. On **iPhone**, Apple doesn't let
> any app read other apps' messages, so the realistic path is working with Apple's own Communication Safety.
> Bringing Night Guard to the phone, where most kids chat, is the project's next milestone.

## What it does

| Screen | What happens |
|---|---|
| **Something felt off** | Paste a chat. Before showing results, Night Guard asks *"did anything feel off to you?"*, then highlights the exact phrases that match common pressure tricks (secrecy, moving to another app, free-stuff links, password requests…) with a calm one-line explanation. If nothing is found, it says so, and reminds the child that their feeling still counts. |
| **Practice** | Short, pre-reviewed fictional scenarios (fake moderator, free Robux link, "don't tell your parents"). Choose a reply, then see why it works or not. |
| **Tell someone** | Pick which quotes to share, and Gemma drafts a short, editable message to a trusted adult ("I didn't do anything wrong, but I need help"). Nothing is sent automatically. |
| **Family** | Kids don't always recognize a bad intention, so parents set **family rules**: which signals are shared with them automatically (default: photo requests, meeting in person, password requests, secrecy, and any high-risk combination). The child is always told when that happens. Parents see the risk type, the app and the flagged phrase, never the whole chat. |

### Proactive: it doesn't wait for the child to paste anything

Grooming in games can take **20 to 45 minutes** (Swansea University, 2016; WeProtect figure cited by Brazil's
Ministry of Justice), so waiting for a child to come and paste a chat is too late. Night Guard watches the chat as
messages arrive and warns the child on the spot:

- **Live demo:** open `/game` (also on the online demo): a fictional game chat where a stranger writes and Night Guard
  reacts on its own.
- **Chrome extension** (`extension/`): load it unpacked (`chrome://extensions` → Developer mode → Load unpacked →
  pick the `extension` folder). It reads new messages on Discord web and WhatsApp Web (experimental) and sends them
  **only to the local server** (`http://localhost:...`); the extension refuses any non-local address. A
  "🛡️ Guard on" badge is always visible, so the child knows the guard is there.

- **Screen guard for installed apps** (`guard/screen_guard.py`, Windows): web chats are only half of it, because
  kids chat inside the **Roblox app, the Discord app, Minecraft, TikTok**. Every few seconds, if the window in
  front is one of those apps, Night Guard takes a screenshot of that window **in memory**, and **Gemma's vision**
  reads the chat locally. The text goes to the same detector; the image is never saved and never leaves the
  computer. Any other window (bank, email, school) is never captured. Run:
  `python -m guard.screen_guard --server http://localhost:8765 --lang en --me <child's username>`

### What the child sees vs. what the family sees

| | Child | Family |
|---|---|---|
| Tone | Plain words, says **"DANGER"** when it is, and compares it to something kids already know: *"It's like a stranger on the street saying 'come with me, but don't tell your mom'. You don't go, and you tell an adult."* Never blames the child. | What happened, why it matters (with sources), and **what to do now**: talk calmly without punishment, keep screenshots, block and report, and for image requests, threats or money demands report to SaferNet / NCMEC and the police. Don't pay. |
| Content | The flagged phrase and three actions: don't reply, block, tell an adult | Risk level, app, contact, flagged phrase. Never the full chat |

### The gap no platform covers

Instagram supervision, Discord Family Center, TikTok Family Pairing and Roblox parental controls each protect **their own app**. The classic pressure path starts in a game and moves to a private app. Night Guard records where each check happened, so the family sees:

> ⚠️ Same contact seen in more than one app: **Alex_17 (Roblox → Instagram)**

**The lazy part:** the tutor repeats less as you learn. Lessons you already know collapse to a single ✓ line, so the guard gets lazier as the kid gets wiser.

## Privacy model

**Local app (the real Night Guard)**
- Analysis and message drafting run **locally** (Ollama + `gemma4:e4b`). Chat text never leaves the computer.
- Full conversations are never stored. For family alerts, only the flagged phrase, risk type, app and contact name
  are saved on that computer (`data/`, git-ignored). Learning progress lives in the browser's localStorage.
- The Family area is a local, single-family view with no login yet. Parent authentication is the next step.

**Public demo (Render)**
- The text you check is sent to the Tinker fine-tuned model to be analyzed. The demo server saves nothing.
- Family rules and alerts stay in each visitor's own browser, so one visitor never sees another's.
- Meant for fictional examples only, and says so on screen.

**If the model can't be reached or answers in an unreadable format**, Night Guard shows
"Couldn't analyze this chat", never a green "nothing found". Every flagged phrase is checked against the chat:
the message index must point to a contact message, and a paraphrased quote is replaced by the real message.

Cloud services otherwise only touch **fictional test data** (evaluation, scenarios).

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

All results come from fictional chats written for testing (30 risky, 30 safe). They show the approach works on
these patterns, not that it catches every real-world case.
Night Guard is a learning and support tool, not a guarantee of safety. It can miss things and can raise false alarms. It does not replace trusted adults or platform reporting tools.

## Prior art and credit

- [Bark](https://www.bark.us/) monitors for parents and sends alerts (cloud, paid).
- [Apple Communication Safety](https://support.apple.com/en-us/105069) blurs photos and videos on-device and offers the child help options.
- [Roblox Sentinel](https://about.roblox.com/newsroom/2026/08/roblox-open-source-safety-models-roost) is open-source platform-side detection.

Night Guard's angle is different: **child-facing, explain-don't-spy, and help-seeking.**

## License

MIT
