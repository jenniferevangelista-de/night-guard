"""Night Guard film, Portuguese version (paper style). Drama at the start, joy once the guard arrives.

  python video/ng_film_pt.py 5 20 40      -> review frames in video/review_pt/
  python video/ng_audio_pt.py && python video/ng_render_pt.py   -> video/night_guard_filme_pt.mp4
"""
import json
import math
import random
import sys
import textwrap
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ng_film import (GREEN, MOON, NIGHT, ROOT, SOFT, WHITE, bubble, card, check, desk_set, moon_window,  # noqa: E402
                     phone, rms_env, shield, speaker, stamp)
from palito import FPS, H, INK, RED, W, dr, eio, eout, font, jit, paper, poof, seg, stick, text, wcircle, wline, wrect  # noqa: E402
from guard.signals import SIGNALS  # noqa: E402

ALERT_EXTRA = 1.6   # room for the 11.4 s spoken warning
SARAH_FILE = ROOT / "web" / "audio" / "pt" / "secrecy.mp3"
PANEL = (29, 37, 80); PANEL2 = (40, 52, 110)


@lru_cache(maxsize=1)
def timeline():
    tl = json.loads((HERE / "timeline_pt.json").read_text(encoding="utf-8"))
    out, shift = {}, 0.0
    for s in tl["scenes"]:
        s = dict(s); s["start"] += shift
        if s["id"] == "alert":
            s["end"] += ALERT_EXTRA; shift = ALERT_EXTRA
        else:
            s["end"] += shift
        out[s["id"]] = s
    return out


def S(sid): return timeline()[sid]


DUR = round(S("end")["end"] + 0.6, 2)
SARAH_AT = round(S("alert")["start"] + S("alert")["voice_dur"] + 0.2, 2)
MUSIC_SWITCH = S("guard")["start"]           # drama -> joy when Night Guard appears


def level(path, t0, t):
    e = rms_env(str(path)); k = int((t - t0) * 12)
    return e[k] if 0 <= k < len(e) else 0.0


@lru_cache(maxsize=1)
def subs():
    out = []
    for s in timeline().values():
        parts = [p.strip() for p in s["line"].replace(": ", ":|").replace(". ", ".|").split("|") if p.strip()]
        merged, cur = [], ""
        for p in parts:
            if cur and len(cur) + len(p) > 68: merged.append(cur); cur = p
            else: cur = (cur + " " + p).strip()
        merged.append(cur)
        final = []
        for p in merged:                                   # very long sentences: split at commas
            while len(p) > 80 and ", " in p[20:]:
                i = p.rfind(", ", 0, 75); i = i if i > 20 else p.find(", ", 20)
                final.append(p[:i + 1]); p = p[i + 2:]
            final.append(p)
        total = sum(len(p) for p in final); t = s["start"]
        for p in final:
            d = s["voice_dur"] * len(p) / total; out.append((t, t + d + 0.2, p)); t += d
    return out


def subtitle(d, t):
    for a, b, s in subs():
        if a <= t < b:
            f = font("segoeprb.ttf", 40); w = d.textlength(s, font=f)
            d.rounded_rectangle((W / 2 - w / 2 - 24, 1002, W / 2 + w / 2 + 24, 1062), 18, fill=(255, 251, 240))
            text(d, s, W / 2, 1031, 40, INK); return


def dark_overlay(img, k):
    """Drama grade for the first act: darker, colder paper that lifts when the guard arrives."""
    if k <= 0: return img
    shade = Image.new("RGB", img.size, (20, 24, 48))
    return Image.blend(img, shade, 0.28 * k)


def pill(d, t, x, y, label, col, seed, w=300):
    wrect(d, x, y, x + w, y + 90, t, seed, 7, fill=(255, 252, 242))
    d.rectangle((x + 8, y + 8, x + 26, y + 82), fill=col)
    text(d, label, x + w / 2 + 10, y + 45, 46, col, "mm", "impact.ttf")


