---
title: "Night Guard: an open-model guard that watches out for kids in game chats, so tired parents don't have to read every message"
published: false
tags: devchallenge, hf26challenge, ai, opensource
---

*This is a submission for the [Hacktoberfest 2026 Week 3 Challenge: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19).*

## What I Built

Parents can't read every chat their kids have in Roblox, Discord or TikTok. Meanwhile the US National Center for Missing & Exploited Children received **more than 50,000 reports of financial sextortion in 2025, about 137 a day** ([NCMEC, 2026](https://us.missingkids.org/blog/2026/ncmec-releases-new-sextortion-data-2025)). And it can be fast: in a Swansea University study of chats between groomers and researchers posing as children, the time from first contact to the first sexual request ranged from **18 minutes to 82 hours** ([Irish Examiner, 2016](https://www.irishexaminer.com/breakingnews/world/paedophiles-can-groom-child-online-in-less-than-20-minutes-753583.html)).

**Night Guard** is a small open-model guard that does the boring, exhausting part for them. It reads the chat **on the family's own computer**, stays quiet when everything is fine, and only speaks up when it sees a documented pressure trick: someone asking a kid to keep a secret, to move to a private app, to send a photo, or threatening to share one.

It talks to two different people in two different ways:

- **To the kid, it's a friend that turns them into a hero.** It warns in plain words and says "danger" when it is one: *"DANGER: someone asked you to hide this from your family. It's like a stranger on the street saying 'come with me, but don't tell your mom'. You don't go, and you tell an adult."* A calm voice can read it aloud. The kid levels up from Rookie to Night Hero as they learn to spot the tricks, and the guard repeats less as they learn.
- **To the parents, it's the Night Guard 🌙.** They get the risk level, the app and the flagged phrase (never the whole chat), why it matters, and what to do right now. Optionally, a push on their phone.

The lazy payoff is the whole point: **the parent doesn't have to read every chat to know when something is wrong, the guard reads them and still shows every new serious event; the kid stops getting lectures, the guard teaches them; and the guard itself gets lazier as the kid gets wiser.**

### What it is not

It's not a bad-words filter and not sentiment analysis. People who groom kids are usually *nice* ("you're so mature for your age", "free Robux for you") and rarely swear. Night Guard uses an open model to read the **whole conversation** and match it against 14 tactics documented by child-safety research, like Public Safety Canada's 2025 guidance on gaming platforms, NCMEC and Thorn.

## Demo

👉 **Try it:** https://night-guard-demo.onrender.com (fictional examples only; the free instance can take ~50 s to wake up)

Start with **① Watch the guard act on its own**: a fictional game chat where a stranger writes and Night Guard warns the kid by itself, without anyone pasting anything.

