"""Optional: endless topic generation with Google Gemini free tier (GEMINI_API_KEY).

Without a key the factory simply consumes topics/queue/*.json written by hand.
"""
import os
import json
import re
import urllib.request

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

CATEGORIES = ["dağ", "doğa", "okyanus", "uzay", "şehir", "hayvan", "insan vücudu", "tarih", "volkan", "çöl",
              "rekor", "gizemli yerler"]

PROMPT = """Sen viral Türkçe YouTube Shorts/Reels/TikTok senaristisin. Kategori: {cat}.
Daha önce yapılan konular (tekrar etme): {done}.
Merak uyandıran, DOĞRULANABİLİR bilgilerden oluşan bir "geri sayım" videosu yaz. Sadece aşağıdaki JSON'u döndür.
Kurallar:
- Toplam anlatım en fazla 780 karakter (yaklaşık 55 saniye). intro.narration <= 85, her item.narration <= 68, outro.narration <= 55 karakter.
- 5 ile 10 arası item; rank büyükten küçüğe. Sayılar emin değilsen "yaklaşık" de; uydurma istatistik yok.
- intro ilk cümlesi şok edici bir kanca olsun. outro yorum yapmaya teşvik etsin.
- stats: [[ikon, metin, sayısal_değer_veya_null], ...] ikonlar: "▲" "☠" "❄" "⚠" "★" "◆"; ilk stat sayıysa üçüncü alanı sayı ver.
- danger 0..1 arası artan.
- scene.type: "terrain" | "space" | "city". terrain preset: pyramid|horn|wall|massif|dome|everest|volcano|dunes|canyon|hills|ocean.
  mood: alpine|arctic|storm|dusk|golden|night|blood|desert. palette: rock|dark|green|sand|canyon|volcano|ocean|ice.
  particles: "snow"|"ash"|"dust"|"spray"|"". ocean için "waves": true, volcano için "lava": true. seed: farklı tam sayılar.
Şema:
{{"id":"slug","category":"{cat}","format":"countdown","series_title":"BÜYÜK HARF BAŞLIK",
"intro":{{"lines":["SATIR1","ANAHTAR KELİME","SATIR3"],"narration":"...","scene":{{...}}}},
"items":[{{"rank":5,"name":"...","place":"Ülke · Bölge","stats":[["▲","...",null],["☠","...",null]],"danger":0.5,"narration":"...","scene":{{...}}}}],
"outro":{{"lines":["SENCE EN","KELİME","HANGİSİ?"],"narration":"...","scene":{{...}}}},
"publish":{{"title":"... #shorts","description":"...","hashtags":["#shorts","..."]}}}}"""


def generate(done_titles, cat):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    body = {"contents": [{"parts": [{"text": PROMPT.format(cat=cat, done=", ".join(done_titles[-40:]))}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.9}}
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={key}",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        txt = json.loads(r.read())["candidates"][0]["content"]["parts"][0]["text"]
    data = json.loads(txt)
    data["id"] = re.sub(r"[^a-z0-9_]+", "_", data.get("id", "konu").lower())[:40]
    validate(data)
    return data


def validate(s):
    total = len(s["intro"]["narration"]) + len(s["outro"]["narration"]) + sum(len(i["narration"]) for i in s["items"])
    assert 3 <= len(s["items"]) <= 10, "item sayısı"
    assert total < 950, f"metin çok uzun ({total})"
    for i in s["items"]:
        assert i["scene"]["type"] in ("terrain", "space", "city")
