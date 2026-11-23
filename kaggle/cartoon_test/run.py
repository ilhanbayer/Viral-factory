"""Kaggle GPU testi: özgün karakterlerle 3D çizgi film kareleri (Playground v2.5 / SDXL) + kısa hareketli klip (LTX-Video / Wan2.2).
Her aşama kendi try/except'inde; çıktılar /kaggle/working altına, günlük log.txt'ye yazılır."""
import os, sys, time, subprocess, traceback, json
OUT = "/kaggle/working"
LOG = open(os.path.join(OUT, "log.txt"), "a")


def log(*a):
    s = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(s + "\n"); LOG.flush()


def sh(cmd):
    log("$", cmd)
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    log(r.stdout[-1500:], r.stderr[-1500:])


sh("nvidia-smi; df -h /kaggle/working /tmp; free -g")
sh("pip install -q -U diffusers transformers accelerate sentencepiece imageio imageio-ffmpeg ftfy")
import torch
log("torch", torch.__version__, "cuda", torch.cuda.is_available(), torch.cuda.device_count())

STYLE = ("3D CGI animated movie still, cute stylized cartoon character with big expressive eyes, "
         "soft global illumination, warm rim light, vibrant saturated colors, lush detailed background, "
         "cinematic lighting, depth of field, highly detailed fur")
PITIR = ("a small cute young hedgehog boy with a round body, soft light-brown spiky quills on his back, "
         "pointy little snout, big shiny green eyes, wearing a yellow knitted scarf")
WORLD = ("enchanted forest village, giant old trees with tiny wooden doors and glowing round windows, "
         "oversized red spotted mushrooms, ferns, warm golden afternoon sunlight through leaves")
SCENES = [
    (f"{PITIR} walking happily along a stone forest path, {WORLD}", 1024, 576, "the hedgehog walks forward along the path, camera slowly follows"),
    (f"{PITIR} finding a giant shiny red apple under a mushroom, amazed, {WORLD}", 1024, 576, "the hedgehog looks at the apple with surprise and smiles, leaves fall gently"),
    (f"{PITIR} trying to push a giant red apple uphill, struggling, funny, {WORLD}", 1024, 576, "the hedgehog pushes the big apple, the apple rolls slowly"),
    (f"close-up of {PITIR} laughing joyfully, {WORLD}", 576, 1024, "the hedgehog laughs and blinks, gentle camera push in"),
]
imgs = []
# ---------------------------------------------------------------- 1) Kareler (kapısız açık modeller)
SIZES = {(1024, 576): (1344, 768), (576, 1024): (768, 1344)}
NEG = "photo, photorealistic, human, 2d, flat, illustration, sketch, sticker, white background, text, watermark, blurry, deformed, extra limbs, two heads, ugly"
from diffusers import DiffusionPipeline
for tag, mid, steps, cfg in (("pg", "playgroundai/playground-v2.5-1024px-aesthetic", 40, 3.0),
                             ):
    try:
        t0 = time.time()
        pipe = DiffusionPipeline.from_pretrained(mid, torch_dtype=torch.float16, variant="fp16").to("cuda")
        if tag == "sdxl":
            pipe.vae.config.force_upcast = True
        log(tag, "yüklendi", round(time.time() - t0), "s")
        got = []
        for k, (p, w, h, _m) in enumerate(SCENES):
            W, H = SIZES[(w, h)]
            t0 = time.time()
            im = pipe(prompt=f"{p}. {STYLE}", negative_prompt=NEG, width=W, height=H, num_inference_steps=steps,
                      guidance_scale=cfg, generator=torch.Generator("cpu").manual_seed(42 + k)).images[0]
            path = os.path.join(OUT, f"{tag}_{k}.jpg")
            im.save(path, quality=92)
            got.append(path)
            log(tag, "kare", k, round(time.time() - t0), "s")
        if not imgs:
            imgs = got
        del pipe
        torch.cuda.empty_cache()
    except Exception:
        log(tag, "HATA", traceback.format_exc()[-2500:])

# ---------------------------------------------------------------- 2) LTX-Video resimden videoya
try:
    if imgs:
        from diffusers import LTXImageToVideoPipeline
        from diffusers.utils import export_to_video, load_image
        t0 = time.time()
        pipe = LTXImageToVideoPipeline.from_pretrained("Lightricks/LTX-Video", torch_dtype=torch.float16)
        pipe.enable_model_cpu_offload()
        pipe.vae.enable_tiling()
        log("ltx yüklendi", round(time.time() - t0), "s")
        for k in range(len(SCENES)):
            if k >= len(imgs):
                continue
            t0 = time.time()
            img = load_image(imgs[k])
            w, h = (768, 448) if img.width > img.height else (448, 768)
            frames = pipe(image=img.resize((w, h)), prompt=SCENES[k][3] + ", smooth natural motion, consistent character, 3D animated movie",
                          negative_prompt="worst quality, inconsistent motion, blurry, jittery, distorted, morphing, scene change, new characters",
                          width=w, height=h, num_frames=73, num_inference_steps=40, decode_timestep=0.03, decode_noise_scale=0.025,
                          generator=torch.Generator("cpu").manual_seed(7)).frames[0]
            export_to_video(frames, os.path.join(OUT, f"ltx_{k}.mp4"), fps=24)
            log("ltx klip", k, round(time.time() - t0), "s")
        del pipe
        torch.cuda.empty_cache()
except Exception:
    log("LTX HATA", traceback.format_exc()[-2500:])

# ---------------------------------------------------------------- 3) Wan2.2 TI2V-5B (süre sınırlı deneme)
try:
    if False:  # Wan2.2: 31 GB RAM yetmedi (çekirdek çöktü); şimdilik kapalı
        from diffusers import WanImageToVideoPipeline, AutoencoderKLWan
        from diffusers.utils import export_to_video, load_image
        t0 = time.time()
        mid = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"
        vae = AutoencoderKLWan.from_pretrained(mid, subfolder="vae", torch_dtype=torch.float32)
        pipe = WanImageToVideoPipeline.from_pretrained(mid, vae=vae, torch_dtype=torch.float16)
        pipe.enable_model_cpu_offload()
        log("wan yüklendi", round(time.time() - t0), "s")
        t0 = time.time()
        img = load_image(imgs[0]).resize((832, 480))
        frames = pipe(image=img, prompt=SCENES[0][0] + ", characters talk and gesture, gentle camera movement",
                      negative_prompt="blurry, distorted, static, low quality, deformed",
                      height=480, width=832, num_frames=49, num_inference_steps=30, guidance_scale=5.0,
                      generator=torch.Generator("cpu").manual_seed(3)).frames[0]
        export_to_video(frames, os.path.join(OUT, "wan_0.mp4"), fps=24)
        log("wan klip", round(time.time() - t0), "s")
except Exception:
    log("WAN HATA", traceback.format_exc()[-2500:])
log("BİTTİ")
