"""Hareketli infografik (motion graphics) sahneleri — düz renkli, temiz 2D anlatım dili.

Fotoğraf yerine (ya da fotoğrafların arasında) kullanılan sahne türleri:
  map      Türkiye / bölge haritası: çizilerek gelen sınır, iğneler, kırmızı X, nokta yağmuru, ok rotası,
           il boyama, ile yakınlaşma, üstte büyük başlık
  sign     yol tabelası (mavi/beyaz/kahverengi), düşerek gelir; önceki tabela soluk yanda kalabilir
  doc      resmî belge kartı (TÜİK vb.): satır vurgusu + sayaç gibi dönen büyük rakam + birim etiketi
  podium   1-2-3 kürsü, kazanan yükselir
  rank     sıralama listesi kayar, istenen sıra vurgulanır
  ratio    piktogram insanlar: n kişiden k'si renkli ("10'DA 4")
  split    iki renkli çapraz ekran: "A MI, B Mİ?" + ortada rozet
  tape     kırmızı zemin, çapraz uyarı şeritleri + büyük ünlem
  building çizgi-sanat yapı (cami, kale, ev, kule, sütun, köprü) çizilerek belirir + etiket rozeti
  qmark    hardal zemin, büyük soru işareti + kırık kelime
Hepsi show={"type": ..., ...} ile senaryodan çağrılır; arka plan rengi türe göre (show["bg"] ile değişir).
"""
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw

from . import story as ST

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TYPES = {"map", "sign", "doc", "podium", "rank", "ratio", "split", "tape", "building", "qmark"}

PAL = dict(navy=(20, 27, 44), char=(30, 28, 30), brown=(52, 38, 30), ochre=(196, 148, 72), red=(168, 46, 38),
           teal=(38, 160, 150), cream=(238, 228, 204), yellow=(244, 178, 44), blue=(28, 78, 178), white=(246, 244, 238),
           land=(40, 38, 40), grey=(120, 118, 116))
BG_OF = dict(map="navy", sign="navy", rank="char", ratio="char", doc="char", podium="char", building="char",
             split="teal", tape="red", qmark="ochre")

_GEO = {}


def _geo():
    if not _GEO:
        try:
            _GEO["c"] = json.load(open(os.path.join(ROOT, "assets/geo/countries.json")))
            _GEO["p"] = json.load(open(os.path.join(ROOT, "assets/geo/tr_provinces.json")))
        except Exception as e:
            print("  [harita] veri yok:", e)
            _GEO["c"], _GEO["p"] = {}, {}
        # Türkçe adlar ve yaygın yazımlar
        alias = {"İstanbul": "Istanbul", "Afyonkarahisar": "Afyon", "Kahramanmaraş": "K. Maras", "Şanlıurfa": "Sanliurfa"}
        for k, v in alias.items():
            if v in _GEO["p"] and k not in _GEO["p"]:
                _GEO["p"][k] = _GEO["p"][v]
    return _GEO


def _norm(s):
    tr = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosuCGIOSUaiu")
    return s.translate(tr).lower().replace(" ", "").replace(".", "")


def lonlat(p):
    """İl adı ya da [boylam, enlem] -> (boylam, enlem)."""
    if isinstance(p, (list, tuple)):
        return float(p[0]), float(p[1])
    g = _geo()["p"]
    if p in g:
        return tuple(g[p]["c"])
    n = _norm(p)
    for k, v in g.items():
        if _norm(k) == n:
            return tuple(v["c"])
    return 35.0, 39.0


def _prov_rings(name):
    g = _geo()["p"]
    n = _norm(name)
    for k, v in g.items():
        if _norm(k) == n:
            return v["rings"]
    return []


