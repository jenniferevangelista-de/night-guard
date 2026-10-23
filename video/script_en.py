"""Night Guard film, English long version: narration (Brian, edge-tts) and timeline.

Run:  python video/script_en.py   -> video/voz_en/n*.mp3 and video/timeline_en.json
"""
import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts

HERE = Path(__file__).parent
VOICE = "en-US-BrianMultilingualNeural"

# scene id, narration, extra seconds after the line
SCENES = [
    ("intro", "Hi, I'm Snoozy, the laziest night watchman you'll ever meet. Slow and steady is my thing. So let me show you how a lazy guard helps keep kids safe.", 0.8),
    ("night", "It's eleven p.m. A kid is playing online. And someone is being way too nice to her.", 1.4),
    ("stat", "In 2025 alone, the US National Center for Missing and Exploited Children received more than fifty thousand "
             "sextortion reports. That's one hundred thirty seven a day. Almost one every ten minutes.", 1.2),
    ("fast", "And it can be fast. In a Swansea University study, the first sexual request came in just eighteen minutes.", 1.0),
    ("platforms", "Roblox, Discord, Minecraft, TikTok. Each platform only watches its own backyard. And predators know it: "
                  "they pull the kid into an encrypted app, where no one else can see.", 1.2),
    ("parents", "Parents can't read every chat. And kids don't always spot the trap.", 1.4),
    ("guard", "Meet Night Guard. An open model that runs on the family's own computer. It reads what's on the screen, "
              "so it protects even inside encrypted apps. And the chat never leaves home.", 0.8),
    ("alert", "When a stranger asks for a secret, it warns the kid right away, in words they understand.", 10.6),
    ("hero", "To the kid, it's a friend. Every trick she learns becomes a medal, until she's a Night Hero.", 1.2),
    ("family", "To parents, it's the Night Guard. One alert, not the whole chat. What happened, and what to do now, "
               "right on their phone.", 1.4),
    ("tech", "Under the hood, it's all open. Gemma 4 reads text and the screen on the computer itself. On Tinker, we fine-tuned "
             "a model that got the format right in seventy out of seventy chats. Temporal survives crashes, Sentry traces every "
             "check without reading the chat, ElevenLabs gives the warnings a voice, and the demo runs on Render.", 1.0),
    ("results", "In testing, it caught thirty six out of thirty six risky chats, in about four seconds.", 1.4),
    ("peace", "Peace for the kid. Peace for the parents. And the more the kid learns, the more the guard can rest.", 1.6),
    ("end", "Night Guard. A partner for parents. A friend for kids. And me? Back to my nap.", 3.0),
]


async def speak(text, out):
    await edge_tts.Communicate(text, VOICE, rate="+0%").save(str(out))


def duration(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


async def main():
    (HERE / "voz_en").mkdir(exist_ok=True)
    t, timeline = 1.2, []
    for i, (sid, line, extra) in enumerate(SCENES, 1):
        out = HERE / "voz_en" / f"n{i}.mp3"
        await speak(line, out)
        d = duration(out)
        timeline.append({"id": sid, "line": line, "voice": out.name, "start": round(t, 2),
                         "voice_dur": round(d, 2), "end": round(t + d + extra, 2)})
        t += d + extra
    (HERE / "timeline_en.json").write_text(json.dumps({"scenes": timeline, "duration": round(t + 0.3, 2)},
                                                      indent=2, ensure_ascii=False), encoding="utf-8")
    for s in timeline:
        print(f"{s['id']:9} {s['start']:6.2f} -> {s['end']:6.2f}  ({s['voice_dur']}s voice)")
    print("total", round(t + 0.3, 2), "s")


if __name__ == "__main__":
    asyncio.run(main())
