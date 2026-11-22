"""Ücretsiz yapay zekâ görsel üretimi (Pollinations.ai, anahtar gerektirmez).

gen(prompt, w, h, seed, out_path) -> out_path | None
Karakter tutarlılığı için: her karakterin sabit, ayrıntılı tarifi + sabit stil son eki + sahne başına sabit seed.
"""
import os
import time
import hashlib
import urllib.parse
import urllib.request

PRE = "3D animated cartoon film scene, full body wide shot, stylized cartoon characters with big expressive eyes: "
STYLE = ("soft global illumination, subsurface scattering, warm rim light, vibrant saturated colors, "
         "cinematic composition, high quality stylized 3D CGI render, not photorealistic, no text, no letters, no watermark")
UA = {"User-Agent": "viral-factory/1.0 (https://github.com/ilhanbayer/viral-factory)"}


def gen(prompt, w, h, seed, out, model="flux", tries=5):
    if os.path.exists(out) and os.path.getsize(out) > 20000:
        return out
    full = f"{PRE}{prompt}. {STYLE}"
    q = urllib.parse.quote(full[:1800], safe="")
    url = (f"https://image.pollinations.ai/prompt/{q}?width={w}&height={h}&seed={seed}&model={model}"
           f"&nologo=true&private=true&enhance=false")
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            data = urllib.request.urlopen(req, timeout=180).read()
            if len(data) > 20000 and data[:3] in (b"\xff\xd8\xff", b"\x89PN"):
                open(out, "wb").write(data)
                _clean(out)
                return out
            print("  [görsel] geçersiz yanıt", len(data))
        except Exception as e:
            print("  [görsel] hata", type(e).__name__, str(e)[:80])
        time.sleep(8 * (k + 1))
    return None


def seed_for(text):
    return int(hashlib.md5(text.encode()).hexdigest()[:6], 16)


def _clean(path):
    """Filigranlı alt şeridi kırp, büyüt ve hafif keskinleştir."""
    import cv2
    im = cv2.imread(path)
    if im is None:
        return
    h, w = im.shape[:2]
    im = im[: int(h * 0.92), : int(w * 0.97)]
    scale = 2 if max(h, w) < 1400 else 1
    im = cv2.resize(im, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
    blur = cv2.GaussianBlur(im, (0, 0), 1.2)
    im = cv2.addWeighted(im, 1.35, blur, -0.35, 0)
    cv2.imwrite(path, im, [cv2.IMWRITE_JPEG_QUALITY, 93])
