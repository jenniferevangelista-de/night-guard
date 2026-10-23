"""Night Guard demo film, Estúdio Kaye paper style (same hand-drawn primitives as 'The Expired Code').

1920x1080, 24 fps, ink re-drawn on twos. Real app screenshots are taped onto the paper.
  python video/ng_film.py 3 30 40      -> review frames in video/review/
  python video/ng_audio.py && python video/ng_render.py   -> video/night_guard_film.mp4
"""
import json
import math
import random
import sys
import textwrap
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT.parent / "codegames" / "historias" / "the_expired_code"))
sys.path.insert(0, str(ROOT))
from palito import (CYAN, FPS, H, INK, PAPER, RED, W, dr, eio, eout, font, jit, paper, poof, seg,  # noqa: E402
                    stick, text, wcircle, wline, wrect)
from guard.signals import SIGNALS  # noqa: E402

NIGHT = (38, 50, 108); MOON = (255, 211, 110); GREEN = (52, 160, 100); WHITE = (255, 255, 255)
SOFT = (120, 112, 125)

# ------------------------------------------------------------------ timeline (narration from script.py)
SHIFT_AFTER_ALERT = 1.3          # extra room so Sarah's spoken warning finishes before the next line
SARAH_GAP = 0.2


@lru_cache(maxsize=1)
def timeline():
    tl = json.loads((HERE / "timeline.json").read_text())
    out, shift = {}, 0.0
    for s in tl["scenes"]:
        s = dict(s); s["start"] += shift
        if s["id"] == "alert":
            s["end"] += SHIFT_AFTER_ALERT; shift = SHIFT_AFTER_ALERT
        else:
            s["end"] += shift
        out[s["id"]] = s
    return out


def S(sid): return timeline()[sid]


DUR = round(S("end")["end"] + 0.6, 2)
SARAH_AT = round(S("alert")["start"] + S("alert")["voice_dur"] + SARAH_GAP, 2)
SARAH_FILE = ROOT / "web" / "audio" / "en" / "secrecy.mp3"


@lru_cache(maxsize=4)
def rms_env(path):
    import soundfile as sf
    a, sr = sf.read(str(path), dtype="float32"); a = a.mean(1) if a.ndim > 1 else a; hop = sr // 12
    r = np.array([np.sqrt(np.mean(a[j:j + hop] ** 2)) for j in range(0, len(a), hop)])
    return (r / (r.max() or 1)).tolist()


def level(path, t0, t):
    e = rms_env(str(path)); k = int((t - t0) * 12)
    return e[k] if 0 <= k < len(e) else 0.0


# ------------------------------------------------------------------ subtitles (narration, split by sentence)
@lru_cache(maxsize=1)
def subs():
    out = []
    for s in timeline().values():
        parts = [p.strip() for p in s["line"].replace("? ", "?|").replace(". ", ".|").split("|") if p.strip()]
        merged, cur = [], ""
        for p in parts:                                   # keep chunks readable (~70 chars)
            if cur and len(cur) + len(p) > 70: merged.append(cur); cur = p
            else: cur = (cur + " " + p).strip()
        merged.append(cur)
        total = sum(len(p) for p in merged); t = s["start"]
        for p in merged:
            d = s["voice_dur"] * len(p) / total; out.append((t, t + d + 0.25, p)); t += d
    return out


def subtitle(d, t):
    for a, b, s in subs():
        if a <= t < b:
            f = font("segoeprb.ttf", 42); w = d.textlength(s, font=f)
            d.rounded_rectangle((W / 2 - w / 2 - 26, 1000, W / 2 + w / 2 + 26, 1062), 18, fill=(255, 251, 240))
            text(d, s, W / 2, 1030, 42, INK); return


# ------------------------------------------------------------------ props
def bubble(d, t, x, y, s, seed, k=1.0, who="Alex_17", col=WHITE, size=40):
    if k <= 0: return
    f = font("segoeprb.ttf", size); w = d.textlength(s, font=f) + 60; h = size + 50
    sc = eout(k); w2, h2 = w * sc, h * sc
    wrect(d, x, y, x + w2, y + h2, t, seed, 5, fill=col)
    wline(d, [(x + 30 * sc, y + h2), (x + 18 * sc, y + h2 + 26 * sc), (x + 56 * sc, y + h2)], t, seed + 7, 5)
    if k >= 0.6:
        text(d, who, x + 14, y - 22, 26, SOFT, "lm")
        text(d, s, x + 30, y + h / 2, size, INK, "lm")


