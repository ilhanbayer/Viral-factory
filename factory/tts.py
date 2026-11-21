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

SR = 44100
GTTS_TEMPO = 1.2
SPEAKERS = {"ahmet": "tr-TR-AhmetNeural", "emel": "tr-TR-EmelNeural"}

CONFIG = {
    "engine": os.environ.get("VOICE_ENGINE", "edge"),
    "speaker": os.environ.get("VOICE_NAME", "ahmet"),
    "rate": os.environ.get("VOICE_RATE", "+8%"),
}

# ses zinciri: düşük uğultu temizliği, netlik, hafif kompresyon
VOICE_FX = ("highpass=f=80,equalizer=f=250:t=q:w=1.2:g=-2.5,equalizer=f=3200:t=q:w=1.0:g=3,"
            "equalizer=f=9000:t=q:w=1:g=1.5,acompressor=threshold=-18dB:ratio=3:attack=5:release=80:makeup=3")


def configure(engine=None, speaker=None, rate=None):
    if engine:
        CONFIG["engine"] = engine
    if speaker:
        CONFIG["speaker"] = speaker
    if rate:
        CONFIG["rate"] = rate


def _dur(path):
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()


def estimate_duration(text):
    return max(1.2, len(text) / 15.5)


# ---------------------------------------------------------------- edge-tts
async def _edge_stream(text, voice, rate, mp3):
    import edge_tts
    try:
        com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")   # edge-tts >= 7
    except TypeError:
        com = edge_tts.Communicate(text, voice, rate=rate)                            # eski sürümler
    words = []
    with open(mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                s = ch["offset"] / 1e7
                words.append((ch["text"], s, s + ch["duration"] / 1e7))
    return words


def _edge(text, base):
    voice = SPEAKERS.get(CONFIG["speaker"].lower(), CONFIG["speaker"])
    mp3 = base + ".mp3"
    words = asyncio.run(_edge_stream(text, voice, CONFIG["rate"], mp3))
    if not os.path.exists(mp3) or os.path.getsize(mp3) < 1000:
        raise RuntimeError("edge-tts boş ses döndürdü")
    # Başlangıçtaki sessizliği kesmiyoruz (kelime zamanları kaymasın); sadece sondakini kırpıyoruz.
    af = "areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse," + VOICE_FX
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-af", af, "-ar", str(SR), "-ac", "1",
                    base + ".wav"], check=True)
    return words or None


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


def synth(text, cache_dir):
    os.makedirs(cache_dir, exist_ok=True)
    order = [CONFIG["engine"]] + [e for e in ENGINES if e != CONFIG["engine"]]
    for eng in order:
        key = hashlib.md5(f"{eng}|{CONFIG['speaker']}|{CONFIG['rate']}|{GTTS_TEMPO}|{text}".encode()).hexdigest()[:16]
        base = os.path.join(cache_dir, f"{eng}_{key}")
        wav, js = base + ".wav", base + ".json"
        if os.path.exists(wav):
            words = json.load(open(js)) if os.path.exists(js) else None
            return wav, _dur(wav), words
        try:
            words = ENGINES[eng](text, base)
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
