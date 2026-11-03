---
title: "What a week of building a kid-safety guard on a laptop GPU taught me about measuring small models"
published: true
tags: mlhacks, devchallenge, hackathon, ai
ai_disclosure_level: some_ai
---

_This is a submission for the [MLH x DEV Writing Challenge](https://dev.to/mlh-hackathon)_

## What I Built

**Night Guard** is an open-source app that helps kids understand what happened in an online chat and decide how to ask for help. It runs on the family's own computer with **Gemma** (`gemma4:e4b`) through Ollama, so the chat text stays on the device.

Kids don't usually meet danger as swear words. They meet it as kindness: "you're so mature for your age", "free Robux for you", "let's talk on another app", "don't tell your parents". A bad-words filter misses all of that, and sentiment analysis reads it as positive. So Night Guard looks for **14 pressure tactics** described in child-safety guidance (secrecy, moving to a private app, photo requests, password requests, coming back after a block, sextortion and others), points to the exact phrase, and explains it in plain words.

It talks to two people in two different ways:

- **The kid** sees the flagged phrase, a short explanation ("It's like a stranger on the street saying 'come with me, but don't tell your mom'"), and three actions: don't reply, block, tell an adult. A **Tell someone** screen turns the quotes the kid picks into an editable message for a trusted adult. That message comes from a fixed template, not from the model, and nothing is sent automatically.
- **The parents** see the risk level, the app, the contact and the flagged phrase, plus what to do now. They never see the whole chat. The family sets which signals are shared, and the kid is always told when that happens.

I built it during the Hacktoberfest 2026 Open-Source AI Challenge, Week 3, whose theme was "Slow and Steady": projects that reward laziness by making someone's life easier. The lazy part here is for parents, who can't read every message their kids get in Roblox or Discord. The guard reads them and only speaks up when something matches a known tactic.

The project won **Best Use of Backboard** in that week ([winners post](https://dev.to/devteam/congrats-to-the-hacktoberfest-open-source-ai-challenge-week-3-slow-and-steady-winners-3e4a)). This post is not a repeat of my submission. It's about how the thing works under the hood and what I learned from measuring it.

### How it works

```
chat messages ──> FastAPI server (localhost) ──> Gemma 4 via Ollama
                         │                          │
                         │                 JSON: tactic id, message index,
                         │                       quote, summary
                         ▼
               postprocessing + scoring
       (quote must exist in the chat, index must point
        to a message from the other person, otherwise dropped)
                         │
          ┌──────────────┴───────────────┐
          ▼                              ▼
   kid's screen (template text,    family view (risk, app,
   optional voice warning)         contact, phrase only)
```

Three ways messages reach the detector:

1. **Paste a chat** on the "Something felt off" screen. Before showing anything, it asks the kid whether something felt off to them, so the kid's own judgment comes first.
2. **A Chrome extension** for Discord web and WhatsApp Web (experimental). It sends only to `localhost` and refuses any other address. Each check gets the **12 most recent messages**.
3. **A screen guard for installed apps** on Windows. Kids chat inside the Roblox and Discord apps, where a browser extension can't see. Every few seconds, if the window in front is one of those apps, the guard takes a screenshot of that window in memory, and Gemma's vision reads the chat text locally. The image is never saved. Any other window (bank, email, school) is never captured. Reading a chat from a screenshot took about 7 s warm and about 23 s cold.

Two rules I kept from day one:

- **If the model fails, the kid never sees "all clear".** An unreachable model or an unreadable answer shows "Couldn't analyze this chat". In the scoring code, an error is never counted as a catch and never counted as a correct "safe".
- **Every quote is checked against the chat.** If the model paraphrases, the real message replaces the paraphrase. If the message index points to the kid's own message, the item is dropped.

## Demo

- Online demo (fictional examples only): https://night-guard-demo.onrender.com
  Start with "Watch the guard act on its own", a fictional game chat where a stranger writes and the guard reacts without anyone pasting anything. The free instance can take about 50 s to wake up.
- Code (MIT): https://github.com/jenniferevangelista-de/night-guard

{% youtube 2dqkL0UDC7k %}

![The live game chat: a stranger asks for secrecy and a selfie, and the guard warns the kid on its own](https://raw.githubusercontent.com/jenniferevangelista-de/night-guard/main/docs/images/live-alert-en.jpg)

The online demo can't run Gemma on the visitor's computer, so it uses a small model I fine-tuned with Tinker (more on that below). The real app runs Gemma locally.

## Partner Technologies

These are the partner tools from the Hacktoberfest challenge that ended up in the code, with what each one actually does in the project.

### Backboard: same prompt, three models, one key

I wanted to know whether my prompt and scoring were tied to one model. Through one Backboard API key I ran three cloud models on the **same 70 fictional development chats** (36 risky, 34 safe), with the same instructions, the same JSON schema in the prompt and the same scoring code:

| Model | Usable answers | Risky flagged | False alarms on safe chats | Signal precision / recall |
|---|---|---|---|---|
| Gemma 3 27B | 69/70 | 36/36 | 3/33 (1 error) | 0.938 / 0.849 |
| Llama 3.3 70B | 69/70 | 36/36 | 3/33 (1 error) | 0.912 / 0.981 |
| Mistral Small 3.1 24B | 70/70 | 36/36 | 3/34 | 0.852 / 0.981 |

All three caught every risky chat, so the chat-level number didn't separate them. The signal level did: Gemma 3 was the most precise, Llama and Mistral found more of the individual tactics. I also tried Qwen 2.5 72B, but it timed out (120 s) in the first smoke test, so I don't report a result for it. The whole comparison, including smoke tests, cost **USD 0.034062** in Backboard billing.

The useful part of Backboard for me was switching models by changing one string, which made it cheap to ask "is this my prompt or is this the model?".

### Tinker: fixing the format, not the knowledge

Tinker doesn't serve Gemma, so for the cloud demo I fine-tuned **Qwen3-8B** with LoRA (rank 16, 2 epochs) on 1,000 fictional training chats that share no sentence with the test set. Results on the same 70 chats:

| | Qwen3-8B base | LoRA (online demo) |
|---|---|---|
| Answers in the app's full schema | 11/70 | **70/70** |
| Risky chats flagged | 0/36 (none usable) | **36/36** |
| False alarms on safe chats | 0/11 valid (23 invalid) | **2/34** |
| Signal precision / recall | n/a | **0.88 / 0.83** |
| Avg time per check on Tinker | 3.0 s | 4.5 s |

The base model looks useless in that table, but it wasn't. When I re-read its saved answers leniently, accepting renamed fields like `signal_id` instead of `id`, it flagged 35 of the 35 risky chats it answered readably. It already saw the patterns. It just didn't speak the app's format. Fine-tuning fixed the format on all 70 chats and also taught it the three tactics I added late.

### Temporal: an evaluation that survives a crash

Evaluating a local model on a laptop is fragile. Ollama crashes, the GPU runs out of memory, the lid gets closed. I moved the evaluation into a Temporal workflow where **each conversation is one activity with automatic retries**. Then I stopped Ollama in the middle of a 60-conversation run on purpose. The saved report shows conversation `s12` finishing on **attempt 5**, after the failed attempts while the model was down, and the conversations already done were kept.

### Render, Sentry, ElevenLabs, Auth0, Browserbase and SerpApi

- **Render** hosts the public demo. Because it's public, it has limits: 4,000 characters per analysis, 30 attempts per visitor per hour, 120 in total per hour, two model calls at a time. When a limit is hit, the kid's screen says the hourly limit is full, never "all clear".
- **Sentry** traces each check with numbers and labels only. An allowlist drops everything else, including message text and names, and a test checks it.
- **ElevenLabs** voiced each of the 14 fixed child warnings once, in English and Portuguese. The app plays those audio files. No chat was ever sent to ElevenLabs.
- **Auth0** is optional login for the parents' view in the local app, limited to verified, allowlisted parent emails.
- **Browserbase and SerpApi** power "Check without opening" for links: Browserbase opens the link in an isolated cloud browser and looks for password fields, SerpApi searches for reports about the domain. Only the URL or the domain is sent, never the conversation.

## Hackathon Experience

I joined Hacktoberfest 2026 as part of the global online event that MLH and DEV ran this October. This year it asked for a brand-new project with open-source AI at its core instead of pull requests, and each week had its own theme and partner categories. I worked solo, from Brazil, on a laptop with an RTX 4050.

The weekly format meant shipping something complete in a few days and then improving it. The partner categories also shaped the project: the cross-model comparison came from trying Backboard, and the crash-tested evaluation came from trying Temporal.

### What I learned

1. **Measure errors separately from answers.** An early version could turn an unreadable model answer into "no risk", which on a safe chat looks like a correct answer. For a safety tool that is the worst possible bug. Now coverage is its own number (Gemma 4 local: **70/70** usable answers), and errors are never catches.
2. **A small local model can be good enough for this job.** `gemma4:e4b`, zero-shot, on the laptop GPU: **36/36** risky chats flagged, **3/34** false alarms, signal precision 0.885 and recall 0.868, about **3.4 s** per check. The first version, on 60 chats, had 4/30 false alarms.
3. **False alarms tell you what the test set is missing.** The three that remain are hard cases I wrote on purpose: a "secret" about a leaked Halloween event in a game, a classmate saying "see you at school", a birthday "how old r u now". Out of context, they read like grooming. For this tool, a false alarm the kid can dismiss costs less than a missed photo request.
4. **Be honest about what the numbers mean.** All 70 chats are fictional, written for testing, and I changed the prompt after seeing some of them. So these are development numbers, not proof that it works on real chats. I wrote that in the README next to the tables.
5. **Fine-tuning can be about format.** The Tinker experiment showed me that the base model already knew the patterns; what it lacked was a reliable output contract. That changed how I think about when fine-tuning is worth it.

### What's next

Night Guard protects Windows computers today. Most kids chat on phones. On Android, the plan is an app that reads message notifications and runs the detector on the device. On iPhone, Apple doesn't let apps read other apps' messages, so the realistic path is working alongside Apple's own Communication Safety.

If you work on child safety, game moderation or small on-device models, I'd like to hear what you would test next.
