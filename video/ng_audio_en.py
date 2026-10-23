"""Mix for the English long film: an original drama bed (A minor, piano + strings + heartbeat) until Night Guard
appears, then Funkorama (Kevin MacLeod, CC BY 4.0). Brian narrates; Sarah speaks the real English warning."""
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

from ng_film_en import DUR, MUSIC_SWITCH, S, SARAH_AT, SARAH_FILE, timeline

HERE = Path(__file__).resolve().parent
SR = 48000; N = int(SR * DUR); rng = np.random.default_rng(7)
FUNK = HERE.parents[1] / "codegames" / "pipeline" / "music" / "incompetech" / "Funkorama.mp3"


def T(s): return int(s * SR)
def tt(d): return np.arange(int(d * SR)) / SR
def hz(m): return 440.0 * 2 ** ((m - 69) / 12)
def lpf(x, k):
    k = max(1, int(k)); c = np.cumsum(np.concatenate([np.zeros(k), x])); return (c[k:] - c[:-k]) / k


def load(p):
    tmp = HERE / "tmp_mix_en.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(p), "-ac", "1", "-ar", str(SR), str(tmp)], check=True)
    a, _ = sf.read(tmp, dtype="float64"); tmp.unlink(); return a


def add(buf, t0, s, g=1.0):
    i = T(t0)
    if i >= N: return
    j = min(N, i + len(s)); buf[i:j] += s[: j - i] * g


# ---- original drama bed: Am - F - Dm - E, 4 s per chord, string pad + low piano + heartbeat
def drama(dur):
    n = int(dur * SR); out = np.zeros(n)
    prog = [(57, [57, 60, 64]), (53, [53, 57, 60]), (50, [50, 53, 57]), (52, [52, 56, 59])]
    step = 4.0
    for k in range(int(dur / step) + 1):
        root, ch = prog[k % 4]; t0 = k * step; m = int(step * SR * 1.15)
        t = np.arange(m) / SR; env = np.minimum(1, t / 1.2) * np.minimum(1, (step * 1.15 - t) / 0.8).clip(0)
        pad = sum(np.sin(2 * np.pi * hz(x) * (1 + dt) * t) + 0.35 * np.sin(4 * np.pi * hz(x) * (1 + dt) * t)
                  for x in ch for dt in (-0.003, 0.003))
        add_local(out, t0, pad * env * 0.05)
        bass = np.sin(2 * np.pi * hz(root - 24) * t) * env * 0.12
        add_local(out, t0, bass)
        for b, x in enumerate([ch[0] + 12, ch[2] + 12, ch[1] + 12, ch[2] + 12]):     # slow piano notes
            pt = np.arange(int(1.6 * SR)) / SR
            note = sum(np.sin(2 * np.pi * hz(x) * h * pt) / h ** 1.5 for h in (1, 2, 3)) * np.exp(-pt * 2.2) * 0.07
            add_local(out, t0 + b * 1.0, note)
    for i in range(int(dur / 1.15)):                                                     # heartbeat
        bt = np.arange(int(0.25 * SR)) / SR
        beat = np.sin(2 * np.pi * (55 + 30 * np.exp(-bt * 30)) * bt) * np.exp(-bt * 18) * 0.35
        add_local(out, i * 1.15, beat); add_local(out, i * 1.15 + 0.28, beat * 0.7)
    return out


def add_local(buf, t0, s):
    i = int(t0 * SR)
    if i >= len(buf): return
    j = min(len(buf), i + len(s)); buf[i:j] += s[: j - i]


voice = np.zeros(N); sfx = np.zeros(N)
for s in timeline().values():
    v = load(HERE / "voz_en" / s["voice"]); add(voice, s["start"], v / (np.abs(v).max() + 1e-9) * 0.9)
v = load(SARAH_FILE); add(voice, SARAH_AT, v / (np.abs(v).max() + 1e-9) * 0.9)