def moon_window(d, t, x0=170, y0=140, x1=520, y1=470):
    d.rectangle((x0, y0, x1, y1), fill=NIGHT)
    wrect(d, x0, y0, x1, y1, t, 400, 8)
    wline(d, [((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1)], t, 401, 6); wline(d, [(x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2)], t, 402, 6)
    cx, cy = x0 + 230, y0 + 100
    d.ellipse((cx - 55, cy - 55, cx + 55, cy + 55), fill=MOON); d.ellipse((cx - 25, cy - 70, cx + 75, cy + 35), fill=NIGHT)
    r = random.Random(4)
    for i in range(9):
        sx, sy = r.uniform(x0 + 20, x1 - 20), r.uniform(y0 + 20, y1 - 20)
        if abs(sx - cx) < 70 and abs(sy - cy) < 70: continue
        tw = 3 + 3 * abs(math.sin(t * 2 + i))
        d.ellipse((sx - tw, sy - tw, sx + tw, sy + tw), fill=WHITE)


def desk_set(d, t, glow=1.0):
    wline(d, [(560, 760), (1240, 760)], t, 101, 9)
    wline(d, [(600, 760), (600, 960)], t, 102, 8); wline(d, [(1200, 760), (1200, 960)], t, 103, 8)
    wline(d, [(80, 960), (1840, 960)], t, 104, 6)
    wrect(d, 790, 738, 960, 758, t, 105, 5, fill=(225, 225, 225))
    wline(d, [(640, 812), (790, 812)], t, 106, 8)
    wline(d, [(650, 812), (650, 960)], t, 107, 7); wline(d, [(780, 812), (780, 960)], t, 108, 7)
    wline(d, [(650, 812), (640, 660)], t, 109, 7)
    fill = tuple(int(a * (1 - glow) + b * glow) for a, b in zip((230, 236, 245), (150, 210, 255)))
    wrect(d, 860, 470, 1180, 690, t, 110, 8, fill=fill)
    wline(d, [(1020, 690), (1020, 760)], t, 111, 8); wline(d, [(960, 760), (1080, 760)], t, 112, 8)


def shield(d, t, cx, cy, s=1.0, k=1.0, eyes="open", seed=500):
    """Night Guard mascot: a shield with a moon and two eyes. k draws it on (0..1)."""
    pts = [(cx, cy - 170 * s), (cx + 140 * s, cy - 120 * s), (cx + 130 * s, cy + 30 * s), (cx, cy + 170 * s),
           (cx - 130 * s, cy + 30 * s), (cx - 140 * s, cy - 120 * s), (cx, cy - 170 * s)]
    if k >= 1:
        d.polygon([jit(p, t, seed + i, 2) for i, p in enumerate(pts[:-1])], fill=NIGHT)
        mx, my = cx - 30 * s, cy - 40 * s
        d.ellipse((mx - 50 * s, my - 50 * s, mx + 50 * s, my + 50 * s), fill=MOON)
        d.ellipse((mx - 20 * s, my - 65 * s, mx + 70 * s, my + 30 * s), fill=NIGHT)
        ey = cy + 40 * s
        for ex in (cx - 40 * s, cx + 40 * s):
            if eyes == "sleep": d.arc((ex - 18 * s, ey - 10 * s, ex + 18 * s, ey + 14 * s), 20, 160, fill=WHITE, width=max(3, int(6 * s)))
            else: d.ellipse((ex - 12 * s, ey - 12 * s, ex + 12 * s, ey + 12 * s), fill=WHITE)
        wline(d, pts, t, seed, int(9 * s) or 4)
    else:                                                  # drawing on: partial outline
        n = max(2, int(len(pts) * eio(k)) + 1)
        wline(d, pts[:n], t, seed, int(9 * s) or 4)


@lru_cache(maxsize=4)
def shot(name, width):
    im = Image.open(ROOT / "docs" / "images" / name).convert("RGB")
    return im.resize((width, int(im.height * width / im.width)), Image.LANCZOS)


def taped(img, t, name, cx, cy, width, rot=-2.0, k=1.0, zoom=1.0):
    if k <= 0: return
    sh = shot(name, int(width * zoom))
    card = Image.new("RGBA", (sh.width + 28, sh.height + 28), (255, 255, 255, 255))
    card.paste(sh, (14, 14))
    a = random.Random(9)
    ang = rot + (1 - eout(k)) * 8
    card = card.rotate(ang, expand=True, resample=Image.BICUBIC)
    shadow = Image.new("RGBA", card.size, (0, 0, 0, 0)); shadow.putalpha(card.split()[3].point(lambda v: v * 0.25))
    y = cy - card.height / 2 + (1 - eout(k)) * 120
    img.paste(Image.new("RGB", card.size, (90, 80, 70)), (int(cx - card.width / 2 + 12), int(y + 14)), shadow)
    img.paste(card, (int(cx - card.width / 2), int(y)), card)
    for i, (dx, dy, tr) in enumerate(((-0.42, -0.5, -18), (0.4, -0.5, 14))):
        tape = Image.new("RGBA", (170, 50), (255, 236, 150, 170)).rotate(tr + a.uniform(-3, 3), expand=True)
        img.paste(tape, (int(cx + dx * card.width - tape.width / 2), int(y + 6 + dy * 0 - tape.height / 2)), tape)


def speaker(d, t, x, y, lvl):
    wline(d, [(x, y - 20), (x + 22, y - 20), (x + 50, y - 46), (x + 50, y + 46), (x + 22, y + 20), (x, y + 20), (x, y - 20)], t, 600, 6)
    for i in range(3):
        if lvl > 0.12 + i * 0.25:
            r = 70 + i * 32; d.arc((x + 50 - r, y - r, x + 50 + r, y + r), -40, 40, fill=RED, width=7)


def phone(d, t, x, y, k_note, lines):
    wrect(d, x, y, x + 480, y + 720, t, 700, 9, fill=(250, 250, 252))
    wline(d, [(x + 130, y + 30), (x + 200, y + 30)], t, 701, 6)
    if k_note > 0:
        yy = y + 70 + (1 - eout(k_note)) * -60
        wrect(d, x + 22, yy, x + 458, yy + 150, t, 702, 5, fill=(255, 240, 240))
        text(d, "Night Guard", x + 40, yy + 30, 30, NIGHT, "lm", "impact.ttf")
        for i, ln in enumerate(lines):
            text(d, ln, x + 40, yy + 70 + i * 34, 28, INK if i else RED, "lm")


def card(d, t, x, y, k, title, line1, line2, col, seed):
    if k <= 0: return
    s = eout(k); w, h = 700 * s, 300 * s; cx, cy = x + 350, y + 150
    wrect(d, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, t, seed, 7, fill=(255, 252, 242))
    if k > 0.7:
        d.rectangle((cx - w / 2 + 8, cy - h / 2 + 8, cx + w / 2 - 8, cy - h / 2 + 22), fill=col)
        text(d, title, cx, cy - 70, 76, col, "mm", "impact.ttf")
        text(d, line1, cx, cy + 20, 40, INK); text(d, line2, cx, cy + 80, 36, SOFT)


def check(d, t, x, y, k, label, seed):
    wrect(d, x, y - 22, x + 44, y + 22, t, seed, 5, fill=WHITE)
    if k > 0:
        wline(d, [(x + 8, y), (x + 20, y + 14), (x + 20 + 30 * eout(k), y + 14 - 40 * eout(k))], t, seed + 3, 7, GREEN)
    text(d, label, x + 70, y, 38, INK, "lm")


def stamp(img, s, cx, cy, ang, col=RED, size=80):
    f = font("impact.ttf", size); im = Image.new("RGBA", (int(len(s) * size * 0.62) + 60, size + 50), (0, 0, 0, 0))
    dd = ImageDraw.Draw(im); dd.rectangle((6, 6, im.width - 6, im.height - 6), outline=col + (255,), width=8)
    dd.text((im.width / 2, im.height / 2), s, font=f, fill=col + (255,), anchor="mm")
    im = im.rotate(ang, expand=True, resample=Image.BICUBIC); img.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)