def padlock(d, t, cx, cy, s=1.0, col=INK, seed=2000):
    d.arc((cx - 40 * s, cy - 95 * s, cx + 40 * s, cy - 5 * s), 180, 360, fill=col, width=int(12 * s))
    wline(d, [(cx - 40 * s, cy - 50 * s), (cx - 40 * s, cy - 20 * s)], t, seed, int(10 * s), col)
    wline(d, [(cx + 40 * s, cy - 50 * s), (cx + 40 * s, cy - 20 * s)], t, seed + 1, int(10 * s), col)
    wrect(d, cx - 65 * s, cy - 25 * s, cx + 65 * s, cy + 70 * s, t, seed + 2, int(8 * s), fill=MOON)
    d.ellipse((cx - 10 * s, cy + 10 * s, cx + 10 * s, cy + 30 * s), fill=col)


def eye(d, t, cx, cy, crossed, seed):
    d.ellipse((cx - 34, cy - 18, cx + 34, cy + 18), outline=INK, width=5); d.ellipse((cx - 9, cy - 9, cx + 9, cy + 9), fill=INK)
    if crossed: wline(d, [(cx - 40, cy + 28), (cx + 40, cy - 28)], t, seed, 6, RED)


def medal(d, t, cx, cy, k, seed):
    if k <= 0: return
    s = eout(k)
    wline(d, [(cx - 14, cy - 60 * s), (cx, cy - 20 * s)], t, seed, 6, RED); wline(d, [(cx + 14, cy - 60 * s), (cx, cy - 20 * s)], t, seed + 1, 6, NIGHT)
    wcircle(d, cx, cy, 30 * s, t, seed + 2, 5, fill=MOON)
    if k > 0.8: text(d, "★", cx, cy, 30, INK, "mm", "seguisym.ttf")


# ------------------------------------------------------------------ scenes
def sc_night(img, d, t):
    moon_window(d, t)
    desk_set(d, t, 1.0)
    typing = math.sin(t * 30) * 7
    stick(d, t, (720, 800), 1.0, lean=10, armL=(30 + typing, -10), armR=(20 - typing, -20), legL=(170, 100), legR=(160, 95),
          mood="happy", look=0.6, seed=1)
    msgs = [(2.2, "você joga MUITO bem"), (3.8, "melhor jogador que já vi"), (5.6, "você é bem maduro pra sua idade"),
            (7.4, "quer gemas grátis? só entre nós")]
    for i, (t0, s) in enumerate(msgs):
        bubble(d, t, 1220 - i * 20, 150 + i * 150, s, 800 + i * 10, seg(t, t0, t0 + 0.35), size=38)
    text(d, "23:04", 345, 520, 48, INK)


def sc_stat(img, d, t):
    a = S("stat")["start"]
    k = eio(seg(t, a + 0.8, a + 7.0)); n = int(50000 * k)
    text(d, f"{n:,}".replace(",", ".") + ("+" if k >= 1 else ""), W / 2, 270, 230, RED, "mm", "impact.ttf")
    text(d, "denúncias de sextorsão em 2025", W / 2, 440, 58, INK)
    text(d, "(NCMEC, Estados Unidos)", W / 2, 505, 36, SOFT)
    pile = int(16 * k)
    for i in range(pile):
        y = 900 - i * 22
        wrect(d, 220 + (i % 2) * 18, y, 480 + (i % 2) * 18, y + 18, t, 900 + i, 4, fill=WHITE)
        wrect(d, 1440 - (i % 2) * 18, y, 1700 - (i % 2) * 18, y + 18, t, 950 + i, 4, fill=WHITE)
    if t > a + 8.6:
        k2 = eout(seg(t, a + 8.6, a + 9.0))
        wrect(d, 600, 600, 920, 880, t, 990, 8, fill=(255, 252, 242)); d.rectangle((608, 608, 912, 660), fill=RED)
        text(d, "POR DIA", 760, 634, 40, WHITE, "mm", "impact.ttf")
        text(d, "137", 760, 770, int(60 + 80 * k2), INK, "mm", "impact.ttf")
    if t > a + 11.4:                                                         # a clock: one every ~10 min
        cx, cy = 1200, 740; wcircle(d, cx, cy, 120, t, 995, 8, fill=(255, 252, 242))
        ang = -math.pi / 2 + (t - a - 11.4) * 2.2
        wline(d, [(cx, cy), (cx + 95 * math.cos(ang), cy + 95 * math.sin(ang))], t, 996, 7, RED)
        wline(d, [(cx, cy), (cx, cy - 60)], t, 997, 9)
        text(d, "1 a cada", 1420, 710, 44, INK, "lm"); text(d, "~10 min", 1420, 775, 60, RED, "lm", "impact.ttf")


