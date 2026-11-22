"""Timeline builder + frame renderer + ffmpeg assembly."""
import os
import json
import math
import time
import shutil
import subprocess
from multiprocessing import Pool

import numpy as np
import cv2

from . import tts
from . import audio as A
from .render3d import make_scene
from .graphics import (text_sprite, extruded_number, pill, blit, Subtitles, Post, word_timings, tr_upper,
                       ease_out_back, ease_out_cubic, ease_in_out, clamp01, rgb_split, zoom_blur, shake,
                       F_DISPLAY, F_BLACK, F_BOLD, F_SYM, RED, YELLOW, WHITE, font)

FPS = 30

# Biçimler: dikey Shorts/Reels/TikTok ve yatay YouTube uzun video.
# S/ox/oy: bilgi panelinin (dikey tasarım koordinatlarında çizilen) ölçek ve kaydırması
# TS/tox/toy: başlık/CTA blokları için aynısı
FORMATS = {
    "vertical": dict(W=1080, H=1920, RW=720, RH=1280, S=1.0, ox=0, oy=0, TS=1.0, toy=0, sub_y=1490, sub_size=68,
                     header_y=70, prog_y=160, peak_y=0.65, peak_x=0.5, planet=(0.5, 0.7), shade="top"),
    "landscape": dict(W=1920, H=1080, RW=1280, RH=720, S=0.62, ox=40, oy=-10, TS=0.7, toy=-240, sub_y=968,
                      sub_size=60, header_y=26, prog_y=92, peak_y=0.56, peak_x=0.66, planet=(0.68, 0.56),
                      shade="left"),
}
FMT = "vertical"
L = FORMATS[FMT]
W, H, RW, RH = L["W"], L["H"], L["RW"], L["RH"]


def set_format(name):
    global FMT, L, W, H, RW, RH
    FMT = name
    L = FORMATS[name]
    W, H, RW, RH = L["W"], L["H"], L["RW"], L["RH"]

ORDINAL_FILL = {"danger": [(255, 214, 0), (255, 150, 0), (255, 42, 52)]}


# ======================================================================= timeline
def build_timeline(script, work, use_tts=True):
    segs = []
    vcache = os.path.join(work, "voice")

    v = script.get("voice", {})
    tts.configure(v.get("engine"), v.get("speaker"), v.get("rate"))
    bounds = {}

    def voice(text, role):
        if use_tts:
            wav, d, words = tts.synth(text, vcache, role)
            bounds[text] = words
            return wav, d
        return None, tts.estimate_duration(text)

    t = 0.0
    intro = script["intro"]
    wav, vd = voice(intro["narration"], "intro")
    d = 0.9 + vd + 0.35
    segs.append(dict(kind="intro", start=t, dur=d, voff=0.9, vdur=vd, wav=wav, data=intro, scene=intro["scene"]))
    t += d
    n_items = len(script["items"])
    for i, it in enumerate(script["items"]):
        wav, vd = voice(it["narration"], "item")
        last = i == n_items - 1
        voff = 0.55 if last else 0.25
        d = max(3.6, voff + vd + 0.3)
        segs.append(dict(kind="item", start=t, dur=d, voff=voff, vdur=vd, wav=wav, data=it, scene=it["scene"],
                         index=i, n=n_items, last=last))
        t += d
    out = script["outro"]
    wav, vd = voice(out["narration"], "outro")
    d = 0.3 + vd + 1.6
    segs.append(dict(kind="outro", start=t, dur=d, voff=0.3, vdur=vd, wav=wav, data=out, scene=out["scene"]))
    t += d
    for s in segs:
        txt = s["data"]["narration"]
        s["words"] = tts.align_words(txt, bounds.get(txt), s["voff"], s["vdur"]) \
            or word_timings(txt, s["voff"], s["vdur"])
    return segs, t