def kid_wrap(s, width=34):
    return textwrap.wrap(s, width)


# ------------------------------------------------------------------ scenes
def sc_night(img, d, t):
    moon_window(d, t)
    desk_set(d, t, 1.0)
    typing = math.sin(t * 30) * 7
    stick(d, t, (720, 800), 1.0, lean=10, armL=(30 + typing, -10), armR=(20 - typing, -20), legL=(170, 100), legR=(160, 95),
          mood="happy", look=0.6, seed=1)
    msgs = [(1.6, "you're SO good at this"), (3.0, "best player I've met"), (4.4, "you're really mature for your age"),
            (5.9, "want free gems? just us")]
    for i, (t0, s) in enumerate(msgs):
        bubble(d, t, 1250 - i * 20, 150 + i * 150, s, 800 + i * 10, seg(t, t0, t0 + 0.35), size=38)
    text(d, "11:04 PM", 345, 520, 44, INK)


def sc_stat(img, d, t):
    a = S("stat")["start"]
    k = eio(seg(t, a + 0.5, a + 4.6)); n = int(50000 * k)
    text(d, f"{n:,}" + ("+" if k >= 1 else ""), W / 2, 330, 230, RED, "mm", "impact.ttf")
    text(d, "financial sextortion reports in 2025", W / 2, 500, 56, INK)
    text(d, "(NCMEC, US)", W / 2, 565, 36, SOFT)
    pile = int(18 * k)
    for i in range(pile):                                                    # paper reports piling up
        x = 300 + (i % 2) * 18; y = 900 - i * 22
        wrect(d, x, y, x + 260, y + 18, t, 900 + i, 4, fill=WHITE)
        x2 = 1360 - (i % 2) * 18
        wrect(d, x2, y, x2 + 260, y + 18, t, 950 + i, 4, fill=WHITE)
    if t > a + 5.0:
        k2 = eout(seg(t, a + 5.0, a + 5.4))
        wrect(d, 760, 640, 1160, 900, t, 990, 8, fill=(255, 252, 242))
        d.rectangle((768, 648, 1152, 700), fill=RED)
        text(d, "EVERY DAY", W / 2, 674, 40, WHITE, "mm", "impact.ttf")
        text(d, "137", W / 2, 800, int(60 + 80 * k2), INK, "mm", "impact.ttf")


