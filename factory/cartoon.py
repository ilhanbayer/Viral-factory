"""Animasyon karakterli hikâye formatı ("format": "cartoon").

Her sahne için Pixar tarzı AI görseli üretilir (imagegen), sonra canlandırılır:
Ken Burns kamera, konuşan karakterde nefes/zıplama, partiküller (yaprak, kar, ışıltı, toz),
çizgi film geçişleri, konuşmacı etiketi + kelime kelime altyazı, karakter sesleri, neşeli müzik + SFX.

Senaryo:
{
 "id": "C001_...", "format": "cartoon", "brand": "HOCA'NIN FIKRALARI",
 "characters": {"hoca": {"name": "Hoca", "desc": "<İngilizce ayrıntılı görünüm tarifi>", "color": [255,214,0],
                          "voice": {"speaker": "tr-TR-AhmetNeural", "rate": "-4%", "pitch": "-10Hz"}}, ...},
 "narrator": {"speaker": "tr-TR-AhmetNeural", "rate": "+0%", "pitch": "-2Hz"},
 "episodes": [{"title": "...", "beats": [BEAT...], "publish": {...}, "thumb": {...}}, ...],
 "long": {"title": "...", "intro": [BEAT...], "outro": [BEAT...], "publish": {...}, "thumb": {...}}
}
BEAT = {"say": "Metin, *vurgu*", "who": "anlatici" | "<karakter id>",
        "img": "<İngilizce sahne tarifi; karakterleri {hoca} gibi yer tutucularla an>",
        "cam": "in|out|left|right|up|down", "fx": "leaves|snow|sparkle|dust|rain|none", "sfx": "boing|pop|slide_up|slide_down|ding|drum|whoosh"}
"""
import json
import math
import os
import re
import subprocess
import time
from multiprocessing import Pool

import numpy as np
import cv2
from PIL import Image, ImageDraw

from . import tts
from . import audio as A
from . import story as ST
from . import imagegen as IG
from .graphics import word_timings

FPS = 30
FMT = {
    "vertical": dict(W=1080, H=1920, GW=768, GH=1344, cap_y=0.78, cap_u=1.05),
    "landscape": dict(W=1920, H=1080, GW=1344, GH=768, cap_y=0.86, cap_u=0.9),
}
CAMS = ["in", "right", "out", "left", "up", "in", "down"]


# ------------------------------------------------------------------ prompts & images
def build_prompt(beat, chars):
    p = beat.get("img", "")
    for cid, c in chars.items():
        p = p.replace("{" + cid + "}", c["desc"])
    return re.sub(r"\s+", " ", p).strip()


def ensure_images(beats, chars, fmt, cache, base_seed):
    os.makedirs(cache, exist_ok=True)
    P = FMT[fmt]
    for i, b in enumerate(beats):
        if b.get("_img_" + fmt):
            continue
        prompt = build_prompt(b, chars)
        seed = base_seed + IG.seed_for(prompt) % 100000
        fn = os.path.join(cache, f"{fmt}_{IG.seed_for(prompt + fmt):08d}.jpg")
        t0 = time.time()
        r = IG.gen(prompt, P["GW"], P["GH"], seed, fn)
        print(f"  [görsel {fmt}] {i + 1}/{len(beats)} {'OK' if r else 'YOK'} {time.time() - t0:.0f}s", flush=True)
        b["_img_" + fmt] = r


# ------------------------------------------------------------------ timeline
def build(beats, chars, narrator, work, use_tts=True):
    vcache = os.path.join(os.path.dirname(os.path.abspath(work)), "_voicecache")  # Shorts ve uzun video ortak
    segs, t = [], 0.0
    for i, b in enumerate(beats):
        say = b["say"].replace("*", "")
        who = b.get("who", "anlatici")
        v = chars.get(who, {}).get("voice", narrator)
        tts.configure_voice(v)
        if use_tts:
            wav, vd, words = tts.synth(say, vcache, "story")
        else:
            wav, vd, words = None, tts.estimate_duration(say), None
        lead = 0.15
        dur = max(1.8, lead + vd + (0.45 if b.get("sfx") else 0.3))
        tim = tts.align_words(say, words, lead, vd) or word_timings(say, lead, vd)
        segs.append(dict(i=i, start=t, dur=dur, voff=lead, vdur=vd, wav=wav, beat=b, words=tim, who=who,
                         kinds=ST.caption_words(b["say"])))
        t += dur
    return segs, t


