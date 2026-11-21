"""Procedural sound design - everything synthesised from code (no samples, no licences).

Layers: ambient wind, cinematic drone/pulse score, whooshes, impacts, braams,
risers, counter ticks, UI pops, + narration with side-chain ducking.
"""
import numpy as np
import wave
from scipy import signal

SR = 44100
rng = np.random.default_rng(1234)


def _t(d):
    return np.arange(int(d * SR)) / SR


def bp(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, hi], btype="band", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def lp(x, f, order=2):
    sos = signal.butter(order, f, btype="low", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def hp(x, f, order=2):
    sos = signal.butter(order, f, btype="high", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def smooth_noise(n, rate_hz, seed):
    r = np.random.default_rng(seed)
    k = max(2, int(n / SR * rate_hz) + 2)
    pts = r.uniform(0, 1, k)
    return np.interp(np.linspace(0, k - 1, n), np.arange(k), pts)


def reverb_ir(dur=2.2, seed=7):
    r = np.random.default_rng(seed)
    t = _t(dur)
    L = r.normal(0, 1, len(t)) * np.exp(-t * 3.2)
    R = r.normal(0, 1, len(t)) * np.exp(-t * 3.2)
    L = lp(L, 6000)
    R = lp(R, 6000)
    L[:int(0.012 * SR)] *= 0
    R[:int(0.017 * SR)] *= 0
    return np.stack([L, R]) * 0.08


IR = reverb_ir()


def reverb(st, wet=0.3):
    out = np.stack([signal.fftconvolve(st[0], IR[0])[:st.shape[1]], signal.fftconvolve(st[1], IR[1])[:st.shape[1]]])
    return st * (1 - wet * 0.3) + out * wet


def pan(x, p):  # p -1..1 (scalar or array)
    l = np.cos((p + 1) * np.pi / 4)
    r = np.sin((p + 1) * np.pi / 4)
    return np.stack([x * l, x * r])


def place(buf, st, t0, gain=1.0):
    i = int(t0 * SR)
    if i < 0:
        st = st[:, -i:]
        i = 0
    n = min(st.shape[1], buf.shape[1] - i)
    if n > 0:
        buf[:, i:i + n] += st[:, :n] * gain


# ------------------------------------------------------------------ one-shots
def whoosh(d=0.55, up=True, seed=0):
    r = np.random.default_rng(seed)
    t = _t(d)
    n = r.normal(0, 1, len(t))
    x = np.zeros_like(n)
    bands = np.geomspace(300, 6000, 10)
    pos = t / d if up else 1 - t / d
    for i in range(len(bands) - 1):
        c = i / (len(bands) - 2)
        w = np.exp(-((pos - c) ** 2) / 0.02)
        x += bp(n, bands[i], bands[i + 1]) * w
    env = np.sin(np.pi * np.clip(t / d, 0, 1)) ** 2.2
    x = x * env
    x /= np.abs(x).max() + 1e-9
    p = np.linspace(-0.8, 0.8, len(t)) * (1 if seed % 2 else -1)
    return pan(x, p)


def impact(d=2.0, seed=0, pitch=55):
    r = np.random.default_rng(seed)
    t = _t(d)
    f = pitch + pitch * 1.8 * np.exp(-t * 14)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.6)
    body = lp(r.normal(0, 1, len(t)), 900) * np.exp(-t * 9) * 0.9
    crack = hp(r.normal(0, 1, len(t)), 2500) * np.exp(-t * 35) * 0.5
    x = np.tanh((sub * 1.2 + body + crack) * 1.4)
    st = np.stack([x, x])
    return reverb(st, 0.45)


def braam(d=3.0, root=36.71, seed=0):
    """Low brass-like 'BRAAM' (detuned saws through opening low-pass)."""
    t = _t(d)
    x = np.zeros_like(t)
    for mult in (1, 1.5, 2, 3):
        for det in (-0.4, 0.0, 0.45):
            f = root * mult + det
            ph = (f * t + rng.uniform()) % 1
            x += (2 * ph - 1) / mult
    env = np.minimum(1, t / 0.06) * np.exp(-t * 0.9)
    cut = 300 + 2200 * np.exp(-t * 2.5)
    # time-varying LP approximated by crossfading two filters
    a = lp(x, 2400, 3)
    b = lp(x, 300, 3)
    k = (cut - 300) / 2200
    y = (a * k + b * (1 - k)) * env
    y = np.tanh(y * 0.5)
    return reverb(np.stack([y, y * 0.96]), 0.5)


def riser(d=2.5, seed=0):
    t = _t(d)
    r = np.random.default_rng(seed)
    n = r.normal(0, 1, len(t))
    pos = t / d
    x = np.zeros_like(t)
    bands = np.geomspace(200, 9000, 12)
    for i in range(len(bands) - 1):
        c = i / (len(bands) - 2)
        x += bp(n, bands[i], bands[i + 1]) * np.exp(-((pos - c) ** 2) / 0.03)
    f = 120 * 2 ** (pos * 4)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.25 + np.sin(2 * np.pi * np.cumsum(f * 1.505) / SR) * 0.15
    y = (x * 0.8 + tone) * pos ** 2.2
    y /= np.abs(y).max() + 1e-9
    return reverb(pan(y, np.sin(t * 9) * 0.5), 0.35)


def tick(seed=0, f=3200):
    t = _t(0.05)
    x = np.sin(2 * np.pi * f * t) * np.exp(-t * 160) + hp(rng.normal(0, 1, len(t)), 4000) * np.exp(-t * 300) * 0.4
    return np.stack([x, x]) * 0.6


def pop(f0=700, f1=1400):
    t = _t(0.12)
    f = f0 + (f1 - f0) * np.minimum(1, t / 0.05)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 35)
    return reverb(np.stack([x, x]), 0.2) * 0.7


