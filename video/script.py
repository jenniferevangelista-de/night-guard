"""Night Guard demo film: narration lines (Brian, edge-tts) and timeline.

Run:  python video/script.py   -> video/voz/n*.mp3 and video/timeline.json
"""
import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts

HERE = Path(__file__).parent
VOICE = "en-US-BrianMultilingualNeural"

# scene id, narration, extra seconds after the line (room for visuals / product audio)
SCENES = [
    ("night", "It's eleven p.m. A kid is playing online. And someone is being very, very nice.", 1.6),
    ("stat", "Last year, one US hotline got more than fifty thousand sextortion reports. About one hundred thirty seven a day.", 1.2),
    ("parents", "Parents can't read every chat. And kids don't always see the trick.", 1.0),
    ("guard", "Meet Night Guard. An open model that reads the chat on the family's own computer.", 1.0),
    ("alert", "When a stranger asks for a secret, it warns the kid right away, in words they get.", 9.6),
    ("family", "Parents get one alert. Not the whole chat. Just what happened, and what to do now.", 2.2),
    ("tech", "Gemma runs it locally and even reads the screen. Tinker taught a model our format. Temporal survives crashes. Sentry traces every check, with no chat inside.", 1.4),
    ("hero", "The more the kid learns, the lazier the guard gets. That's the lazy payoff.", 1.6),
    ("end", "Night Guard. Try it today.", 2.6),
]


async def speak(text, out):
    await edge_tts.Communicate(text, VOICE, rate="+0%").save(str(out))


def duration(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


async def main():
    (HERE / "voz").mkdir(exist_ok=True)
    t, timeline = 0.4, []
    for i, (sid, line, extra) in enumerate(SCENES, 1):
        out = HERE / "voz" / f"n{i}.mp3"
        if not out.exists():
            await speak(line, out)
        d = duration(out)
        timeline.append({"id": sid, "line": line, "voice": out.name, "start": round(t, 2),
                         "voice_dur": round(d, 2), "end": round(t + d + extra, 2)})
        t += d + extra
    (HERE / "timeline.json").write_text(json.dumps({"scenes": timeline, "duration": round(t + 0.3, 2)}, indent=2))
    for s in timeline:
        print(f"{s['id']:8} {s['start']:6.2f} -> {s['end']:6.2f}  ({s['voice_dur']}s voice)")
    print("total", round(t + 0.3, 2), "s")


if __name__ == "__main__":
    asyncio.run(main())