def sc_parents(img, d, t):
    a = S("parents")["start"]
    r = random.Random(12)
    for i in range(40):                                                      # chat flood
        x = r.uniform(60, 1000); sp = r.uniform(250, 420); y = -80 + (t - a - r.uniform(0, 2.4)) * sp
        if -80 < y < 900:
            wrect(d, x, y, x + 150, y + 56, t, 1000 + i, 4, fill=WHITE)
            wline(d, [(x + 18, y + 22), (x + 130, y + 22)], t, 1100 + i, 4, SOFT); wline(d, [(x + 18, y + 38), (x + 90, y + 38)], t, 1200 + i, 4, SOFT)
    stick(d, t, (520, 780), 1.15, lean=-6, armL=(150, 200), armR=(30, -60), legL=(105, 90), legR=(75, 90), mood="sad", look=-0.4, seed=40)
    text(d, "?", 640, 330 + math.sin(t * 6) * 8, 120, RED, "mm", "impact.ttf")
    # kid with a "free gems" bubble hiding a hook
    stick(d, t, (1450, 820), 0.85, armL=(200, 240), armR=(-40, -80), legL=(105, 90), legR=(75, 90), mood="happy", look=-0.6, seed=60)
    bubble(d, t, 1250, 330, "free gems for you!", 1300, seg(t, a + 2.0, a + 2.4), size=40)
    if t > a + 3.2:
        hx, hy = 1520, 470
        wline(d, [(hx, 430), (hx, hy + 30)], t, 1310, 5)
        d.arc((hx - 34, hy, hx + 6, hy + 60), 0, 200, fill=RED, width=7)
        text(d, "the trick", hx + 120, hy + 40, 36, RED)