def shimmer(d=2.0):
    t = _t(d)
    x = np.zeros_like(t)
    for i, f in enumerate([1174.66, 1396.91, 1760.0, 2349.32]):
        x += np.sin(2 * np.pi * f * t) * np.exp(-t * (2.2 + i * 0.4)) * np.minimum(1, t / (0.01 + i * 0.05))
    return reverb(pan(x / 3, np.sin(t * 4) * 0.6), 0.6)


def glitch(d=0.18, seed=0):
    r = np.random.default_rng(seed)
    t = _t(d)
    sq = np.sign(np.sin(2 * np.pi * r.uniform(200, 900) * t))
    x = (sq * 0.4 + r.normal(0, 0.5, len(t))) * (r.random(len(t) // 400 + 1).repeat(400)[:len(t)] > 0.4)
    x = bp(x, 400, 7000) * np.exp(-t * 10)
    return np.stack([x, np.roll(x, 120)]) * 0.5


# ------------------------------------------------------------------ beds
def wind_bed(total, intensity_curve):
    n = int(total * SR)
    base = rng.normal(0, 1, n)
    out = np.zeros((2, n))
    for ch in range(2):
        nb = np.roll(base, ch * 5000) if ch else base
        lo = bp(nb, 120, 600) * (0.5 + 0.8 * smooth_noise(n, 0.35, 10 + ch))
        hi = bp(nb, 900, 2600) * (0.2 + 0.9 * smooth_noise(n, 0.6, 20 + ch) ** 2)
        whistle = bp(nb, 1500, 1650, 2) * smooth_noise(n, 0.25, 30 + ch) ** 3 * 2.5
        out[ch] = lo + hi * 0.6 + whistle
    out /= np.abs(out).max() + 1e-9
    return out * intensity_curve[None, :]


NOTE = lambda m: 440 * 2 ** ((m - 69) / 12)
CHORDS = [[38, 50, 53, 57], [34, 50, 53, 58], [31, 50, 55, 58], [33, 49, 52, 57]]   # Dm  Bb  Gm  A


def score(total, bpm, intensity, events):
    """Dark cinematic pulse score. intensity: per-sample 0..1; events: list of (t, 'drop'|'stop')."""
    n = int(total * SR)
    t = np.arange(n) / SR
    beat = 60 / bpm
    bar = beat * 4
    pad = np.zeros(n)
    bass = np.zeros(n)
    for bi in range(int(total / bar) + 2):
        ch = CHORDS[bi % 4]
        s0 = int(bi * bar * SR)
        s1 = min(n, int((bi + 1) * bar * SR + 0.3 * SR))
        if s0 >= n:
            break
        tt = t[s0:s1] - bi * bar
        env = np.minimum(1, tt / 0.4) * np.minimum(1, np.maximum(0, (bar + 0.3 - tt)) / 0.4)
        seg = np.zeros_like(tt)
        for m in ch[1:]:
            for det in (-0.12, 0.0, 0.13):
                f = NOTE(m) * 2 ** (det / 12)
                seg += np.sin(2 * np.pi * f * tt + det * 7) + 0.3 * np.sin(4 * np.pi * f * tt)
        pad[s0:s1] += seg * env
        fb = NOTE(ch[0])
        # pulsing bass 8ths
        pulse = np.exp(-((tt % (beat / 2)) * 9))
        bass[s0:s1] += (np.sin(2 * np.pi * fb * tt) + 0.5 * np.sin(2 * np.pi * fb * 2 * tt)) * pulse * env
    pad = lp(pad, 1800) * 0.11
    bass = lp(np.tanh(bass * 1.5), 400) * 0.35
    # kick on beats, hats on 8ths (enter with intensity)
    kick = np.zeros(n)
    hat = np.zeros(n)
    kt = _t(0.35)
    k1 = np.sin(2 * np.pi * np.cumsum(45 + 110 * np.exp(-kt * 30)) / SR) * np.exp(-kt * 8)
    ht = _t(0.06)
    h1 = hp(rng.normal(0, 1, len(ht)), 7000) * np.exp(-ht * 70)
    nb = int(total / beat) + 1
    for i in range(nb):
        s = int(i * beat * SR)
        if s + len(k1) < n:
            kick[s:s + len(k1)] += k1
        for half in (0, 0.5):
            s2 = int((i + half) * beat * SR)
            if s2 + len(h1) < n:
                hat[s2:s2 + len(h1)] += h1 * (0.6 if half else 0.35)
    I = intensity
    mix = pad * (0.6 + 0.4 * I) + bass * (0.25 + 0.75 * I) + kick * 0.55 * np.clip(I * 1.6 - 0.4, 0, 1) \
        + hat * 0.18 * np.clip(I * 2 - 1, 0, 1)
    # stops (dramatic silence)
    for (te, kind, d) in events:
        if kind == "stop":
            a, b = int(te * SR), int((te + d) * SR)
            g = np.ones(n)
            g[a:b] = 0
            g = lp(g, 30, 1)
            mix *= g
    st = np.stack([mix, np.roll(mix, 300) * 0.98])
    return reverb(st, 0.25)


# ------------------------------------------------------------------ mix
def read_wav_mono(path):
    with wave.open(path) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        if w.getnchannels() == 2:
            a = a.reshape(-1, 2).mean(1)
        return a


def write_wav(path, st):
    st = np.clip(st, -1, 1)
    data = (st.T * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def build_mix(total, voices, sfx, intensity_pts, wind_pts, events, bpm=96):
    """voices: [(t0, wav_path)], sfx: [(t, name, kwargs, gain)], *_pts: [(t, value)] keyframes."""
    n = int(total * SR)
    tt = np.arange(n) / SR
    I = np.interp(tt, [p[0] for p in intensity_pts], [p[1] for p in intensity_pts])
    Wc = np.interp(tt, [p[0] for p in wind_pts], [p[1] for p in wind_pts])
    music = score(total, bpm, I, events)[:, :n]
    wind = wind_bed(total, Wc)[:, :n]
    vbuf = np.zeros((2, n))
    for t0, path in voices:
        if path:
            v = read_wav_mono(path)
            v = v / (np.abs(v).max() + 1e-9) * 0.92
            place(vbuf, np.stack([v, v]), t0)
    vb = reverb(vbuf, 0.06)
    # side-chain ducking
    env = np.abs(vbuf[0])
    env = lp(env, 8, 1)
    env = np.clip(env / (env.max() + 1e-9) * 2.2, 0, 1)
    duck = 1 - 0.55 * env
    fx = np.zeros((2, n))
    gens = {"whoosh": whoosh, "impact": impact, "braam": braam, "riser": riser, "tick": tick,
            "pop": pop, "shimmer": shimmer, "glitch": glitch}
    for t0, name, kw, gain in sfx:
        place(fx, gens[name](**kw), t0, gain)
    mix = music * 0.55 * duck + wind * 0.10 * (1 - 0.4 * env) + fx * 0.42 + vb * 1.0
    # gentle master glue + soft clip
    mix = np.tanh(mix * 1.1) * 0.9
    fade = np.minimum(1, np.minimum(tt / 0.05, (total - tt) / 0.6))
    return mix * fade
