"""Hikâye formatı: senaryo -> (1 yatay uzun video + N dikey Shorts) üretimi."""
import json
import math
import os
import subprocess
import time
from multiprocessing import Pool

import numpy as np
import cv2
from PIL import Image

from . import tts
from . import audio as A
from . import story as ST
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
        dur = max(1.3, lead + vd + (0.35 if b.get("sfx") in ("hit", "riser") else 0.14))
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


def render_chunk(args):
    segs, fmt, brand, theme, out_path, preview, total = (list(args) + [None])[:7]
    cv2.setNumThreads(1)
    ST.set_theme(theme)
    P = FMT[fmt]
    W, H, u = P["W"], P["H"], P["u"]
    hu = 1.0 if fmt == "vertical" else 0.85
    cx, cy = W / 2, H * P["cy"]
    total = total or (segs[-1]["start"] + segs[-1]["dur"])
    bg = ST.background(W, H)
    atm = ST.Atmosphere(W, H, seed=int(segs[0]["start"]))
    grains = [_grain(H, W, k) for k in range(6)]
    brand_spr = ST.brand_sprite(brand, 1.0 if fmt == "vertical" else 0.8)
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
            ST.ghost_word(fr, kw, t, D, W, H, u)
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ST.draw_visual(layer, show, t, D, cx, cy, u)
            la = np.array(layer)
            # sürekli kamera hareketi + vurgulu kelimede darbe
            punch = sum(max(0.0, 1 - (t - h) / 0.28) for h in hot if t >= h)
            zin = ST.eo(t / 0.18)
            sc = 1.0 + 0.08 * (t / D) + 0.07 * (1 - zin) + 0.05 * min(1, punch)
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
            bh, bw = brand_spr.shape[:2]
            by, bx = int(40 * P["cap_u"]), int((W - bw) / 2) if fmt == "vertical" else int(50)
            al = brand_spr[..., 3:4].astype(np.float32) / 255
            fr[by:by + bh, bx:bx + bw] = (fr[by:by + bh, bx:bx + bw] * (1 - al) + brand_spr[..., :3] * al).astype(np.uint8)
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


def fetch_photos(beats, cache):
    """'photo' sahnelerinin görsellerini (Wikimedia Commons vb. telifsiz kaynak URL'si) indir."""
    import hashlib
    import urllib.request
    os.makedirs(cache, exist_ok=True)
    for b in beats:
        sh = b.get("show", {})
        if sh.get("type") != "photo" or not sh.get("url"):
            continue
        fn = os.path.join(cache, hashlib.md5(sh["url"].encode()).hexdigest()[:12] + ".img")
        if not os.path.exists(fn):
            try:
                req = urllib.request.Request(sh["url"], headers={"User-Agent": "viral-factory/1.0 (github.com/ilhanbayer)"})
                open(fn, "wb").write(urllib.request.urlopen(req, timeout=60).read())
            except Exception as e:
                print("  [foto] indirilemedi:", sh["url"][:80], type(e).__name__)
                continue
        sh["_local"] = fn


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
    """Tıklanma odaklı kapak: büyük, kısa, kontrastlı başlık + ikon (1280x720 / 1080x1920)."""
    ST.set_theme(theme)
    P = FMT[fmt]
    W, H = P["W"], P["H"]
    fr = ST.background(W, H)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    from PIL import ImageDraw
    d = ImageDraw.Draw(layer)
    lines = thumb.get("lines", ["GİZEM"])
    u = 1.0 if fmt == "landscape" else 1.25
    x0 = W * (0.06 if fmt == "landscape" else 0.5)
    y = H * (0.16 if fmt == "landscape" else 0.2)
    for i, ln in enumerate(lines[:3]):
        red = i == thumb.get("red", 1)
        f = ST.F((175 if red else 120) * u, 900)
        anchor = "lm" if fmt == "landscape" else "mm"
        d.text((x0 + 8, y + 10), ST.up(ln), font=f, fill=(0, 0, 0, 200), anchor=anchor)
        d.text((x0, y), ST.up(ln), font=f, fill=(ST.C["red"] if red else (250, 248, 240)) + (255,), anchor=anchor)
        y += (200 if red else 150) * u
    ic = thumb.get("icon", "question")
    cx, cy = (W * 0.78, H * 0.55) if fmt == "landscape" else (W * 0.5, H * 0.72)
    ST.icon(d, ic, cx, cy, (520 if fmt == "landscape" else 640), 2.0, (235, 232, 224), ST.C["red"])
    a = np.array(layer)
    al = a[..., 3:4].astype(np.float32) / 255
    out = (fr * (1 - al) + a[..., :3] * al).astype(np.uint8)
    img = Image.fromarray(out)
    if fmt == "landscape":
        img = img.resize((1280, 720), Image.LANCZOS)
    img.save(path, quality=90)


def produce_one(vid, beats, fmt, brand, theme, publish, out_dir, use_tts=True, workers=None, preview=False,
                thumb=None, chapters=None):
    work = os.path.join(out_dir, vid + "_work")
    os.makedirs(work, exist_ok=True)
    print(f"▶ {vid} [{fmt}]: seslendirme + zaman çizelgesi")
    fetch_photos(beats, os.path.join(out_dir, "_photos"))
    segs, total = build(beats, os.path.join(out_dir, "_voicecache"), use_tts)
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
    meta = f"{publish.get('title', vid)}\n\n{desc}\n\n{' '.join(publish.get('hashtags', []))}\n"
    open(os.path.join(out_dir, vid + "_metadata.txt"), "w", encoding="utf-8").write(meta)
    kp = os.path.join(out_dir, vid + "_kapak.jpg")
    if thumb:
        make_thumbnail(kp, thumb, fmt, theme, brand)
    else:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{min(total - 0.1, 1.2):.2f}", "-i", final,
                        "-frames:v", "1", "-q:v", "2", kp], check=True)
    print(f"✔ {final}")
    return final


def produce_story(script, out_dir, use_tts=True, workers=None):
    v = script.get("voice", {})
    tts.configure(v.get("engine"), v.get("speaker"), v.get("rate"), v.get("pitch"))
    brand = script.get("brand", "GİZEM DOSYASI")
    theme = script.get("theme", "dosya")
    pub = script.get("publish", {})
    finals = []
    L = script["long"]
    finals.append(produce_one(script["id"], L["beats"], "landscape", brand, theme, pub.get("long", {}), out_dir,
                              use_tts, workers, thumb=L.get("thumb"), chapters=L.get("chapters")))
    for k, sh in enumerate(script.get("shorts", [])):
        beats = sh.get("hook", []) + L["beats"][sh["from"]:sh["to"] + 1] + sh.get("outro", [])
        p = (pub.get("shorts") or [{}] * 3)[k] if k < len(pub.get("shorts", [])) else {}
        finals.append(produce_one(f"{script['id']}_short{k + 1}", beats, "vertical", brand, theme, p, out_dir,
                                  use_tts, workers))
    return finals
