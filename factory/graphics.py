"""Motion-graphics layer: text sprites, compositing, easing, post-processing."""
import os
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")
F_DISPLAY = os.path.join(FONT_DIR, "Anton-Regular.ttf")
F_BLACK = os.path.join(FONT_DIR, "Inter-Black.otf")
F_BOLD = os.path.join(FONT_DIR, "Inter-Bold.otf")
F_SYM = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")

RED = (255, 42, 52)
YELLOW = (255, 214, 0)
WHITE = (255, 255, 255)

_fc = {}


def font(path, size):
    k = (path, size)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(path, size)
    return _fc[k]


def tr_upper(s):
    return s.replace("i", "İ").replace("ı", "I").upper()


# ------------------------------------------------------------------ easing
def clamp01(x):
    return max(0.0, min(1.0, x))


def ease_out_cubic(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_out_back(x, s=1.9):
    x = clamp01(x)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def ease_in_out(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


# ------------------------------------------------------------------ sprites (RGBA uint8 numpy)
def text_sprite(text, fpath, size, fill=WHITE, stroke=0, stroke_fill=(0, 0, 0), shadow=True,
                glow=None, pad=40, tracking=0):
    f = font(fpath, size)
    if tracking:
        widths = [f.getlength(ch) + tracking for ch in text]
        w = int(sum(widths)) + pad * 2
    else:
        w = int(f.getlength(text)) + pad * 2
    asc, desc = f.getmetrics()
    h = asc + desc + pad * 2
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def draw_text(dd, xy, **kw):
        if tracking:
            x, y = xy
            for ch in text:
                dd.text((x, y), ch, font=f, **kw)
                x += f.getlength(ch) + tracking
        else:
            dd.text(xy, text, font=f, **kw)

    if shadow:
        sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw_text(ImageDraw.Draw(sh), (pad + 6, pad + 10), fill=(0, 0, 0, 170), stroke_width=stroke, stroke_fill=(0, 0, 0, 170))
        sh = sh.filter(ImageFilter.GaussianBlur(10))
        img = Image.alpha_composite(img, sh)
    if glow:
        gl = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw_text(ImageDraw.Draw(gl), (pad, pad), fill=glow + (255,), stroke_width=stroke + 6, stroke_fill=glow + (255,))
        gl = gl.filter(ImageFilter.GaussianBlur(18))
        img = Image.alpha_composite(img, gl)
    d = ImageDraw.Draw(img)
    draw_text(d, (pad, pad), fill=fill + (255,) if len(fill) == 3 else fill, stroke_width=stroke, stroke_fill=stroke_fill)
    return np.array(img)


def extruded_number(text, size=330, depth=22, front=WHITE, side=(150, 10, 20)):
    """Pseudo-3D extruded number (stacked layers) - motion-graphics 'rank' badge."""
    f = font(F_DISPLAY, size)
    pad = 60
    w = int(f.getlength(text)) + pad * 2 + depth
    asc, desc = f.getmetrics()
    h = asc + desc + pad * 2 + depth
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((pad + depth + 14, pad + depth + 20), text, font=f, fill=(0, 0, 0, 190))
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(16)))
    gl = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(gl).text((pad, pad), text, font=f, fill=RED + (255,), stroke_width=10, stroke_fill=RED + (255,))
    img = Image.alpha_composite(img, gl.filter(ImageFilter.GaussianBlur(28)))
    d = ImageDraw.Draw(img)
    for i in range(depth, 0, -1):
        k = 0.55 + 0.45 * (1 - i / depth)
        c = tuple(int(v * k) for v in side) + (255,)
        d.text((pad + i, pad + i), text, font=f, fill=c)
    # front face with vertical gradient
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((pad, pad), text, font=f, fill=255)
    grad = np.zeros((h, w, 4), np.uint8)
    t = np.linspace(0, 1, h)[:, None]
    top = np.array(front, np.float32)
    bot = np.array((255, 200, 200), np.float32)
    grad[..., :3] = (top * (1 - t[..., None]) + bot * t[..., None]).astype(np.uint8)[:, :, :] if False else \
        (top[None, None, :] * (1 - t[..., None]) + bot[None, None, :] * t[..., None]).astype(np.uint8)
    grad[..., 3] = np.array(mask)
    img = Image.alpha_composite(img, Image.fromarray(grad, "RGBA"))
    return np.array(img)


