"""Seslendirme motorları (ikisi de ücretsiz, API anahtarı gerektirmez).

  edge  : Microsoft Edge sinir ağı sesleri (tr-TR-AhmetNeural / tr-TR-EmelNeural).
          Çok doğal; ayrıca kelime zaman damgaları verir -> altyazı sese birebir oturur.
  gtts  : Google Translate TTS.

Seçim: run.py --voice edge|gtts --speaker ahmet|emel
       ya da ortam değişkenleri VOICE_ENGINE / VOICE_NAME / VOICE_RATE
       ya da konu JSON'unda "voice": {"engine": "edge", "speaker": "emel", "rate": "+8%"}
Seçilen motor çalışmazsa diğerine, o da çalışmazsa süre tahminine düşer.

synth() -> (wav_path | None, süre_sn, kelime_zamanları | None)
kelime_zamanları: [(kelime, başlangıç_sn, bitiş_sn), ...]  (wav'ın başına göre)
"""
import os
import json
import asyncio
import subprocess
import hashlib
import wave
import re
import numpy as np

SR = 44100
GTTS_TEMPO = 1.2
SPEAKERS = {"ahmet": "tr-TR-AhmetNeural", "emel": "tr-TR-EmelNeural"}

CONFIG = {
    "engine": os.environ.get("VOICE_ENGINE", "edge"),
    "speaker": os.environ.get("VOICE_NAME", "ahmet"),
    "rate": os.environ.get("VOICE_RATE", "+14%"),
    "pitch": os.environ.get("VOICE_PITCH", "-2Hz"),     # biraz daha tok, otoriter anlatıcı
}

# ses zinciri: düşük uğultu temizliği, netlik, hafif kompresyon
# "trailer" anlatıcı zinciri: gövde (150 Hz), çamur temizliği (300 Hz), netlik (3.5 kHz), hava (10 kHz),
# sibilans kontrolü, yayın tipi kompresyon ve limitör
VOICE_FX = ("highpass=f=70,equalizer=f=150:t=q:w=1.0:g=3,equalizer=f=300:t=q:w=1.2:g=-3,"
            "equalizer=f=3500:t=q:w=1.0:g=3.5,equalizer=f=10000:t=q:w=1.0:g=2,deesser=i=0.35,"
            "acompressor=threshold=-21dB:ratio=4:attack=4:release=90:makeup=5,alimiter=limit=0.95")


def configure(engine=None, speaker=None, rate=None, pitch=None):
    if engine:
        CONFIG["engine"] = engine
    if speaker:
        CONFIG["speaker"] = speaker
    if rate:
        CONFIG["rate"] = rate
    if pitch:
        CONFIG["pitch"] = pitch


def _dur(path):
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()


def estimate_duration(text):
    return max(1.2, len(text) / 15.5)


# ---------------------------------------------------------------- edge-tts
async def _edge_stream(text, voice, rate, pitch, volume, mp3):
    import edge_tts
    kw = dict(rate=rate, pitch=pitch, volume=volume)
    try:
        com = edge_tts.Communicate(text, voice, boundary="WordBoundary", **kw)   # edge-tts >= 7
    except TypeError:
        com = edge_tts.Communicate(text, voice, **kw)                            # eski sürümler
    words = []
    with open(mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                s = ch["offset"] / 1e7
                words.append((ch["text"], s, s + ch["duration"] / 1e7))
    return words


def _sentences(text):
    return [s for s in re.split(r"(?<=[.!?:])\s+", text.strip()) if s]


def _pct(s):
    return int(str(s).replace("%", "").replace("+", "") or 0)


def prosody(role, i, n, sent):
    """Sunucu/belgesel anlatıcısı gibi vurgu: cümlenin videodaki görevine göre hız, ton, güç ve ardından gelen es."""
    r, p, v, pause = _pct(CONFIG["rate"]), _pct(CONFIG["pitch"].replace("Hz", "")), 0, 0.17
    if role == "item" and i == 0:            # "Yedinci, Matterhorn."  -> tok, yüksek, kısa es
        r, p, v, pause = r - 6, p + 7, v + 12, 0.12
    elif role == "intro" and i == 0:          # kanca: biraz daha ağır ve gizemli
        r, p, pause = r - 4, p - 2, 0.22
    elif role == "intro" and i == n - 1:      # "İşte ...!" -> coşkulu
        r, p, v = r + 4, p + 8, v + 15
    elif role == "outro":
        r, p, v = r + 2, p + 4, v + 8
    if sent.endswith("!"):
        p, v = p + 4, v + 8
    if sent.endswith("?"):
        p += 3
    if i == n - 1:
        pause = 0.0
    return f"{r:+d}%", f"{p:+d}Hz", f"{v:+d}%", pause


def _decode(mp3):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", mp3, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def _edge(text, base, role="item"):
    voice = SPEAKERS.get(CONFIG["speaker"].lower(), CONFIG["speaker"])
    sents = _sentences(text)
    thr = 10 ** (-42 / 20)
    out, words, t = [], [], 0.0
    for i, s in enumerate(sents):
        rate, pitch, vol, pause = prosody(role, i, len(sents), s)
        mp3 = f"{base}_{i}.mp3"
        wb = asyncio.run(_edge_stream(s, voice, rate, pitch, vol, mp3))
        if not os.path.exists(mp3) or os.path.getsize(mp3) < 500:
            raise RuntimeError("edge-tts boş ses döndürdü")
        a = _decode(mp3)
        nz = np.nonzero(np.abs(a) > thr)[0]
        if len(nz) == 0:
            continue
        lead = max(0, nz[0] - int(0.02 * SR))
        a = a[lead:nz[-1] + int(0.06 * SR)]
        off = t - lead / SR
        words += [(w, max(t, off + s0), off + s1) for w, s0, s1 in wb]
        out.append(a)
        t += len(a) / SR
        if pause:
            out.append(np.zeros(int(pause * SR), np.float32))
            t += pause
    if not out:
        raise RuntimeError("edge-tts ses üretmedi")
    a = np.concatenate(out)
    tmp = base + "_dry.wav"
    _write_mono(tmp, a)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-af", VOICE_FX, "-ar", str(SR), "-ac", "1",
                    base + ".wav"], check=True)
    return words or None


