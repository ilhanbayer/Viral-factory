"""Hikâye formatı: senaryo -> (1 yatay uzun video + N dikey Shorts) üretimi."""
import json
import math
import re
import os
import subprocess
import time
from multiprocessing import Pool

import numpy as np
import cv2
from PIL import Image, ImageFilter

from . import tts
from . import audio as A
from . import story as ST
from . import broll as BR
from .graphics import word_timings

FPS = 30
FMT = {
    "vertical": dict(W=1080, H=1920, u=1.0, cy=0.42, cap_y=0.75, cap_u=1.0),
    "landscape": dict(W=1920, H=1080, u=0.66, cy=0.43, cap_y=0.87, cap_u=0.85),
}


# ------------------------------------------------------------------ timeline
def build(beats, work, use_tts=True):
    vcache = os.path.join(work, "voice")
    segs, t = [], 0.0
    n = len(beats)
    for i, b in enumerate(beats):
        say = b["say"].replace("*", "")
        role = "intro" if i == 0 else ("outro" if i == n - 1 else "story")
        if use_tts:
            wav, vd, words = tts.synth(say, vcache, role)
        else:
            wav, vd, words = None, tts.estimate_duration(say), None
        lead = 0.12
        dur = max(1.5, lead + vd + (0.5 if b.get("sfx") in ("hit", "riser") else 0.3))
        tim = tts.align_words(say, words, lead, vd) or word_timings(say, lead, vd)
        segs.append(dict(i=i, start=t, dur=dur, voff=lead, vdur=vd, wav=wav, beat=b, words=tim,
                         kinds=ST.caption_words(b["say"])))
        t += dur
    return segs, t