def pill(text, fpath, size, bg=(0, 0, 0, 160), fg=WHITE, padx=30, pady=16, radius=None, accent=None, icon=None,
         icon_col=RED):
    f = font(fpath, size)
    fi = font(F_SYM, int(size * 0.95))
    iw = int(fi.getlength(icon)) + 14 if icon else 0
    tw = int(f.getlength(text))
    asc, desc = f.getmetrics()
    h = asc + desc + pady * 2 - int(size * 0.12)
    w = tw + iw + padx * 2 + (14 if accent else 0)
    img = Image.new("RGBA", (w + 20, h + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = radius if radius is not None else h // 2
    d.rounded_rectangle((10, 10, 10 + w, 10 + h), r, fill=bg)
    x = 10 + padx
    if accent:
        d.rounded_rectangle((10, 10, 10 + 10, 10 + h), 4, fill=accent + (255,))
        x += 14
    if icon:
        d.text((x, 10 + pady - int(size * 0.02)), icon, font=fi, fill=icon_col + (255,))
        x += iw
    d.text((x, 10 + pady - int(size * 0.1)), text, font=f, fill=fg + (255,))
    return np.array(img)


def blit(frame, spr, x, y, alpha=1.0, scale=1.0, anchor="tl", clip_w=None):
    """Alpha-composite RGBA sprite onto RGB uint8 frame in place."""
    if alpha <= 0.003 or spr is None:
        return
    if scale != 1.0:
        if scale <= 0.01:
            return
        spr = cv2.resize(spr, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    h, w = spr.shape[:2]
    if anchor == "c":
        x, y = x - w / 2, y - h / 2
    elif anchor == "tc":
        x = x - w / 2
    elif anchor == "lc":
        y = y - h / 2
    x, y = int(round(x)), int(round(y))
    if clip_w is not None:
        spr = spr[:, : max(0, int(clip_w * w))]
        w = spr.shape[1]
        if w == 0:
            return
    H, W = frame.shape[:2]
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + w, W), min(y + h, H)
    if x1 <= x0 or y1 <= y0:
        return
    s = spr[y0 - y:y1 - y, x0 - x:x1 - x]
    a = s[..., 3:4].astype(np.float32) * (alpha / 255.0)
    roi = frame[y0:y1, x0:x1]
    roi[:] = (roi * (1 - a) + s[..., :3] * a).astype(np.uint8)


# ------------------------------------------------------------------ subtitles
def split_chunks(text, max_chars=20, max_words=3):
    words = text.split()
    chunks, cur = [], []
    for w in words:
        if cur and (len(" ".join(cur + [w])) > max_chars or len(cur) >= max_words):
            chunks.append(cur)
            cur = []
        cur.append(w)
        if w[-1] in ".?!,:;" and len(cur) >= 1:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def word_timings(text, start, dur):
    """Distribute words over the narration window proportional to their spoken length."""
    words = text.split()
    wts = [len(w) + 2.5 + (4 if w[-1] in ".?!" else 1.5 if w[-1] in ",:;" else 0) for w in words]
    tot = sum(wts)
    t = start
    out = []
    for w, k in zip(words, wts):
        d = dur * k / tot
        out.append((w, t, t + d))
        t += d
    return out


class Subtitles:
    """Karaoke-style word-highlight captions, sprites cached per (chunk, active word)."""

    def __init__(self, size=70):
        self.size = size
        self.cache = {}

    def sprite(self, words, active):
        key = (tuple(words), active)
        if key in self.cache:
            return self.cache[key]
        f = font(F_BLACK, self.size)
        txt = [tr_upper(w.rstrip(".,;:")) for w in words]
        space = f.getlength(" ")
        widths = [f.getlength(w) for w in txt]
        pad = 40
        W = int(sum(widths) + space * (len(txt) - 1)) + pad * 2
        asc, desc = f.getmetrics()
        H = asc + desc + pad * 2
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ds = ImageDraw.Draw(sh)
        x = pad
        for w, wd in zip(txt, widths):
            ds.text((x + 4, pad + 8), w, font=f, fill=(0, 0, 0, 200), stroke_width=9, stroke_fill=(0, 0, 0, 200))
            x += wd + space
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(8)))
        d = ImageDraw.Draw(img)
        x = pad
        for i, (w, wd) in enumerate(zip(txt, widths)):
            if i == active:
                d.rounded_rectangle((x - 14, pad + 4, x + wd + 14, pad + asc + desc - 2), 14, fill=RED + (255,))
                d.text((x, pad), w, font=f, fill=WHITE + (255,), stroke_width=4, stroke_fill=(120, 0, 0, 255))
            else:
                d.text((x, pad), w, font=f, fill=WHITE + (255,), stroke_width=8, stroke_fill=(0, 0, 0, 255))
            x += wd + space
        arr = np.array(img)
        self.cache[key] = arr
        return arr

    def draw(self, frame, timings, t, cx, cy):
        if not timings:
            return
        # group into chunks
        chunks = split_chunks(" ".join(w for w, _, _ in timings))
        i = 0
        for ch in chunks:
            seg = timings[i:i + len(ch)]
            i += len(ch)
            c0, c1 = seg[0][1], seg[-1][2]
            if c0 - 0.02 <= t < c1 + 0.12:
                active = -1
                for j, (_, a, b) in enumerate(seg):
                    if a <= t < b:
                        active = j
                spr = self.sprite([w for w, _, _ in seg], active)
                p = (t - c0) / 0.12
                sc = 0.75 + 0.25 * ease_out_back(p, 2.2)
                blit(frame, spr, cx, cy, alpha=clamp01(p * 2), scale=sc, anchor="c")
                return