![The live game chat: a stranger asks for secrecy and a selfie, and the guard warns the kid on its own](https://raw.githubusercontent.com/jenniferevangelista-de/night-guard/main/docs/images/live-alert-en.jpg)

Then **③ See what parents get**:

![The parents' view: risk level, app, flagged phrase, why it matters and what to do now](https://raw.githubusercontent.com/jenniferevangelista-de/night-guard/main/docs/images/parents-en.jpg)

The online demo runs the **Tinker fine-tuned model** in the cloud so judges can try it without installing anything. The real Night Guard runs on the family's computer with **Gemma**, where chats never leave the device.

## Code

{% github jenniferevangelista-de/night-guard %}

The repo has 28 automated tests (`pytest tests`), including the exact failure cases our auditor reported, so those bugs can't quietly come back.

## How I Built It

### The detector: Gemma 4, on the kid's computer

The core is `gemma4:e4b` running locally through **Ollama** on a laptop GPU (RTX 4050, 6 GB). Each check sends the recent messages with a structured JSON schema and gets back the signals it found, the message index and the exact quote.

I don't trust the model blindly. Every answer goes through checks before a kid or parent sees it:

- **An unreadable answer is never "all clear".** If the model is down or answers in a broken format, the kid sees *"Couldn't analyze this chat. This is NOT an all-clear"*, never a green light. (Our auditor caught that the first version turned failures into "no risk". Fixed, and the evaluations now count a failed analysis as an error, never as a catch or as a correct "safe".)
- **Evidence is checked against the chat.** The quote must exist in a message from the contact; a paraphrased quote is replaced by the real message; the kid's own messages are never flagged.
- **Two narrow tactics need their own words in the chat.** "Came back with a new account" only counts if the chat mentions being blocked or ignored, and "you're so mature" flattery only counts with maturity or age words. Before this, a classmate who lost his password and a compliment on a Minecraft build were flagged.

**Results on a fictional test set of 70 chats (36 risky, 34 safe), written by me for testing:**

| | First version (60 chats, 11 signals) | Now (70 chats, 14 signals) |
|---|---|---|
| Valid analyses (an error never counts as a catch) | not measured | **70/70** |
| Risky chats flagged | 30/30 | **36/36** |
| False alarms on safe chats | 4/30 (13%) | **3/34 (9%)** |
| Signal precision / recall | 89% / 87% | 88% / 87% |
| Avg time per check | 3.8 s | 3.9 s |

The three remaining false alarms are on purpose hard cases: an in-game "secret" about a hidden chest, a classmate saying "see you at school", and "how old r u now" on a birthday. Honesty note: two newer hard cases were fixed **after** I saw them fail, so they're no longer a blind test. And 36/36 on fictional chats shows the approach works on these patterns, not that it catches everything in the real world.

### Proactive: it doesn't wait for a kid to paste anything

Pressure can escalate within a single chat session, so "paste your chat here" often comes too late. Night Guard watches as messages arrive:

- **Screen guard with Gemma's vision.** Kids chat inside *installed* apps (the Roblox app, the Discord app, Minecraft). Every few seconds Night Guard checks which **program** owns the window in front (by its process, not its title, so a browser tab or a document called "Roblox" is ignored). Only if it is one of those apps does it take a screenshot **in memory**, Gemma 4 reads the chat from the image locally (~7 s warm), and the text goes to the same detector. The image is never saved and never leaves the computer. Banking, email or school windows are not on the list, so they are never captured. If the window changes before the capture, nothing is read.
- **A Chrome extension** for web chats (Discord web and WhatsApp Web, experimental), which only talks to the local server and refuses any other address.
- A **"🛡️ Guard on"** badge is always visible, and it turns into *"Guard paused: can't analyze right now"* when the model is down, so silence never looks like safety. Kids know it's there. Research on teens shows covert monitoring backfires: in a study of 736 teen-written reviews of safety apps, 76% gave one star ([Ghosh et al.](https://www.cs.ucf.edu/~jjl/pubs/pn1838-ghoshA.pdf)).

### Fine-tuning with Tinker: teaching a model to speak the app's language

Tinker doesn't serve Gemma, so for the cloud demo I fine-tuned **Qwen3-8B** with a LoRA (rank 16) on **Thinking Machines' Tinker**, using fictional training chats that share no sentence with the test set. Two runs: v1 (11 tactics, 800 chats) and v2 (14 tactics, 1,000 chats, ~1.23M tokens), all compared on the same 70 test chats:

| | Qwen3-8B base | LoRA v1 | LoRA v2 (online demo) |
|---|---|---|---|
| Answers that follow the app's full schema (tactic id, message index, quote, summary) | 11 / 70 | 70 / 70 | **70 / 70** |
| Risky chats flagged, counting only schema-valid answers | 0 / 36 (none of the 36 was valid) | 36 / 36 | **36 / 36** |
| False alarms on safe chats | 0 / 11 valid (23 invalid) | 3 / 34 | **2 / 34** |
| Signal precision / recall | n/a (no valid risky answer) | 0.84 / 0.79 | **0.88 / 0.83** |
| Avg time per check | 3.0 s | 5.0 s | 4.5 s |


An answer only counts if every field matches the schema the app uses, and an invalid answer is an error, never a catch. The base model often renames fields (`signal_id` instead of `id`). Read leniently, it flagged 35 of the 35 risky chats it answered readably, so it often *sees* the pattern; it just can't answer in a form an app can use every time. Fine-tuning fixed the format on all 70 chats and found more signals, and v2 learned the three newer tactics. The online demo runs v2. Two honest limits: the false-alarm gap between v1 and v2 (3 vs 2 of 34) is a single chat, and the LoRA is not faster than the base model; the win is answers an app can always use. Every raw answer is saved per case in the repo, so anyone can recount.

### Temporal: an evaluation that survives a crashing laptop

Evaluating a local model on a laptop is fragile. The evaluation runs as a **Temporal** workflow where each conversation is an activity with automatic retries. I killed Ollama on purpose at conversation 11 of 60: the workflow retried 6 times while the model was down and resumed at conversation 12 when it came back. Nothing lost, nothing re-run, same final numbers.

![Temporal workflow completed after the crash test](https://raw.githubusercontent.com/jenniferevangelista-de/night-guard/main/docs/images/temporal.jpg)

### ElevenLabs: a calm voice for kids who don't read fast yet

Younger kids and kids with dyslexia may not read a warning in time. Every child warning (14 tactics × English and Portuguese) was voiced once with **ElevenLabs** (Sarah voice, `eleven_multilingual_v2`) and shipped as audio files. In the live game demo and in the screen guard popup, the guard reads the most serious new warning aloud, and it speaks again if the stranger insists with a new message. Only the fixed warning texts were ever sent to ElevenLabs. No chat, ever.

### Sentry: tracing the agent without reading the chats

Every check is traced in **Sentry** as an agent run (`night-guard.check`) with a model call inside (`gen_ai.chat`) and the evidence step after it. That's how I saw that a cold Gemma call takes up to 8 s and a warm one about 4.5 s on this laptop. The traces carry only numbers and labels: model, backend, latency, number of messages, severity and tactic ids. Never a message, a name or a quote: `send_default_pii` is off, local variables are not captured, and every event goes through an **allowlist**: only fields known to hold numbers and labels are kept, everything else (request bodies, breadcrumbs, exception text, any new field) is dropped. A test pushes a fake event full of a marker string and checks the marker never survives. The UI's status polling is sampled out so the agent runs stand out.

![Sentry traces: each night-guard.check with its gen_ai.chat model call](https://raw.githubusercontent.com/jenniferevangelista-de/night-guard/main/docs/images/sentry.jpg)

### Render: one click for the judges

The public demo runs on **Render** (Blueprint `render.yaml`, free instance), with the Tinker fine-tuned model as its AI backend. The demo server **stores nothing**: family rules and alerts stay in each visitor's own browser, and the screen says to use fictional examples only.

### What the family gets

- **Family rules:** for each tactic, "Tell family" or "Child decides". Photo requests, meeting in person, password requests, secrecy, coming back after a block and sextortion go to the family by default. The kid is always told when that happens: *"Your family will know about this. You're not in trouble."*
- **The gap no platform covers:** Instagram supervision, Discord Family Center, TikTok Family Pairing and Roblox parental controls each protect their own app. The classic path starts in a game and moves to a private app. Night Guard points out a possible match: *"Same name seen in more than one app (possibly the same person): Alex_17 (Roblox → Instagram)"*. It's a hint to check, not proof, because names can repeat.
- **What to do now**, by severity: talk calmly and without punishment (kids who get in trouble stop telling), keep screenshots, block and report, and for image requests, threats or money demands, report to SaferNet Brasil or the NCMEC CyberTipline and the police. Don't pay.
- **Phone alerts** through ntfy (free, no account) with only the risk level, the app and the kind of risk.
- **"Tell someone":** the kid picks what to share and gets a ready message for Mom, Dad or a teacher, built only from their own words and the flagged quotes, so nothing is invented.

### Limits and next step

- **Phones are the next milestone.** Today Night Guard protects a Windows computer. On **Android**, the plan is an app that reads message notifications (the permission parental tools use there) and runs the detector on-device. On **iPhone**, Apple doesn't let any app read other apps' messages, so the realistic path is Apple's own Communication Safety.
- It's a learning and support tool, not a guarantee of safety. It can miss things and raise false alarms. It doesn't replace trusted adults or platform reporting.
- All test data is fictional. No real children's conversations were used anywhere.

## Why Does Open Innovation Matter?

Child safety is the clearest case for open models I know. A guard that reads a kid's private chats should **run on the family's own computer**, be **inspectable**, and be **free**. The best-known commercial monitor costs about US$14 a month and analyzes messages on its servers. Platforms protect only their own walls. Roblox open-sourced its Sentinel safety models in 2026, which is great for platforms; Night Guard is the other half: an open, local tool that sits with the family and works across apps.

Open weights made every part of this possible: Gemma reading text and screenshots on a laptop GPU, a Qwen LoRA fine-tuned in an afternoon, and anyone able to audit exactly which 14 tactics trigger a warning and what words a kid will see.

## My Agent Session

I built this in about three days with an AI coding agent (Claude) as the builder and a second AI (ChatGPT) as an independent auditor, plus me as the person who decided what a kid and a parent should actually see. The auditor's review is why failures never show as "all clear", why the demo server stores nothing, and why the help message can't invent things. Each round goes through a separate private review repository: the builder delivers, the reviewer tests and writes a verdict, and only the reviewer can approve.

## The Lazy Payoff

- **Parents** don't have to read every chat. They get one alert when it matters, with what to do, and they stay the ones who talk and decide.
- **Kids** stop getting lectures. They get a short, honest warning in the moment, and they level up.
- **The guard** gets lazier over time: lessons a kid already knows collapse into a single ✓ line. *"You know every trick. Night Guard can rest a little 😴."*

## Prize Categories

- **Best Use of Gemma:** local text detector and screen-reading vision guard (`gemma4:e4b`).
- **Best Use of Tinker:** Qwen3-8B LoRA fine-tune with a measured improvement over the base model.
- **Best Use of Render:** public demo deployed from a Blueprint, running the fine-tuned model.
- **Best Use of Temporal:** durable evaluation workflow, crash-tested.
- **Best Use of ElevenLabs:** spoken child warnings in two languages.
- **Best Use of Sentry Agent Tracing:** agent runs and model calls traced with no chat content.