def sc_fast(img, d, t):
    a = S("fast")["start"]
    cx, cy = W / 2, 470
    wcircle(d, cx, cy, 260, t, 1100, 10, fill=(255, 252, 242))
    wrect(d, cx - 40, cy - 310, cx + 40, cy - 270, t, 1101, 8, fill=INK)
    k = eio(seg(t, a + 0.5, a + 5.5))
    for i in range(12):
        an = i / 12 * 2 * math.pi - math.pi / 2
        wline(d, [(cx + 220 * math.cos(an), cy + 220 * math.sin(an)), (cx + 245 * math.cos(an), cy + 245 * math.sin(an))], t, 1110 + i, 5)
    pts = [(cx, cy)] + [(cx + 200 * math.cos(-math.pi / 2 + j / 30 * k * 2 * math.pi / 3),
                         cy + 200 * math.sin(-math.pi / 2 + j / 30 * k * 2 * math.pi / 3)) for j in range(31)]
    if k > 0.02: d.polygon(pts, fill=(255, 190, 190))
    an = -math.pi / 2 + k * 2 * math.pi / 3
    wline(d, [(cx, cy), (cx + 210 * math.cos(an), cy + 210 * math.sin(an))], t, 1150, 9, RED)
    text(d, f"{int(20 * k)} min", cx, cy + 90, 80, INK, "mm", "impact.ttf")
    text(d, "aliciamento dentro de um jogo", W / 2, 830, 54, INK)
    text(d, "pode levar de 20 a 45 minutos (Univ. de Swansea; WeProtect)", W / 2, 900, 34, SOFT)


