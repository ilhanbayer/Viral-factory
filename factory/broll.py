"""B-roll ve etkileşim katmanı (Kasım 2026):
- Fotoğraf havuzu: her videoda konuyla ilgili çok sayıda gerçek (Commons) fotoğraf.
- Çekimler: her sahne ~2,2 sn'lik çekimlere bölünür; her çekimde başka bir fotoğraf tam ekran,
  hızlı Ken Burns + 2.5D perspektif eğim + ışık süpürmesi ile hareket eder -> ekran hiç sabit kalmaz.
- CTA animasyonları: video ortasında BEĞEN + YORUM YAZ, sonunda TAKİP ET butonuna tıklama animasyonu."""
import math
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import story as ST

SHOT = 2.2      # saniye: bir çekimin uzunluğu
_CACHE = {}
UI = {
    "tr": dict(like="BEĞEN", comment="YORUM YAZ", follow="TAKİP ET", followed="TAKİP EDİLDİ"),
    "en": dict(like="LIKE", comment="COMMENT", follow="FOLLOW", followed="FOLLOWING"),
    "de": dict(like="GEFÄLLT MIR", comment="KOMMENTIEREN", follow="FOLGEN", followed="GEFOLGT"),
}
LOGO = {"brand": "İLGİNÇ BİLGİLER", "mono": "İB"}


def _ease(x):
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def load_bd(path, W, H):
    """Fotoğrafı tam ekran b-roll için hazırla: 1.25x kapla, hafif yumuşat, renk biraz korunur, karartılır."""
    key = (path, W, H)
    if key in _CACHE:
        return _CACHE[key]
    out = None
    try:
        im = Image.open(path).convert("RGB")
        k = 1.25
        sc = max(W * k / im.width, H * k / im.height)
        im = im.resize((int(im.width * sc) + 2, int(im.height * sc) + 2), Image.LANCZOS)
        im = im.filter(ImageFilter.GaussianBlur(1.2 * min(W, H) / 1080))
        a = np.array(im).astype(np.float32)
        g = a.mean(-1, keepdims=True)
        tone = np.array(ST.C["paper"], np.float32) / 255
        a = (g * 0.35 + a * 0.65) * (0.55 + 0.45 * tone)   # sıcak, belgesel tonu
        hh, ww = a.shape[:2]
        yy, xx = np.mgrid[0:hh, 0:ww].astype(np.float32)
        d = np.sqrt(((xx - ww / 2) / (ww / 2)) ** 2 + ((yy - hh / 2) / (hh / 2)) ** 2)
        a *= (0.58 * np.clip(1.3 - 0.7 * d, 0.3, 1))[..., None]
        out = np.clip(a, 0, 255).astype(np.uint8)
    except Exception as e:
        print("  [b-roll] okunamadı:", path, type(e).__name__)
    _CACHE[key] = out
    return out