# ------------------------------------------------------------------ post-processing
class Post:
    def __init__(self, W, H, seed=0):
        self.W, self.H = W, H
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
        self.vig = np.clip(1.15 - 0.42 * d ** 2.2, 0.35, 1)[..., None].astype(np.float32)
        rng = np.random.default_rng(seed)
        self.grain = [rng.normal(0, 6, (H // 2, W // 2)).astype(np.float32) for _ in range(8)]
        lut = np.arange(256) / 255.0
        lut = lut + 0.12 * np.sin(2 * np.pi * lut) * -0.5 + 0.0   # gentle S-curve
        lut = np.clip(0.5 + (lut - 0.5) * 1.12, 0, 1)
        self.lut = (lut * 255).astype(np.uint8)

    def grade_low(self, img):
        """img float RGB 0..1 at render res -> filmic tone map + saturation."""
        img = np.maximum(img, 0)
        img = img * 1.08
        img = img / (1 + img * 0.18)                    # soft shoulder
        lum = img.mean(-1, keepdims=True)
        img = lum + (img - lum) * 1.18
        return np.clip(img, 0, 1)

    def finish(self, frame, fi):
        # bloom
        small = cv2.resize(frame, (self.W // 8, self.H // 8), interpolation=cv2.INTER_AREA).astype(np.float32)
        br = np.clip(small - 170, 0, None)
        br = cv2.GaussianBlur(br, (0, 0), 6)
        bloom = cv2.resize(br, (self.W, self.H), interpolation=cv2.INTER_LINEAR)
        f = frame.astype(np.float32) * self.vig + bloom * 0.9
        g = cv2.resize(self.grain[fi % 8], (self.W, self.H), interpolation=cv2.INTER_NEAREST)
        f += g[..., None]
        f = np.clip(f, 0, 255).astype(np.uint8)
        return cv2.LUT(f, self.lut)


def rgb_split(frame, amt):
    if amt < 1:
        return frame
    a = int(amt)
    out = frame.copy()
    out[:, a:, 0] = frame[:, :-a, 0]
    out[:, :-a, 2] = frame[:, a:, 2]
    return out


def zoom_blur(frame, zoom, blur):
    H, W = frame.shape[:2]
    if abs(zoom - 1) > 1e-3:
        M = cv2.getRotationMatrix2D((W / 2, H / 2), 0, zoom)
        frame = cv2.warpAffine(frame, M, (W, H), borderMode=cv2.BORDER_REFLECT)
    if blur >= 2:
        k = int(blur) | 1
        frame = cv2.blur(frame, (k, 1))
    return frame


def shake(frame, amt, t):
    if amt < 0.5:
        return frame
    H, W = frame.shape[:2]
    dx = amt * np.sin(t * 91.0) * 1.0
    dy = amt * np.cos(t * 77.0) * 0.8
    M = np.float32([[1.02, 0, dx - W * 0.01], [0, 1.02, dy - H * 0.01]])
    return cv2.warpAffine(frame, M, (W, H), borderMode=cv2.BORDER_REFLECT)