# ======================================================================= overlays
class Overlay:
    def __init__(self, script, seg):
        self.s = script
        self.seg = seg
        self.subs = Subtitles(L["sub_size"])
        S = self.S = L["S"]
        z = lambda v: max(8, int(round(v * S)))
        self.z = z
        k = seg["kind"]
        self.hold = 9.0 if seg["dur"] > 16 else 1e9      # uzun bölümlerde bilgi kartları sonra çekilir
        if k == "item":
            it = seg["data"]
            self.rank = extruded_number(f"#{it['rank']}", z(290), depth=z(22))
            name = tr_upper(it["name"])
            size = 150 if len(name) <= 9 else int(150 * 9 / len(name) + 10)
            self.name = text_sprite(name, F_DISPLAY, z(size), fill=WHITE, stroke=0, glow=None, pad=z(40))
            self.place = pill(it["place"], F_BOLD, z(40), bg=(0, 0, 0, 150), icon="◉", icon_col=RED)
            self.header = pill(tr_upper(script["series_title"]), F_BLACK, 32, bg=(10, 10, 14, 185), accent=RED)
            self.stat2 = None
            st = it["stats"]
            self.stat1 = st[0]
            if len(st) > 1:
                self.stat2 = pill(st[1][1], F_BLACK, z(44), bg=(180, 20, 30, 225), icon=st[1][0], icon_col=WHITE)
            self.danger_lbl = text_sprite(tr_upper(script.get("meter_label", "TEHLİKE")), F_BLACK, z(34), fill=WHITE,
                                          shadow=True, pad=z(10), tracking=4)
            pin = it.get("pin_label", f"ZİRVE  {st[0][1]}" if script.get("category") == "dağ" else None)
            self.pin_lbl = pill(pin, F_BLACK, 34, bg=(255, 255, 255, 235), fg=(15, 15, 20)) if pin else None
        else:
            lines = seg["data"]["lines"]
            q = lambda v: max(8, int(round(v * L["TS"])))
            mid = 230 if len(lines[1]) <= 9 else max(120, int(230 * 9 / len(lines[1])) + 20)
            self.lines = [
                text_sprite(lines[0], F_BLACK, q(92), fill=WHITE, pad=30),
                text_sprite(lines[1], F_DISPLAY, q(mid), fill=RED, glow=(255, 30, 40), pad=40),
                text_sprite(lines[2], F_DISPLAY, q(210), fill=WHITE, pad=40),
            ]
            if k == "outro":
                c1, c2 = seg["data"].get("cta", ["YORUMLARA YAZ", "TAKİP ET"])
                self.cta1 = pill(c1, F_BLACK, q(50), bg=(0, 0, 0, 170), icon="✎", icon_col=YELLOW)
                self.cta2 = pill(c2, F_BLACK, q(66), bg=(255, 42, 52, 255), icon="✚", icon_col=WHITE)

    def counter_pill(self, p):
        icon, label, val = self.stat1
        if val:
            v = int(round(val * ease_out_cubic(p)))
            txt = f"{v:,}".replace(",", ".") + " m"
        else:
            txt = label
        return pill(txt, F_BLACK, self.z(44), bg=(255, 255, 255, 235), fg=(15, 15, 20), icon=icon, icon_col=RED)

    def draw(self, fr, t, info, gt):
        seg = self.seg
        k = seg["kind"]
        if k == "item":
            self.draw_item(fr, t, info)
        elif k == "intro":
            self.draw_title(fr, t, 0.15)
        else:
            self.draw_title(fr, t, 0.1, outro=True)
        self.subs.draw(fr, seg["words"], t, W / 2, L["sub_y"])

    def draw_title(self, fr, t, t0, outro=False):
        TS, toy = L["TS"], L["toy"]
        Ty = lambda y: toy + y * TS
        ys = [Ty(v) for v in ([560, 680, 930] if not outro else [430, 545, 790])]
        for i, spr in enumerate(self.lines):
            ts = t0 + i * 0.28
            p = (t - ts) / 0.16
            if p <= 0:
                continue
            sc = 2.6 - 1.6 * ease_out_cubic(p)
            blit(fr, spr, W / 2, ys[i] + spr.shape[0] / 2, alpha=clamp01(p * 1.5), scale=sc, anchor="c")
        if outro:
            p1 = (t - 1.2) / 0.3
            if p1 > 0:
                blit(fr, self.cta1, W / 2, Ty(1170), alpha=clamp01(p1), scale=0.7 + 0.3 * ease_out_back(p1), anchor="c")
            p2 = (t - 1.6) / 0.3
            if p2 > 0:
                pulse = 1 + 0.06 * math.sin((t - 1.6) * 7)
                blit(fr, self.cta2, W / 2, Ty(1300), alpha=clamp01(p2), scale=(0.6 + 0.4 * ease_out_back(p2)) * pulse, anchor="c")
                # arrow
                ay = Ty(1375) + 14 * math.sin(t * 8)
                aw = 36 * TS
                pts = np.array([[W / 2 - aw, ay], [W / 2 + aw, ay], [W / 2, ay + aw * 1.1]], np.int32)
                if p2 > 0.5:
                    cv2.fillConvexPoly(fr, pts, YELLOW, cv2.LINE_AA)

    def draw_item(self, fr, t, info):
        seg = self.seg
        S, ox, oy = self.S, L["ox"], L["oy"]
        X = lambda x: ox + x * S
        Y = lambda y: oy + y * S
        I = lambda v: int(round(v))
        fade = 1 - clamp01((t - self.hold) / 0.6)
        # header + progress
        blit(fr, self.header, W / 2, L["header_y"], anchor="tc")
        n, idx = seg["n"], seg["index"]
        if n > 1:
            bw, gap = 64, 10
            x0 = W / 2 - (n * bw + (n - 1) * gap) / 2
            py = L["prog_y"]
            for j in range(n):
                x = int(x0 + j * (bw + gap))
                col = (255, 255, 255) if j < idx else (RED if j == idx else (90, 90, 95))
                if j == idx and int(t * 4) % 2:
                    col = (255, 120, 120)
                cv2.rectangle(fr, (x, py), (x + bw, py + 8), col, -1, cv2.LINE_AA)
        # rank slam
        p = (t - 0.04) / 0.28
        if p > 0:
            sc = 1.9 - 0.9 * ease_out_back(p, 1.4)
            h, w = self.rank.shape[:2]
            blit(fr, self.rank, X(30) + w / 2, Y(190) + h / 2, alpha=clamp01(p * 2), scale=sc, anchor="c")
        # name wipe
        p = (t - 0.22) / 0.35
        ny = Y(545)
        if p > 0:
            blit(fr, self.name, X(40), ny, clip_w=ease_out_cubic(p))
            uw = int((self.name.shape[1] - 80 * S) * ease_out_cubic((t - 0.3) / 0.4))
            if uw > 0:
                yb = ny + self.name.shape[0] - 52 * S
                cv2.rectangle(fr, (I(X(80)), I(yb)), (I(X(80) + uw), I(yb + 8 * S)), RED, -1)
        if fade <= 0:
            return
        # place
        p = (t - 0.45) / 0.3
        if p > 0:
            blit(fr, self.place, X(50 - 60 * (1 - ease_out_cubic(p))), Y(790), alpha=clamp01(p) * fade)
        # stat chips
        p = (t - 0.62) / 0.3
        if p > 0:
            cp = self.counter_pill(clamp01((t - 0.62) / 0.9))
            blit(fr, cp, X(50), Y(885 + 40 * (1 - ease_out_cubic(p))), alpha=clamp01(p) * fade)
            cw = cp.shape[1] / S
        else:
            cw = 380
        if self.stat2 is not None:
            p = (t - 0.82) / 0.3
            if p > 0:
                blit(fr, self.stat2, X(50 + max(cw, 360) + 8), Y(885 + 40 * (1 - ease_out_cubic(p))),
                     alpha=clamp01(p) * fade)
        # meter
        p = (t - 1.0) / 0.25
        if p > 0:
            ov = fr.copy() if fade < 1 else fr
            blit(ov, self.danger_lbl, X(50), Y(995), alpha=clamp01(p))
            lvl = seg["data"]["danger"]
            fill = clamp01((t - 1.05) / 0.8) * lvl * 10
            bx = 50 + self.danger_lbl.shape[1] / S + 4
            y0, y1 = I(Y(1010)), I(Y(1040))
            for j in range(10):
                x = bx + j * 52
                a = clamp01(fill - j)
                cv2.rectangle(ov, (I(X(x)), y0), (I(X(x + 44)), y1), (60, 60, 66), -1, cv2.LINE_AA)
                if a > 0:
                    c = np.array([255, 214, 0]) * (1 - j / 9) + np.array([255, 30, 40]) * (j / 9)
                    cv2.rectangle(ov, (I(X(x)), y0), (I(X(x + 44 * a)), y1), tuple(int(v) for v in c), -1, cv2.LINE_AA)
            if ov is not fr:
                cv2.addWeighted(ov, fade, fr, 1 - fade, 0, fr)
        # 3D summit pin (projected from the 3D scene)
        if "peak_xy" in info:
            px, py = info["peak_xy"]
            px, py = px * W / RW, py * H / RH
            p = (t - 1.25) / 0.35
            if p > 0 and 0 < px < W and 0 < py < H:
                a = clamp01(p) * fade
                for k in range(2):
                    ph = ((t * 1.2 + k * 0.5) % 1.0)
                    r = int(10 + 50 * ph)
                    ov = fr.copy()
                    cv2.ellipse(ov, (int(px), int(py)), (r, int(r * 0.45)), 0, 0, 360, (255, 255, 255), 3, cv2.LINE_AA)
                    cv2.addWeighted(ov, a * (1 - ph), fr, 1 - a * (1 - ph), 0, fr)
                if a < 0.05:
                    return
                cv2.circle(fr, (int(px), int(py)), 9, RED, -1, cv2.LINE_AA)
                cv2.circle(fr, (int(px), int(py)), 9, WHITE, 2, cv2.LINE_AA)
                ly = int(py - 60 * ease_out_cubic(p))
                cv2.line(fr, (int(px), int(py) - 10), (int(px), ly), WHITE, 3, cv2.LINE_AA)
                if self.pin_lbl is None:
                    return
                lx = px + 14 if px < W * 0.55 else px - self.pin_lbl.shape[1] - 14
                blit(fr, self.pin_lbl, lx, ly - self.pin_lbl.shape[0] / 2, alpha=a)