def sc_platforms(img, d, t):
    a = S("platforms")["start"]
    apps = [("Roblox", RED), ("Discord", (88, 101, 242)), ("Minecraft", GREEN), ("TikTok", INK)]
    for i, (n, col) in enumerate(apps):
        t0 = a + 0.4 + i * 0.7
        if t < t0: continue
        x, y = 120 + (i % 2) * 520, 120 + (i // 2) * 300
        pill(d, t, x, y, n, col, 1200 + i * 10, 360)
        for j in range(7):                                                   # its own little fence
            fx = x - 10 + j * 64
            wline(d, [(fx, y + 150), (fx, y + 200)], t, 1250 + i * 10 + j, 5, SOFT)
        wline(d, [(x - 20, y + 165), (x + 390, y + 165)], t, 1290 + i, 5, SOFT)
        eye(d, t, x + 410, y + 45, False, 1300 + i)
    if t > a + 4.6: text(d, "cada uma vigia só o próprio quintal", 560, 760, 46, INK)
    if t > a + 8.6:                                                          # the jump to an encrypted app
        k = eout(seg(t, a + 8.6, a + 9.8))
        sx, sy, ex, ey = 520, 220, 1420, 420
        mx = sx + (ex - sx) * k; my = sy + (ey - sy) * k - 180 * math.sin(math.pi * k)
        pts = [(sx + (mx - sx) * j / 12, sy + (my - sy) * j / 12 - 180 * math.sin(math.pi * k * j / 12) * (1 - j / 12)) for j in range(13)]
        wline(d, pts, t, 1350, 8, RED)
        padlock(d, t, 1500, 420, 1.6)
        text(d, "app criptografado", 1500, 620, 50, INK)
        if t > a + 11.2:
            eye(d, t, 1500, 710, True, 1360)
            text(d, "ninguém mais vê", 1500, 790, 50, RED)


def sc_parents(img, d, t):
    a = S("parents")["start"]
    r = random.Random(12)
    for i in range(40):
        x = r.uniform(60, 1000); sp = r.uniform(250, 420); y = -80 + (t - a - r.uniform(0, 2.4)) * sp
        if -80 < y < 900:
            wrect(d, x, y, x + 150, y + 56, t, 1000 + i, 4, fill=WHITE)
            wline(d, [(x + 18, y + 22), (x + 130, y + 22)], t, 1100 + i, 4, SOFT); wline(d, [(x + 18, y + 38), (x + 90, y + 38)], t, 1200 + i, 4, SOFT)
    stick(d, t, (520, 780), 1.15, lean=-6, armL=(150, 200), armR=(30, -60), legL=(105, 90), legR=(75, 90), mood="sad", look=-0.4, seed=40)
    text(d, "?", 640, 330 + math.sin(t * 6) * 8, 120, RED, "mm", "impact.ttf")
    stick(d, t, (1450, 820), 0.85, armL=(200, 240), armR=(-40, -80), legL=(105, 90), legR=(75, 90), mood="happy", look=-0.6, seed=60)
    bubble(d, t, 1210, 330, "presente grátis pra você!", 1300, seg(t, a + 2.6, a + 3.0), size=38)
    if t > a + 4.0:
        hx, hy = 1520, 470
        wline(d, [(hx, 430), (hx, hy + 30)], t, 1310, 5)
        d.arc((hx - 34, hy, hx + 6, hy + 60), 0, 200, fill=RED, width=7)
        text(d, "a armadilha", hx + 130, hy + 40, 38, RED)


def sc_guard(img, d, t):
    a = S("guard")["start"]
    k = seg(t, a + 0.2, a + 1.4)
    shield(d, t, 520, 380, 1.2, k if k < 1 else 1.0)
    poof(d, t, 520, 380, seg(t, a + 1.3, a + 2.0))
    if t > a + 1.4:
        z = eout(seg(t, a + 1.4, a + 1.9))
        text(d, "NIGHT GUARD", 520, 650, int(40 + 70 * z), NIGHT, "mm", "impact.ttf")
    if t > a + 3.0:                                                          # the family's own computer
        x, y = 900, 160
        wrect(d, x, y, x + 300, y + 180, t, 1400, 7, fill=(225, 238, 255))
        wline(d, [(x - 30, y + 200), (x + 330, y + 200)], t, 1401, 8)
        wline(d, [(x + 90, y + 130), (x + 150, y + 60), (x + 210, y + 130)], t, 1402, 6)
        wrect(d, x + 115, y + 105, x + 185, y + 150, t, 1403, 5)
        text(d, "roda no computador", x + 360, y + 70, 40, INK, "lm"); text(d, "da própria família", x + 360, y + 125, 40, INK, "lm")
    if t > a + 7.5:                                                          # reads the screen -> covers encrypted apps
        padlock(d, t, 1130, 600, 1.1)
        shield(d, t, 1250, 600, 0.45, 1.0, seed=560)
        text(d, "lê a tela: protege até", 1340, 570, 40, INK, "lm")
        text(d, "no app criptografado", 1340, 625, 40, GREEN, "lm")
    if t > a + 12.0:
        text(d, "a conversa nunca sai de casa", 1340, 760, 44, NIGHT, "lm", "impact.ttf")


def popup(d, t, x, y, k):
    """The child's warning, redrawn in the app's colors (Portuguese text from guard/signals.py)."""
    if k <= 0: return
    w, h = 720, 640; yy = y + (1 - eout(k)) * 80
    d.rounded_rectangle((x, yy, x + w, yy + h), 26, fill=PANEL, outline=(255, 122, 138), width=6)
    text(d, "🛑", x + 40, yy + 52, 40, RED, "mm", "seguiemj.ttf")
    text(d, "Pare! Isso pode ser perigoso", x + 80, yy + 52, 42, WHITE, "lm", "segoeuib.ttf")
    kid = SIGNALS["secrecy"]["kid"]["pt"]
    for i, ln in enumerate(textwrap.wrap(kid, 40)[:6]):
        text(d, ln, x + 36, yy + 120 + i * 44, 32, WHITE, "lm", "segoeui.ttf")
    text(d, '"não conta pros seus pais tá? eles não iam entender"', x + 36, yy + 400, 26, (166, 174, 214), "lm", "segoeuii.ttf")
    d.rounded_rectangle((x + 30, yy + 440, x + w - 30, yy + 510), 14, fill=(42, 47, 94), outline=MOON, width=2)
    text(d, "Sua família vai saber. Você não está encrencado.", x + 50, yy + 475, 25, WHITE, "lm", "segoeui.ttf")
    d.rounded_rectangle((x + 30, yy + 545, x + 200, yy + 610), 12, fill=MOON)
    text(d, "Entendi", x + 115, yy + 577, 32, (42, 32, 0), "mm", "segoeuib.ttf")
    d.rounded_rectangle((x + 220, yy + 545, x + 520, yy + 610), 12, outline=(80, 90, 150), width=3)
    text(d, "Contar pra alguém", x + 370, yy + 577, 30, WHITE, "mm", "segoeuib.ttf")


def game_chat(d, t, a):
    x, y = 90, 140
    d.rounded_rectangle((x, y, x + 760, y + 760), 24, fill=(70, 150, 80))
    for i in range(6): d.rectangle((x + 20 + i * 120, y + 20, x + 80 + i * 120, y + 740), fill=(80, 165, 90))
    d.rounded_rectangle((x + 330, y + 300, x + 480, y + 450), 6, fill=(160, 168, 172))
    d.rounded_rectangle((x + 60, y + 520, x + 720, y + 740), 18, fill=(28, 70, 50))
    msgs = [("Alex_17", "quantos anos vc tem? pais em casa?"), ("você", "11. tão no trabalho"),
            ("Alex_17", "não conta pros seus pais tá?")]
    for i, (who, s) in enumerate(msgs):
        if t > a + 0.6 + i * 1.6:
            text(d, f"{who}: {s}", x + 85, y + 560 + i * 60, 26, WHITE if who != "você" else MOON, "lm", "segoeui.ttf")


def sc_alert(img, d, t):
    a = S("alert")["start"]
    game_chat(d, t, a)
    popup(d, t, 1060, 150, seg(t, SARAH_AT - 0.8, SARAH_AT - 0.3))
    if t >= SARAH_AT - 0.3:
        speaker(d, t, 930, 470, level(SARAH_FILE, SARAH_AT, t))
        stamp(img, "PERIGO", 1660, 860, 6, RED, 74)
    return img


def sc_hero(img, d, t):
    a = S("hero")["start"]
    k = eio(seg(t, a + 0.6, a + 6.0))
    for i in range(14):                                                      # one medal per tactic learned
        medal(d, t, 160 + i * 115, 200, seg(t, a + 0.6 + i * 0.38, a + 0.9 + i * 0.38), 1700 + i * 5)
    x0, x1, y = 260, 1660, 330
    wrect(d, x0, y, x1, y + 44, t, 1790, 6, fill=WHITE)
    d.rectangle((x0 + 6, y + 6, x0 + 6 + (x1 - x0 - 12) * k, y + 38), fill=MOON)
    for i, r in enumerate(["Aprendiz", "Vigia", "Heroína da Noite"]):
        text(d, r, x0 + (x1 - x0) * i / 2, y + 90, 40, INK if k * 2 >= i else SOFT)
    hero = k >= 1
    hy = 860 - (abs(math.sin((t - a) * 5)) * 60 if hero else 0)
    if hero:
        d.polygon([jit(p, t, 1795 + i) for i, p in enumerate([(948, hy - 112), (972, hy - 112), (1055, hy + 30), (865, hy + 30)])], fill=RED)
        text(d, "HEROÍNA DA NOITE!", W / 2, 520, 76, RED, "mm", "impact.ttf")
    stick(d, t, (960, hy), 1.0, armL=(-130, -110) if hero else (200, 240), armR=(-50, -70) if hero else (-30, -60),
          legL=(110, 80), legR=(70, 100), mood="happy", seed=90)
    shield(d, t, 1550, 760, 0.6, 1.0, seed=520)
    text(d, "amigo", 1550, 900, 40, NIGHT)


def sc_family(img, d, t):
    a = S("family")["start"]
    stick(d, t, (330, 800), 1.15, armL=(110, -60), armR=(60, -100), legL=(105, 90), legR=(75, 90),
          mood="happy" if t > a + 3 else "normal", look=0.6, seed=110)
    shield(d, t, 330, 250, 0.55, 1.0, seed=580)
    text(d, "Guarda Noturno", 330, 400, 46, NIGHT, "mm", "impact.ttf")
    phone(d, t, 640, 120, seg(t, a + 2.0, a + 2.4), ["risco ALTO · Roblox", "segredo, pedido de foto"])
    steps = [(a + 6.6, "falar com calma"), (a + 7.8, "guardar prints"), (a + 9.0, "bloquear, denunciar")]
    text(d, "o que fazer agora", 670, 440, 40, NIGHT, "lm", "impact.ttf")
    for i, (t0, s) in enumerate(steps):
        if t > t0 - 0.3: check(d, t, 670, 520 + i * 80, seg(t, t0, t0 + 0.3), s, 1500 + i * 10)
    if t > a + 4.0:
        text(d, "um alerta só", 1500, 300, 60, RED, "mm", "impact.ttf")
        text(d, "sem a conversa inteira", 1500, 380, 44, INK)
        text(d, "SaferNet · Canal de denúncia", 1500, 470, 32, SOFT)


def sc_tech(img, d, t):
    s = S("tech"); a, v = s["start"], s["voice_dur"]
    cards = [(0.08, "GEMMA 4", "lê texto e tela", "no próprio computador", NIGHT),
             (0.27, "TINKER", "Qwen3-8B treinado", "70/70 no formato", RED),
             (0.55, "TEMPORAL", "aguenta queda", "nada se perde", GREEN),
             (0.66, "SENTRY", "acompanha cada checagem", "sem ler a conversa", (120, 70, 160)),
             (0.80, "ELEVENLABS", "voz nos avisos", "pra quem lê devagar", (200, 120, 30)),
             (0.91, "RENDER", "demonstração online", "um clique", (40, 110, 160))]
    for i, (f, ti, l1, l2, col) in enumerate(cards):
        t0 = a + f * v
        x = 70 + (i % 3) * 600; y = 70 + (i // 3) * 420
        card_small(d, t, x, y, seg(t, t0, t0 + 0.4), ti, l1, l2, col, 1600 + i * 20)
    if t > a + v - 0.5:
        stamp(img, "TECNOLOGIA ABERTA", W / 2, 470, -4, RED, 80)


def card_small(d, t, x, y, k, title, l1, l2, col, seed):
    if k <= 0: return
    s = eout(k); w, h = 560 * s, 330 * s; cx, cy = x + 280, y + 165
    wrect(d, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, t, seed, 7, fill=(255, 252, 242))
    if k > 0.7:
        d.rectangle((cx - w / 2 + 8, cy - h / 2 + 8, cx + w / 2 - 8, cy - h / 2 + 22), fill=col)
        text(d, title, cx, cy - 70, 66, col, "mm", "impact.ttf")
        text(d, l1, cx, cy + 20, 38, INK); text(d, l2, cx, cy + 80, 34, SOFT)


def sc_results(img, d, t):
    a = S("results")["start"]
    stats = [("36/36", "conversas de risco detectadas"), ("~4 s", "por checagem, no notebook"),
             ("70/70", "respostas no formato certo"), ("28", "testes automáticos")]
    for i, (big, small) in enumerate(stats):
        t0 = a + 0.4 + i * 1.3
        if t < t0: continue
        z = eout(seg(t, t0, t0 + 0.4)); x = 480 + (i % 2) * 960; y = 250 + (i // 2) * 360
        text(d, big, x, y, int(60 + 90 * z), RED if i == 0 else NIGHT, "mm", "impact.ttf")
        text(d, small, x, y + 110, 40, INK)
    text(d, "em 70 conversas de teste fictícias", W / 2, 940, 32, SOFT)


def sc_peace(img, d, t):
    a = S("peace")["start"]
    # left: the kid sleeping safe
    wrect(d, 140, 640, 760, 760, t, 1900, 8, fill=(200, 215, 245))
    wline(d, [(140, 760), (140, 900)], t, 1901, 8); wline(d, [(760, 760), (760, 900)], t, 1902, 8)
    wrect(d, 160, 590, 330, 650, t, 1903, 6, fill=WHITE)
    wcircle(d, 260, 580, 52, t, 1904, 7, fill=(247, 242, 230))
    d.arc((222, 570, 252, 590), 20, 160, fill=INK, width=5); d.arc((268, 570, 298, 590), 20, 160, fill=INK, width=5)
    d.arc((240, 590, 280, 615), 20, 160, fill=INK, width=5)
    for i in range(3):
        zt = (t * 0.7 + i * 0.33) % 1
        text(d, "z", 360 + zt * 80, 520 - zt * 140, int(36 + 26 * zt), NIGHT, "mm", "impact.ttf")
    text(d, "paz pra criança", 450, 960 - 40, 50, NIGHT)
    # right: parents relaxed on the sofa
    if t > a + 2.0:
        wrect(d, 1100, 700, 1760, 820, t, 1950, 8, fill=(240, 200, 170))
        wrect(d, 1100, 600, 1760, 700, t, 1951, 8, fill=(250, 215, 185))
        stick(d, t, (1320, 700), 0.85, armL=(160, 200), armR=(30, -40), legL=(20, 90), legR=(10, 90), mood="happy", seed=130)
        stick(d, t, (1540, 700), 0.85, armL=(150, 170), armR=(20, -60), legL=(20, 90), legR=(10, 90), mood="happy", seed=140)
        for i in range(3):
            ht = (t * 0.6 + i * 0.33) % 1
            text(d, "♥", 1430 + (i - 1) * 60, 380 - ht * 120, int(40 + 20 * ht), RED, "mm", "seguisym.ttf")
        text(d, "paz pros pais", 1430, 920, 50, NIGHT)
    if t > a + 5.0:
        shield(d, t, W / 2, 330, 0.55, 1.0, "sleep", seed=600)
        text(d, "o guarda descansa", W / 2, 470, 38, INK)


def sc_end(img, d, t):
    a = S("end")["start"]
    shield(d, t, W / 2, 280, 0.9, 1.0)
    z = eout(seg(t, a, a + 0.5))
    text(d, "Night Guard", W / 2, 540, int(60 + 80 * z), NIGHT, "mm", "impact.ttf")
    if t > a + 1.0: text(d, "parceiro dos pais · amigo das crianças", W / 2, 650, 52, INK)
    if t > a + 2.4: text(d, "night-guard-demo.onrender.com", W / 2, 750, 50, RED)
    if t > a + 3.0: text(d, "Gemma · Tinker · Render · Temporal · ElevenLabs · Sentry", W / 2, 840, 34, SOFT)
    text(d, 'Música: "Funkorama", Kevin MacLeod (incompetech.com), CC BY 4.0 · trilha de abertura original', W / 2, 1050, 22, SOFT)


ORDER = [("night", sc_night), ("stat", sc_stat), ("fast", sc_fast), ("platforms", sc_platforms), ("parents", sc_parents),
         ("guard", sc_guard), ("alert", sc_alert), ("hero", sc_hero), ("family", sc_family), ("tech", sc_tech),
         ("results", sc_results), ("peace", sc_peace), ("end", sc_end)]


def render(t):
    img = paper().copy(); d = ImageDraw.Draw(img)
    fn = ORDER[0][1]
    for sid, f in ORDER:
        if t >= (S(sid)["start"] if sid != "night" else 0): fn = f
    img = fn(img, d, t) or img
    img = dark_overlay(img, 1 - seg(t, MUSIC_SWITCH, MUSIC_SWITCH + 1.5))
    if fn is not sc_end: subtitle(ImageDraw.Draw(img), t)
    if t < 1.0: img = Image.blend(Image.new("RGB", img.size, (0, 0, 0)), img, t)    # fade in from black
    return img


if __name__ == "__main__":
    rv = HERE / "review_pt"; rv.mkdir(exist_ok=True)
    pts = [float(a) for a in sys.argv[1:]] or [8, 22, 31, 47, 56, 72, 85, 99, 112, 137, 145, 155, 162]
    for x in pts:
        render(x).save(rv / f"f_{x:05.1f}.jpg", quality=82)
    print("ok", DUR, "sarah at", SARAH_AT, "switch", MUSIC_SWITCH)
