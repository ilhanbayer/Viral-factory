"""Chatterbox Multilingual (MIT) Türkçe ses testi: farklı referans sesler + duygu ayarları, CPU hızı ve
anlaşılırlık (faster-whisper ile karakter hata oranı)."""
import os, sys, time, asyncio, subprocess, json
import torch
_orig = torch.load
def _load(*a, **k):
    k.setdefault("map_location", "cpu")
    return _orig(*a, **k)
torch.load = _load
import torchaudio as ta
import edge_tts

OUT = "voicetest"
os.makedirs(OUT, exist_ok=True)
REF_TEXT = ("Bir varmış bir yokmuş. Evvel zaman içinde, kalbur saman içinde, Akşehir'de çok bilge "
            "ve bir o kadar da şakacı bir adam yaşarmış. Herkes ona Hoca derdi.")
LINES = [
    ("anlatici", "Bir gün Hoca, komşusundan büyük bir kazan ödünç ister. Ertesi gün kazanın içine minicik bir tencere koyup geri getirir."),
    ("hoca", "Müjde komşu! Senin kazan doğurdu, bu da yavrusu!"),
    ("komsu", "Hocam, kazan doğurur mu hiç? Ama madem öyle diyorsun, olsun bakalım!"),
]
REFS = {"ahmet": ("tr-TR-AhmetNeural", "-4Hz"), "emel": ("tr-TR-EmelNeural", "+0Hz"),
        "andrew": ("en-US-AndrewMultilingualNeural", "-2Hz"), "brian": ("en-US-BrianMultilingualNeural", "-6Hz")}


async def mk(voice, pitch, path):
    await edge_tts.Communicate(REF_TEXT, voice, pitch=pitch, rate="-5%").save(path + ".mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path + ".mp3", "-ar", "24000", "-ac", "1", path], check=True)

for k, (v, p) in REFS.items():
    asyncio.run(mk(v, p, f"{OUT}/ref_{k}.wav"))

from chatterbox.mtl_tts import ChatterboxMultilingualTTS
t0 = time.time()
model = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
print("model yüklendi", round(time.time() - t0), "s", flush=True)
torch.set_num_threads(os.cpu_count())

configs = [
    ("A_varsayilan", None, 0.5, 0.5),
    ("B_ahmet_dramatik", f"{OUT}/ref_ahmet.wav", 0.75, 0.3),
    ("C_andrew_dramatik", f"{OUT}/ref_andrew.wav", 0.75, 0.3),
    ("D_brian_sakin", f"{OUT}/ref_brian.wav", 0.5, 0.5),
    ("E_emel_dramatik", f"{OUT}/ref_emel.wav", 0.7, 0.35),
]
from faster_whisper import WhisperModel
asr = WhisperModel("small", device="cpu", compute_type="int8")

def cer(a, b):
    import difflib
    norm = lambda s: "".join(c for c in s.lower() if c.isalnum())
    a, b = norm(a), norm(b)
    return 1 - difflib.SequenceMatcher(None, a, b).ratio()

report = {}
for name, ref, ex, cfg in configs:
    parts, gen_t, audio_t = [], 0, 0
    for who, text in LINES:
        t0 = time.time()
        kw = dict(language_id="tr", exaggeration=ex, cfg_weight=cfg)
        if ref:
            kw["audio_prompt_path"] = ref
        wav = model.generate(text, **kw)
        gen_t += time.time() - t0
        p = f"{OUT}/{name}_{who}.wav"
        ta.save(p, wav, model.sr)
        audio_t += wav.shape[-1] / model.sr
        parts.append(p)
    lst = f"{OUT}/{name}.txt"
    open(lst, "w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-b:a", "160k",
                    f"{OUT}/{name}.mp3"], check=True)
    segs, _ = asr.transcribe(f"{OUT}/{name}.mp3", language="tr")
    hyp = " ".join(s.text for s in segs)
    e = cer(" ".join(t for _, t in LINES), hyp)
    report[name] = {"cer": round(e, 3), "gen_s": round(gen_t, 1), "audio_s": round(audio_t, 1),
                    "rtf": round(gen_t / max(audio_t, 0.1), 2), "asr": hyp}
    print(name, report[name], flush=True)
json.dump(report, open(f"{OUT}/rapor.json", "w"), ensure_ascii=False, indent=1)

# r2