# ======================================================================= segment render
def render_segment(args):
    seg, script, out_path, preview_times, fmt = args
    set_format(fmt)
    cv2.setNumThreads(1)
    t_start = time.time()
    spec = dict(seg["scene"])
    if spec.get("type", "terrain") == "terrain":
        if seg["kind"] == "item":
            spec["peak_screen_y"] = L["peak_y"]
        spec.setdefault("peak_screen_x", L["peak_x"] if seg["kind"] == "item" else 0.5)
    elif spec.get("type") == "space":
        spec["planet_xy"] = L["planet"] if seg["kind"] == "item" else (0.5, 0.62)
    scene = make_scene(spec, RW, RH)
    shade = shade_mask()
    post = Post(W, H, seed=int(seg["start"] * 10))
    ov = Overlay(script, seg)
    nfr = int(round(seg["dur"] * FPS))
    if preview_times is not None:
        frames = [int(x * FPS) for x in preview_times]
        outs = []
    else:
        tmp = out_path[:-4] + ".part.mp4"
        proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                 "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                                 "-crf", "20", "-maxrate", "8M", "-bufsize", "16M", "-pix_fmt", "yuv420p", "-r", str(FPS), tmp], stdin=subprocess.PIPE)
        frames = range(nfr)
    D = seg["dur"]
    for fi in frames:
        t = fi / FPS
        gt = seg["start"] + t
        img, info = scene.render(t, D)
        img = post.grade_low(img)
        fr = (img * 255).astype(np.uint8)
        fr = cv2.resize(fr, (W, H), interpolation=cv2.INTER_CUBIC)
        scene.draw_particles(fr, info, gt, 2.0)  # particle size in output pixels
        fr = post.finish(fr, fi)
        # darken top for legibility
        fr = (fr.astype(np.float32) * shade).astype(np.uint8) if seg["kind"] == "item" or FMT == "vertical" else fr
        ov.draw(fr, t, info, gt)
        # transitions / camera FX
        zin = clamp01(t / 0.22)
        zout = clamp01((t - (D - 0.2)) / 0.2)
        zoom = 1 + 0.18 * (1 - ease_out_cubic(zin)) + 0.10 * zout ** 2
        blur = 60 * (1 - ease_out_cubic(zin)) + 50 * zout ** 2
        fr = zoom_blur(fr, zoom, blur)
        hit = 0.0
        if seg["kind"] == "item":
            hit = max(0, 1 - (t - 0.04) / 0.35) if t > 0.04 else 0
        elif seg["kind"] == "intro":
            for i in range(3):
                ts = 0.15 + i * 0.28 + 0.12
                if t >= ts:
                    hit = max(hit, max(0, 1 - (t - ts) / 0.3))
        if hit > 0:
            fr = shake(fr, 22 * hit, gt)
            fr = rgb_split(fr, 14 * hit)
        if t < 0.12 and seg["start"] > 0:
            a = 1 - t / 0.12
            fr = cv2.addWeighted(fr, 1 - 0.7 * a, np.full_like(fr, 255), 0.7 * a, 0)
        if preview_times is not None:
            outs.append(fr)
        else:
            proc.stdin.write(fr.tobytes())
    if preview_times is not None:
        return outs
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed for " + out_path)
    os.replace(tmp, out_path)
    print(f"  ✓ {os.path.basename(out_path)}  {nfr} kare  {time.time() - t_start:.0f}s", flush=True)
    return out_path


