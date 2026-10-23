"""Build video 2: the screen recording in a frame on paper, Snoozy narrating beside it, feature titles and subtitles.

  python video/walkthrough/wt_build.py pt   -> video/walkthrough/night_guard_tour_<lang>.mp4
"""
import json
import subprocess
import sys
import textwrap
from functools import lru_cache
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
VIDEO = HERE.parent
ROOT = VIDEO.parent
sys.path.insert(0, str(VIDEO))
sys.path.insert(0, str(ROOT.parent / "codegames" / "historias" / "the_expired_code"))
from palito import INK, font, paper, text  # noqa: E402
from ng_sloth import sloth  # noqa: E402

LANG = sys.argv[1] if len(sys.argv) > 1 else "pt"
W, H, FPS, SR = 1920, 1080, 24, 48000
FX, FY, FW, FH = 40, 40, 1536, 960                     # where the recording sits
NIGHT = (38, 50, 108); SOFT = (120, 112, 125)
TITLES = {
    "pt": {"home": "Liga e desliga", "check": "Algo me incomodou", "result": "O aviso pra criança", "tell": "Contar pra alguém",
           "benign": "Conversa normal", "link": "Conferir link", "auth": "Login dos pais", "practice": "Praticar e medalhas", "parents": "Área dos pais", "game": "Modo ao vivo",
           "off": "Desligar de verdade", "fault": "Falha simulada", "end": "Night Guard"},
    "en": {"home": "On and off", "check": "Something felt off", "result": "The kid's warning", "tell": "Tell someone",
           "benign": "A normal chat", "link": "Check a link", "auth": "Parents sign in", "practice": "Practice and medals", "parents": "Parents' area", "game": "Live mode",
           "off": "Off means off", "fault": "Simulated failure", "end": "Night Guard"},
}[LANG]

narr = {n["id"]: n for n in json.loads((HERE / f"narr_{LANG}.json").read_text(encoding="utf-8"))}
ev = json.loads((HERE / f"events_{LANG}.json").read_text(encoding="utf-8"))
off = ev["frames_t0"]
segs = [{**s, "vstart": round(s["start"] - off, 2)} for s in ev["segments"]]
rec = HERE / ev["video"]


def _dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout)


# A warning the app spoke while Snoozy was still talking gets its own moment: when his line ends, the picture
# holds still, the app's voice plays in full, then everything after continues (shifted by that pause).
WARN = []                                                  # (time in the final video, mp3 path)
_holds = []
for a in sorted(ev["audio"], key=lambda a: a["t"]):
    p = ROOT / a["src"].lstrip("/")
    if not p.exists():
        continue
    t0 = a["t"] - off
    seg_ = next((s for s in segs if s["vstart"] <= t0 < s["vstart"] + narr[s["id"]]["dur"] + 0.3), None)
    if seg_ is None:
        WARN.append([t0, p]); continue
    nxt = next((s2["vstart"] for s2 in segs if s2["vstart"] > seg_["vstart"]), seg_["vstart"] + narr[seg_["id"]]["dur"] + 0.4)
    hold_at = round(nxt - 0.02, 2)                         # right when his line is over, before the next part
    _holds.append((hold_at, round(_dur(p) + 0.5, 2), p))
if _holds:
    held = HERE / f"_held_{LANG}.mp4"
    pieces, last = [], 0.0
    for k, (at, d, _) in enumerate(_holds):
        a_ = HERE / f"_part{k}a.mp4"; still = HERE / f"_still{k}.png"; f_ = HERE / f"_part{k}f.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(last), "-to", str(at), "-i", str(rec), "-an", "-r", "24",
                        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(a_)], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(max(0, at - 0.05)), "-i", str(rec), "-frames:v", "1", str(still)], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(still), "-t", str(d), "-r", "24",
                        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(f_)], check=True)
        pieces += [a_, f_]; last = at
    b_ = HERE / "_partZ.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(last), "-i", str(rec), "-an", "-r", "24",
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(b_)], check=True)
    pieces.append(b_)
    lst = HERE / "_parts.txt"; lst.write_text("\n".join(f"file '{x.name}'" for x in pieces), encoding="utf-8")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(held)], check=True)
    for x in list(pieces) + [lst] + list(HERE.glob("_still*.png")): x.unlink()
    rec = held
    shift = 0.0
    for at, d, p in _holds:
        WARN.append([at + shift, p])
        for s in segs:
            if s["vstart"] >= at + shift: s["vstart"] = round(s["vstart"] + d, 2)
        for w in WARN[:-1]:
            if w[0] >= at + shift: w[0] += d
        shift += d
    # warnings already outside narration that come after a hold move with the picture
