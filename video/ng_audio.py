"""Mix for the Night Guard film: Brian narration, Sarah's real ElevenLabs warning, sound effects, Funkorama at 30% ducked."""
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

from ng_film import DUR, S, SARAH_AT, SARAH_FILE, timeline

HERE = Path(__file__).resolve().parent
SR = 48000; N = int(SR * DUR); rng = np.random.default_rng(1)
MUSIC = HERE.parents[1] / "codegames" / "pipeline" / "music" / "incompetech" / "Funkorama.mp3"


def T(s): return int(s * SR)
def tt(d): return np.arange(int(d * SR)) / SR
def lpf(x, k):
    k = max(1, int(k)); c = np.cumsum(np.concatenate([np.zeros(k), x])); return (c[k:] - c[:-k]) / k


def load(p):
    tmp = HERE / "tmp_mix.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(p), "-ac", "1", "-ar", str(SR), str(tmp)], check=True)
    a, _ = sf.read(tmp, dtype="float64"); tmp.unlink(); return a


voice = np.zeros(N); sfx = np.zeros(N)
def add(buf, t0, s, g=1.0):
    i = T(t0); j = min(N, i + len(s)); buf[i:j] += s[: j - i] * g

for s in timeline().values():
    v = load(HERE / "voz" / s["voice"]); add(voice, s["start"], v / (np.abs(v).max() + 1e-9) * 0.9)
v = load(SARAH_FILE); add(voice, SARAH_AT, v / (np.abs(v).max() + 1e-9) * 0.9)

def pop(): t = tt(0.18); return np.sin(2 * np.pi * (700 + 900 * t) * t) * np.exp(-t * 28) * 0.5
def thud(): t = tt(0.35); return np.sin(2 * np.pi * (90 + 120 * np.exp(-t * 25)) * t) * np.exp(-t * 12) + lpf(rng.normal(0, 1, len(t)), 3) * np.exp(-t * 40) * 0.5
def poofs(): t = tt(0.9); return lpf(rng.normal(0, 1, len(t)), 6) * np.sin(np.pi * t / 0.9) ** 2 * 0.9
def chime(f0=1320): t = tt(0.6); return sum(np.sin(2 * np.pi * f0 * m * t) / m for m in (1, 2, 3)) * np.exp(-t * 5) * 0.25
def swish(): t = tt(0.3); return lpf(rng.normal(0, 1, len(t)), 2) * np.sin(np.pi * t / 0.3) ** 2 * 0.35
def alarm(): t = tt(0.5); return np.sign(np.sin(2 * np.pi * 660 * t)) * (np.sin(2 * np.pi * 4 * t) > 0) * np.exp(-t * 3) * 0.15

for t0 in (1.6, 3.0, 4.4, 5.9): add(sfx, t0, pop())                                         # chat bubbles
a = S("stat")["start"]; add(sfx, a + 4.6, thud()); add(sfx, a + 5.0, thud(), 0.7)
a = S("parents")["start"]; add(sfx, a + 2.0, pop())
a = S("guard")["start"]; add(sfx, a + 1.3, poofs()); add(sfx, a + 1.5, chime(880)); add(sfx, a + 1.65, chime(1320))
a = S("alert")["start"]; add(sfx, a + 0.1, swish()); add(sfx, SARAH_AT - 0.5, alarm()); add(sfx, SARAH_AT - 0.3, thud(), 0.6)
a = S("family")["start"]; add(sfx, a, swish()); add(sfx, a + 1.0, chime(1568)); add(sfx, a + 1.12, chime(2093))
for t0 in (2.6, 3.6, 4.6): add(sfx, a + t0, pop(), 0.7)
s = S("tech")
for f in (0.0, 0.30, 0.55, 0.74): add(sfx, s["start"] + f * s["voice_dur"], swish())
add(sfx, s["start"] + s["voice_dur"] + 0.2, thud())
a = S("hero")["start"]
for i in range(6): add(sfx, a + 0.4 + i * 0.5, chime(880 + 110 * i), 0.6)
add(sfx, a + 3.3, chime(1760), 1.0)
a = S("end")["start"]; add(sfx, a, chime(880), 1.0); add(sfx, a + 0.15, chime(1320), 1.0)

m = load(MUSIC)
while len(m) < N: m = np.concatenate([m, m])
m = m[:N] / (np.abs(m).max() + 1e-9)
duck = lpf((np.abs(voice) > 0.02).astype(float), SR // 4); duck = 1 - 0.6 * np.clip(duck * 3, 0, 1)
fade = np.ones(N); fade[T(DUR - 2.0):] = np.linspace(1, 0, N - T(DUR - 2.0))
mix = voice + sfx * 0.7 + m * 0.30 * duck * fade
mix = np.tanh(mix * 0.9) / np.tanh(0.9); mix = mix / np.abs(mix).max() * 0.95
sf.write(HERE / "mix_film.wav", np.stack([mix, mix], 1), SR); print("ok", DUR)