def shade_mask():
    """Yazıların okunması için hafif karartma: dikeyde üstte, yatayda solda."""
    if L["shade"] == "top":
        g = np.ones(H, np.float32)
        g[:1150] = np.linspace(0.55, 1.0, 1150) ** 0.8
        return g[:, None, None]
    g = np.ones(W, np.float32)
    g[:1150] = np.linspace(0.45, 1.0, 1150) ** 0.9
    return g[None, :, None]


# ======================================================================= sound design plan
def plan_audio(segs, total):
    sfx, voices, events = [], [], []
    inten, wind = [(0, 0.25)], [(0, 0.8)]
    for s in segs:
        st, k = s["start"], s["kind"]
        if s["wav"]:
            voices.append((st + s["voff"], s["wav"]))
        if st > 0:
            sfx.append((st - 0.32, "whoosh", {"d": 0.5, "seed": int(st * 7)}, 0.9))
        mood = s["scene"].get("mood", "")
        wind.append((st + 0.2, 1.0 if mood in ("storm", "arctic", "blood", "night") else 0.55))
        if k == "intro":
            sfx.append((0.15, "braam", {"d": 3.2}, 1.0))
            for i in range(3):
                sfx.append((0.15 + i * 0.28 + 0.1, "impact", {"pitch": 50 + i * 6, "seed": i}, 0.8))
            inten.append((st + s["dur"], 0.35))
        elif k == "item":
            frac = (s["index"] + 1) / s["n"]
            if s["last"] and s["n"] > 1:
                sfx.append((st - 2.6, "riser", {"d": 2.4}, 0.9))
                events.append((st - 0.45, "stop", 0.5))
                sfx.append((st + 0.05, "braam", {"d": 3.0, "root": 29.14}, 1.0))
                sfx.append((st + 0.05, "impact", {"pitch": 40, "d": 2.5}, 1.1))
            else:
                sfx.append((st + 0.05, "impact", {"pitch": 52 + (s["index"] % 3) * 5, "seed": s["index"]}, 0.75))
            sfx.append((st + 0.05, "glitch", {"seed": s["index"]}, 0.45))
            sfx.append((st + 0.25, "whoosh", {"d": 0.35, "seed": s["index"] + 50}, 0.35))
            sfx.append((st + 0.62, "pop", {}, 0.45))
            for j in range(13):
                sfx.append((st + 0.64 + j * 0.065, "tick", {"f": 2600 + j * 120}, 0.22))
            sfx.append((st + 0.82, "pop", {"f0": 500, "f1": 1000}, 0.45))
            for j in range(int(s["data"]["danger"] * 10)):
                sfx.append((st + 1.08 + j * 0.08, "tick", {"f": 1200 + j * 150}, 0.25))
            sfx.append((st + 1.25, "pop", {"f0": 900, "f1": 1800}, 0.4))
            inten.append((st + 0.1, 0.35 + 0.65 * frac))
        else:
            sfx.append((st + 0.15, "shimmer", {}, 0.7))
            sfx.append((st + 0.1, "impact", {"pitch": 45}, 0.6))
            sfx.append((st + 1.6, "pop", {}, 0.5))
            inten.append((st + 0.3, 0.6))
            inten.append((total, 0.3))
    inten.append((total, inten[-1][1]))
    wind.append((total, 0.6))
    return sfx, voices, events, inten, wind