# ------------------------------------------------------------------ particles
class Particles:
    def __init__(self, W, H, kind, seed=0):
        self.W, self.H, self.kind = W, H, kind
        r = np.random.default_rng(seed)
        n = {"leaves": 26, "snow": 140, "sparkle": 50, "dust": 70, "rain": 160}.get(kind, 0)
        self.p = r.uniform(0, 1, (n, 5))

    def draw(self, fr, t):
        W, H = self.W, self.H
        if self.kind in ("none", None) or len(self.p) == 0:
            return fr
        ov = fr.copy()
        for x, y, s, v, ph in self.p:
            if self.kind == "snow":
                px, py = ((x + math.sin(t * 0.8 + ph * 6) * 0.02) % 1) * W, ((y + t * 0.06 * (0.5 + v)) % 1) * H
                cv2.circle(ov, (int(px), int(py)), int(2 + s * 4), (250, 250, 255), -1, cv2.LINE_AA)
            elif self.kind == "rain":
                px, py = ((x + t * 0.05) % 1) * W, ((y + t * 1.1 * (0.6 + v)) % 1) * H
                cv2.line(ov, (int(px), int(py)), (int(px - 6), int(py + 30)), (200, 210, 230), 2, cv2.LINE_AA)
            elif self.kind == "leaves":
                px = ((x + t * 0.04 * (0.5 + v) + math.sin(t + ph * 6) * 0.03) % 1) * W
                py = ((y + t * 0.05 * (0.5 + v)) % 1) * H
                ang = t * 90 * (v - 0.5) + ph * 360
                col = [(230, 140, 40), (200, 80, 30), (240, 190, 60)][int(ph * 3) % 3]
                cv2.ellipse(ov, (int(px), int(py)), (int(10 + s * 10), int(5 + s * 5)), ang, 0, 360, col, -1, cv2.LINE_AA)
            elif self.kind == "sparkle":
                a = abs(math.sin(t * (2 + v * 3) + ph * 6))
                px, py = x * W, ((y - t * 0.015) % 1) * H
                r_ = int(2 + 6 * a * s)
                c = int(200 + 55 * a)
                cv2.line(ov, (int(px - r_ * 2), int(py)), (int(px + r_ * 2), int(py)), (255, c, 160), 2, cv2.LINE_AA)
                cv2.line(ov, (int(px), int(py - r_ * 2)), (int(px), int(py + r_ * 2)), (255, c, 160), 2, cv2.LINE_AA)
            elif self.kind == "dust":
                px = ((x + t * 0.008 * (v - 0.5)) % 1) * W
                py = ((y - t * 0.01 * v) % 1) * H
                c = int(180 + 60 * abs(math.sin(t + ph * 5)))
                cv2.circle(ov, (int(px), int(py)), int(1 + s * 2.5), (c, c, int(c * 0.85)), -1, cv2.LINE_AA)
        return cv2.addWeighted(ov, 0.75, fr, 0.25, 0)


# ------------------------------------------------------------------ render
def _load(path, W, H, fallback_show, t, dur):
    if path and os.path.exists(path):
        im = cv2.cvtColor(cv2.imread(path), cv2.COLOR_BGR2RGB)
        return cv2.resize(im, (int(W * 1.18), int(H * 1.18)), interpolation=cv2.INTER_CUBIC)
    # yedek: prosedürel canlandırma sahnesi
    layer = Image.new("RGBA", (int(W * 1.18), int(H * 1.18)), (0, 0, 0, 255))
    ST.draw_scene(layer, fallback_show or {"type": "scene", "sky": "day", "land": "hills"}, 1.0, dur,
                  layer.width, layer.height, 1.0)
    return np.array(layer)[..., :3]


