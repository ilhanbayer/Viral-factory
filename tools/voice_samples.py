"""Ses örnekleri: aynı gerilimli metni farklı ücretsiz seslerle okutur (GitHub Actions'ta çalışır)."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from factory import tts  # noqa: E402

TEXT = ("Şubat 1959. Dokuz deneyimli dağcı, çadırlarını içeriden keserek karanlığa kaçtı. "
        "Bazıları yalnızca çoraplarıyla, bazıları yalınayak. Hiçbiri geri dönmedi.")
VOICES = [
    ("01_ahmet", "tr-TR-AhmetNeural", "+6%", "-2Hz"),
    ("02_ahmet_gerilim", "tr-TR-AhmetNeural", "+0%", "-9Hz"),
    ("03_emel", "tr-TR-EmelNeural", "+6%", "-2Hz"),
    ("04_andrew", "en-US-AndrewMultilingualNeural", "+4%", "-2Hz"),
    ("05_brian", "en-US-BrianMultilingualNeural", "+4%", "-2Hz"),
    ("06_florian", "de-DE-FlorianMultilingualNeural", "+4%", "-2Hz"),
    ("07_remy", "fr-FR-RemyMultilingualNeural", "+4%", "-2Hz"),
    ("08_giuseppe", "it-IT-GiuseppeMultilingualNeural", "+4%", "-2Hz"),
    ("09_ava", "en-US-AvaMultilingualNeural", "+4%", "+0Hz"),
    ("10_emma", "en-US-EmmaMultilingualNeural", "+4%", "+0Hz"),
]
out = sys.argv[1] if len(sys.argv) > 1 else "samples"
os.makedirs(out, exist_ok=True)
made = []
for name, voice, rate, pitch in VOICES:
    tts.configure("edge", voice, rate, pitch)
    try:
        wav, d, _ = tts.synth(TEXT, os.path.join(out, "_cache"), "story")
        if not wav:
            raise RuntimeError("ses yok")
    except Exception as e:
        print("ATLANDI", name, e)
        continue
    mp3 = os.path.join(out, f"ses_{name}.mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-b:a", "160k", mp3], check=True)
    made.append(mp3)
    print("OK", name, round(d, 1), "sn")
# hepsi tek dosyada, araya bip ve 1 sn boşluk
lst = os.path.join(out, "list.txt")
beep = os.path.join(out, "_beep.mp3")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=880:d=0.15", "-f", "lavfi", "-i",
                "anullsrc=r=44100:cl=mono", "-filter_complex", "[0][1]concat=n=2:v=0:a=1,atrim=0:1.0[a]", "-map", "[a]",
                "-ar", "44100", "-ac", "1", "-b:a", "160k", beep], check=True)
with open(lst, "w") as f:
    for m in made:
        f.write(f"file '{os.path.abspath(beep)}'\nfile '{os.path.abspath(m)}'\n")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-ar", "44100", "-ac", "1",
                "-b:a", "160k", os.path.join(out, "TUM_SESLER.mp3")], check=True)
print("\n".join(made))