def sc_guard(img, d, t):
    a = S("guard")["start"]
    k = seg(t, a + 0.2, a + 1.4)
    shield(d, t, W / 2, 380, 1.25, k if k < 1 else 1.0)
    poof(d, t, W / 2, 380, seg(t, a + 1.3, a + 2.0))
    if t > a + 1.4:
        z = eout(seg(t, a + 1.4, a + 1.9))
        text(d, "NIGHT GUARD", W / 2, 655, int(40 + 90 * z), NIGHT, "mm", "impact.ttf")
    if t > a + 2.6:                                                          # the family's own computer
        x, y = 640, 760
        wrect(d, x, y, x + 260, y + 150, t, 1400, 7, fill=(225, 238, 255))
        wline(d, [(x - 30, y + 170), (x + 290, y + 170)], t, 1401, 8)
        wline(d, [(x + 70, y + 110), (x + 130, y + 50), (x + 190, y + 110)], t, 1402, 6)
        wrect(d, x + 95, y + 85, x + 165, y + 130, t, 1403, 5)
        text(d, "runs on the family's computer", 960, 800, 44, INK, "lm")
        text(d, "chats never leave home", 960, 860, 40, GREEN, "lm")


def sc_alert(img, d, t):
    a = S("alert")["start"]
    zoom = 1.0 + 0.06 * seg(t, a, a + 14)
    taped(img, t, "live-alert-en.jpg", 650, 500, 780, -2.0, seg(t, a + 0.1, a + 0.8), zoom)
    d = ImageDraw.Draw(img)
    lvl = level(SARAH_FILE, SARAH_AT, t)
    mood = "normal" if t < SARAH_AT else "sad"
    stick(d, t, (1790, 830), 0.75, armL=(200, 240), armR=(-30, -60) if t < SARAH_AT else (-120, -150), legL=(105, 90), legR=(75, 90),
          mood=mood, look=-0.8, seed=80)
    if t >= SARAH_AT - 0.3:
        speaker(d, t, 1240, 280, lvl)
        stamp(img, "DANGER", 1600, 270, 6, RED, 70); d = ImageDraw.Draw(img)
        kid = SIGNALS["secrecy"]["kid"]["en"]
        for i, ln in enumerate(kid_wrap(kid, 32)):
            text(d, ln, 1150, 420 + i * 46, 34, INK, "lm")
    return img


def sc_family(img, d, t):
    a = S("family")["start"]
    taped(img, t, "parents-en.jpg", 560, 480, 760, 2.0, seg(t, a, a + 0.7))
    d = ImageDraw.Draw(img)
    phone(d, t, 1200, 120, seg(t, a + 1.0, a + 1.4), ["HIGH risk · Roblox", "secret, photo request"])
    steps = [(a + 2.6, "talk calmly"), (a + 3.6, "keep screenshots"), (a + 4.6, "block and report")]
    text(d, "what to do now", 1230, 440, 40, NIGHT, "lm", "impact.ttf")
    for i, (t0, s) in enumerate(steps):
        if t > t0 - 0.3: check(d, t, 1230, 520 + i * 80, seg(t, t0, t0 + 0.3), s, 1500 + i * 10)
    text(d, "not the whole chat", 1430, 900, 40, RED)