# ------------------------------------------------------------------ yardımcılar
def background(kind, W, H, _cache={}):
    """Düz renk + hafif vinyet + kâğıt dokusu (referans videodaki gibi)."""
    key = (kind, W, H)
    if key in _cache:
        return _cache[key]
    col = np.array(PAL.get(kind, kind if isinstance(kind, tuple) else PAL["navy"]), np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H * 0.45) / (H / 2)) ** 2)
    v = np.clip(1.12 - 0.42 * d, 0.55, 1.12)[..., None]
    rng = np.random.default_rng(7)
    noise = rng.normal(0, 5, (H // 4 + 1, W // 4 + 1)).astype(np.float32)
    noise = np.kron(noise, np.ones((4, 4), np.float32))[:H, :W][..., None]
    out = np.clip(col * v + noise, 0, 255).astype(np.uint8)
    _cache[key] = out
    return out


def _box_text(d, xy, text, font, fill, bg, pad, u, rot_img=None, radius=8):
    x, y = xy
    w = font.getlength(text)
    h = font.size
    d.rounded_rectangle((x - w / 2 - pad, y - h * 0.62 - pad * 0.5, x + w / 2 + pad, y + h * 0.62 + pad * 0.5),
                        radius=int(radius * u), fill=bg)
    d.text((x, y), text, font=font, fill=fill, anchor="mm")


def _fit(d, text, size, maxw, weight=800):
    f = ST.F(size, weight)
    while size > 20 and d.textlength(text, font=f) > maxw:
        size *= 0.92
        f = ST.F(size, weight)
    return f


def _stamp(img, text, cx, cy, u, col, rot=-8, size=46):
    """Eğik etiket/rozet (ör. '1100'LER', 'SELÇUKLU')."""
    f = ST.F(size * u, 900)
    tw = int(f.getlength(text) + 44 * u)
    th = int(size * 1.55 * u)
    im = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    dd = ImageDraw.Draw(im)
    dd.rounded_rectangle((0, 0, tw - 1, th - 1), radius=int(6 * u), fill=col + (255,))
    dd.text((tw / 2, th / 2), text, font=f, fill=(25, 22, 20), anchor="mm")
    im = im.rotate(rot, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


# ------------------------------------------------------------------ harita
VIEWS = {"tr": (25.2, 45.3, 35.4, 42.6), "wide": (19.0, 46.0, 33.5, 44.5), "west": (19.0, 37.0, 34.5, 43.5),
         "med": (10.0, 46.0, 28.0, 46.5)}


def draw_map(img, show, t, dur, W, H, u):
    d = ImageDraw.Draw(img)
    x0, x1, y0, y1 = VIEWS.get(show.get("view", "tr"), VIEWS["tr"])
    k = math.cos(math.radians((y0 + y1) / 2))
    mw = W * 1.04
    sc = mw / ((x1 - x0) * k)
    my = H * 0.40
    ccx, ccy = (x0 + x1) / 2, (y0 + y1) / 2
    zoom, fx, fy = 1.0, ccx, ccy
    if show.get("focus"):
        flon, flat = lonlat(show["focus"])
        z = eo_((t - 0.35) / 0.9)
        zoom = 1 + (float(show.get("zoom", 2.4)) - 1) * z
        fx, fy = ccx + (flon - ccx) * z, ccy + (flat - ccy) * z

    def P(lon, lat):
        return (W / 2 + (lon - fx) * k * sc * zoom, my - (lat - fy) * sc * zoom)

    g = _geo()
    draw_in = eo_(t / 0.55)
    lw = max(2, int(4 * u))
    hl_country = show.get("fill_country")
    for code, rings in g["c"].items():
        main = code == "TR"
        if not main and show.get("view", "tr") == "tr" and not show.get("neighbours", True):
            continue
        for r in rings:
            pts = [P(*p) for p in r]
            if len(pts) < 3:
                continue
            if main or code == hl_country:
                fill = PAL["teal"] if code == hl_country else PAL["land"]
                d.polygon(pts, fill=fill + (255,))
                n = max(2, int(len(pts) * draw_in))
                d.line(pts[:n], fill=PAL["white"] + (255,), width=lw, joint="curve")
            else:
                d.polygon(pts, fill=(30, 36, 52, 255))
                d.line(pts + [pts[0]], fill=(90, 98, 120, 200), width=max(1, lw // 2))
    for name in show.get("fill", []):
        a = ST.cl((t - 0.3) / 0.35)
        for r in _prov_rings(name):
            pts = [P(*p) for p in r]
            if len(pts) > 2:
                d.polygon(pts, fill=PAL["teal"] + (int(255 * a),))
                d.line(pts + [pts[0]], fill=PAL["white"] + (int(255 * a),), width=max(1, lw // 2))
    # nokta yağmuru (ör. 45 il)
    nd = int(show.get("dots", 0))
    if nd:
        rng = np.random.default_rng(int(show.get("seed", 3)))
        names = list(g["p"].keys())
        pick = rng.choice(len(names), size=min(nd, len(names)), replace=False)
        for i, j in enumerate(pick):
            a = ST.cl((t - 0.2 - i * 0.025) / 0.15)
            if a <= 0:
                continue
            x, y = P(*g["p"][names[j]]["c"])
            r = 9 * u * ST.eb(a)
            d.rectangle((x - r, y - r, x + r, y + r), fill=PAL["yellow"] + (255,))
    # rota (ok + hareketli işaret)
    rt = show.get("route")
    if rt:
        ax, ay = P(*lonlat(rt["from"]))
        bx, by = P(*lonlat(rt["to"]))
        mx, my2 = (ax + bx) / 2, min(ay, by) - abs(bx - ax) * 0.28
        p = eo_((t - 0.3) / 1.0)
        pts = []
        for i in range(41):
            s = i / 40 * p
            pts.append(((1 - s) ** 2 * ax + 2 * (1 - s) * s * mx + s * s * bx, (1 - s) ** 2 * ay + 2 * (1 - s) * s * my2 + s * s * by))
        for i in range(0, len(pts) - 1, 2):
            d.line([pts[i], pts[i + 1]], fill=PAL["yellow"] + (255,), width=int(6 * u))
        if p > 0.02:
            hx, hy = pts[-1]
            d.ellipse((hx - 12 * u, hy - 12 * u, hx + 12 * u, hy + 12 * u), fill=PAL["yellow"] + (255,))
        for (lx, ly), lab in ((P(*lonlat(rt["from"])), rt.get("from_label")), (P(*lonlat(rt["to"])), rt.get("to_label"))):
            if lab:
                d.text((lx, ly + 34 * u), ST.up(lab), font=ST.F(30 * u, 800), fill=PAL["white"] + (230,), anchor="mm")
    # iğneler
    for i, pin in enumerate(show.get("pins", [])):
        a = ST.cl((t - 0.35 - i * 0.3) / 0.25)
        if a <= 0:
            continue
        x, y = P(*lonlat(pin.get("at")))
        hop = (1 - ST.eb(a)) * 60 * u
        d.ellipse((x - 9 * u, y - 9 * u, x + 9 * u, y + 9 * u), fill=PAL["white"] + (255,))
        col = PAL["red"] if pin.get("red") else PAL["yellow"]
        py = y - 34 * u - hop
        d.ellipse((x - 22 * u, py - 22 * u, x + 22 * u, py + 22 * u), fill=col + (int(255 * a),))
        d.polygon([(x - 17 * u, py + 12 * u), (x + 17 * u, py + 12 * u), (x, y - 8 * u)], fill=col + (int(255 * a),))
        d.ellipse((x - 8 * u, py - 8 * u, x + 8 * u, py + 8 * u), fill=PAL["land"] + (255,))
        if pin.get("label"):
            f = ST.F(34 * u, 800)
            _box_text(d, (x, py - 52 * u), ST.up(pin["label"]), f, (20, 20, 22, int(255 * a)), PAL["white"] + (int(255 * a),), 12 * u, u)
    # kırmızı X
    for i, xn in enumerate(show.get("x", [])):
        a = ST.cl((t - 0.45 - i * 0.45) / 0.22)
        if a <= 0:
            continue
        x, y = P(*lonlat(xn))
        r = 46 * u
        w = int(14 * u)
        d.line((x - r, y - r, x - r + 2 * r * min(1, a * 2), y - r + 2 * r * min(1, a * 2)), fill=(226, 52, 42, 255), width=w)
        if a > 0.5:
            b = (a - 0.5) * 2
            d.line((x + r, y - r, x + r - 2 * r * b, y - r + 2 * r * b), fill=(226, 52, 42, 255), width=w)
        lab = xn if isinstance(xn, str) else ""
        if lab and show.get("x_labels", True):
            d.text((x, y - r - 30 * u), ST.up(lab), font=ST.F(32 * u, 800), fill=PAL["white"] + (240,), anchor="mm")
    _title(d, show, t, W, H, u)


def _title(d, show, t, W, H, u):
    if show.get("title"):
        a = ST.cl((t - 0.1) / 0.25)
        f = _fit(d, ST.up(show["title"]), 120 * u, W * 0.86, 900)
        y = H * 0.12 + (1 - ST.eb(a)) * 40 * u
        d.text((W / 2, y), ST.up(show["title"]), font=f, fill=PAL["yellow"] + (int(255 * a),), anchor="mm")
        if show.get("sub"):
            ST.spaced(d, (W / 2, y + f.size * 0.7), ST.up(show["sub"]), ST.F(34 * u, 700), PAL["white"] + (int(220 * a),), 8 * u)


def eo_(x):
    return ST.eo(x)


# ------------------------------------------------------------------ tabela
SIGN_COL = dict(blue=(PAL["blue"], PAL["white"]), white=(PAL["white"], (20, 20, 22)), brown=((122, 74, 40), PAL["white"]),
                green=((26, 120, 70), PAL["white"]))


def _sign(img, cx, cy, text, style, u, a=1.0, scale=1.0, pole=True, H=1920, dim=False):
    d = ImageDraw.Draw(img)
    bg, fg = SIGN_COL.get(style, SIGN_COL["blue"])
    f = _fit(d, text, 104 * u * scale, 820 * u * scale, 900)
    w = f.getlength(text) + 90 * u * scale
    h = f.size * 1.55
    al = int(255 * a * (0.45 if dim else 1))
    if pole:
        for px in (cx - w * 0.3, cx + w * 0.3):
            d.rectangle((px - 9 * u * scale, cy, px + 9 * u * scale, H + 50), fill=(150, 150, 156, al))
    d.rounded_rectangle((cx - w / 2 - 6 * u, cy - h / 2 - 6 * u, cx + w / 2 + 6 * u, cy + h / 2 + 6 * u),
                        radius=int(22 * u * scale), fill=(250, 250, 250, al))
    d.rounded_rectangle((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), radius=int(18 * u * scale), fill=bg + (al,))
    d.rounded_rectangle((cx - w / 2 + 10 * u * scale, cy - h / 2 + 10 * u * scale, cx + w / 2 - 10 * u * scale,
                         cy + h / 2 - 10 * u * scale), radius=int(12 * u * scale), outline=fg + (al,), width=max(2, int(4 * u * scale)))
    d.text((cx, cy), text, font=f, fill=fg + (al,), anchor="mm")
    return w, h


def draw_sign(img, show, t, dur, W, H, u):
    d = ImageDraw.Draw(img)
    a = ST.cl(t / 0.3)
    y = H * 0.44 - (1 - ST.eb(a, 1.3)) * 500 * u
    swing = math.sin(t * 7) * math.exp(-t * 3) * 2.5
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    if show.get("prev"):
        _sign(lay, W * 0.27, H * 0.40, ST.up(show["prev"]), show.get("prev_style", "blue"), u, 1, 0.62, True, H, dim=True)
        cx = W * 0.70
        scl = 0.72
    else:
        cx = W / 2
        scl = 1.0
    _sign(lay, cx, y, ST.up(show.get("text", "")), show.get("style", "blue"), u, a, scl, True, H)
    lay = lay.rotate(swing, center=(cx, y), resample=Image.BICUBIC)
    img.alpha_composite(lay)
    if show.get("tag"):
        tg = ST.cl((t - 0.5) / 0.2)
        if tg > 0:
            _stamp(img, ST.up(show["tag"]), cx, y - 170 * u * scl, u, PAL["yellow"], rot=-4, size=40)
    _title(d, show, t, W, H, u)


# ------------------------------------------------------------------ belge + sayaç
def _odometer(img, cx, cy, value, t, u, size=150):
    """Rakamlar sayaç gibi dönerek yerine oturur."""
    f = ST.F(size * u, 900)
    s = str(value)
    w = f.getlength(s) + 60 * u
    h = size * 1.25 * u
    box = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
    d = ImageDraw.Draw(box)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=int(14 * u), fill=(26, 24, 26, 255),
                        outline=PAL["yellow"] + (255,), width=int(5 * u))
    ox, oy = cx - w / 2, cy - h / 2
    cx, cy = w / 2, h / 2
    x = cx - f.getlength(s) / 2
    for i, ch in enumerate(s):
        cw = f.getlength(ch)
        if ch.isdigit():
            p = ST.eo((t - i * 0.06) / 0.9)
            roll = (int(ch) + (1 - p) * (13 + i * 3)) % 10
            base = int(roll)
            frac = roll - base
            for dv, off in ((base, -frac), ((base + 1) % 10, 1 - frac)):
                yy = cy + off * size * u * 0.95
                if abs(off) < 0.98:
                    a = int(255 * (1 - abs(off)))
                    d.text((x + cw / 2, yy), str(dv), font=f, fill=PAL["yellow"] + (a,), anchor="mm")
        else:
            d.text((x + cw / 2, cy), ch, font=f, fill=PAL["yellow"] + (255,), anchor="mm")
        x += cw
    # rakamlar kutunun dışına taşmasın: iç bölgeyi kırp
    m = int(8 * u)
    inner = Image.new("L", box.size, 0)
    ImageDraw.Draw(inner).rounded_rectangle((m, m, box.width - m, box.height - m), radius=int(10 * u), fill=255)
    frame = Image.new("RGBA", box.size, (0, 0, 0, 0))
    ImageDraw.Draw(frame).rounded_rectangle((0, 0, w - 1, h - 1), radius=int(14 * u), fill=(26, 24, 26, 255),
                                            outline=PAL["yellow"] + (255,), width=int(5 * u))
    frame.paste(box, (0, 0), inner)
    img.alpha_composite(frame, (int(ox), int(oy)))


def draw_doc(img, show, t, dur, W, H, u):
    cw, ch = 600 * u, 740 * u
    card = Image.new("RGBA", (int(cw), int(ch)), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=int(10 * u), fill=PAL["cream"] + (255,))
    cd.text((40 * u, 70 * u), ST.up(show.get("org", "RESMÎ KAYIT")), font=ST.F(78 * u, 900), fill=(30, 28, 26), anchor="lm")
    if show.get("year"):
        yr = str(show["year"])
        f = ST.F(48 * u, 900)
        bw = f.getlength(yr) + 30 * u
        cd.rounded_rectangle((cw - 40 * u - bw, 40 * u, cw - 40 * u, 104 * u), radius=int(6 * u), outline=(196, 50, 40, 255),
                             width=int(5 * u))
        cd.text((cw - 40 * u - bw / 2, 72 * u), yr, font=f, fill=(196, 50, 40), anchor="mm")
    if show.get("sub"):
        cd.text((40 * u, 128 * u), ST.up(show["sub"]), font=ST.F(24 * u, 600), fill=(90, 84, 76), anchor="lm")
    cd.line((40 * u, 150 * u, cw - 40 * u, 150 * u), fill=(40, 36, 32), width=int(4 * u))
    rng = np.random.default_rng(5)
    row_i = 3
    for i in range(9):
        y = 200 * u + i * 58 * u
        if i == row_i and t > 0.35:
            a = ST.cl((t - 0.35) / 0.25)
            cd.rectangle((24 * u, y - 24 * u, 24 * u + (cw - 48 * u) * ST.eo(a), y + 24 * u), fill=PAL["teal"] + (255,))
            cd.text((44 * u, y), ST.up(show.get("row", "")), font=ST.F(34 * u, 900), fill=(20, 40, 38), anchor="lm")
            cd.rectangle((cw - 210 * u, y - 7 * u, cw - 60 * u, y + 7 * u), fill=(20, 20, 20, 255))
        else:
            ln = 140 + rng.integers(60, 260)
            cd.rounded_rectangle((44 * u, y - 8 * u, 44 * u + ln * u, y + 8 * u), radius=int(8 * u), fill=(196, 188, 170, 255))
            cd.rounded_rectangle((cw - 210 * u, y - 8 * u, cw - 60 * u, y + 8 * u), radius=int(8 * u), fill=(196, 188, 170, 255))
    a = ST.cl(t / 0.3)
    z = 1.0 + 0.55 * ST.eo((t - 0.75) / 0.6) if show.get("value") else 1.0
    card = card.rotate(3 * (1 - a) + (-2 if show.get("value") else 1.5), expand=True, resample=Image.BICUBIC)
    if z != 1.0:
        card = card.resize((int(card.width * z), int(card.height * z)), Image.BICUBIC)
    cx, cy = W / 2, H * 0.37 + (1 - ST.eo(a)) * 300 * u + (z - 1) * 230 * u
    img.alpha_composite(card, (int(cx - card.width / 2), int(cy - card.height / 2)))
    if show.get("value") and t > 0.9:
        _odometer(img, W / 2, H * 0.40, show["value"], t - 0.9, u, 140)
        if show.get("unit") and t > 1.7:
            _stamp(img, ST.up(show["unit"]), W / 2, H * 0.40 + 150 * u, u, PAL["yellow"], rot=0, size=46)


# ------------------------------------------------------------------ kürsü & sıralama
def draw_podium(img, show, t, dur, W, H, u):
    d = ImageDraw.Draw(img)
    base = H * 0.66
    bw = 230 * u
    for i, (dx, hh, lab) in enumerate(((-1.15, 170, "2."), (0, 420, "1."), (1.15, 120, "3."))):
        grow = ST.eo((t - 0.15 - (0.25 if i == 1 else 0)) / 0.55) if i == 1 else ST.eo(t / 0.4)
        h = hh * u * grow
        x = W / 2 + dx * bw
        col = PAL["teal"] if i == 1 else (58, 56, 58)
        d.rectangle((x - bw / 2 + 8 * u, base - h, x + bw / 2 - 8 * u, base), fill=col + (255,))
        if h > 60 * u:
            d.text((x, base - h + 55 * u), lab, font=ST.F(70 * u, 900), fill=(20, 20, 22, 255) if i == 1 else (120, 118, 118, 255),
                   anchor="mm")
    d.rectangle((0, base, W, base + 12 * u), fill=(16, 16, 18, 255))
    if t > 0.8:
        a = ST.cl((t - 0.8) / 0.25)
        y = base - 420 * u - 80 * u
        f = _fit(d, ST.up(show.get("win", "")), 76 * u, W * 0.8, 900)
        d.text((W / 2, y - (1 - ST.eb(a)) * 40 * u), ST.up(show.get("win", "")), font=f, fill=PAL["white"] + (int(255 * a),), anchor="mm")
        _star(d, W / 2, y - 95 * u, 46 * u * ST.eb(a), PAL["yellow"], t)
    _title(d, show, t, W, H, u)


def _star(d, x, y, r, col, t):
    pts = []
    for i in range(16):
        ang = i * math.pi / 8 + t * 0.6
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((x + rr * math.cos(ang), y + rr * math.sin(ang)))
    d.polygon(pts, fill=col + (255,))


def draw_rank(img, show, t, dur, W, H, u):
    d = ImageDraw.Draw(img)
    pos = int(show.get("pos", 5))
    rowh = 92 * u
    scroll = ST.eo((t - 0.2) / max(0.6, dur * 0.55)) * max(0, pos - 5) * rowh
    top = H * 0.22
    for i in range(1, pos + 7):
        y = top + (i - 1) * rowh - scroll
        if y < H * 0.17 or y > H * 0.86:
            continue
        a = 1.0 - max(0, (abs(y - H * 0.5) - H * 0.25) / (H * 0.12))
        a = ST.cl(a)
        hit = i == pos and t > dur * 0.55
        d.text((120 * u, y), f"{i}.", font=ST.F(54 * u, 900), fill=(PAL["yellow"] if i == pos else PAL["grey"]) + (int(255 * a),), anchor="rm")
        if hit:
            b = ST.cl((t - dur * 0.55) / 0.25)
            d.rounded_rectangle((150 * u, y - 36 * u, 150 * u + (W - 260 * u) * ST.eo(b), y + 36 * u), radius=int(6 * u),
                                fill=PAL["teal"] + (255,))
            d.text((175 * u, y), ST.up(show.get("name", "")), font=ST.F(50 * u, 900), fill=(16, 30, 30, 255), anchor="lm")
        else:
            ln = (260 + (i * 97) % 300) * u
            d.rounded_rectangle((150 * u, y - 24 * u, 150 * u + ln, y + 24 * u), radius=int(6 * u), fill=(58, 56, 58, int(255 * a)))
    if show.get("title"):
        d.rectangle((0, 0, W, H * 0.165), fill=PAL["char"] + (255,))
        f = _fit(d, ST.up(show["title"]), 46 * u, W * 0.9, 900)
        d.text((W / 2, H * 0.14), ST.up(show["title"]), font=f, fill=PAL["yellow"] + (255,), anchor="mm")


# ------------------------------------------------------------------ piktogram oranı
def draw_ratio(img, show, t, dur, W, H, u):
    d = ImageDraw.Draw(img)
    n, k = int(show.get("n", 10)), int(show.get("k", 4))
    per = min(5, n)
    rows = (n + per - 1) // per
    h = 200 * u
    for i in range(n):
        r, c = divmod(i, per)
        x = W / 2 + (c - (per - 1) / 2) * 150 * u
        y = H * 0.40 + (r - (rows - 1) / 2) * (h + 50 * u) + h / 2
        a = ST.cl((t - i * 0.05) / 0.2)
        on = i < k and t > 0.6 + i * 0.12
        col = PAL["teal"] if on else ((PAL["cream"] if i < k else (84, 82, 84)))
        ST.person(d, x, y, h * (0.9 + 0.1 * ST.eb(a)), col + (int(255 * a),))
    _title(d, show, t, W, H, u)


# ------------------------------------------------------------------ ikiye bölünmüş ekran
def draw_split(img, show, t, dur, W, H, u):
    d = ImageDraw.Draw(img)
    a = ST.eo(t / 0.35)
    tilt = H * 0.06
    mid = H * 0.45
    d.polygon([(-50, mid + tilt), (W + 50, mid - tilt), (W + 50, H + 50), (-50, H + 50)], fill=PAL["red"] + (255,))
    for txt, y, col in ((show.get("top", ""), H * 0.26, PAL["white"]), (show.get("bottom", ""), H * 0.60, PAL["white"])):
        f = _fit(d, ST.up(txt), 110 * u, W * 0.9, 900)
        d.text((W / 2 + (1 - a) * (W if y < mid else -W), y), ST.up(txt), font=f, fill=col + (255,), anchor="mm")
        d.text((W / 2, y - 110 * u if y < mid else y + 110 * u), "?", font=ST.F(70 * u, 900), fill=(20, 20, 20, 200), anchor="mm")
    if show.get("badge"):
        b = ST.cl((t - 0.5) / 0.3)
        r = 120 * u * ST.eb(b)
        cx, cy = W / 2, mid
        if r > 2:
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(24, 22, 22, 255), outline=PAL["yellow"] + (255,), width=int(6 * u))
            words = ST.up(show["badge"]).split()
            for j, w in enumerate(words[:2]):
                d.text((cx, cy + (j - (len(words[:2]) - 1) / 2) * 52 * u), w, font=ST.F(44 * u * ST.eb(b), 900),
                       fill=PAL["yellow"] + (255,), anchor="mm")


# ------------------------------------------------------------------ uyarı şeridi
def draw_tape(img, show, t, dur, W, H, u):
    d = ImageDraw.Draw(img)
    word = ST.up(show.get("text", "DİKKAT"))
    a = ST.cl(t / 0.25)
    d.text((W / 2, H * 0.42), "!", font=ST.F(560 * u * (0.8 + 0.2 * ST.eb(a)), 900), fill=(22, 18, 18, 255), anchor="mm")
    for j, (ang, yc) in enumerate(((-22, H * 0.36), (18, H * 0.50))):
        p = ST.eo((t - j * 0.15) / 0.35)
        L = int(W * 1.8)
        th = int(86 * u)
        strip = Image.new("RGBA", (L, th), PAL["cream"] + (255,))
        sd = ImageDraw.Draw(strip)
        unit = f"{word} · "
        f = ST.F(48 * u, 900)
        x = -((t * 120 * u) % f.getlength(unit))
        while x < L:
            sd.text((x, th / 2), unit, font=f, fill=(24, 22, 20), anchor="lm")
            x += f.getlength(unit)
        strip = strip.rotate(ang, expand=True, resample=Image.BICUBIC)
        ox = int(W / 2 - strip.width / 2 + (1 - p) * W * (1 if j else -1))
        img.alpha_composite(strip, (ox, int(yc - strip.height / 2)))


# ------------------------------------------------------------------ çizgi-sanat yapı
def _building_lines(kind, cx, by, s):
    """Yapı çizgileri: [(x0,y0,x1,y1), ...] ve dolgu çokgenleri."""
    L, polys = [], []
    if kind == "mosque":
        w, h = 520 * s, 230 * s
        polys.append([(cx - w / 2, by), (cx - w / 2, by - h), (cx + w / 2, by - h), (cx + w / 2, by)])
        dome = [(cx + 120 * s * math.cos(a), by - h - 110 * s * math.sin(a)) for a in np.linspace(0, math.pi, 24)]
        polys.append(dome + [(cx - 120 * s, by - h)])
        mx = cx - w / 2 - 70 * s
        polys.append([(mx - 22 * s, by), (mx - 22 * s, by - 470 * s), (mx, by - 560 * s), (mx + 22 * s, by - 470 * s), (mx + 22 * s, by)])
        for i in range(-2, 3):
            x = cx + i * 95 * s
            L.append((x - 22 * s, by - 20 * s, x - 22 * s, by - 110 * s))
            L.append((x + 22 * s, by - 20 * s, x + 22 * s, by - 110 * s))
            L.append((x - 22 * s, by - 110 * s, x + 22 * s, by - 110 * s))
    elif kind == "castle":
        w, h = 620 * s, 300 * s
        top = by - h
        pts = [(cx - w / 2, by), (cx - w / 2, top)]
        n = 9
        for i in range(n):
            x0 = cx - w / 2 + i * w / n
            pts += [(x0, top - (40 * s if i % 2 == 0 else 0)), (x0 + w / n, top - (40 * s if i % 2 == 0 else 0))]
        pts += [(cx + w / 2, top), (cx + w / 2, by)]
        polys.append(pts)
        polys.append([(cx - 60 * s, by), (cx - 60 * s, by - 120 * s), (cx, by - 170 * s), (cx + 60 * s, by - 120 * s), (cx + 60 * s, by)])
    elif kind == "house":
        w, h = 400 * s, 330 * s
        polys.append([(cx - w / 2, by), (cx - w / 2, by - h), (cx + w / 2, by - h), (cx + w / 2, by)])
        for r in range(2):
            for c in (-1, 1):
                x, y = cx + c * 100 * s, by - h + 80 * s + r * 130 * s
                L += [(x - 35 * s, y, x + 35 * s, y), (x - 35 * s, y, x - 35 * s, y + 80 * s), (x + 35 * s, y, x + 35 * s, y + 80 * s)]
        L.append((cx - w / 2 - 10 * s, by - h, cx + w / 2 + 10 * s, by - h))
    elif kind == "columns":
        w = 560 * s
        polys.append([(cx - w / 2 - 30 * s, by - 380 * s), (cx, by - 470 * s), (cx + w / 2 + 30 * s, by - 380 * s)])
        for i in range(6):
            x = cx - w / 2 + i * w / 5
            polys.append([(x - 24 * s, by), (x - 24 * s, by - 370 * s), (x + 24 * s, by - 370 * s), (x + 24 * s, by)])
    elif kind == "tower":
        polys.append([(cx - 80 * s, by), (cx - 60 * s, by - 520 * s), (cx + 60 * s, by - 520 * s), (cx + 80 * s, by)])
        polys.append([(cx - 75 * s, by - 520 * s), (cx, by - 640 * s), (cx + 75 * s, by - 520 * s)])
    else:   # bridge
        w = 700 * s
        polys.append([(cx - w / 2, by - 160 * s), (cx + w / 2, by - 160 * s), (cx + w / 2, by - 120 * s), (cx - w / 2, by - 120 * s)])
        for i in range(3):
            x = cx - w / 3 + i * w / 3
            arc = [(x + 100 * s * math.cos(a), by - 120 * s - 0 * s - 100 * s * math.sin(a) + 100 * s) for a in np.linspace(0, math.pi, 16)]
            L += [(arc[j][0], arc[j][1], arc[j + 1][0], arc[j + 1][1]) for j in range(len(arc) - 1)]
    return L, polys


def draw_building(img, show, t, dur, W, H, u):
    d = ImageDraw.Draw(img)
    cx, by = W / 2, H * 0.56
    L, polys = _building_lines(show.get("kind", "mosque"), cx, by, u)
    draw = ST.eo(t / 0.6)
    fill = ST.cl((t - 0.55) / 0.35)
    lw = max(2, int(5 * u))
    fc = PAL["cream"] if not show.get("glow") else (214, 196, 160)
    for poly in polys:
        if fill > 0:
            d.polygon(poly, fill=fc + (int(200 * fill),))
        n = max(2, int((len(poly) + 1) * draw))
        d.line((poly + [poly[0]])[:n], fill=PAL["white"] + (255,), width=lw)
    for i, (x0, y0, x1, y1) in enumerate(L):
        a = ST.cl((t - 0.3 - i * 0.02) / 0.2)
        if a > 0:
            d.line((x0, y0, x0 + (x1 - x0) * a, y0 + (y1 - y0) * a), fill=(70, 64, 58, 255) if fill > 0.5 else PAL["white"] + (255,), width=lw)
    d.line((0, by, W, by), fill=(90, 86, 84, 255), width=max(1, lw // 2))
    if show.get("label"):
        _stamp(img, ST.up(show["label"]), W * 0.68, H * 0.24, u, PAL["teal"], rot=-3, size=44)
    if show.get("tag"):
        tg = ST.cl((t - 0.7) / 0.2)
        if tg > 0:
            _stamp(img, ST.up(show["tag"]), W * 0.32, by + 70 * u, u, PAL["yellow"], rot=-6, size=50)
    _title(d, show, t, W, H, u) if show.get("title") else None


# ------------------------------------------------------------------ soru işareti
def draw_qmark(img, show, t, dur, W, H, u):
    d = ImageDraw.Draw(img)
    a = ST.cl(t / 0.3)
    wob = math.sin(t * 4) * 4
    q = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(q).text((W / 2, H * 0.40), "?", font=ST.F(760 * u * (0.85 + 0.15 * ST.eb(a)), 900), fill=(26, 22, 18, 255), anchor="mm")
    img.alpha_composite(q.rotate(wob + 8, center=(W / 2, H * 0.4), resample=Image.BICUBIC))
    if show.get("word"):
        f = _fit(d, ST.up(show["word"]), 130 * u, W * 0.85, 900)
        d.text((W / 2, H * 0.64), ST.up(show["word"]), font=f, fill=(26, 22, 18, int(255 * ST.cl((t - 0.4) / 0.2))), anchor="mm")


DRAW = dict(map=draw_map, sign=draw_sign, doc=draw_doc, podium=draw_podium, rank=draw_rank, ratio=draw_ratio,
            split=draw_split, tape=draw_tape, building=draw_building, qmark=draw_qmark)


def draw(img, show, t, dur, u):
    W, H = img.size
    DRAW[show["type"]](img, show, t, dur, W, H, u)


def bg_kind(show):
    return show.get("bg") or BG_OF.get(show.get("type"), "navy")