REC_DUR = _dur(rec)
print("recording", rec.name, round(REC_DUR, 2), "holds", [(h[0], h[1]) for h in _holds])
DUR = round(segs[-1]["vstart"] + narr["end"]["dur"] + 2.0, 2)   # the last screen holds until Snoozy is done


def load(p):
    tmp = HERE / "_tmp.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(p), "-ac", "1", "-ar", str(SR), str(tmp)], check=True)
    a, _ = sf.read(tmp, dtype="float64"); tmp.unlink(); return a


@lru_cache(maxsize=32)
def env(path):
    a = load(path); hop = SR // 12
    r = np.array([np.sqrt(np.mean(a[j:j + hop] ** 2)) for j in range(0, len(a), hop)])
    return (r / (r.max() or 1)).tolist()


def talking(t):
    for s in segs:
        n = narr[s["id"]]
        if s["vstart"] <= t < s["vstart"] + n["dur"]:
            e = env(str(HERE / n["voice"])); k = int((t - s["vstart"]) * 12)
            m = e[k] if 0 <= k < len(e) else 0.0
            return 0.0 if m < 0.12 else min(1.0, m * 1.25)
    return None


def subs():
    out = []
    for s in segs:
        n = narr[s["id"]]
        parts = [p.strip() for p in n["line"].replace(": ", ":|").replace(". ", ".|").replace("? ", "?|").split("|") if p.strip()]
        total = sum(len(p) for p in parts); t = s["vstart"]
        for p in parts:
            d = n["dur"] * len(p) / total; out.append((t, t + d + 0.15, p, s["id"])); t += d
    return out


SUBS = subs()


@lru_cache(maxsize=1)
def base():
    """Paper with a transparent window where the recording shows through, plus a soft shadow and frame."""
    im = paper().copy().convert("RGBA")
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(sh)
    d.rounded_rectangle((FX + 10, FY + 14, FX + FW + 10, FY + FH + 14), 22, fill=(60, 50, 40, 70))
    im = Image.alpha_composite(im, sh)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((FX - 8, FY - 8, FX + FW + 8, FY + FH + 8), 26, fill=(34, 30, 38, 255))
    hole = Image.new("L", (W, H), 255); ImageDraw.Draw(hole).rounded_rectangle((FX, FY, FX + FW, FY + FH), 18, fill=0)
    im.putalpha(Image.fromarray(np.minimum(np.array(im.split()[3]), np.array(hole))))
    return im


def frame(t):
    im = base().copy(); d = ImageDraw.Draw(im)
    cur = [s for s in segs if s["vstart"] <= t]
    sid = cur[-1]["id"] if cur else segs[0]["id"]
    idx = [s["id"] for s in segs].index(sid) + 1
    cx = (FX + FW + W) / 2
    text(d, f"{idx}/{len(segs)}", cx, 90, 40, SOFT)
    for i, ln in enumerate(textwrap.wrap(TITLES[sid], 11)):
        text(d, ln, cx, 160 + i * 66, 60, NIGHT, "mm", "impact.ttf")
    m = talking(t)
    sloth(im, t, cx, 1000, 330, m or 0.0, "talk" if m is not None else "listen")
    d = ImageDraw.Draw(im)
    for a, b, s, _ in SUBS:
        if a <= t < b:
            f = font("segoeprb.ttf", 38); w = d.textlength(s, font=f)
            if w > 1500:
                lines = textwrap.wrap(s, 70)
            else:
                lines = [s]
            hh = 54 * len(lines)
            y0 = FY + FH - 30 - hh
            mw = max(d.textlength(l, font=f) for l in lines)
            d.rounded_rectangle((FX + FW / 2 - mw / 2 - 22, y0 - 8, FX + FW / 2 + mw / 2 + 22, y0 + hh + 4), 16, fill=(255, 251, 240, 235))
            for i, l in enumerate(lines):
                text(d, l, FX + FW / 2, y0 + 25 + i * 54, 38, INK)
            break
    if t < 0.6:
        im.putalpha(Image.fromarray((np.array(im.split()[3]) * 1.0).astype(np.uint8)))
    return im