def name_tag(fr, name, col, x, y, u):
    f = ST.F(int(40 * u), 800)
    tw = f.getlength(name)
    img = Image.new("RGBA", (int(tw + 46 * u), int(62 * u)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius=int(16 * u), fill=tuple(col) + (240,))
    d.text((23 * u, img.height / 2), name, font=f, fill=(20, 20, 24, 255), anchor="lm")
    a = np.array(img)
    h, w = a.shape[:2]
    x0, y0 = int(x - w / 2), int(y)
    al = a[..., 3:4].astype(np.float32) / 255
    fr[y0:y0 + h, x0:x0 + w] = (fr[y0:y0 + h, x0:x0 + w] * (1 - al) + a[..., :3] * al).astype(np.uint8)


def render_chunk(args):
    segs, fmt, brand, chars, out_path, preview, total = args
    cv2.setNumThreads(1)
    ST.set_theme({"red": (255, 70, 60), "orange": (255, 214, 0)})
    P = FMT[fmt]
    W, H = P["W"], P["H"]
    u = P["cap_u"]
    brand_spr = ST.brand_sprite(brand, 1.0 if fmt == "vertical" else 0.8)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    vig = np.clip(1.12 - 0.35 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2), 0.55, 1)[..., None]
    if preview is None:
        tmp = out_path[:-4] + ".part.mp4"
        proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                 "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                                 "-crf", "20", "-maxrate", "9M", "-bufsize", "18M", "-pix_fmt", "yuv420p", tmp],
                                stdin=subprocess.PIPE)
    shots = []
    for s in segs:
        b = s["beat"]
        D = s["dur"]
        src = _load(b.get("_img_" + fmt), W, H, b.get("fallback"), 0, D)
        sh, sw = src.shape[:2]
        cam = b.get("cam") or CAMS[s["i"] % len(CAMS)]
        parts = Particles(W, H, b.get("fx", "dust"), seed=s["i"])
        hot = [s["words"][i][1] for i, (w, k) in enumerate(s["kinds"]) if k == "red" and i < len(s["words"])]
        trans = ["zoom", "whip", "flash", "whip", "zoom"][s["i"] % 5] if s["i"] > 0 else "zoom"
        who = s["who"]
        ch = chars.get(who)
        frames = [int(x * FPS) for x in preview] if preview is not None else range(int(round(D * FPS)))
        for k in frames:
            t = k / FPS
            gt = s["start"] + t
            p = t / D
            e = p * p * (3 - 2 * p)
            # Ken Burns
            z = {"in": 1.0 + 0.14 * e, "out": 1.14 - 0.14 * e}.get(cam, 1.07)
            ox = {"left": 0.5 + 0.35 * (e - 0.5), "right": 0.5 - 0.35 * (e - 0.5)}.get(cam, 0.5)
            oy = {"up": 0.5 + 0.3 * (e - 0.5), "down": 0.5 - 0.3 * (e - 0.5)}.get(cam, 0.5)
            # konuşma "nefesi" + vurgu darbesi
            talk = 0.006 * math.sin(gt * 14) if (s["voff"] < t < s["voff"] + s["vdur"]) else 0
            punch = sum(max(0.0, 1 - (t - h) / 0.25) for h in hot if t >= h)
            z *= 1 + talk + 0.04 * min(1, punch) + 0.06 * (1 - ST.eo(t / 0.2))
            cw, chh = W * 1.18 / z, H * 1.18 / z
            cw, chh = min(cw, sw), min(chh, sh)
            x0 = (sw - cw) * ox
            y0 = (sh - chh) * oy
            M = np.float32([[W / cw, 0, -x0 * W / cw], [0, H / chh, -y0 * H / chh]])
            ang = 0.6 * math.sin(gt * 0.4)
            R = cv2.getRotationMatrix2D((W / 2, H / 2), ang, 1.0)
            M3 = np.vstack([M, [0, 0, 1]])
            M = (np.vstack([R, [0, 0, 1]]) @ M3)[:2]
            fr = cv2.warpAffine(src, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            fr = parts.draw(fr, gt)
            f = fr.astype(np.float32) * vig
            # sıcak renk + kontrast
            f = np.clip((f - 128) * 1.06 + 128 + np.array([6, 2, -4]), 0, 255)
            fr = f.astype(np.uint8)
            fr = ST.transition(fr, trans, t, s["i"]) if s["i"] > 0 else fr
            # konuşmacı etiketi + altyazı
            cap_y = H * P["cap_y"]
            if ch and t > 0.1:
                name_tag(fr, ST.up(ch.get("name", who)), ch.get("color", [255, 214, 0]), W / 2,
                         int(cap_y - 120 * u), u)
            ST.draw_caption(fr, s["kinds"], s["words"], t, W / 2, cap_y, u)
            bh, bw = brand_spr.shape[:2]
            by, bx = int(36 * u), int((W - bw) / 2) if fmt == "vertical" else 46
            al = brand_spr[..., 3:4].astype(np.float32) / 255
            fr[by:by + bh, bx:bx + bw] = (fr[by:by + bh, bx:bx + bw] * (1 - al) + brand_spr[..., :3] * al).astype(np.uint8)
            pr = min(1.0, gt / max(total, 1))
            cv2.rectangle(fr, (0, H - 8), (int(W * pr), H), (255, 214, 0), -1)
            if preview is not None:
                shots.append(fr)
            else:
                proc.stdin.write(fr.tobytes())
    if preview is not None:
        return shots
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg")
    os.replace(tmp, out_path)
    return out_path


def plan_audio(segs):
    sfx, voices = [], []
    for s in segs:
        st, b = s["start"], s["beat"]
        if s["wav"]:
            voices.append((st + s["voff"], s["wav"]))
        if s["i"] > 0:
            sfx.append((st - 0.12, "whoosh", {"d": 0.35, "seed": s["i"]}, 0.3))
        if b.get("sfx"):
            sfx.append((st + 0.05, b["sfx"], {}, 0.7))
        for i, (w, k) in enumerate(s["kinds"]):
            if k == "red" and i < len(s["words"]):
                sfx.append((st + s["words"][i][1], "pop", {}, 0.25))
    return sfx, voices


def produce_one(vid, beats, fmt, script, publish, out_dir, use_tts=True, thumb=None, preview=False):
    chars = script.get("characters", {})
    work = os.path.join(out_dir, vid + "_work")
    os.makedirs(work, exist_ok=True)
    print(f"▶ {vid} [{fmt}] görseller")
    ensure_images(beats, chars, fmt, os.path.join(out_dir, "_cartoon_img"), script.get("seed", 1000))
    segs, total = build(beats, chars, script.get("narrator", {}), out_dir, use_tts)
    print(f"  süre {total:.1f}s, {len(segs)} sahne")
    if preview:
        out = []
        for s in segs[:: max(1, len(segs) // 6)]:
            out += render_chunk(([s], fmt, script.get("brand", ""), chars, None, [min(1.2, s["dur"] - 0.1)], total))
        return out
    chunks, cur, acc = [], [], 0
    for s in segs:
        cur.append(s)
        acc += s["dur"]
        if acc > 12:
            chunks.append(cur)
            cur, acc = [], 0
    if cur:
        chunks.append(cur)
    jobs = [(c, fmt, script.get("brand", ""), chars, os.path.join(work, f"c_{i:03d}.mp4"), None, total)
            for i, c in enumerate(chunks)]
    with Pool(os.cpu_count()) as pool:
        list(pool.imap_unordered(render_chunk, [j for j in jobs if not os.path.exists(j[4])]))
    sfx, voices = plan_audio(segs)
    mix = A.build_cartoon_mix(total, voices, sfx, seed=len(vid))
    raw = os.path.join(work, "mix.wav")
    A.write_wav(raw, mix)
    master = os.path.join(work, "master.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", "loudnorm=I=-14:TP=-1.2:LRA=9",
                    "-ar", "44100", master], check=True)
    lst = os.path.join(work, "list.txt")
    open(lst, "w").write("".join(f"file '{os.path.abspath(j[4])}'\n" for j in jobs))
    silent = os.path.join(work, "video.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
                    silent], check=True)
    final = os.path.join(out_dir, vid + ".mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", master, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                    final[:-4] + ".part.mp4"], check=True)
    os.replace(final[:-4] + ".part.mp4", final)
    from .story_compose import write_srt, make_thumbnail, chapters_text
    write_srt(segs, os.path.join(out_dir, vid + ".srt"))
    ch = chapters_text(segs, publish.get("_chapters")) if fmt == "landscape" else ""
    desc = publish.get("description", "") + (("\n\n" + ch) if ch else "")
    meta = f"{publish.get('title', vid)}\n\n{desc}\n\n{' '.join(publish.get('hashtags', []))}\n"
    open(os.path.join(out_dir, vid + "_metadata.txt"), "w", encoding="utf-8").write(meta)
    kp = os.path.join(out_dir, vid + "_kapak.jpg")
    tb = dict(thumb or {})
    bi = tb.pop("beat", 0)
    img = beats[min(bi, len(beats) - 1)].get("_img_" + fmt)
    if img:
        tb["photo"] = img
        tb.setdefault("tag", "")
        make_thumbnail(kp, tb, fmt, "dosya", script.get("brand", ""))
    else:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1.0", "-i", final, "-frames:v", "1", "-q:v", "2",
                        kp], check=True)
    print(f"✔ {final}")
    return final


def produce_cartoon(script, out_dir, use_tts=True):
    finals = []
    eps = script["episodes"]
    L = script.get("long")
    # Shorts: her bölüm ayrı dikey video
    for k, ep in enumerate(eps):
        finals.append(produce_one(f"{script['id']}_short{k + 1}", ep["beats"], "vertical", script,
                                  ep.get("publish", {}), out_dir, use_tts, ep.get("thumb")))
    # Uzun: giriş + tüm bölümler + kapanış (yatay)
    if L:
        beats, chapters = list(L.get("intro", [])), []
        for ep in eps:
            chapters.append([len(beats), ep.get("title", "Bölüm")])
            beats += ep["beats"]
        beats += L.get("outro", [])
        pub = dict(L.get("publish", {}))
        pub["_chapters"] = [[0, "Giriş"]] + chapters if L.get("intro") else chapters
        finals.insert(0, produce_one(script["id"], beats, "landscape", script, pub, out_dir, use_tts, L.get("thumb")))
    return finals