def shot_frame(bd, W, H, t, dur, seed):
    """Tek çekim: yön ve hareket tohumdan; yakınlaşma/uzaklaşma + kayma + perspektif eğim."""
    rng = np.random.default_rng(seed)
    hh, ww = bd.shape[:2]
    p = min(1.0, t / max(dur, 0.1))
    zin = rng.random() < 0.6
    z0, z1 = (1.0, 1.14) if zin else (1.14, 1.0)
    z = z0 + (z1 - z0) * (0.5 - 0.5 * math.cos(math.pi * p))
    ax, ay = rng.uniform(-1, 1), rng.uniform(-1, 1)
    cw, ch = ww / z / 1.25 * 1.0, hh / z / 1.25
    cx = ww / 2 + ax * (ww - cw) * 0.45 * (p - 0.5) * 2
    cy = hh / 2 + ay * (hh - ch) * 0.45 * (p - 0.5) * 2
    tilt = (rng.uniform(0.02, 0.05) * (1 if rng.random() < 0.5 else -1)) * math.sin(math.pi * p)
    x0, y0, x1, y1 = cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2
    dx = tilt * cw
    src = np.float32([[x0 + dx, y0], [x1 - dx, y0], [x1 + dx, y1], [x0 - dx, y1]])
    dst = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    M = cv2.getPerspectiveTransform(src, dst)
    fr = cv2.warpPerspective(bd, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    # ışık süpürmesi (cam parlaması gibi geçen ince bant)
    sweep = (t * 0.35 + rng.random()) % 1.6 - 0.3
    if 0 < sweep < 1:
        xs = np.arange(W, dtype=np.float32)
        band = np.exp(-((xs - sweep * W * 1.3 + 0.15 * W) / (W * 0.08)) ** 2) * 28
        fr = np.clip(fr.astype(np.float32) + band[None, :, None], 0, 255).astype(np.uint8)
    return fr


def build_pool(beats):
    """Videodaki tüm yerel fotoğraflar (ilk görünme sırasıyla, tekrarsız)."""
    pool = []
    for b in beats:
        sh = b.get("show", {})
        for p in [sh.get("_local")] + list(sh.get("_extra", [])):
            if p and p not in pool and os.path.exists(p):
                pool.append(p)
    return pool


def fill_missing_photos(beats, pool):
    """Fotoğrafı bulunamayan 'photo' sahnelerine (ikon yerine) havuzdan gerçek fotoğraf ver."""
    if not pool:
        return 0
    own = {b.get("show", {}).get("_local") for b in beats}
    spare = [p for p in pool if p not in own] or list(pool)
    n = 0
    for b in beats:
        sh = b.get("show", {})
        if sh.get("type") == "photo" and not sh.get("_local"):
            sh["_local"] = spare[n % len(spare)]
            n += 1
    return n


def assign_shots(segs, pool):
    """Her sahneye çekim listesi: [(başlangıç_sn, foto_yolu, tohum)]. Sahne animasyonlarında b-roll yok."""
    k = 0
    for s in segs:
        sh = s["beat"].get("show", {})
        if sh.get("type") == "scene" or not pool:
            s["shots"] = []
            continue
        n = max(1, int(round(s["dur"] / SHOT)))
        shots = []
        own = sh.get("_local")
        for j in range(n):
            if j == 0 and own:
                path = own
            else:
                path = pool[k % len(pool)]
                k += 1
            shots.append((j * s["dur"] / n, path, s["i"] * 31 + j * 7))
        s["shots"] = shots


def current_shot(s, t):
    cur = None
    for i, sh in enumerate(s.get("shots", [])):
        if t >= sh[0]:
            cur = (i, sh)
    return cur


# ------------------------------------------------------------------ CTA (beğen / yorum / takip)
def _thumb(d, cx, cy, s, col):
    d.rounded_rectangle((cx - s * 0.42, cy - s * 0.05, cx - s * 0.18, cy + s * 0.45), radius=int(s * 0.05), fill=col)
    d.rounded_rectangle((cx - s * 0.12, cy - s * 0.05, cx + s * 0.42, cy + s * 0.45), radius=int(s * 0.12), fill=col)
    d.polygon([(cx - s * 0.12, cy), (cx + s * 0.02, cy - s * 0.45), (cx + s * 0.14, cy - s * 0.42),
               (cx + s * 0.1, cy - s * 0.05)], fill=col)


def _bubble(d, cx, cy, s, col):
    d.rounded_rectangle((cx - s * 0.45, cy - s * 0.35, cx + s * 0.45, cy + s * 0.25), radius=int(s * 0.18), fill=col)
    d.polygon([(cx - s * 0.2, cy + s * 0.2), (cx - s * 0.32, cy + s * 0.45), (cx + s * 0.02, cy + s * 0.22)], fill=col)
    for i in (-1, 0, 1):
        d.ellipse((cx + i * s * 0.2 - s * 0.06, cy - s * 0.1, cx + i * s * 0.2 + s * 0.06, cy + s * 0.02),
                  fill=(30, 30, 34))


def _bell(d, cx, cy, s, col, ang):
    pts = []
    for k in range(13):
        a = math.pi * k / 12
        pts.append((cx - s * 0.38 * math.cos(a) * (1 if k else 1), cy + s * 0.25 - s * 0.55 * math.sin(a)))
    c, sn = math.cos(ang), math.sin(ang)
    rot = lambda p: (cx + (p[0] - cx) * c - (p[1] - cy + s * 0.3) * sn, cy - s * 0.3 + (p[0] - cx) * sn + (p[1] - cy + s * 0.3) * c)
    d.polygon([rot(p) for p in pts + [(cx + s * 0.45, cy + s * 0.3), (cx - s * 0.45, cy + s * 0.3)]], fill=col)
    bx, by = rot((cx, cy + s * 0.42))
    d.ellipse((bx - s * 0.09, by - s * 0.09, bx + s * 0.09, by + s * 0.09), fill=col)


def cta_layer(W, H, kind, t, u, brand=None):
    """kind: 'like' (orta) ya da 'follow' (son). t: CTA başlangıcından beri sn. RGBA katman döner ya da None."""
    D = 2.8 if kind == "like" else 3.2
    if t < 0 or t > D:
        return None
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    tx = UI.get(ST.LANG, UI["en"])
    brand = brand or LOGO["brand"]
    a_in = _ease(t / 0.35)
    a_out = 1 - _ease((t - (D - 0.35)) / 0.35)
    a = max(0.0, min(a_in, a_out))
    sc = 0.6 + 0.4 * ST.eb(min(1, t / 0.4)) if t < 0.4 else 1.0
    y = H * (0.83 if H > W else 0.78)
    white, red, dark = (255, 255, 255, int(255 * a)), ST.C["red"] + (int(255 * a),), (20, 20, 24, int(230 * a))
    if kind == "like":
        s = 120 * u * sc
        gap = 30 * u
        w1, w2 = 330 * u * sc, 380 * u * sc
        x0 = W / 2 - (w1 + w2 + gap) / 2
        # BEĞEN
        d.rounded_rectangle((x0, y - s / 2, x0 + w1, y + s / 2), radius=int(s / 2), fill=dark)
        bump = 1 + 0.25 * max(0, math.sin((t - 0.5) * 9)) * (0.5 < t < 1.2)
        tcol = red if t > 0.6 else white
        _thumb(d, x0 + s * 0.55, y - s * 0.03, s * 0.55 * bump, tcol)
        d.text((x0 + s * 1.0, y), tx["like"], font=ST.F(int(46 * u * sc), 900), fill=white, anchor="lm")
        # küçük kalpler
        if 0.6 < t < 1.6:
            for k in range(5):
                p = (t - 0.6) / 1.0
                hx = x0 + s * 0.55 + math.sin(k * 2.1) * 60 * u * p
                hy = y - s * 0.4 - 140 * u * p - k * 12 * u
                r = 12 * u * (1 - p)
                d.ellipse((hx - r, hy - r, hx + r, hy + r), fill=ST.C["red"] + (int(220 * a * (1 - p)),))
        # YORUM YAZ
        x1 = x0 + w1 + gap
        d.rounded_rectangle((x1, y - s / 2, x1 + w2, y + s / 2), radius=int(s / 2), fill=dark)
        _bubble(d, x1 + s * 0.55, y, s * 0.55, white)
        d.text((x1 + s * 1.0, y), tx["comment"], font=ST.F(int(46 * u * sc), 900), fill=white, anchor="lm")
    else:
        s = 130 * u * sc
        w = 640 * u * sc
        x0 = W / 2 - w / 2
        clicked = t > 1.25
        d.rounded_rectangle((x0, y - s / 2, x0 + w, y + s / 2), radius=int(s / 2), fill=dark)
        # logo dairesi
        lx = x0 + s * 0.55
        d.ellipse((lx - s * 0.38, y - s * 0.38, lx + s * 0.38, y + s * 0.38), fill=(255, 205, 40, int(255 * a)))
        d.text((lx, y + 2 * u), LOGO["mono"], font=ST.F(int(40 * u * sc), 900), fill=(20, 20, 20, int(255 * a)), anchor="mm")
        d.text((x0 + s * 1.05, y), brand, font=ST.F(int(34 * u * sc), 800), fill=white, anchor="lm")
        bw = 250 * u * sc
        bx0 = x0 + w - bw - 18 * u
        press = 0.92 if 1.1 < t < 1.3 else 1.0
        bh = (s - 30 * u) * press
        d.rounded_rectangle((bx0, y - bh / 2, bx0 + bw, y + bh / 2), radius=int(bh / 2),
                            fill=((70, 70, 76, int(255 * a)) if clicked else red))
        d.text((bx0 + bw / 2, y), tx["followed"] if clicked else tx["follow"],
               font=ST.F(int((30 if clicked else 40) * u * sc), 900), fill=white, anchor="mm")
        # zil
        if clicked:
            ang = 0.5 * math.sin((t - 1.25) * 22) * max(0, 1 - (t - 1.25) / 1.2)
            _bell(d, x0 + w + 70 * u, y, 90 * u, (255, 205, 40, int(255 * a)), ang)
        # el / imleç
        if t < 1.6:
            p = _ease((t - 0.3) / 0.8)
            hx = bx0 + bw * 0.6 + (1 - p) * 220 * u
            hy = y + 40 * u + (1 - p) * 260 * u
            d.ellipse((hx - 26 * u, hy - 26 * u, hx + 26 * u, hy + 26 * u), fill=(255, 255, 255, int(235 * a)),
                      outline=(20, 20, 20, int(255 * a)), width=max(2, int(4 * u)))
            if 1.1 < t < 1.45:
                r = (t - 1.1) * 260 * u
                d.ellipse((hx - r, hy - r, hx + r, hy + r), outline=(255, 255, 255, int(200 * (1 - (t - 1.1) / 0.35))),
                          width=max(2, int(5 * u)))
    return layer


def cta_times(total):
    """(başlangıç, tür) listesi: ortada beğen+yorum, sonda takip."""
    out = []
    if total > 12:
        out.append((total * 0.42, "like"))
    out.append((max(0.0, total - 3.4), "follow"))
    return out
