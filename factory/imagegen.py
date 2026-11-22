"""Ücretsiz yapay zekâ görsel üretimi (Pollinations.ai, anahtar gerektirmez).

gen(prompt, w, h, seed, out_path) -> out_path | None
Karakter tutarlılığı için: her karakterin sabit, ayrıntılı tarifi + sabit stil son eki + sahne başına sabit seed.
"""
import os
import time
import hashlib
import urllib.parse
import urllib.request

STYLE = ("3D animated feature film still, Pixar and Disney style, adorable expressive cartoon characters with big "
         "eyes, soft cinematic lighting, warm vibrant saturated colors, highly detailed, depth of field, "
         "storybook atmosphere, no text, no letters, no watermark")
UA = {"User-Agent": "viral-factory/1.0 (https://github.com/ilhanbayer/viral-factory)"}


def gen(prompt, w, h, seed, out, model="flux", tries=5):
    if os.path.exists(out) and os.path.getsize(out) > 20000:
        return out
    full = f"{prompt}. {STYLE}"
    q = urllib.parse.quote(full[:1800], safe="")
    url = (f"https://image.pollinations.ai/prompt/{q}?width={w}&height={h}&seed={seed}&model={model}"
           f"&nologo=true&private=true&enhance=false")
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            data = urllib.request.urlopen(req, timeout=180).read()
            if len(data) > 20000 and data[:3] in (b"\xff\xd8\xff", b"\x89PN"):
                open(out, "wb").write(data)
                return out
            print("  [görsel] geçersiz yanıt", len(data))
        except Exception as e:
            print("  [görsel] hata", type(e).__name__, str(e)[:80])
        time.sleep(8 * (k + 1))
    return None


def seed_for(text):
    return int(hashlib.md5(text.encode()).hexdigest()[:6], 16)
