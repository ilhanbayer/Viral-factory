"""Hikâye (belgesel / gizem dosyası) motoru.

Koyu, vinyetli arka plan üzerinde 2D kinetik infografik sahneler:
dosya kartı + daktilo + damga, çetele, büyük rakam, siluetler, yer işareti, tarih,
gazete kupürü, teori listesi, ikonlar. Kelime kelime birikerek beliren altyazı.

Senaryo biçimi (topics/queue/*.json, "format": "story"):
{
 "id": "...", "format": "story", "brand": "GİZEM DOSYASI", "theme": {...isteğe bağlı...},
 "long":  {"title": "...", "beats": [BEAT, ...]},
 "shorts": [{"title": "...", "hook": [BEAT...], "from": 3, "to": 14, "outro": [BEAT...]}, ...],
 "publish": {"long": {...}, "shorts": [{...}, ...]}
}
BEAT = {"say": "Anlatım metni, *vurgulu* kelimeler yıldızlı", "show": {"type": "dossier", ...},
        "sfx": "riser|hit|none" (isteğe bağlı)}
"""
import math
import os

import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")
_ROBOTO = os.path.join(FONT_DIR, "Roboto-Variable.ttf")
_MONO = os.path.join(FONT_DIR, "DejaVuSansMono-Bold.ttf")
_SYM = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")

THEMES = {
    "dosya": dict(bg=(13, 13, 16), glow=(70, 50, 30), red=(214, 38, 38), orange=(240, 160, 58),
                  paper=(226, 213, 180), ink=(38, 34, 28), text=(236, 232, 224)),
    "soguk": dict(bg=(9, 13, 20), glow=(30, 55, 85), red=(222, 45, 55), orange=(90, 190, 255),
                  paper=(214, 220, 226), ink=(28, 32, 40), text=(230, 236, 244)),
    "kan": dict(bg=(14, 8, 9), glow=(90, 20, 20), red=(235, 35, 35), orange=(255, 196, 70),
                paper=(222, 206, 176), ink=(40, 30, 26), text=(240, 230, 226)),
    "zehir": dict(bg=(9, 14, 11), glow=(40, 75, 40), red=(225, 50, 45), orange=(170, 235, 80),
                  paper=(220, 222, 196), ink=(30, 36, 28), text=(232, 240, 228)),
}
C = dict(THEMES["dosya"])


def set_theme(name_or_dict):
    C.clear()
    if isinstance(name_or_dict, dict):
        C.update(THEMES["dosya"])
        C.update({k: tuple(v) if isinstance(v, list) else v for k, v in name_or_dict.items()})
    else:
        C.update(THEMES.get(name_or_dict, THEMES["dosya"]))


_fc = {}


def F(size, weight=700, width=75):
    key = ("r", int(size), weight, width)
    if key not in _fc:
        f = ImageFont.truetype(_ROBOTO, int(size))
        try:
            f.set_variation_by_axes([weight, width])
        except Exception:
            pass
        _fc[key] = f
    return _fc[key]


def M(size):
    key = ("m", int(size))
    if key not in _fc:
        _fc[key] = ImageFont.truetype(_MONO, int(size))
    return _fc[key]


def S(size):
    key = ("s", int(size))
    if key not in _fc:
        _fc[key] = ImageFont.truetype(_SYM, int(size))
    return _fc[key]


def up(s):
    return s.replace("i", "İ").replace("ı", "I").upper()


def cl(x):
    return max(0.0, min(1.0, x))


def eo(x):
    x = cl(x)
    return 1 - (1 - x) ** 3


def eb(x, s=1.7):
    x = cl(x)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def A(col, a):
    return tuple(col[:3]) + (int(max(0, min(255, a))),)


def spaced(d, xy, text, font, fill, spacing, anchor="m"):
    """Harf aralıklı yazı (ör. 'Y A Ş I N D A')."""
    widths = [font.getlength(ch) for ch in text]
    total = sum(widths) + spacing * (len(text) - 1)
    x, y = xy
    if anchor == "m":
        x -= total / 2
    for ch, w in zip(text, widths):
        d.text((x, y), ch, font=font, fill=fill, anchor="lm")
        x += w + spacing


# ============================================================ silhouettes & icons
def person(d, x, y, h, col):
    """Basit insan silueti; (x, y) ayak ortası."""
    hr = h * 0.105
    d.ellipse((x - hr, y - h, x + hr, y - h + 2 * hr), fill=col)
    bw = h * 0.16
    d.rounded_rectangle((x - bw, y - h + 2.25 * hr, x + bw, y - h * 0.42), radius=int(bw * 0.8), fill=col)
    lw = h * 0.065
    d.rounded_rectangle((x - bw * 0.9, y - h * 0.48, x - bw * 0.9 + 2 * lw, y), radius=int(lw), fill=col)
    d.rounded_rectangle((x + bw * 0.9 - 2 * lw, y - h * 0.48, x + bw * 0.9, y), radius=int(lw), fill=col)


