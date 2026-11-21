# Viral Video Fabrikası 🎬

Bu sistem Türkçe, yaklaşık 60 saniyelik, 3D animasyonlu, altyazılı ve seslendirmeli dikey videoları (Shorts / Reels / TikTok, 1080×1920, 30 fps) **otomatik ve ücretsiz** olarak üretir.

| Katman | Nasıl yapılıyor | Maliyet |
|---|---|---|
| 3D sahneler | Saf numpy 3D render motoru (`factory/render3d.py`). Prosedürel dağ, volkan, çöl, kanyon, okyanus, gezegen ve şehir sahneleri; yörüngede dönen kamera, sis, bulut, kar, kül, güneş parlaması | 0 ₺ |
| Motion graphics | 3D çıkıntılı sıra numarası, isim efekti, sayaç, tehlike barı, 3D sahneye iğnelenen zirve işareti, ilerleme çubuğu, geçiş efektleri (zoom-blur, flaş, RGB glitch, sarsıntı), bloom, vinyet, film greni | 0 ₺ |
| Altyazı | Kelime kelime vurgulanan karaoke stili altyazı; ayrıca `.srt` dosyası | 0 ₺ |
| Seslendirme | Varsayılan: Microsoft edge-tts sinir ağı sesleri (Ahmet / Emel), kelime zamanlı altyazıyla. Alternatif: Google TTS (gTTS). İkisi de anahtarsız; biri çalışmazsa diğerine geçer | 0 ₺ |
| Ses tasarımı | Tamamı koddan sentezleniyor (`factory/audio.py`): rüzgâr atmosferi, sinematik drone/pulse müzik, whoosh, impact, BRAAM, riser, sayaç tıkları, glitch, dramatik sessizlik, seslendirme altında otomatik müzik kısma (ducking), −14 LUFS mastering. Lisans sorunu yok | 0 ₺ |
| Süreklilik | GitHub Actions her gün kuyruktaki sıradaki konuyu üretir. Kuyruk boşalınca isteğe bağlı olarak Gemini'nin ücretsiz katmanıyla yeni senaryo yazar | 0 ₺ |
| Yayın | İsteğe bağlı YouTube Shorts otomatik yükleme (YouTube Data API, ücretsiz kota) | 0 ₺ |

## Hızlı başlangıç (kendi bilgisayarında)

```bash
# ffmpeg ve Python 3.10+ gerekir
pip install -r requirements.txt
python run.py                      # kuyruktaki sıradaki konuyu üretir → output/
python run.py --count 3            # art arda 3 video
python run.py --topic topics/queue/001_en_tehlikeli_10_dag.json
```

Her video için şu dosyalar çıkar: `video.mp4`, `video.srt`, `video_kapak.jpg` ve `video_metadata.txt` (başlık, açıklama, hashtag).
2 çekirdekli bir makinede bir video yaklaşık 4–5 dakikada hazır olur.

## Seslendirme ayarları

```bash
python run.py                          # Microsoft Ahmet (varsayılan)
python run.py --speaker emel           # Microsoft Emel (kadın sesi)
python run.py --rate +15%              # daha hızlı konuşma
python run.py --voice gtts             # Google TTS
```
Konu dosyasına özel ses tanımlamak için JSON'a şunu ekleyebilirsin: `"voice": {"engine": "edge", "speaker": "emel", "rate": "+10%"}`. Dosyada yazan ayar komut satırındakinden önceliklidir.
GitHub'da ise *Settings → Variables* bölümünde `VOICE_ENGINE` (edge/gtts) ve `VOICE_NAME` (ahmet/emel) değişkenleriyle seçilir.
edge-tts her kelimenin söylendiği anı da verdiği için altyazıdaki vurgu sesle birebir eşleşir. gTTS bu bilgiyi vermez; onda vurgu tahmini zamanlamayla yapılır.

## Tam otomatik kurulum (GitHub, ücretsiz)

1. Bu klasörü bir GitHub deposuna yükle.
2. *Settings → Secrets and variables → Actions* bölümüne istediğin anahtarları ekle (hepsi isteğe bağlı):
   * `GEMINI_API_KEY`: aistudio.google.com adresinden ücretsiz alınır. Kuyruk boşalınca yeni konuları kendisi yazar.
   * `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`: YouTube'a otomatik yükleme için (aşağıya bak).
3. `.github/workflows/daily.yml` dosyası her gün 18:47'de (TR saati) çalışır. *Actions → Run workflow* ile elle de başlatabilirsin.
4. Videolar her çalıştırmanın **Artifacts** bölümünden indirilir. Anahtarlar girildiyse YouTube'a da otomatik yüklenir.

### YouTube yenileme anahtarı (bir kerelik)
Google Cloud Console'da bir proje aç, *YouTube Data API v3*'ü etkinleştir ve *OAuth client (Desktop)* oluştur. Ardından
[OAuth Playground](https://developers.google.com/oauthplayground) üzerinden kendi client bilgilerinle
`https://www.googleapis.com/auth/youtube.upload` kapsamını yetkilendirip refresh token'ı al.
Doğrulanmamış uygulamalarda videolar "gizli" olarak yüklenebilir. Google'ın uygulama denetimini tamamlayınca herkese açık yayın yapılabilir.

> **TikTok / Instagram:** Bu iki platformun otomatik yükleme API'leri işletme hesabı ve uygulama onayı istiyor. Onay gelene kadar Artifacts'tan indirdiğin mp4 dosyasını, `_metadata.txt` içindeki metinle birlikte telefondan yükleyebilirsin.

## Yeni konu eklemek

`topics/queue/` klasörüne bir JSON dosyası koy (örnekler: `001_…json`, `002_…json`). Dosyalar alfabetik sırayla işlenir ve biten konu `topics/done/` klasörüne taşınır.

* **Süre:** Toplam anlatım yaklaşık 780 karakter olursa video ~60 saniye sürer.
* **Sahne türleri:** `terrain` için presetler: `pyramid, horn, wall, massif, dome, everest, volcano, dunes, canyon, hills, ocean`. Bunların yanında `space` (gezegen) ve `city` (gece şehri) sahneleri var.
* **Atmosfer (mood):** `alpine, arctic, storm, dusk, golden, night, blood, desert`
* **Renk paleti:** `rock, dark, green, sand, canyon, volcano, ocean, ice`
* **Parçacıklar:** `snow, ash, dust, spray`
* **Ek seçenekler:** `seed` (her sahnede farklı arazi), `radius` (kamera uzaklığı), `orbit` (dönüş miktarı), `lava`, `waves`, `pin_label` (3D işaretin yazısı)

## Dosya yapısı
```
run.py                     tek komutla üretim
factory/render3d.py        3D motor
factory/graphics.py        motion graphics, altyazı, post-process
factory/audio.py           ses sentezi ve miks
factory/tts.py             Google TTS
factory/compose.py         zaman çizelgesi, render, ffmpeg montaj
factory/scriptgen.py       Gemini ile otomatik senaryo (isteğe bağlı)
factory/upload_youtube.py  YouTube yükleme (isteğe bağlı)
fonts/                     Anton, Inter, DejaVu (açık lisanslı)
```