# ======================================================================= extras
def write_srt(segs, path):
    def ts(x):
        ms = int(round(x * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    from .graphics import split_chunks
    n = 1
    lines = []
    for s in segs:
        words = s["words"]
        i = 0
        for ch in split_chunks(" ".join(w for w, _, _ in words)):
            seg = words[i:i + len(ch)]
            i += len(ch)
            lines += [str(n), f"{ts(s['start'] + seg[0][1])} --> {ts(s['start'] + seg[-1][2])}", " ".join(ch), ""]
            n += 1
    open(path, "w", encoding="utf-8").write("\n".join(lines))


def produce(script_path, out_dir, use_tts=True, workers=None, preview=False):
    script = json.load(open(script_path, encoding="utf-8"))
    vid = script["id"]
    work = os.path.join(out_dir, vid + "_work")
    os.makedirs(work, exist_ok=True)
    print(f"▶ {vid}: zaman çizelgesi + seslendirme")
    segs, total = build_timeline(script, work, use_tts)
    print(f"  toplam süre {total:.1f}s, {len(segs)} sahne")

    if preview:
        shots = []
        for s in [segs[0], segs[1], segs[-2], segs[-1]]:
            shots += render_segment((s, script, None, [min(s["dur"] - 0.05, 1.9)], FMT))
        return segs, total, shots

    jobs = [(s, script, os.path.join(work, f"seg_{i:02d}.mp4"), None, FMT) for i, s in enumerate(segs)]
    todo = [j for j in jobs if not os.path.exists(j[2])]
    print(f"▶ 3D render: {len(todo)} sahne, {workers or os.cpu_count()} işlemci")
    with Pool(workers or os.cpu_count()) as pool:
        list(pool.imap_unordered(render_segment, sorted(todo, key=lambda j: -j[0]["dur"])))

    print("▶ ses tasarımı")
    sfx, voices, events, inten, wind = plan_audio(segs, total)
    mix = A.build_mix(total, voices, sfx, inten, wind, events)
    raw = os.path.join(work, "mix.wav")
    A.write_wav(raw, mix)
    master = os.path.join(work, "master.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af",
                    "loudnorm=I=-14:TP=-1.2:LRA=9", "-ar", "44100", master], check=True)

    print("▶ birleştirme")
    lst = os.path.join(work, "list.txt")
    open(lst, "w").write("".join(f"file '{os.path.abspath(j[2])}'\n" for j in jobs))
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
    pub = script.get("publish", {})
    meta = f"{pub.get('title', '')}\n\n{pub.get('description', '')}\n\n{' '.join(pub.get('hashtags', []))}\n"
    open(os.path.join(out_dir, vid + "_metadata.txt"), "w", encoding="utf-8").write(meta)
    # thumbnail from the #1 reveal
    last = segs[-2]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{last['start'] + 1.9:.2f}", "-i", final,
                    "-frames:v", "1", "-q:v", "2", os.path.join(out_dir, vid + "_kapak.jpg")], check=True)
    print(f"✔ {final}")
    return final
