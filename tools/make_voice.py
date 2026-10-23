"""Generate the spoken versions of Night Guard's fixed child alerts with ElevenLabs.

Only the fixed warning texts in guard/signals.py are sent (e.g. "DANGER: someone asked you to hide this...").
No chat content ever goes to ElevenLabs. The MP3s are saved in web/audio/<lang>/<signal>.mp3 and shipped with
the app, so the voice works offline and nothing is generated at runtime.

Needs ELEVENLABS_API_KEY in .env. Optional: ELEVENLABS_VOICE_ID (otherwise a calm premade voice is picked).
Run:  .venv\\Scripts\\python tools\\make_voice.py
"""

import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from guard.env import load_env  # noqa: E402
from guard.signals import SIGNALS  # noqa: E402

load_env()
KEY = os.environ.get("ELEVENLABS_API_KEY", "").strip()
API = "https://api.elevenlabs.io/v1"
PREFERRED = ["Sarah", "Rachel", "Laura", "Alice", "Matilda"]  # warm, calm voices from the premade library


FAMILY = {
    "en": "Your family will know about this. You're not in trouble. Go tell your mom, your dad or an adult you trust, right now.",
    "pt": "Sua família vai ficar sabendo. Você não está encrencado. Vai agora contar pra sua mãe, seu pai ou um adulto de confiança.",
}
SARAH = "EXAVITQu4vr4xnSDxMaL"  # premade "Sarah": soft, reassuring; works with a text-to-speech-only key


def pick_voice():
    if os.environ.get("ELEVENLABS_VOICE_ID"):
        return os.environ["ELEVENLABS_VOICE_ID"], "custom"
    r = httpx.get(f"{API}/voices", headers={"xi-api-key": KEY}, timeout=30)
    if r.status_code != 200:  # key without voices_read permission: use the known premade voice
        return SARAH, "Sarah (premade)"
    voices = r.json()["voices"]
    by_name = {v["name"].split(" ")[0]: v for v in voices}
    v = next((by_name[n] for n in PREFERRED if n in by_name), voices[0])
    return v["voice_id"], v["name"]


def speak(text, voice_id, out):
    r = httpx.post(
        f"{API}/text-to-speech/{voice_id}?output_format=mp3_44100_128",
        headers={"xi-api-key": KEY},
        json={"text": text, "model_id": "eleven_multilingual_v2",
              "voice_settings": {"stability": 0.6, "similarity_boost": 0.75, "style": 0.2}},
        timeout=120,
    )
    r.raise_for_status()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(r.content)


if __name__ == "__main__":
    if not KEY:
        sys.exit("Add ELEVENLABS_API_KEY=... to .env first.")
    voice_id, name = pick_voice()
    print(f"voice: {name}")
    total = 0
    for sid, meta in SIGNALS.items():
        for lang in ("en", "pt"):
            out = ROOT / "web" / "audio" / lang / f"{sid}.mp3"
            if out.exists() and "--force" not in sys.argv:
                continue
            speak(meta["kid"][lang], voice_id, out)
            total += len(meta["kid"][lang])
            print(f"  {lang}/{sid}.mp3")
    for lang, txt in FAMILY.items():                       # fixed "tell your parents" line, played when the family is told
        out = ROOT / "web" / "audio" / lang / "family.mp3"
        if out.exists() and "--force" not in sys.argv:
            continue
        speak(txt, voice_id, out); total += len(txt); print(f"  {lang}/family.mp3")
    print(f"done ({total} characters sent, fixed alert texts only)")