def mix():
    N = int(DUR * SR); voice = np.zeros(N); fx = np.zeros(N)

    def add(buf, t0, a, g=0.9):
        i = int(t0 * SR)
        if i >= N: return
        j = min(N, i + len(a)); buf[i:j] += a[: j - i] * g
    for s in segs:
        a = load(HERE / narr[s["id"]]["voice"]); add(voice, s["vstart"], a / (np.abs(a).max() + 1e-9))
    spoken = [(s["vstart"], s["vstart"] + narr[s["id"]]["dur"] + 0.3) for s in segs]
    WARN.sort(key=lambda x: x[0])
    for k, (t0, p) in enumerate(WARN):                      # the real spoken warnings, never over Snoozy's voice
        w = load(p)
        if k + 1 < len(WARN):                               # the app stops a clip when the next one starts
            w = w[: max(0, int((WARN[k + 1][0] - t0) * SR))]
        t1 = t0 + len(w) / SR
        if any(t0 < b and t1 > s0 for s0, b in spoken):
            print("skipped (would overlap):", round(t0, 1), p.name); continue
        add(fx, t0, w / (np.abs(w).max() + 1e-9), 0.85)
        print("warning voice at", round(t0, 1), p.name)
    music = load(ROOT.parent / "codegames" / "pipeline" / "music" / "incompetech" / "Funkorama.mp3")
    while len(music) < N: music = np.concatenate([music, music])
    music = music[:N] / (np.abs(music).max() + 1e-9)
    talk = np.abs(voice) + np.abs(fx)
    kern = SR // 4; c = np.cumsum(np.concatenate([np.zeros(kern), (talk > 0.02).astype(float)]))
    duck = 1 - 0.65 * np.clip((c[kern:] - c[:-kern]) / kern * 3, 0, 1)
    fade = np.ones(N); fade[int((DUR - 2) * SR):] = np.linspace(1, 0, N - int((DUR - 2) * SR))
    out = voice + fx + music * 0.22 * duck * fade
    out = np.tanh(out * 0.9) / np.tanh(0.9); out = out / np.abs(out).max() * 0.95
    sf.write(HERE / f"_mix_{LANG}.wav", np.stack([out, out], 1), SR)


if __name__ == "__main__":
    mix()
    dst = HERE / f"night_guard_tour_{LANG}.mp4"
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-i", str(rec),
                           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-i", str(HERE / f"_mix_{LANG}.wav"),
                           "-filter_complex", f"[0:v]fps={FPS},tpad=stop_mode=clone:stop_duration=6,scale={FW}:{FH},pad={W}:{H}:{FX}:{FY}:color=#f7f2e6[bg];[bg][1:v]overlay=0:0:shortest=1[v]",
                           "-map", "[v]", "-map", "2:a", "-t", str(DUR), "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                           "-pix_fmt", "yuv420p", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", str(dst)],
                          stdin=subprocess.PIPE)
    for i in range(int(DUR * FPS)):
        ff.stdin.write(frame(i / FPS).tobytes())
    ff.stdin.close(); ff.wait()
    (HERE / f"_mix_{LANG}.wav").unlink()
    print("done", dst.name, DUR)