def pop(): t = tt(0.18); return np.sin(2 * np.pi * (700 + 900 * t) * t) * np.exp(-t * 28) * 0.5
def thud(): t = tt(0.35); return np.sin(2 * np.pi * (90 + 120 * np.exp(-t * 25)) * t) * np.exp(-t * 12) + lpf(rng.normal(0, 1, len(t)), 3) * np.exp(-t * 40) * 0.5
def poofs(): t = tt(0.9); return lpf(rng.normal(0, 1, len(t)), 6) * np.sin(np.pi * t / 0.9) ** 2 * 0.9
def chime(f0=1320): t = tt(0.6); return sum(np.sin(2 * np.pi * f0 * m * t) / m for m in (1, 2, 3)) * np.exp(-t * 5) * 0.25
def swish(): t = tt(0.3); return lpf(rng.normal(0, 1, len(t)), 2) * np.sin(np.pi * t / 0.3) ** 2 * 0.35
def alarm(): t = tt(0.5); return np.sign(np.sin(2 * np.pi * 660 * t)) * (np.sin(2 * np.pi * 4 * t) > 0) * np.exp(-t * 3) * 0.15
def tick(): t = tt(0.05); return np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 120) * 0.4

for t0 in (2.2, 3.8, 5.6, 7.4): add(sfx, t0, pop())
a = S("stat")["start"]; add(sfx, a + 7.0, thud()); add(sfx, a + 8.6, thud(), 0.7)
a = S("fast")["start"]
for i in range(10): add(sfx, a + 0.5 + i * 0.5, tick())
a = S("platforms")["start"]
for i in range(4): add(sfx, a + 0.4 + i * 0.7, pop(), 0.6)
add(sfx, a + 8.6, swish()); add(sfx, a + 9.8, thud(), 0.8)
a = S("parents")["start"]; add(sfx, a + 2.6, pop())
a = S("guard")["start"]; add(sfx, a + 1.3, poofs()); add(sfx, a + 1.5, chime(880)); add(sfx, a + 1.65, chime(1320))
add(sfx, SARAH_AT - 0.8, alarm()); add(sfx, SARAH_AT - 0.3, thud(), 0.6)
a = S("hero")["start"]
for i in range(14): add(sfx, a + 0.6 + i * 0.38, chime(880 + 60 * (i % 7)), 0.45)
add(sfx, a + 6.0, chime(1760), 1.0)
a = S("family")["start"]; add(sfx, a + 2.0, chime(1568)); add(sfx, a + 2.12, chime(2093))
for t0 in (4.4, 5.4, 6.4): add(sfx, a + t0, pop(), 0.7)
s = S("tech")
for f in (0.08, 0.27, 0.55, 0.66, 0.80, 0.91): add(sfx, s["start"] + f * s["voice_dur"], swish())
add(sfx, s["start"] + s["voice_dur"] - 0.5, thud())
a = S("results")["start"]
for i in range(4): add(sfx, a + 0.4 + i * 1.3, chime(1047 + 130 * i), 0.7)
a = S("end")["start"]; add(sfx, a, chime(880), 1.0); add(sfx, a + 0.15, chime(1320), 1.0)

# music: drama until the guard arrives, 2 s crossfade into Funkorama
dr = np.zeros(N); d = drama(MUSIC_SWITCH + 3); dr[:len(d)] = d[:N]; dr = dr / (np.abs(dr).max() + 1e-9)
fk = load(FUNK)
while len(fk) < N: fk = np.concatenate([fk, fk])
fk = fk[:N] / (np.abs(fk).max() + 1e-9)
x = np.clip((np.arange(N) / SR - MUSIC_SWITCH) / 2.0, 0, 1)
music = dr * (1 - x) * 0.55 + fk * x * 0.30
music[:T(1.5)] *= np.linspace(0, 1, T(1.5))
duck = lpf((np.abs(voice) > 0.02).astype(float), SR // 4); duck = 1 - 0.55 * np.clip(duck * 3, 0, 1)
fade = np.ones(N); fade[T(DUR - 2.5):] = np.linspace(1, 0, N - T(DUR - 2.5))
mix = voice + sfx * 0.7 + music * duck * fade
mix = np.tanh(mix * 0.9) / np.tanh(0.9); mix = mix / np.abs(mix).max() * 0.95
sf.write(HERE / "mix_film_en.wav", np.stack([mix, mix], 1), SR); print("ok", DUR)