def _write_mono(path, a):
    a = np.clip(a, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((a * 32767).astype(np.int16).tobytes())


# ---------------------------------------------------------------- gTTS
def _gtts(text, base):
    from gtts import gTTS
    mp3 = base + ".mp3"
    gTTS(text=text, lang="tr", slow=False).save(mp3)
    af = (f"silenceremove=start_periods=1:start_threshold=-45dB,"
          f"areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
          f"atempo={GTTS_TEMPO}," + VOICE_FX)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-af", af, "-ar", str(SR), "-ac", "1",
                    base + ".wav"], check=True)
    return None


ENGINES = {"edge": _edge, "gtts": _gtts}


def synth(text, cache_dir, role="item"):
    os.makedirs(cache_dir, exist_ok=True)
    order = [CONFIG["engine"]] + [e for e in ENGINES if e != CONFIG["engine"]]
    for eng in order:
        key = hashlib.md5(f"{eng}|{role}|{CONFIG['speaker']}|{CONFIG['rate']}|{CONFIG['pitch']}|{GTTS_TEMPO}|v2|{text}".encode()).hexdigest()[:16]
        base = os.path.join(cache_dir, f"{eng}_{key}")
        wav, js = base + ".wav", base + ".json"
        if os.path.exists(wav):
            words = json.load(open(js)) if os.path.exists(js) else None
            return wav, _dur(wav), words
        try:
            words = _edge(text, base, role) if eng == "edge" else _gtts(text, base)
        except Exception as e:
            print(f"  [tts] {eng} kullanılamadı ({type(e).__name__}: {str(e)[:80]})")
            continue
        if words:
            json.dump(words, open(js, "w"), ensure_ascii=False)
        if eng != order[0]:
            print(f"  [tts] yedek motor kullanıldı: {eng}")
        return wav, _dur(wav), words
    print("  [tts] hiçbir motor çalışmadı: sessiz, süre tahmini kullanılıyor")
    return None, estimate_duration(text), None


def align_words(narration, boundaries, voff, vdur):
    """Map TTS word boundaries onto the narration's whitespace words (punctuation kept for display).
    Returns [(word, start, end)] relative to segment, or None if alignment is not reliable."""
    if not boundaries:
        return None
    words = narration.split()
    out, j, bad = [], 0, 0
    norm = lambda s: "".join(c for c in s.lower() if c.isalnum())
    for w in words:
        nw = norm(w)
        if j >= len(boundaries):
            return None
        s = boundaries[j][1]
        e = boundaries[j][2]
        acc = norm(boundaries[j][0])
        j += 1
        # a narration word may be split into several TTS tokens (ör. 1865'ten -> 1865 / ten)
        while acc != nw and j < len(boundaries) and len(acc) < len(nw):
            acc += norm(boundaries[j][0])
            e = boundaries[j][2]
            j += 1
        if acc != nw:
            bad += 1
        out.append([w, voff + s, voff + e])
    if bad > max(1, len(words) // 4):
        return None
    # fill gaps so the highlight never flickers off between words
    for i in range(len(out) - 1):
        out[i][2] = max(out[i][2], out[i + 1][1])
    out[-1][2] = max(out[-1][2], voff + vdur)
    return [tuple(x) for x in out]