def icon(d, name, cx, cy, s, t, col, red):
    """Prosedürel ikonlar. s: ikon boyutu (px)."""
    if name == "tent":
        p = [(cx - s * 0.55, cy + s * 0.35), (cx, cy - s * 0.4), (cx + s * 0.55, cy + s * 0.35)]
        d.polygon(p, fill=col)
        d.polygon([(cx - s * 0.12, cy + s * 0.35), (cx, cy + s * 0.02), (cx + s * 0.12, cy + s * 0.35)], fill=C["bg"])
        k = eo(t / 0.8)
        if k > 0:   # içeriden kesik
            x0, y0 = cx + s * 0.12, cy - s * 0.18
            x1, y1 = cx + s * 0.32, cy + s * 0.25
            d.line((x0, y0, x0 + (x1 - x0) * k, y0 + (y1 - y0) * k), fill=red, width=max(3, int(s * 0.03)))
        d.line((cx - s * 0.75, cy + s * 0.36, cx + s * 0.75, cy + s * 0.36), fill=col, width=max(2, int(s * 0.015)))
    elif name == "mountain":
        d.polygon([(cx - s * 0.7, cy + s * 0.4), (cx - s * 0.15, cy - s * 0.4), (cx + s * 0.35, cy + s * 0.4)], fill=col)
        d.polygon([(cx - s * 0.1, cy + s * 0.4), (cx + s * 0.3, cy - s * 0.15), (cx + s * 0.75, cy + s * 0.4)],
                  fill=tuple(int(v * 0.7) for v in col[:3]))
        d.polygon([(cx - s * 0.15, cy - s * 0.4), (cx - s * 0.27, cy - s * 0.22), (cx - s * 0.03, cy - s * 0.22)],
                  fill=(250, 250, 250))
    elif name == "footprints":
        n = 7
        for i in range(n):
            k = cl(t * 4 - i * 0.5)
            if k <= 0:
                continue
            fx = cx - s * 0.5 + i * s * 0.17
            fy = cy + s * 0.35 - i * s * 0.12 + (s * 0.06 if i % 2 else -s * 0.06)
            a = int(255 * k)
            d.ellipse((fx - s * 0.04, fy - s * 0.07, fx + s * 0.04, fy + s * 0.05), fill=A(col, a))
            d.ellipse((fx - s * 0.03, fy + s * 0.06, fx + s * 0.03, fy + s * 0.11), fill=A(col, a))
    elif name == "clock":
        r = s * 0.42
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=max(4, int(s * 0.035)))
        for i in range(12):
            a = i * math.pi / 6
            d.line((cx + math.sin(a) * r * 0.82, cy - math.cos(a) * r * 0.82, cx + math.sin(a) * r * 0.92,
                    cy - math.cos(a) * r * 0.92), fill=col, width=3)
        am = t * 2.5
        d.line((cx, cy, cx + math.sin(am) * r * 0.75, cy - math.cos(am) * r * 0.75), fill=red, width=max(3, int(s * 0.02)))
        d.line((cx, cy, cx + math.sin(am / 12) * r * 0.5, cy - math.cos(am / 12) * r * 0.5), fill=col,
               width=max(4, int(s * 0.03)))
        d.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), fill=red)
    elif name == "question":
        d.text((cx, cy), "?", font=F(s * 1.1, 900), fill=red, anchor="mm")
    elif name == "eye":
        w, h = s * 0.6, s * 0.28
        d.chord((cx - w, cy - h * 1.6, cx + w, cy + h * 1.6), 200, 340, fill=col)
        d.chord((cx - w, cy - h * 1.6, cx + w, cy + h * 1.6), 20, 160, fill=col)
        d.ellipse((cx - h * 0.8, cy - h * 0.8, cx + h * 0.8, cy + h * 0.8), fill=C["bg"])
        r = h * 0.45 * (0.8 + 0.2 * math.sin(t * 3))
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=red)
    elif name == "ufo":
        yy = cy + math.sin(t * 2) * s * 0.04
        d.ellipse((cx - s * 0.2, yy - s * 0.25, cx + s * 0.2, yy + s * 0.05), fill=(140, 160, 170))
        d.ellipse((cx - s * 0.6, yy - s * 0.08, cx + s * 0.6, yy + s * 0.12), fill=col)
        d.polygon([(cx - s * 0.18, yy + s * 0.1), (cx + s * 0.18, yy + s * 0.1), (cx + s * 0.4, yy + s * 0.75),
                   (cx - s * 0.4, yy + s * 0.75)], fill=A(C["orange"], 60))
    elif name == "snow" or name == "avalanche":
        d.polygon([(cx - s * 0.75, cy + s * 0.45), (cx + s * 0.75, cy - s * 0.35), (cx + s * 0.75, cy + s * 0.45)],
                  fill=(225, 230, 236))
        if name == "avalanche":
            for i in range(9):
                k = cl(t * 1.2 - i * 0.07)
                bx = cx + s * 0.55 - k * s * 0.9 + (i % 3) * s * 0.05
                by = cy - s * 0.25 + k * s * 0.55 + (i // 3) * s * 0.07
                d.rectangle((bx - s * 0.06, by - s * 0.04, bx + s * 0.06, by + s * 0.04), fill=(245, 248, 252))
    elif name == "thermometer":
        d.rounded_rectangle((cx - s * 0.07, cy - s * 0.5, cx + s * 0.07, cy + s * 0.25), radius=int(s * 0.07),
                            outline=col, width=max(4, int(s * 0.03)))
        d.ellipse((cx - s * 0.15, cy + s * 0.18, cx + s * 0.15, cy + s * 0.48), fill=(90, 170, 255))
        lv = 0.6 - 0.5 * eo(t / 1.2)
        d.rectangle((cx - s * 0.035, cy - s * 0.45 + (1 - lv) * s * 0.65, cx + s * 0.035, cy + s * 0.25),
                    fill=(90, 170, 255))
    elif name == "documents":
        for i in range(3):
            o = (2 - i) * s * 0.06
            d.rectangle((cx - s * 0.32 + o, cy - s * 0.42 + o, cx + s * 0.32 + o, cy + s * 0.42 + o),
                        fill=C["paper"], outline=(0, 0, 0))
        for j in range(6):
            d.rectangle((cx - s * 0.22, cy - s * 0.28 + j * s * 0.1, cx + s * (0.22 - 0.1 * (j % 2)),
                         cy - s * 0.24 + j * s * 0.1), fill=(0, 0, 0) if j % 3 else C["ink"])
    elif name == "radiation":
        r = s * 0.45
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=C["orange"])
        for k in range(3):
            a0 = k * 120 + t * 20
            d.pieslice((cx - r * 0.85, cy - r * 0.85, cx + r * 0.85, cy + r * 0.85), a0 - 30, a0 + 30, fill=(20, 20, 20))
        d.ellipse((cx - r * 0.25, cy - r * 0.25, cx + r * 0.25, cy + r * 0.25), fill=C["orange"])
        d.ellipse((cx - r * 0.15, cy - r * 0.15, cx + r * 0.15, cy + r * 0.15), fill=(20, 20, 20))
    elif name == "camera":
        d.rounded_rectangle((cx - s * 0.5, cy - s * 0.25, cx + s * 0.5, cy + s * 0.35), radius=int(s * 0.07), fill=col)
        d.rectangle((cx - s * 0.18, cy - s * 0.38, cx + s * 0.12, cy - s * 0.25), fill=col)
        d.ellipse((cx - s * 0.2, cy - s * 0.15, cx + s * 0.2, cy + s * 0.25), fill=C["bg"])
        d.ellipse((cx - s * 0.12, cy - s * 0.07, cx + s * 0.12, cy + s * 0.17), fill=col)
        if int(t * 3) % 3 == 0:
            d.ellipse((cx + s * 0.3, cy - s * 0.18, cx + s * 0.4, cy - s * 0.08), fill=red)
    else:   # bilinmeyen -> soru işareti
        d.text((cx, cy), "?", font=F(s, 900), fill=red, anchor="mm")


