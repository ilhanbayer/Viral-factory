#!/usr/bin/env python3
"""Viral video fabrikası - tek komut.

  python run.py                 # kuyruktaki sıradaki konuyu üret (kuyruk boşsa Gemini ile yeni konu yazar)
  python run.py --count 3       # art arda 3 video
  python run.py --topic topics/queue/001_en_tehlikeli_10_dag.json
  python run.py --no-tts        # seslendirmesiz (test)
  python run.py --voice gtts    # Google sesi (varsayılan: Microsoft edge, Ahmet)
  python run.py --speaker emel  # kadın sesi
  python run.py --upload        # bittikten sonra YouTube'a yükle
"""
import argparse
import glob
import json
import os
import random
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from factory.compose import produce  # noqa: E402
from factory import scriptgen  # noqa: E402

QUEUE = os.path.join(ROOT, "topics", "queue")
DONE = os.path.join(ROOT, "topics", "done")
OUT = os.path.join(ROOT, "output")


def next_topic():
    files = sorted(glob.glob(os.path.join(QUEUE, "*.json")))
    if files:
        return files[0]
    if os.environ.get("AUTO_GEMINI") != "1":   # eski liste formatını üretmesin; konu kuyruğu asistan tarafından doldurulur
        return None
    done = [json.load(open(f, encoding="utf-8")).get("series_title", "") for f in glob.glob(os.path.join(DONE, "*.json"))]
    cat = random.choice(scriptgen.CATEGORIES)
    print(f"Kuyruk boş → Gemini ile yeni konu ({cat})")
    for attempt in range(3):
        try:
            data = scriptgen.generate(done, cat)
        except Exception as e:
            print("  üretim hatası:", e)
            continue
        if data:
            n = len(glob.glob(os.path.join(DONE, "*.json"))) + 1
            path = os.path.join(QUEUE, f"{n:03d}_{data['id']}.json")
            json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            return path
        break
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--no-tts", action="store_true")
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--keep-work", action="store_true")
    ap.add_argument("--voice", choices=["edge", "gtts"], help="seslendirme motoru (varsayılan: edge)")
    ap.add_argument("--speaker", help="edge sesi: ahmet | emel")
    ap.add_argument("--rate", help="edge konuşma hızı, ör. +8%%")
    a = ap.parse_args()
    from factory import tts
    tts.configure(a.voice, a.speaker, a.rate)
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(DONE, exist_ok=True)
    for _ in range(a.count):
        path = a.topic or next_topic()
        if not path:
            print("Üretilecek konu yok. topics/queue içine JSON ekleyin ya da GEMINI_API_KEY tanımlayın.")
            return
        script = json.load(open(path, encoding="utf-8"))
        if script.get("format") == "cartoon":
            from factory.cartoon import produce_cartoon
            finals = produce_cartoon(script, OUT, use_tts=not a.no_tts)
            final = finals[0]
        elif script.get("format") == "story":
            from factory.story_compose import produce_story
            finals = produce_story(script, OUT, use_tts=not a.no_tts)
            final = finals[0]
        else:
            final = produce(path, OUT, use_tts=not a.no_tts)
        if a.upload and script.get("format") not in ("story", "cartoon"):
            from factory.upload_youtube import upload
            p = script.get("publish", {})
            upload(final, p.get("title", script["series_title"]),
                   p.get("description", "") + "\n\n" + " ".join(p.get("hashtags", [])), p.get("hashtags", []))
        if not a.topic and os.path.dirname(os.path.abspath(path)) == QUEUE:
            shutil.move(path, os.path.join(DONE, os.path.basename(path)))
        if not a.keep_work:
            for d in glob.glob(os.path.join(OUT, "*_work")) + [os.path.join(OUT, "_voicecache")]:
                shutil.rmtree(d, ignore_errors=True)
        a.topic = None


if __name__ == "__main__":
    main()