def sc_tech(img, d, t):
    s = S("tech"); a, v = s["start"], s["voice_dur"]
    cards = [(0.0, "GEMMA", "runs locally, reads the screen", "gemma4:e4b on a laptop GPU", NIGHT),
             (0.30, "TINKER", "fine-tuned Qwen3-8B (LoRA)", "70/70 valid answers", RED),
             (0.55, "TEMPORAL", "evaluation survives a crash", "retries, nothing lost", GREEN),
             (0.74, "SENTRY", "traces every check", "no chat inside", (120, 70, 160))]
    for i, (f, ti, l1, l2, col) in enumerate(cards):
        t0 = a + f * v
        card(d, t, 180 + (i % 2) * 860, 140 + (i // 2) * 380, seg(t, t0, t0 + 0.4), ti, l1, l2, col, 1600 + i * 20)
    if t > a + v + 0.2:
        stamp(img, "OPEN MODELS", W / 2, 520, -5, RED, 90)


def sc_hero(img, d, t):
    a = S("hero")["start"]
    k = eio(seg(t, a + 0.3, a + 3.3))
    ranks = ["Rookie", "Spotter", "Night Hero"]
    x0, x1, y = 260, 1100, 220
    wrect(d, x0, y, x1, y + 50, t, 1700, 6, fill=WHITE)
    d.rectangle((x0 + 6, y + 6, x0 + 6 + (x1 - x0 - 12) * k, y + 44), fill=MOON)
    for i, r in enumerate(ranks):
        xx = x0 + (x1 - x0) * i / 2
        text(d, r, xx, y + 100, 40, INK if k * 2 >= i else SOFT)
    hero = k >= 1
    hy = 820 - (abs(math.sin((t - a) * 5)) * 60 if hero else 0)
    if hero:                                                                # cape behind the shoulders
        d.polygon([jit(p, t, 1710 + i) for i, p in enumerate([(628, hy - 112), (652, hy - 112), (735, hy + 30), (545, hy + 30)])], fill=RED)
    stick(d, t, (640, hy), 1.0,
          armL=(-130, -110) if hero else (200, 240), armR=(-50, -70) if hero else (-30, -60),
          legL=(110, 80), legR=(70, 100), mood="happy", seed=90)
    if hero: text(d, "NIGHT HERO!", 640, 450, 70, RED, "mm", "impact.ttf")
    sleepy = t > a + 3.0
    shield(d, t, 1450, 600, 0.9, 1.0, "sleep" if sleepy else "open", seed=520)
    if sleepy:
        for i in range(3):
            zt = (t * 0.8 + i * 0.33) % 1
            text(d, "z", 1580 + zt * 90, 420 - zt * 160, int(40 + 30 * zt), NIGHT, "mm", "impact.ttf")
        text(d, "Night Guard can rest a little", 1450, 860, 40, INK)


def sc_end(img, d, t):
    a = S("end")["start"]
    shield(d, t, W / 2, 300, 0.9, 1.0)
    z = eout(seg(t, a, a + 0.5))
    text(d, "Night Guard", W / 2, 560, int(60 + 80 * z), NIGHT, "mm", "impact.ttf")
    if t > a + 0.6: text(d, "an open-model guard for kids' chats", W / 2, 670, 50, INK)
    if t > a + 1.2: text(d, "night-guard-demo.onrender.com", W / 2, 760, 50, RED)
    if t > a + 1.8: text(d, "Gemma · Tinker · Render · Temporal · ElevenLabs · Sentry", W / 2, 850, 34, SOFT)
    text(d, 'Music: "Funkorama" Kevin MacLeod (incompetech.com), CC BY 4.0', W / 2, 1050, 22, SOFT)


ORDER = [("night", sc_night), ("stat", sc_stat), ("parents", sc_parents), ("guard", sc_guard), ("alert", sc_alert),
         ("family", sc_family), ("tech", sc_tech), ("hero", sc_hero), ("end", sc_end)]


def render(t):
    img = paper().copy(); d = ImageDraw.Draw(img)
    fn = ORDER[0][1]
    for sid, f in ORDER:
        if t >= (S(sid)["start"] if sid != "night" else 0): fn = f
    out = fn(img, d, t)
    img = out or img
    d = ImageDraw.Draw(img)
    if fn is not sc_end: subtitle(d, t)
    return img


if __name__ == "__main__":
    rv = HERE / "review"; rv.mkdir(exist_ok=True)
    pts = [float(a) for a in sys.argv[1:]] or [5, 13, 20, 27, 40, 49, 61, 69, 75]
    for x in pts:
        render(x).save(rv / f"f_{x:05.1f}.jpg", quality=82)
    print("ok", DUR, "sarah at", SARAH_AT)