# ------------------------------------------------------------------ render
def _grain(H, W, k):
    rng = np.random.default_rng(k)
    return cv2.resize(rng.normal(0, 7, (H // 3, W // 3)).astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR)


TRANS = ["whip", "zoom", "glitch", "whip", "flash", "zoom"]


def _keyword(beat):
    for w in beat["say"].split():
        if "*" in w:
            return ST.up(w.replace("*", "").strip(".,!?;:"))
    return ""


def _hot_times(s):
    """Vurgulu (*) kelimelerin söylenme anları -> kamera darbesi + ses."""
    out = []
    for i, (w, k) in enumerate(s["kinds"]):
        if k == "red" and i < len(s["words"]):
            out.append(s["words"][i][1])
    return out


_BD = {}
BACKDROP_FALLBACK = [None]   # videoda hiç foto yoksa kapak fotoğrafı


def _backdrop(path, W, H):
    """Belgesel arka planı: ilgili arşiv fotoğrafı, tam ekran, hafif bulanık, tema tonunda ve karartılmış.
    Boş/siyah zemin yerine her karede gerçek bir doku olur."""
    key = (path, W, H)
    if key in _BD:
        return _BD[key]
    out = None
    try:
        im = Image.open(path).convert("RGB")
        k = 1.16
        sc = max(W * k / im.width, H * k / im.height)
        im = im.resize((int(im.width * sc) + 2, int(im.height * sc) + 2), Image.LANCZOS)
        im = im.filter(ImageFilter.GaussianBlur(9 * min(W, H) / 1080))
        a = np.array(im).astype(np.float32)
        g = a.mean(-1, keepdims=True)
        tone = np.array(ST.C["paper"], np.float32) / 255
        a = (g * 0.75 + a * 0.25) * tone
        hh, ww = a.shape[:2]
        yy, xx = np.mgrid[0:hh, 0:ww].astype(np.float32)
        d = np.sqrt(((xx - ww / 2) / (ww / 2)) ** 2 + ((yy - hh / 2) / (hh / 2)) ** 2)
        a *= (0.30 * np.clip(1.25 - 0.75 * d, 0.25, 1))[..., None]
        out = a.astype(np.float32)
    except Exception as e:
        print("  [arka plan] okunamadı:", path, type(e).__name__)
    _BD[key] = out
    return out


def _bd_frame(bd, W, H, gt, t, D):
    hh, ww = bd.shape[:2]
    fx = 0.5 + 0.45 * math.sin(gt * 0.07)
    fy = 0.5 + 0.45 * math.cos(gt * 0.05)
    x0, y0 = int((ww - W) * fx), int((hh - H) * fy)
    return bd[y0:y0 + H, x0:x0 + W]


def assign_backdrops(segs, extra=None):
    """Her sahneye en yakın fotoğrafı arka plan olarak ata (önce kendisi, sonra önceki, sonra sonraki)."""
    paths = [s["beat"].get("show", {}).get("_local") for s in segs]
    for i, s in enumerate(segs):
        typ = s["beat"].get("show", {}).get("type", "title")
        if typ == "scene":
            s["bd"] = None
            continue
        cand = [paths[j] for j in list(range(i, -1, -1)) + list(range(i + 1, len(segs))) if paths[j]]
        s["bd"] = cand[0] if cand else extra


def render_chunk(args):
    segs, fmt, brand, theme, out_path, preview, total = (list(args) + [None])[:7]
    cv2.setNumThreads(1)
    ST.set_theme(theme)
    ST.LANG = segs[0].get("lang", "tr")
    P = FMT[fmt]
    W, H, u = P["W"], P["H"], P["u"]
    hu = 1.0 if fmt == "vertical" else 0.85
    cx, cy = W / 2, H * P["cy"]
    total = total or (segs[-1]["start"] + segs[-1]["dur"])
    bg = ST.background(W, H)
    atm = ST.Atmosphere(W, H, seed=int(segs[0]["start"]))
    grains = [_grain(H, W, k) for k in range(6)]
    brand_spr = ST.brand_sprite(brand, 1.0 if fmt == "vertical" else 0.8)
    _m = re.search(r"(\d+)\s*/\s*(\d+)\s*$", brand or "")
    series_kn = (int(_m.group(1)), int(_m.group(2))) if _m and 1 < int(_m.group(2)) <= 12 else None
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    vig_r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    red_vig = np.clip(vig_r - 0.55, 0, 1)[..., None] ** 1.5
    if preview is None:
        tmp = out_path[:-4] + ".part.mp4"
        proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                 "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                                 "-crf", "21", "-maxrate", "8M", "-bufsize", "16M", "-pix_fmt", "yuv420p", tmp],
                                stdin=subprocess.PIPE)
    shots = []
    fi = 0
    for s in segs:
        D = s["dur"]
        frames = [int(x * FPS) for x in preview] if preview is not None else range(int(round(D * FPS)))
        show = s["beat"].get("show", {"type": "title", "lines": [s["beat"]["say"][:20]]})
        kw = _keyword(s["beat"])
        hot = _hot_times(s)
        trans = TRANS[s["i"] % len(TRANS)] if s["i"] > 0 else "zoom"
        hit = s["beat"].get("sfx") == "hit"
        for k in frames:
            t = k / FPS
            gt = s["start"] + t
            fr = atm.apply(bg, gt, ST.C["glow"])
            cs = BR.current_shot(s, t)
            bdp = None if cs else s.get("bd")
            if cs:
                si, (t0s, sp, seed) = cs
                bdi = BR.load_bd(sp, W, H)
                if bdi is not None:
                    nxt = s["shots"][si + 1][0] if si + 1 < len(s["shots"]) else D
                    sf = BR.shot_frame(bdi, W, H, t - t0s, nxt - t0s, seed).astype(np.float32)
                    fr = np.clip(sf + fr.astype(np.float32) * 0.25, 0, 255)
                    if si > 0 and t - t0s < 0.12:   # çekim içi kesme: kısa flaş
                        fr = fr + 90 * (1 - (t - t0s) / 0.12)
                    fr = np.clip(fr, 0, 255).astype(np.uint8)
            if bdp:
                bd = _backdrop(bdp, W, H)
                if bd is not None:
                    fr = np.clip(_bd_frame(bd, W, H, gt, t, D) + fr.astype(np.float32) * 0.55, 0, 255).astype(np.uint8)
            ST.ghost_word(fr, kw, t, D, W, H, u)
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ST.draw_visual(layer, show, t, D, cx, cy, u)
            la = np.array(layer)
            # sürekli kamera hareketi + vurgulu kelimede darbe
            punch = sum(max(0.0, 1 - (t - h) / 0.28) for h in hot if t >= h)
            zin = ST.eo(t / 0.18)
            sc = 1.0 + 0.08 * (t / D) + 0.07 * (1 - zin) + 0.05 * min(1, punch) + (0.04 if show.get("type") == "scene" else 0)
            ang = 0.8 * math.sin(gt * 0.35) + (1.2 * math.sin(t * 40) * max(0, 1 - t / 0.3) if hit else 0)
            dx = 14 * u * math.sin(gt * 0.5) + 6 * u * math.sin(t * 50) * min(1, punch)
            dy = 10 * u * math.cos(gt * 0.4)
            M_ = cv2.getRotationMatrix2D((cx, cy), ang, sc)
            M_[0, 2] += dx
            M_[1, 2] += dy
            la = cv2.warpAffine(la, M_, (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
            a = la[..., 3:4].astype(np.float32) / 255 * min(1.0, 0.25 + zin)
            f = fr.astype(np.float32) * (1 - a) + la[..., :3].astype(np.float32) * a
            f += grains[(fi + k) % 6][..., None]
            # kırmızı nabız (gerilim anı)
            pulse = (max(0, 1 - t / 0.6) if hit else 0) + 0.35 * min(1, punch)
            if pulse > 0.01:
                f += red_vig * np.array(ST.C["red"], np.float32) * 0.55 * pulse
            fr = np.clip(f, 0, 255).astype(np.uint8)
            fr = ST.transition(fr, trans, t, s["i"]) if s["i"] > 0 else fr
            ST.hud(fr, gt, total, W, H, hu)
            ST.draw_caption(fr, s["kinds"], s["words"], t, W / 2, H * P["cap_y"], P["cap_u"])
            for (ct0, kind) in BR.cta_times(total):
                if 0 <= gt - ct0 <= 3.3:
                    cl_ = BR.cta_layer(W, H, kind, gt - ct0, P["cap_u"])
                    if cl_ is not None:
                        ca = np.array(cl_)
                        al_ = ca[..., 3:4].astype(np.float32) / 255
                        fr = (fr * (1 - al_) + ca[..., :3] * al_).astype(np.uint8)
            bh, bw = brand_spr.shape[:2]
            by, bx = int(40 * P["cap_u"]), int((W - bw) / 2) if fmt == "vertical" else int(50)
            al = brand_spr[..., 3:4].astype(np.float32) / 255
            fr[by:by + bh, bx:bx + bw] = (fr[by:by + bh, bx:bx + bw] * (1 - al) + brand_spr[..., :3] * al).astype(np.uint8)
            if series_kn and fmt == "vertical":
                _series_bar(fr, series_kn, gt / max(total, 0.1), W, by + bh + int(12 * P["cap_u"]), P["cap_u"])
            if preview is not None:
                shots.append(fr)
            else:
                proc.stdin.write(fr.tobytes())
        fi += len(frames) if preview is None else 1
    if preview is not None:
        return shots
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg")
    os.replace(tmp, out_path)
    return out_path


COMMONS = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "viral-factory/1.0 (https://github.com/ilhanbayer/viral-factory)"}
OK_LIC = ("public domain", "pd", "cc0", "cc by", "cc-by", "cc by-sa", "cc-by-sa")
CREDITS = []


def _get_json(url):
    import urllib.request
    req = urllib.request.Request(url, headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=40).read())


def _strip_html(s):
    import re
    return re.sub(r"<[^>]+>", "", s or "").strip()


USED_TITLES = set()


def _commons_search(query):
    """Arama: sonuç yoksa sorguyu sondan kelime atarak gevşet (çok kelimeli aramalar boş dönüyordu)."""
    import urllib.parse
    words = query.split()
    tried = []
    while words:
        qq = " ".join(words)
        tried.append(qq)
        q = urllib.parse.urlencode({"action": "query", "list": "search", "srnamespace": 6, "srlimit": 20,
                                    "srsearch": qq + " filetype:bitmap", "format": "json"})
        try:
            res = [r["title"] for r in _get_json(COMMONS + "?" + q)["query"]["search"]]
        except Exception as e:
            res = None
            for _ in range(2):   # oran sınırı / boş yanıt: bekle ve yeniden dene
                time.sleep(2)
                try:
                    res = [r["title"] for r in _get_json(COMMONS + "?" + q).get("query", {}).get("search", [])]
                    break
                except Exception:
                    res = None
            if res is None:
                print("  [commons] arama hatası", type(e).__name__)
                return []
        res = [t for t in res if not any(b in t.lower() for b in ("map", "harita", "logo", "flag of", "coat of arms", ".svg"))]
        if len([t for t in res if t not in USED_TITLES]) >= 1:
            if len(tried) > 1:
                print("  [commons] gevşetilmiş arama:", qq)
            return res
        if len(words) <= 1:
            break
        words = words[:-1]
    return []


def commons_lookup(title=None, query=None, min_w=700):
    """Wikimedia Commons: dosya adından ya da aramadan serbest lisanslı görsel bul.
    Aynı videoda kullanılmış dosyayı tekrar seçmez. Döner: (thumb_url, credit_text) ya da (None, None)."""
    import urllib.parse
    titles = []
    if title:
        titles = [title if title.startswith("File:") else "File:" + title]
    elif query:
        titles = _commons_search(query)
    for tt in titles:
        if tt in USED_TITLES and not title:
            continue
        q = urllib.parse.urlencode({"action": "query", "titles": tt, "prop": "imageinfo", "redirects": 1,
                                    "iiprop": "url|size|extmetadata|mime", "iiurlwidth": 1600, "format": "json"})
        try:
            pages = _get_json(COMMONS + "?" + q)["query"]["pages"]
        except Exception:
            continue
        for pg in pages.values():
            ii = (pg.get("imageinfo") or [{}])[0]
            if not ii or ii.get("width", 0) < min_w or "image" not in ii.get("mime", "image"):
                continue
            md = ii.get("extmetadata", {})
            lic = _strip_html(md.get("LicenseShortName", {}).get("value", ""))
            if not any(k in lic.lower() for k in OK_LIC):
                continue
            artist = _strip_html(md.get("Artist", {}).get("value", "")) or "Bilinmiyor"
            if artist.lower().startswith("anonymous"):
                artist = "Anonim"
            USED_TITLES.add(tt)
            USED_TITLES.add(pg.get("title", tt))
            return ii.get("thumburl") or ii.get("url"), f"{artist[:80]} ({lic}) — {pg.get('title')}"
    return None, None


def _download(url, cache):
    import hashlib
    import urllib.request
    fn = os.path.join(cache, hashlib.md5(url.encode()).hexdigest()[:12] + ".img")
    if not os.path.exists(fn):
        try:
            req = urllib.request.Request(url, headers=UA)
            open(fn, "wb").write(urllib.request.urlopen(req, timeout=60).read())
        except Exception as e:
            print("  [foto] indirilemedi:", url[:80], type(e).__name__)
            return None
    return fn


def fetch_extra(query, cache, n=2):
    """Aynı aramadan n tane daha (farklı) fotoğraf: b-roll havuzu için."""
    os.makedirs(cache, exist_ok=True)
    out = []
    if n <= 0:
        return out
    try:
        titles = _commons_search(query)
    except Exception:
        return out
    for tt in titles:
        if len(out) >= n:
            break
        if tt in USED_TITLES:
            continue
        url, credit = commons_lookup(title=tt)
        if not url:
            USED_TITLES.add(tt)
            continue
        fn = _download(url, cache)
        if fn:
            out.append(fn)
            if credit and credit not in CREDITS:
                CREDITS.append(credit)
    return out


def fetch_broll(terms, cache, n=3):
    paths = []
    for q in terms or []:
        paths += fetch_extra(q, cache, n)
    return paths


def fetch_photos(beats, cache):
    """'photo' sahneleri: url, commons (dosya adı) ya da search (arama) ile telifsiz görsel indir.
    Bulunamazsa 'fallback_scene' varsa sahne canlandırmasına, yoksa ikona düşer."""
    import hashlib
    import urllib.request
    os.makedirs(cache, exist_ok=True)
    for b in beats:
        sh = b.get("show", {})
        if sh.get("type") != "photo" or sh.get("_local"):
            continue
        url, credit = sh.get("url"), sh.get("credit")
        if not url and (sh.get("commons") or sh.get("search")):
            url, credit = commons_lookup(sh.get("commons"), sh.get("search"))
            if not url and sh.get("commons") and sh.get("search"):
                url, credit = commons_lookup(None, sh.get("search"))
        fn = None
        if url:
            fn = os.path.join(cache, hashlib.md5(url.encode()).hexdigest()[:12] + ".img")
            if not os.path.exists(fn):
                try:
                    req = urllib.request.Request(url, headers=UA)
                    open(fn, "wb").write(urllib.request.urlopen(req, timeout=60).read())
                except Exception as e:
                    print("  [foto] indirilemedi:", url[:80], type(e).__name__)
                    fn = None
        if not fn:
            print("  [foto] bulunamadı:", sh.get("commons") or sh.get("search") or sh.get("url"))
            fb = sh.get("fallback_show") or sh.get("fallback_scene")
            if fb and fb.get("type") == "icon" and fb.get("name", "camera") == "camera":
                fb = None   # boş kamera ikonu yerine havuzdan gerçek fotoğraf (fill_missing_photos)
            if fb:   # fotoğraf yoksa canlandırma ya da bilgi kartı
                b["show"] = dict(fb)
                b["show"].setdefault("type", "scene")
                if b["show"]["type"] == "scene":
                    b["show"].setdefault("label", sh.get("label"))
            continue
        sh["_local"] = fn
        if credit and credit not in CREDITS:
            CREDITS.append(credit)
        if sh.get("search") and not sh.get("_extra_done"):
            sh["_extra_done"] = True
            sh["_extra"] = fetch_extra(sh["search"], cache, n=int(sh.get("extra", 2)))


# ------------------------------------------------------------------ audio
def plan_audio(segs, total):
    sfx, voices, events = [], [], []
    inten, wind = [(0, 0.15)], [(0, 0.25), (total, 0.25)]
    n = len(segs)
    for s in segs:
        st, b = s["start"], s["beat"]
        show = b.get("show", {})
        typ = show.get("type")
        if s["wav"]:
            voices.append((st + s["voff"], s["wav"]))
        if s["i"] > 0:
            sfx.append((st - 0.15, "whoosh", {"d": 0.4, "seed": s["i"]}, 0.45))
            if s["i"] % 6 == 2:
                sfx.append((st, "glitch", {"seed": s["i"]}, 0.35))
        for h in _hot_times(s):
            sfx.append((st + h, "impact", {"pitch": 70, "d": 0.6, "seed": s["i"] + 7}, 0.22))
        if typ == "photo":
            sfx.append((st + 0.02, "tick", {"f": 5200}, 0.5))
            sfx.append((st + 0.06, "glitch", {"seed": 99}, 0.25))
        if typ == "dossier":
            for j in range(int(len(show.get("name", "X")) * 1.0)):
                sfx.append((st + 0.15 + j * 0.06, "tick", {"f": 1800 + (j % 3) * 400}, 0.18))
            if show.get("stamp"):
                sfx.append((st + s["dur"] * 0.55, "impact", {"pitch": 75, "d": 0.9, "seed": s["i"]}, 0.55))
        elif typ == "tally":
            for j in range(int(show.get("n", 5))):
                sfx.append((st + j * min(1.6, s["dur"] * 0.6) / max(1, int(show.get("n", 5))), "tick", {"f": 900},
                            0.25))
        elif typ in ("number", "date", "place", "list", "people", "headline"):
            sfx.append((st + 0.05, "pop", {"f0": 500, "f1": 900}, 0.25))
        if b.get("sfx") == "hit":
            events.append((st - 0.4, "stop", 0.4))
            sfx.append((st, "impact", {"pitch": 45, "d": 2.0, "seed": s["i"]}, 0.85))
            sfx.append((st, "braam", {"d": 2.4}, 0.5))
        elif b.get("sfx") == "riser":
            sfx.append((st + s["dur"] - 2.2, "riser", {"d": 2.2, "seed": s["i"]}, 0.6))
        inten.append((st, 0.45 + 0.5 * (s["i"] / max(1, n - 1))))
    for s in segs:
        for j, (t0s, _, _) in enumerate(s.get("shots", [])):
            if j > 0:
                sfx.append((s["start"] + t0s - 0.08, "whoosh", {"d": 0.25, "seed": s["i"] * 5 + j}, 0.22))
    for (ct0, kind) in BR.cta_times(total):
        if kind == "like":
            sfx.append((ct0 + 0.05, "pop", {"f0": 600, "f1": 1200}, 0.45))
            sfx.append((ct0 + 0.6, "pop", {"f0": 900, "f1": 1700}, 0.4))
        else:
            sfx.append((ct0 + 0.05, "pop", {"f0": 600, "f1": 1200}, 0.4))
            sfx.append((ct0 + 1.2, "tick", {"f": 2400}, 0.6))
            sfx.append((ct0 + 1.25, "shimmer", {"d": 1.2}, 0.35))
    inten.append((total, 0.3))
    return sfx, voices, events, inten, wind


def write_srt(segs, path):
    def ts(x):
        ms = int(round(x * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    lines, n = [], 1
    for s in segs:
        for c in ST.chunk(s["kinds"]):
            a = s["start"] + s["words"][c[0][2]][1]
            b = s["start"] + s["words"][c[-1][2]][2]
            lines += [str(n), f"{ts(a)} --> {ts(b)}", " ".join(w for w, _, _ in c), ""]
            n += 1
    open(path, "w", encoding="utf-8").write("\n".join(lines))


# ------------------------------------------------------------------ produce one video
def chapters_text(segs, chapters):
    """YouTube bölümleri: [[beat_index, "Başlık"], ...] -> '00:00 Başlık' satırları (ilk 00:00, en az 3, >=10 sn)."""
    if not chapters or len(chapters) < 3:
        return ""
    out, last = [], -99
    for bi, name in sorted(chapters):
        if bi >= len(segs):
            continue
        ts = 0 if not out else segs[bi]["start"]
        if ts - last < 10:
            continue
        m, s = divmod(int(ts), 60)
        out.append(f"{m:02d}:{s:02d} {name}")
        last = ts
    return "Bölümler:\n" + "\n".join(out) if len(out) >= 3 else ""


def make_thumbnail(path, thumb, fmt, theme, brand):
    """Tıklatan kapak: gerçek fotoğraf ya da canlandırma sahnesi arka planı, dev kontrastlı yazı,
    kırmızı daire + ok, 'GERÇEK OLAY' etiketi. thumb = {"lines":[..], "red":1, "icon":..., "photo":"<yerel yol>",
    "scene":{...}, "tag":"GERÇEK OLAY"}"""
    from PIL import ImageDraw, ImageFilter, ImageEnhance
    ST.set_theme(theme)
    W, H = (1280, 720) if fmt == "landscape" else (1080, 1920)
    u = W / 1280 if fmt == "landscape" else 1.0
    bg = None
    if thumb.get("photo"):
        bg = ST.load_photo(thumb["photo"])
    if bg is not None:
        iw, ih = bg.size
        sc = max(W / iw, H / ih)
        bg = bg.resize((int(iw * sc) + 1, int(ih * sc) + 1), Image.LANCZOS)
        bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
        bg = ImageEnhance.Contrast(ImageEnhance.Color(bg).enhance(0.6)).enhance(1.35).convert("RGBA")
    elif thumb.get("scene"):
        bg = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        ST.draw_scene(bg, thumb["scene"], 1.2, 3.0, W, H, 0.9 * u)
    else:
        bg = Image.fromarray(ST.background(W, H)).convert("RGBA")
    # sol tarafı karart (yazı okunurluğu) + kırmızı kenar tonu
    sh = np.zeros((H, W, 4), np.uint8)
    gx = np.linspace(1, 0, W)[None, :] ** 1.2
    sh[..., 3] = (gx * 190).astype(np.uint8)
    bg.alpha_composite(Image.fromarray(sh))
    d = ImageDraw.Draw(bg)
    if not thumb.get("photo") and not thumb.get("scene"):
        ST.icon(d, thumb.get("icon", "question"), W * 0.76, H * 0.55, 470 * u, 2.0, (235, 232, 224), ST.C["red"])
    # kırmızı daire + ok (dikkat noktası)
    tx, ty = W * thumb.get("focus_x", 0.74), H * thumb.get("focus_y", 0.5)
    r = 150 * u
    d.ellipse((tx - r, ty - r, tx + r, ty + r), outline=(235, 30, 30, 255), width=int(12 * u))
    ex, ey = tx - r * 0.78, ty - r * 0.62          # dairenin sol üst kenarı
    ax, ay = ex - r * 1.1, ey - r * 0.9
    d.line((ax, ay, ex, ey), fill=(235, 30, 30, 255), width=int(16 * u))
    d.polygon([(ex + 8 * u, ey + 8 * u), (ex - r * 0.42, ey - r * 0.08), (ex - r * 0.08, ey - r * 0.42)], fill=(235, 30, 30, 255))
    # yazılar (kalın kontur)
    lines = thumb.get("lines", ["GİZEM"])
    x0 = 46 * u
    y = H * 0.2 if fmt == "landscape" else H * 0.15
    for i, ln in enumerate(lines[:3]):
        red = i == thumb.get("red", 1)
        size = (150 if red else 104) * u
        f = ST.F(size, 900)
        while f.getlength(ST.up(ln)) > W * 0.62 and size > 50:
            size -= 6
            f = ST.F(size, 900)
        col = (255, 214, 0) if red else (255, 255, 255)
        d.text((x0, y), ST.up(ln), font=f, fill=col + (255,), anchor="lm", stroke_width=int(10 * u),
               stroke_fill=(0, 0, 0, 255))
        y += size * 1.12
    tag = thumb.get("tag", "GERÇEK OLAY")
    if tag:
        f = ST.F(40 * u, 800)
        tw = f.getlength(tag)
        d.rounded_rectangle((x0, H - 110 * u, x0 + tw + 40 * u, H - 50 * u), radius=int(10 * u), fill=(220, 25, 25, 255))
        d.text((x0 + 20 * u, H - 80 * u), tag, font=f, fill=(255, 255, 255, 255), anchor="lm")
    bg.convert("RGB").save(path, quality=90)


def produce_one(vid, beats, fmt, brand, theme, publish, out_dir, use_tts=True, workers=None, preview=False,
                thumb=None, chapters=None, broll_terms=None):
    work = os.path.join(out_dir, vid + "_work")
    os.makedirs(work, exist_ok=True)
    print(f"▶ {vid} [{fmt}]: seslendirme + zaman çizelgesi")
    fetch_photos(beats, os.path.join(out_dir, "_photos"))
    if beats and beats[0].get("show", {}).get("type") == "photo":
        beats[0]["show"].setdefault("circle", True)   # kanca: ilk fotoğrafta kırmızı daire vurgusu
    broll_paths = fetch_broll(broll_terms, os.path.join(out_dir, "_photos"))
    segs, total = build(beats, os.path.join(out_dir, "_voicecache"), use_tts)
    for s_ in segs:
        s_["lang"] = ST.LANG
    assign_backdrops(segs, BACKDROP_FALLBACK[0])
    pool = BR.build_pool(beats) + [p for p in (broll_paths or []) if p]
    if not pool and BACKDROP_FALLBACK[0]:
        pool = [BACKDROP_FALLBACK[0]]
    nfill = BR.fill_missing_photos(beats, pool)
    if nfill:
        print(f"  [foto] {nfill} eksik fotoğraf havuzdan dolduruldu")
    BR.assign_shots(segs, pool)
    print(f"  b-roll havuzu: {len(pool)} fotoğraf")
    print(f"  süre {total:.1f}s, {len(segs)} sahne")
    if preview:
        pick = [segs[0], segs[len(segs) // 3], segs[2 * len(segs) // 3], segs[-1]]
        shots = []
        for s in pick:
            shots += render_chunk(([s], fmt, brand, theme, None, [min(s["dur"] - 0.05, 1.4)], total))
        return shots
    # sahneleri ~12 sn'lik parçalara böl, paralel render
    chunks, cur, acc = [], [], 0
    for s in segs:
        cur.append(s)
        acc += s["dur"]
        if acc > 12:
            chunks.append(cur)
            cur, acc = [], 0
    if cur:
        chunks.append(cur)
    jobs = [(c, fmt, brand, theme, os.path.join(work, f"c_{i:03d}.mp4"), None, total) for i, c in enumerate(chunks)]
    todo = [j for j in jobs if not os.path.exists(j[4])]
    t0 = time.time()
    with Pool(workers or os.cpu_count()) as pool:
        list(pool.imap_unordered(render_chunk, todo))
    print(f"  render {time.time() - t0:.0f}s")
    sfx, voices, events, inten, wind = plan_audio(segs, total)
    mix = A.build_mix(total, voices, sfx, inten, wind, events, bpm=72)
    raw = os.path.join(work, "mix.wav")
    A.write_wav(raw, mix)
    master = os.path.join(work, "master.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", "loudnorm=I=-14:TP=-1.2:LRA=9",
                    "-ar", "44100", master], check=True)
    lst = os.path.join(work, "list.txt")
    open(lst, "w").write("".join(f"file '{os.path.abspath(j[4])}'\n" for j in jobs))
    silent = os.path.join(work, "video.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent],
                   check=True)
    final = os.path.join(out_dir, vid + ".mp4")
    tmp = final[:-4] + ".part.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", master, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", tmp],
                   check=True)
    os.replace(tmp, final)
    write_srt(segs, os.path.join(out_dir, vid + ".srt"))
    ch = chapters_text(segs, chapters) if fmt == "landscape" else ""
    desc = publish.get("description", "") + (("\n\n" + ch) if ch else "")
    if CREDITS:
        desc += ("\n\nGörseller: Wikimedia Commons — " if ST.LANG == "tr" else "\n\nImages: Wikimedia Commons — ") + "; ".join(CREDITS[:30])
    meta = f"{publish.get('title', vid)}\n\n{desc}\n\n{' '.join(publish.get('hashtags', []))}\n"
    open(os.path.join(out_dir, vid + "_metadata.txt"), "w", encoding="utf-8").write(meta)
    kp = os.path.join(out_dir, vid + "_kapak.jpg")
    if thumb and (thumb.get("photo_url") or thumb.get("photo_search") or thumb.get("photo_commons")):
        tb = [{"show": {"type": "photo", "url": thumb.get("photo_url"), "search": thumb.get("photo_search"),
                        "commons": thumb.get("photo_commons")}}]
        saved = set(USED_TITLES)
        USED_TITLES.clear()   # kapak için en iyi eşleşme (videoda kullanılmış olsa da) seçilebilir
        fetch_photos(tb, os.path.join(out_dir, "_photos"))
        USED_TITLES.update(saved)
        thumb = dict(thumb, photo=tb[0]["show"].get("_local"))
    if thumb:
        make_thumbnail(kp, thumb, fmt, theme, brand)
    else:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{min(total - 0.1, 1.2):.2f}", "-i", final,
                        "-frames:v", "1", "-q:v", "2", kp], check=True)
    print(f"✔ {final}")
    return final


def produce_story(script, out_dir, use_tts=True, workers=None):
    CREDITS.clear()
    USED_TITLES.clear()
    v = script.get("voice", {})
    tts.configure(v.get("engine"), v.get("speaker"), v.get("rate"), v.get("pitch"))
    brand = script.get("brand", "GİZEM DOSYASI")
    theme = script.get("theme", "dosya")
    pub = script.get("publish", {})
    finals = []
    ST.LANG = script.get("lang", "tr")
    lg = script.get("logo") or {}
    BR.LOGO.update({"brand": lg.get("brand", script.get("brand", "İLGİNÇ BİLGİLER")), "mono": lg.get("mono", "İB")})
    PART = {"tr": "BÖLÜM", "en": "PART", "de": "TEIL"}.get(ST.LANG, "PART")
    if script.get("parts"):   # Shorts dizisi: her bölüm kendi senaryosuyla ~1 dk dikey video (BÖLÜM k/n)
        n = len(script["parts"])
        BACKDROP_FALLBACK[0] = None
        for k, part in enumerate(script["parts"]):
            th = dict(part.get("thumb") or {})
            if th and not th.get("tag"):
                th["tag"] = f"{PART} {k + 1}"
            USED_TITLES.clear()
            CREDITS.clear()   # künye bölüm başına: yalnızca o bölümde kullanılan görseller
            finals.append(produce_one(f"{script['id']}_part{k + 1}", part["beats"], "vertical",
                                      f"{brand} · {PART} {k + 1}/{n}", theme, part.get("publish", {}), out_dir,
                                      use_tts, workers, thumb=th or None,
                                      broll_terms=part.get("broll") or script.get("broll")))
        return finals
    L = script["long"]
    th = L.get("thumb") or {}
    BACKDROP_FALLBACK[0] = None
    if th.get("photo_commons") or th.get("photo_search") or th.get("photo_url"):
        tb = [{"show": {"type": "photo", "url": th.get("photo_url"), "search": th.get("photo_search"),
                        "commons": th.get("photo_commons")}}]
        fetch_photos(tb, os.path.join(out_dir, "_photos"))
        USED_TITLES.clear()
        BACKDROP_FALLBACK[0] = tb[0]["show"].get("_local")
    finals.append(produce_one(script["id"], L["beats"], "landscape", brand, theme, pub.get("long", {}), out_dir,
                              use_tts, workers, thumb=L.get("thumb"), chapters=L.get("chapters")))
    for k, sh in enumerate(script.get("shorts", [])):
        beats = sh.get("hook", []) + L["beats"][sh["from"]:sh["to"] + 1] + sh.get("outro", [])
        p = (pub.get("shorts") or [{}] * 3)[k] if k < len(pub.get("shorts", [])) else {}
        finals.append(produce_one(f"{script['id']}_short{k + 1}", beats, "vertical", brand, theme, p, out_dir,
                                  use_tts, workers))
    return finals

def _series_bar(fr, kn, prog, W, y, u):
    """Dizi ilerleme çubuğu (Stories tarzı): biten bölümler beyaz, bu bölüm kırmızı dolar, sonrakiler soluk.
    İzleyiciye dizinin devam ettiğini gösterir -> sonraki bölüme geçiş (binge) artar."""
    k, n = kn
    sw, gap, sh = int(88 * u), int(10 * u), max(4, int(9 * u))
    tot = n * sw + (n - 1) * gap
    x0 = (W - tot) // 2
    for i in range(n):
        xa = x0 + i * (sw + gap)
        reg = fr[y:y + sh, xa:xa + sw].astype(np.float32)
        fr[y:y + sh, xa:xa + sw] = (reg * 0.45 + np.array((255, 255, 255), np.float32) * 0.55 * 0.45).astype(np.uint8)
        if i < k - 1:
            fill = sw
            col = (245, 245, 240)
        elif i == k - 1:
            fill = int(sw * min(1.0, max(0.0, prog)))
            col = tuple(int(c) for c in ST.C["red"])
        else:
            fill = 0
            col = (0, 0, 0)
        if fill > 0:
            fr[y:y + sh, xa:xa + fill] = col
