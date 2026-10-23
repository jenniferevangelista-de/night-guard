"""Snoozy / Soneca: Gemmy's cousin, a sloth dressed as a night watchman. He narrates the film.

Drawn with the same ink + paper language as the stick figures, with Gemmy's family traits: big glossy eyes
and the cyan gem (on his cap). The mouth follows the narration loudness; he blinks slowly and yawns at the end.
  python video/ng_sloth.py   -> video/review_en/sloth_sheet.png
"""
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "codegames" / "historias" / "the_expired_code"))
from palito import INK, dr, font, jit, wcircle, wline, wrect  # noqa: E402

FUR = (152, 116, 84); FUR_D = (112, 82, 58); MASK = (236, 214, 178); PATCH = (88, 60, 42)
NAVY = (38, 50, 108); NAVY_D = (26, 34, 78); GEM = (60, 200, 235); GOLD = (255, 211, 110); WHITE = (255, 255, 255)


def sloth(img, t, cx, by, h=420, m=0.0, mood="talk", wave=0.0, seed=7000):
    """Draw Snoozy with his feet at (cx, by) and total height h.
    m: mouth open 0..1 · mood: talk | listen | sleep | yawn · wave: 0..1 how much the right arm waves."""
    s = h / 430.0
    d = ImageDraw.Draw(img)
    X = lambda u: cx + u * s
    Y = lambda v: by - v * s
    w = max(3, int(6 * s))
    sway = math.sin(dr(t) / 12 * 1.6) * 3 * s                       # slow, lazy sway on twos

    # legs and feet
    for sx in (-1, 1):
        d.ellipse((X(sx * 40 - 28), Y(40), X(sx * 40 + 28), Y(0)), fill=FUR, outline=INK, width=w)
    # body: navy uniform with a moon badge and a belt
    body = [(X(-80), Y(230)), (X(80), Y(230)), (X(92), Y(60)), (X(70), Y(30)), (X(-70), Y(30)), (X(-92), Y(60))]
    d.polygon([jit(p, t, seed + i, 1.6 * s) for i, p in enumerate(body)], fill=NAVY)
    wline(d, body + [body[0]], t, seed + 10, w)
    wline(d, [(X(-88), Y(85)), (X(88), Y(85))], t, seed + 11, w, GOLD)
    bx, bdy = X(-38), Y(175)
    d.ellipse((bx - 20 * s, bdy - 20 * s, bx + 20 * s, bdy + 20 * s), fill=GOLD, outline=INK, width=max(2, w // 2))
    d.ellipse((bx - 4 * s, bdy - 22 * s, bx + 26 * s, bdy + 12 * s), fill=NAVY)   # crescent cut
    # left arm: long and relaxed, holding a flashlight
    sh_l = (X(-78), Y(210)); el_l = (X(-112), Y(130)); ha_l = (X(-96), Y(70))
    wline(d, [sh_l, el_l, ha_l], t, seed + 20, int(26 * s), FUR)
    wrect(d, ha_l[0] - 14 * s, ha_l[1] - 40 * s, ha_l[0] + 14 * s, ha_l[1] + 10 * s, t, seed + 21, max(2, w // 2), fill=(90, 90, 100))
    d.polygon([(ha_l[0] - 14 * s, ha_l[1] + 10 * s), (ha_l[0] + 14 * s, ha_l[1] + 10 * s), (ha_l[0] + 34 * s, ha_l[1] + 60 * s),
               (ha_l[0] - 34 * s, ha_l[1] + 60 * s)], fill=(255, 240, 170))
    # right arm: waves slowly when greeting
    # angles in degrees, screen coords (90 = straight down, -90 = straight up)
    a1 = math.radians(80 - 105 * wave)                                   # upper arm: hanging -> raised
    a2 = math.radians(80 - 165 * wave + 22 * wave * math.sin(dr(t) / 12 * 5))   # forearm waves slowly
    sh_r = (X(78), Y(210))
    el_r = (sh_r[0] + 75 * s * math.cos(a1), sh_r[1] + 75 * s * math.sin(a1))
    ha_r = (el_r[0] + 72 * s * math.cos(a2), el_r[1] + 72 * s * math.sin(a2))
    ang = a2
    wline(d, [sh_r, el_r, ha_r], t, seed + 30, int(26 * s), FUR)
    for k in (-1, 0, 1):                                              # sloth claws
        a2 = ang + k * 0.35
        wline(d, [ha_r, (ha_r[0] + 22 * s * math.cos(a2), ha_r[1] + 22 * s * math.sin(a2))], t, seed + 31 + k, max(2, w // 2), (240, 230, 210))

    # head
    hx, hy, hr = X(0) + sway, Y(310), 100 * s
    wcircle(d, hx, hy, hr, t, seed + 40, w, fill=FUR)
    d.ellipse((hx - 80 * s, hy - 52 * s, hx + 80 * s, hy + 66 * s), fill=MASK)
    for sx in (-1, 1):                                                # droopy eye patches + Gemmy-style eyes
        ex, ey = hx + sx * 38 * s, hy + 2 * s
        rot = math.radians(sx * 28)                                   # teardrop patch drooping outward
        pts = []
        for k in range(24):
            th = 2 * math.pi * k / 24
            rx, ry = 30 * s, 20 * s * (1.25 if math.sin(th) > 0 else 1.0)
            px, py = rx * math.cos(th), ry * math.sin(th)
            pts.append((ex + sx * 4 * s + px * math.cos(rot) - py * math.sin(rot), ey + 4 * s + px * math.sin(rot) + py * math.cos(rot)))
        d.polygon(pts, fill=PATCH)
        if mood == "sleep" or (mood != "yawn" and (t % 4.1) < 0.18):
            d.arc((ex - 15 * s, ey - 6 * s, ex + 15 * s, ey + 14 * s), 20, 160, fill=WHITE, width=max(2, int(5 * s)))
        else:
            d.ellipse((ex - 15 * s, ey - 13 * s, ex + 15 * s, ey + 17 * s), fill=INK)
            d.ellipse((ex - 9 * s, ey - 9 * s, ex - 1 * s, ey - 1 * s), fill=WHITE)
            d.chord((ex - 17 * s, ey - 16 * s, ex + 17 * s, ey + 8 * s), 180, 360, fill=PATCH)   # lazy half-closed lids
    d.ellipse((hx - 14 * s, hy + 22 * s, hx + 14 * s, hy + 38 * s), fill=INK)                      # nose
    my = hy + 46 * s
    if mood == "yawn":
        d.ellipse((hx - 22 * s, my - 4 * s, hx + 22 * s, my + 44 * s), fill=INK)
    elif m > 0.06:
        o = 0.35 + 0.65 * min(1.0, m)
        d.chord((hx - 24 * s, my - 6 * s, hx + 24 * s, my + 34 * s * o + 6 * s), 0, 180, fill=INK)
        d.chord((hx - 12 * s, my + 8 * s * o, hx + 12 * s, my + 30 * s * o + 6 * s), 0, 180, fill=(232, 110, 120))
    else:
        d.arc((hx - 22 * s, my - 14 * s, hx + 22 * s, my + 12 * s), 20, 160, fill=INK, width=max(2, int(5 * s)))
    # watchman cap with Gemmy's cyan gem
    cap = [(hx - 92 * s, hy - 54 * s), (hx - 78 * s, hy - 112 * s), (hx, hy - 136 * s), (hx + 78 * s, hy - 112 * s), (hx + 92 * s, hy - 54 * s)]
    d.polygon([jit(p, t, seed + 60 + i, 1.4 * s) for i, p in enumerate(cap)], fill=NAVY)
    wline(d, cap + [cap[0]], t, seed + 61, w)
    d.polygon([(hx - 104 * s, hy - 56 * s), (hx + 112 * s, hy - 60 * s), (hx + 128 * s, hy - 40 * s), (hx - 96 * s, hy - 38 * s)], fill=NAVY_D)
    wline(d, [(hx - 104 * s, hy - 56 * s), (hx + 112 * s, hy - 60 * s), (hx + 128 * s, hy - 40 * s), (hx - 96 * s, hy - 38 * s), (hx - 104 * s, hy - 56 * s)], t, seed + 62, max(2, w - 1))
    gx, gy, gs = hx, hy - 96 * s, 20 * s
    d.polygon([(gx, gy - gs), (gx + gs * 0.75, gy), (gx, gy + gs), (gx - gs * 0.75, gy)], fill=GEM, outline=INK)
    if mood == "sleep":
        r = random.Random(3)
        for i in range(3):
            zt = (t * 0.6 + i * 0.33) % 1
            d.text((hx + 110 * s + zt * 60 * s, hy - 120 * s - zt * 120 * s), "z", fill=NAVY, font=font("impact.ttf", int((30 + 24 * zt) * s * 1.6)), anchor="mm")


def kid_in_bed(d, t, label=None, label_font=None):
    """A kid asleep under a blanket: whole body, not just the head."""
    wrect(d, 140, 650, 780, 760, t, 1900, 8, fill=(244, 244, 250))            # mattress
    wline(d, [(140, 760), (140, 900)], t, 1901, 8); wline(d, [(780, 760), (780, 900)], t, 1902, 8)
    wline(d, [(140, 560), (140, 760)], t, 1909, 8)                              # headboard
    wrect(d, 160, 600, 320, 652, t, 1903, 6, fill=WHITE)                        # pillow
    wline(d, [(300, 610), (470, 622), (640, 628)], t, 1905, 8)                  # torso and legs under the blanket
    wline(d, [(640, 628), (700, 612)], t, 1906, 7); wline(d, [(640, 628), (705, 632)], t, 1907, 7)   # feet
    blanket = [(320, 596), (430, 588), (560, 600), (690, 606), (705, 652), (318, 652)]
    d.polygon([jit(p, t, 1910 + i, 2) for i, p in enumerate(blanket)], fill=(170, 195, 245))
    wline(d, blanket + [blanket[0]], t, 1911, 6)
    for i in range(4):                                                          # little stars on the blanket
        sx = 380 + i * 80; d.ellipse((sx - 5, 620 - 5, sx + 5, 620 + 5), fill=(255, 211, 110))
    wline(d, [(330, 612), (400, 600), (470, 610)], t, 1912, 7)                  # arm resting on top
    wcircle(d, 255, 588, 50, t, 1904, 7, fill=(247, 242, 230))                   # head on the pillow
    d.arc((218, 576, 248, 596), 20, 160, fill=INK, width=5); d.arc((262, 576, 292, 596), 20, 160, fill=INK, width=5)
    d.arc((236, 598, 276, 620), 20, 160, fill=INK, width=5)


if __name__ == "__main__":
    from palito import paper
    img = paper().copy()
    for i, (mood, m, wv) in enumerate([("talk", 0.0, 0.0), ("talk", 0.9, 0.0), ("talk", 0.4, 1.0), ("listen", 0, 0), ("yawn", 0, 0), ("sleep", 0, 0)]):
        sloth(img, i * 0.3, 170 + i * 320, 900, 420, m, mood, wv)
    kid_in_bed(ImageDraw.Draw(img), 0.0)
    out = HERE / "review_en"; out.mkdir(exist_ok=True)
    img.save(out / "sloth_sheet.png"); print("ok")