# ============================================================ visual templates
def draw_visual(img, show, t, dur, cx, cy, u):
    """img: PIL RGBA katman. u: ölçek (dikeyde 1)."""
    d = ImageDraw.Draw(img)
    typ = show.get("type", "title")
    red, org, txt = C["red"], C["orange"], C["text"]

    if typ == "photo":
        draw_photo(img, show, t, dur, cx, cy, u)
        return typ
    if typ == "tally":
        n = int(show.get("n", 5))
        k = n * eo(t / max(0.5, min(1.6, dur * 0.6)))
        mh = 190 * u
        gw = 135 * u
        groups = (n + 4) // 5
        total_w = groups * gw - 40 * u
        x0 = cx - total_w / 2
        drawn = 0
        for g in range(groups):
            gx = x0 + g * gw
            for i in range(5):
                if drawn >= n:
                    break
                a = cl(k - drawn)
                if a <= 0:
                    break
                col = red if (drawn == n - 1 and show.get("last_red", True)) else txt
                if i < 4:
                    x = gx + i * 24 * u
                    d.line((x, cy - mh / 2, x, cy - mh / 2 + mh * a), fill=col, width=int(11 * u))
                else:
                    d.line((gx - 14 * u, cy + mh * 0.28, gx - 14 * u + (100 * u) * a, cy + mh * 0.28 - mh * 0.62 * a),
                           fill=col, width=int(11 * u))
                drawn += 1
        if show.get("label"):
            d.text((cx, cy + mh * 0.85), up(show["label"]), font=F(66 * u), fill=red, anchor="mm")

    elif typ == "dossier":
        cw, ch = 760 * u, 1020 * u
        card = Image.new("RGBA", (int(cw), int(ch)), A(C["paper"], 255))
        cd = ImageDraw.Draw(card)
        rng = np.random.default_rng(7)
        # kâğıt dokusu ve lekeler (ayrı katmanda, yarı saydam)
        stain = Image.new("RGBA", card.size, (0, 0, 0, 0))
        sdr = ImageDraw.Draw(stain)
        for _ in range(26):
            x, y, r = rng.uniform(0, cw), rng.uniform(0, ch), rng.uniform(20, 120) * u
            sdr.ellipse((x - r, y - r, x + r, y + r), fill=(140, 115, 70, 22))
        stain = stain.filter(ImageFilter.GaussianBlur(14 * u))
        card.alpha_composite(stain)
        cd = ImageDraw.Draw(card)
        cd.text((40 * u, 46 * u), f"DOSYA NO: {show.get('no', '19██/██')}", font=M(26 * u), fill=C["ink"], anchor="lm")
        # fotoğraf
        px0, py0, pw, ph = 60 * u, 100 * u, 250 * u, 300 * u
        cd.rectangle((px0, py0, px0 + pw, py0 + ph), fill=(28, 28, 30))
        person(cd, px0 + pw / 2, py0 + ph + 40 * u, 320 * u, (8, 8, 9))
        cd.text((px0 + pw / 2, py0 + ph * 0.55), "?", font=F(150 * u, 900), fill=red, anchor="mm")
        # isim (daktilo)
        name = up(show.get("name", "BİLİNMİYOR"))
        nk = int(len(name) * cl((t - 0.15) / max(0.6, dur * 0.45)))
        cd.text((50 * u, 470 * u), name[:nk] + ("█" if nk < len(name) and int(t * 6) % 2 == 0 else ""),
                font=M(46 * u), fill=C["ink"], anchor="lm")
        y = 650 * u
        for i, (k_, v) in enumerate(show.get("fields", {"DOĞUM YERİ": "?", "DURUM": "██"}).items()):
            cd.text((50 * u, y), f"{up(k_)}: ", font=M(26 * u), fill=C["ink"], anchor="lm")
            fx = 50 * u + M(26 * u).getlength(f"{up(k_)}: ")
            if "█" in str(v):
                cd.rectangle((fx, y - 12 * u, fx + 180 * u, y + 12 * u), fill=C["ink"])
            else:
                cd.text((fx, y), up(str(v)), font=M(26 * u), fill=C["ink"], anchor="lm")
            y += 50 * u
        # damga
        st = show.get("stamp")
        sk = (t - dur * 0.55) / 0.18
        if st and sk > 0:
            sc = 1.8 - 0.8 * eo(sk)
            f = F(120 * u * sc, 900)
            tw = f.getlength(up(st))
            simg = Image.new("RGBA", (int(tw + 80 * u * sc), int(200 * u * sc)), (0, 0, 0, 0))
            sd = ImageDraw.Draw(simg)
            sd.rectangle((8, 8, simg.width - 8, simg.height - 8), outline=A(red, 235), width=int(10 * u * sc))
            sd.text((simg.width / 2, simg.height / 2), up(st), font=f, fill=A(red, 235), anchor="mm")
            simg = simg.rotate(12, expand=True, resample=Image.BICUBIC)
            card.alpha_composite(simg, (int(cw * 0.62 - simg.width / 2), int(230 * u - simg.height / 2)))
        rot = show.get("rot", -3) + 2 * (1 - eo(t / 0.4))
        card = card.rotate(rot, expand=True, resample=Image.BICUBIC)
        sh = Image.new("RGBA", card.size, (0, 0, 0, 0))
        sh.paste((0, 0, 0, 170), (0, 0), card.split()[3])
        sh = sh.filter(ImageFilter.GaussianBlur(20 * u))
        img.alpha_composite(sh, (int(cx - card.width / 2 + 18 * u), int(cy - card.height / 2 + 26 * u)))
        img.alpha_composite(card, (int(cx - card.width / 2), int(cy - card.height / 2)))

    elif typ == "number":
        val = show.get("value", 0)
        if isinstance(val, (int, float)):
            v = val * eo(t / 0.9)
            s = f"{int(round(v)):,}".replace(",", ".") if float(val).is_integer() else f"{v:.1f}".replace(".", ",")
        else:
            s = str(val)
        s = show.get("prefix", "") + s + show.get("suffix", "")
        f = F(min(420, 1400 / max(1, len(s))) * u, 800)
        ny = cy - (180 * u if show.get("figures") else 60 * u)
        d.text((cx, ny), s, font=f, fill=org, anchor="mm")
        if show.get("label"):
            spaced(d, (cx, ny + f.size * 0.62), up(show["label"]), F(40 * u, 600), A(txt, 200), 14 * u)
        figs = show.get("figures")
        if figs:
            n = len(figs)
            for i, fg in enumerate(figs):
                a = cl((t - 0.3 - i * 0.15) / 0.3)
                h = (300 if fg == "adult" else 200) * u
                x = cx + (i - (n - 1) / 2) * 120 * u
                person(d, x, cy + 520 * u, h, A((5, 5, 6) if fg != "red" else red, 255 * a))

    elif typ == "people":
        n = int(show.get("n", 9))
        hl = set(show.get("highlight", []))
        per_row = min(n, int(show.get("per_row", 5)))
        rows = (n + per_row - 1) // per_row
        h = 230 * u if rows == 1 else 190 * u
        for i in range(n):
            r, c = divmod(i, per_row)
            cnt = min(per_row, n - r * per_row)
            x = cx + (c - (cnt - 1) / 2) * 140 * u
            y = cy + h / 2 + (r - (rows - 1) / 2) * (h + 40 * u)
            a = cl((t - i * 0.08) / 0.25)
            gone = show.get("fade_out") and t > dur * 0.55 and i not in hl
            col = red if i in hl else txt
            br = 1 + 0.015 * math.sin(t * 3 + i)
            person(d, x, y, h * (0.85 + 0.15 * a) * br, A(col, 255 * a * (0.25 if gone else 1)))
        if show.get("label"):
            d.text((cx, cy + h + rows * 120 * u), up(show["label"]), font=F(60 * u), fill=red, anchor="mm")

    elif typ == "place":
        r0 = 22 * u
        for k in range(3):
            ph = (t * 0.8 + k / 3) % 1
            rr = r0 + 220 * u * ph
            d.ellipse((cx - rr, cy - rr * 0.45 + 40 * u, cx + rr, cy + rr * 0.45 + 40 * u), outline=A(red, 220 * (1 - ph)),
                      width=int(4 * u))
        py = cy - 60 * u * eb(t / 0.5)
        d.ellipse((cx - 55 * u, py - 160 * u, cx + 55 * u, py - 50 * u), fill=red)
        d.polygon([(cx - 48 * u, py - 90 * u), (cx + 48 * u, py - 90 * u), (cx, py + 40 * u)], fill=red)
        d.ellipse((cx - 22 * u, py - 128 * u, cx + 22 * u, py - 84 * u), fill=C["bg"])
        d.text((cx, cy + 190 * u), up(show.get("name", "")), font=F(110 * u, 800), fill=txt, anchor="mm")
        if show.get("sub"):
            spaced(d, (cx, cy + 270 * u), up(show["sub"]), F(36 * u, 600), A(txt, 170), 10 * u)
        if show.get("coords"):
            co = show["coords"]
            n = int(len(co) * cl(t / 1.0))
            d.text((cx, cy + 340 * u), co[:n], font=M(34 * u), fill=org, anchor="mm")

    elif typ == "date":
        cw, ch = 520 * u, 560 * u
        x0, y0 = cx - cw / 2, cy - ch / 2
        flip = eo(t / 0.45)
        d.rounded_rectangle((x0, y0, x0 + cw, y0 + ch), radius=int(24 * u), fill=(235, 232, 225))
        d.rounded_rectangle((x0, y0, x0 + cw, y0 + 140 * u), radius=int(24 * u), fill=red)
        d.rectangle((x0, y0 + 110 * u, x0 + cw, y0 + 140 * u), fill=red)
        d.text((cx, y0 + 72 * u), up(show.get("month", "")), font=F(64 * u, 800), fill=(255, 255, 255), anchor="mm")
        d.text((cx, y0 + 140 * u + (ch - 140 * u) * 0.45 + (1 - flip) * 60 * u), str(show.get("day", "")),
               font=F(270 * u, 900), fill=A((25, 25, 28), 255 * flip), anchor="mm")
        if show.get("year"):
            d.text((cx, y0 + ch + 90 * u), str(show["year"]), font=F(120 * u, 800), fill=org, anchor="mm")

    elif typ == "headline":
        cw, ch = 820 * u, 640 * u
        paper = Image.new("RGBA", (int(cw), int(ch)), A((222, 216, 200), 255))
        pd = ImageDraw.Draw(paper)
        pd.text((cw / 2, 60 * u), up(show.get("paper", "GAZETE")), font=F(64 * u, 900, 100), fill=(20, 20, 20), anchor="mm")
        pd.line((30 * u, 110 * u, cw - 30 * u, 110 * u), fill=(20, 20, 20), width=int(4 * u))
        words = up(show.get("text", "")).split()
        nk = int(len(words) * cl(t / max(0.8, dur * 0.5))) or 1
        lines, cur = [], ""
        fh = F(84 * u, 900)
        for w in words[:nk]:
            if fh.getlength((cur + " " + w).strip()) > cw - 80 * u:
                lines.append(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        lines.append(cur)
        for i, ln in enumerate(lines[:4]):
            pd.text((40 * u, 170 * u + i * 95 * u), ln, font=fh, fill=(15, 15, 15), anchor="lm")
        for j in range(5):
            pd.rectangle((40 * u, 560 * u - j * 28 * u, cw - 40 * u - (j % 2) * 120 * u, 572 * u - j * 28 * u),
                         fill=(150, 145, 135))
        paper = paper.rotate(show.get("rot", 2), expand=True, resample=Image.BICUBIC)
        img.alpha_composite(paper, (int(cx - paper.width / 2), int(cy - paper.height / 2)))

    elif typ == "list":
        items = show.get("items", [])
        strike = set(show.get("strike", []))
        f = F(96 * u, 800)
        for i, it in enumerate(items):
            a = cl((t - i * 0.35) / 0.25)
            if a <= 0:
                continue
            y = cy + (i - (len(items) - 1) / 2) * 165 * u
            tx = up(it)
            w = f.getlength(tx) + 80 * u
            x = cx - w / 2 - (1 - eo(a)) * 80 * u
            d.rounded_rectangle((x, y - 68 * u, x + w, y + 68 * u), radius=int(14 * u), fill=A((30, 30, 34), 230 * a),
                                outline=A(red if i in strike else txt, 120 * a), width=int(3 * u))
            d.text((x + w / 2, y), tx, font=f, fill=A(txt, 255 * a), anchor="mm")
            if i in strike:
                sk = cl((t - dur * 0.6 - i * 0.15) / 0.25)
                if sk > 0:
                    d.line((x + 20 * u, y, x + 20 * u + (w - 40 * u) * sk, y), fill=red, width=int(9 * u))

    elif typ == "icon":
        bob = math.sin(t * 2.2) * 10 * u
        icon(d, show.get("name", "question"), cx, cy + bob, 560 * u * (0.92 + 0.08 * eo(t / 0.4)) * (1 + 0.02 * math.sin(t * 3)),
             t, txt, red)
        if show.get("label"):
            d.text((cx, cy + 420 * u), up(show["label"]), font=F(70 * u, 800), fill=org, anchor="mm")

    elif typ == "quote":
        d.text((cx, cy - 260 * u), "“", font=F(300 * u, 900), fill=red, anchor="mm")
        words = show.get("text", "").split()
        nk = max(1, int(len(words) * cl(t / max(0.8, dur * 0.6))))
        f = F(92 * u, 700)
        lines, cur = [], ""
        for w in words[:nk]:
            if f.getlength((cur + " " + w).strip()) > 900 * u:
                lines.append(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        lines.append(cur)
        for i, ln in enumerate(lines):
            d.text((cx, cy - 80 * u + i * 110 * u), ln, font=f, fill=txt, anchor="mm")
        if show.get("who"):
            d.text((cx, cy + 60 * u + len(lines) * 110 * u), "— " + up(show["who"]), font=F(44 * u, 600), fill=org,
                   anchor="mm")

    elif typ == "title":
        lines = show.get("lines", ["BAŞLIK"])
        hl = show.get("red", 1)
        y = cy - (len(lines) - 1) * 80 * u
        for i, ln in enumerate(lines):
            a = cl((t - i * 0.22) / 0.18)
            if a <= 0:
                continue
            size = (170 if i == hl else 90) * u * (1.5 - 0.5 * eo(a))
            d.text((cx, y), up(ln), font=F(size, 900 if i == hl else 700), fill=A(red if i == hl else txt, 255 * a),
                   anchor="mm")
            y += (200 if i == hl else 140) * u
    return typ


# ============================================================ captions
def caption_words(say):
    out = []
    for w in say.split():
        hot = w.startswith("*") or w.endswith("*") or w.strip("*.,!?;:").endswith("*")
        clean = w.replace("*", "")
        num = any(ch.isdigit() for ch in clean)
        out.append((clean, "red" if hot else ("org" if num else "txt")))
    return out


def chunk(words, max_chars=18, max_words=3):
    ch, cur = [], []
    for i, (w, k) in enumerate(words):
        if cur and (len(" ".join(x[0] for x in cur + [(w, k)])) > max_chars or len(cur) >= max_words):
            ch.append(cur)
            cur = []
        cur.append((w, k, i))
        if w[-1] in ".?!,:;":
            ch.append(cur)
            cur = []
    if cur:
        ch.append(cur)
    return ch


def draw_caption(fr, words_kind, timings, t, cx, cy, u):
    """Kelimeler söylendikçe birikerek belirir (ADI → ADI HAMDİ → ADI HAMDİ KAYAPINAR)."""
    if not timings:
        return
    chunks = chunk(words_kind)
    cur = None
    for c in chunks:
        a = timings[c[0][2]][1]
        b = timings[c[-1][2]][2]
        if a - 0.05 <= t < b + 0.25:
            cur = c
    if cur is None:
        return
    vis = [(w, k) for (w, k, i) in cur if timings[i][1] - 0.04 <= t]
    if not vis:
        return
    last_start = max(timings[i][1] for (w, k, i) in cur if timings[i][1] - 0.04 <= t)
    pop = 1 + 0.14 * (1 - eo((t - last_start) / 0.16))
    f = F(84 * u, 700)
    cols = {"red": C["red"], "org": C["orange"], "txt": (245, 242, 236)}
    words = [up(w.strip(",.;:")) for w, _ in vis]
    space = f.getlength(" ")
    total = sum(f.getlength(w) for w in words) + space * (len(words) - 1)
    H, W = fr.shape[:2]
    pad = int(60 * u)
    bw, bh = int(total + pad * 2), int(f.size * 1.6)
    layer = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.ellipse((0, bh * 0.15, bw, bh * 0.95), fill=(0, 0, 0, 150))
    layer = layer.filter(ImageFilter.GaussianBlur(18 * u))
    ld = ImageDraw.Draw(layer)
    x = pad
    for w, (_, k) in zip(words, vis):
        ld.text((x + 3 * u, bh / 2 + 4 * u), w, font=f, fill=(0, 0, 0, 200), anchor="lm")
        ld.text((x, bh / 2), w, font=f, fill=cols[k] + (255,), anchor="lm")
        x += f.getlength(w) + space
    if pop > 1.005:
        layer = layer.resize((int(bw * pop), int(bh * pop)), Image.BILINEAR)
        bw, bh = layer.size
    arr = np.array(layer)
    x0, y0 = int(cx - bw / 2), int(cy - bh / 2)
    x1, y1 = min(W, x0 + bw), min(H, y0 + bh)
    xs, ys = max(0, x0), max(0, y0)
    s = arr[ys - y0:y1 - y0, xs - x0:x1 - x0]
    al = s[..., 3:4].astype(np.float32) / 255
    fr[ys:y1, xs:x1] = (fr[ys:y1, xs:x1] * (1 - al) + s[..., :3] * al).astype(np.uint8)


# ============================================================ background & brand
def background(W, H, seed=0):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = W / 2, H * 0.45
    d = np.sqrt(((xx - cx) / (W * 0.75)) ** 2 + ((yy - cy) / (H * 0.6)) ** 2)
    bg = np.array(C["bg"], np.float32)
    glow = np.array(C["glow"], np.float32)
    img = bg + glow * np.clip(1 - d, 0, 1)[..., None] ** 1.6 * 0.55
    img *= np.clip(1.15 - 0.55 * d ** 1.8, 0.25, 1)[..., None]
    return np.clip(img, 0, 255).astype(np.uint8)


def brand_sprite(text, u):
    f = F(40 * u, 700)
    w = int(sum(f.getlength(c) + 7 * u for c in up(text)) + 70 * u)
    im = Image.new("RGBA", (w, int(76 * u)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 14 * u, 7 * u, 62 * u), fill=C["red"] + (255,))
    spaced(d, (26 * u, 38 * u), up(text), f, (235, 230, 222, 235), 7 * u, anchor="l")
    return np.array(im)


# ============================================================ DİNAMİK KATMANLAR (sürekli hareket)
class Atmosphere:
    """Arka planda sürekli hareket: sis akışı, toz parçacıkları, ışık süzmesi."""

    def __init__(self, W, H, seed=0):
        self.W, self.H = W, H
        rng = np.random.default_rng(seed)
        n = 256
        k = np.fft.fftfreq(n)
        kk = np.sqrt(k[:, None] ** 2 + k[None, :] ** 2)
        kk[0, 0] = 1
        f = kk ** -1.6 * np.exp(1j * rng.uniform(0, 6.28, (n, n)))
        f[0, 0] = 0
        fog = np.real(np.fft.ifft2(f))
        fog = (fog - fog.min()) / (fog.max() - fog.min())
        fog = np.clip((fog - 0.45) * 2.2, 0, 1).astype(np.float32)
        self.fog = cv2.resize(np.tile(fog, (1, 2)), (W * 2, H), interpolation=cv2.INTER_CUBIC)
        self.p = rng.uniform(0, 1, (90, 4)).astype(np.float32)   # x, y, size, speed
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        self.diag = (xx / W + yy / H * 0.6)

    def apply(self, fr, t, glow):
        W, H = self.W, self.H
        off = int((t * 18) % W)
        fog = self.fog[:, off:off + W]
        f = fr.astype(np.float32)
        f += fog[..., None] * (np.array(glow, np.float32) * 0.55 + 14)
        # ışık süzmesi
        ph = (t * 0.07) % 1.6 - 0.3
        band = np.exp(-((self.diag - ph * 1.8) ** 2) / 0.012) * 26
        f += band[..., None]
        out = np.clip(f, 0, 255).astype(np.uint8)
        # toz
        for x, y, s, v in self.p:
            px = int(((x + t * 0.01 * (0.3 + v)) % 1) * W)
            py = int(((y - t * 0.02 * (0.3 + v)) % 1) * H)
            r = max(1, int(1 + s * 3.5 * W / 1080))
            a = 0.25 + 0.5 * abs(math.sin(t * (1 + v) + x * 10))
            c = int(170 * a)
            cv2.circle(out, (px, py), r, (c, c, c), -1, cv2.LINE_AA)
        return out


def ghost_word(fr, word, t, dur, W, H, u):
    """Arka planda dev, yarı saydam anahtar kelime (kinetik tipografi)."""
    if not word:
        return
    f = F(330 * u, 900)
    tw = f.getlength(word)
    img = Image.new("L", (int(tw + 40), int(f.size * 1.3)), 0)
    ImageDraw.Draw(img).text((20, f.size * 0.65), word, font=f, fill=255, anchor="lm")
    a = np.array(img).astype(np.float32) / 255 * 0.07 * min(1, t / 0.4)
    x0 = int(W / 2 - img.width / 2 + (0.5 - t / max(dur, 0.1)) * 120 * u)
    y0 = int(H * 0.2 - img.height / 2)
    x1, y1 = max(0, x0), max(0, y0)
    x2, y2 = min(W, x0 + img.width), min(H, y0 + img.height)
    if x2 <= x1 or y2 <= y1:
        return
    sub = a[y1 - y0:y2 - y0, x1 - x0:x2 - x0, None]
    col = np.array(C["red"], np.float32)
    fr[y1:y2, x1:x2] = np.clip(fr[y1:y2, x1:x2] * (1 - sub) + col * sub, 0, 255).astype(np.uint8)


def hud(fr, gt, total, W, H, u, file_no="001"):
    """Vizör köşeleri, yanıp sönen KAYIT, zaman kodu, alt ilerleme çubuğu."""
    col = (220, 216, 206)
    m, L_ = int(34 * u), int(60 * u)
    th = max(2, int(3 * u))
    for (x, y, dx, dy) in [(m, m + int(60 * u), 1, 1), (W - m, m + int(60 * u), -1, 1), (m, H - m, 1, -1),
                           (W - m, H - m, -1, -1)]:
        cv2.line(fr, (x, y), (x + dx * L_, y), col, th, cv2.LINE_AA)
        cv2.line(fr, (x, y), (x, y + dy * L_), col, th, cv2.LINE_AA)
    if int(gt * 1.6) % 2 == 0:
        cv2.circle(fr, (W - m - int(150 * u), m + int(96 * u)), int(9 * u), C["red"], -1, cv2.LINE_AA)
    mm, ss = divmod(int(gt), 60)
    fr_ = int((gt % 1) * 30)
    txt = f"KAYIT  {mm:02d}:{ss:02d}:{fr_:02d}"
    cv2.putText(fr, txt, (W - m - int(130 * u), m + int(104 * u)), cv2.FONT_HERSHEY_SIMPLEX, 0.62 * u, col,
                max(1, int(1.6 * u)), cv2.LINE_AA)
    cv2.putText(fr, f"DOSYA #{file_no}", (m + int(20 * u), H - m - int(22 * u)), cv2.FONT_HERSHEY_SIMPLEX,
                0.6 * u, col, max(1, int(1.5 * u)), cv2.LINE_AA)
    p = min(1.0, gt / max(total, 1))
    y = H - int(8 * u)
    cv2.rectangle(fr, (0, y), (W, H), (40, 40, 44), -1)
    cv2.rectangle(fr, (0, y), (int(W * p), H), C["red"], -1)


def transition(fr, kind, t, seed):
    """Sahne girişi efektleri (ilk ~0.22 sn)."""
    k = 1 - eo(t / 0.22)
    if k <= 0.01:
        return fr
    H, W = fr.shape[:2]
    if kind == "whip":
        dx = int(W * 0.35 * k) * (1 if seed % 2 else -1)
        M_ = np.float32([[1, 0, dx], [0, 1, 0]])
        fr = cv2.warpAffine(fr, M_, (W, H), borderMode=cv2.BORDER_REFLECT)
        kz = int(90 * k) | 1
        return cv2.blur(fr, (kz, 1))
    if kind == "glitch":
        out = fr.copy()
        a = int(30 * k)
        if a > 0:
            out[:, a:, 0] = fr[:, :-a, 0]
            out[:, :-a, 2] = fr[:, a:, 2]
        rng = np.random.default_rng(int(t * 1000) + seed)
        for _ in range(int(8 * k)):
            y = rng.integers(0, H - 40)
            h = rng.integers(8, 60)
            out[y:y + h] = np.roll(out[y:y + h], rng.integers(-120, 120), axis=1)
        return out
    if kind == "flash":
        return cv2.addWeighted(fr, 1 - 0.85 * k, np.full_like(fr, 255), 0.85 * k, 0)
    # zoom
    s = 1 + 0.25 * k
    M_ = cv2.getRotationMatrix2D((W / 2, H / 2), 0, s)
    fr = cv2.warpAffine(fr, M_, (W, H), borderMode=cv2.BORDER_REFLECT)
    return cv2.blur(fr, (int(25 * k) | 1, int(25 * k) | 1))


_photo_cache = {}


def load_photo(path):
    if path in _photo_cache:
        return _photo_cache[path]
    im = None
    if path and os.path.exists(path):
        try:
            im = Image.open(path).convert("RGB")
        except Exception:
            im = None
    _photo_cache[path] = im
    return im


def draw_photo(img, show, t, dur, cx, cy, u):
    """Arşiv fotoğrafı: Ken Burns + eskitilmiş ton + kâğıt çerçeve + bant + etiket."""
    ph = load_photo(show.get("_local"))
    if ph is None:
        icon(ImageDraw.Draw(img), show.get("fallback_icon", "camera"), cx, cy, 520 * u, t, C["text"], C["red"])
        return
    fw, fh = int(860 * u), int(640 * u)
    if show.get("portrait"):
        fw, fh = int(640 * u), int(820 * u)
    s = 1.06 + 0.12 * (t / max(dur, 0.1))
    iw, ih = ph.size
    sc = max(fw / iw, fh / ih) * s
    pw, phh = int(iw * sc), int(ih * sc)
    dx = (pw - fw) * (0.5 + 0.35 * math.sin(t * 0.25 + 1))
    dy = (phh - fh) * (0.5 + 0.3 * math.cos(t * 0.2))
    crop = ph.resize((pw, phh), Image.BICUBIC).crop((int(dx), int(dy), int(dx) + fw, int(dy) + fh))
    a = np.array(crop).astype(np.float32)
    g = a.mean(-1, keepdims=True)
    tone = np.array(C["paper"], np.float32) / 255
    a = np.clip((g * 0.85 + a * 0.15) * tone * 1.05, 0, 255)
    rng = np.random.default_rng(int(t * 24))
    a += rng.normal(0, 9, a.shape[:2])[..., None]
    crop = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    bw = int(22 * u)
    frame = Image.new("RGBA", (fw + 2 * bw, fh + 2 * bw + int(70 * u)), (238, 233, 220, 255))
    frame.paste(crop, (bw, bw))
    fd = ImageDraw.Draw(frame)
    if show.get("label"):
        fd.text((bw, fh + bw + int(36 * u)), up(show["label"]), font=M(int(30 * u)), fill=(40, 36, 30), anchor="lm")
    for (tx, ty, ang) in [(0.12, 0, -20), (0.88, 0, 22)]:
        tape = Image.new("RGBA", (int(170 * u), int(46 * u)), (220, 205, 150, 170))
        tape = tape.rotate(ang, expand=True)
        frame.alpha_composite(tape, (int(frame.width * tx - tape.width / 2), int(-tape.height * 0.35) + 10))
    rot = show.get("rot", -2.5) + 1.5 * math.sin(t * 0.6)
    frame = frame.rotate(rot, expand=True, resample=Image.BICUBIC)
    sh = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    sh.paste((0, 0, 0, 160), (0, 0), frame.split()[3])
    sh = sh.filter(ImageFilter.GaussianBlur(18 * u))
    img.alpha_composite(sh, (int(cx - frame.width / 2 + 16 * u), int(cy - frame.height / 2 + 24 * u)))
    img.alpha_composite(frame, (int(cx - frame.width / 2), int(cy - frame.height / 2)))
