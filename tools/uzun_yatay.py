#!/usr/bin/env python3
"""Bir Shorts dizisini (topics/done/<id>.json) YATAY (1920x1080) uzun videoya çevirir.

Dikey bölümleri yan yana bulanık arka planla yapıştırmak yerine, tüm bölümlerin senaryosu
tek bir yatay kurguda baştan render edilir: tam ekran yatay fotoğraf çekimleri, yatay yazı
yerleşimi, YouTube bölümleri (chapters). Bölüm sonlarındaki "Bölüm k'de..." ve "takip et"
cümleleri çıkarılır; sonda tek bir abone ol çağrısı kalır.

  python tools/uzun_yatay.py S010_derinkuyu_urgup [--title "..."]
Çıktı: output/<id>_yatay.mp4 (+ _kapak.jpg, _metadata.txt, .srt)
"""
import argparse
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TEASER = re.compile(r"^\s*(Bölüm \d+['’]?(de|da|te|ta)\b|In Part \d+|Part \d+:)", re.I)


def is_follow(b):
    sh = b.get("show", {})
    return sh.get("type") == "icon" and sh.get("name") == "eye"


def clean_title(t):
    t = re.sub(r"\s*#shorts", "", t)
    t = re.sub(r"\s*(Bölüm|Part)\s*\d+\s*$", "", t.strip())
    return t.strip()


def to_long(series, title=None):
    lang = series.get("lang", "tr")
    parts = series["parts"]
    beats, chapters, descs = [], [], []
    for k, p in enumerate(parts):
        last = k == len(parts) - 1
        pb = [dict(b, show=dict(b["show"])) for b in p["beats"]]
        if not last:
            while pb and (is_follow(pb[-1]) or TEASER.search(pb[-1]["say"])):
                pb.pop()
        else:
            if pb and is_follow(pb[-1]):
                pb[-1]["say"] = "Yeni diziler için *abone ol*." if lang == "tr" else "*Subscribe* for more hidden stories."
                pb[-1]["show"]["label"] = "ABONE OL · BİLDİRİMİ AÇ" if lang == "tr" else "SUBSCRIBE · TURN ON NOTIFICATIONS"
        chapters.append([len(beats), clean_title(p["publish"]["title"])])
        beats += pb
        descs.append(p["publish"].get("description", "").split("\n\n")[0])
    name = series["title"].split(":", 1)[-1].replace("(EN)", "").strip()
    title = title or name
    intro = descs[0]
    if lang == "tr":
        desc = f"{name}: dizinin tüm bölümleri tek videoda.\n\n{intro}\n\nSence en şaşırtıcı bilgi hangisiydi? Yorumlara yaz, yeni diziler için abone ol!"
    else:
        desc = f"{name}: the full series in one video.\n\n{intro}\n\nWhich fact surprised you most? Tell us in the comments and subscribe for more!"
    tags = []
    for p in parts:
        for h in p["publish"].get("hashtags", []):
            if h != "#shorts" and h not in tags:
                tags.append(h)
    tags.append("#belgesel" if lang == "tr" else "#documentary")
    th = dict(parts[0].get("thumb") or {})
    th.pop("tag", None)
    return {
        "id": series["id"] + "_yatay", "format": "story", "title": title, "brand": series.get("brand"),
        "theme": series.get("theme", "dosya"), "lang": lang, "voice": series.get("voice"), "logo": series.get("logo"),
        "long": {"beats": beats, "chapters": chapters, "thumb": th},
        "publish": {"long": {"title": title[:100], "description": desc, "hashtags": tags[:8]}},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sid")
    ap.add_argument("--title")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    f = (glob.glob(os.path.join(ROOT, "topics", "*", a.sid + ".json")) or [a.sid])[0]
    series = json.load(open(f, encoding="utf-8"))
    script = to_long(series, a.title)
    print(f"{script['id']}: {len(script['long']['beats'])} sahne, {len(script['long']['chapters'])} bölüm")
    if a.dry:
        print(json.dumps(script["long"]["chapters"], ensure_ascii=False))
        return
    from factory.story_compose import produce_story
    out = os.path.join(ROOT, "output")
    os.makedirs(out, exist_ok=True)
    produce_story(script, out)


if __name__ == "__main__":
    main()
