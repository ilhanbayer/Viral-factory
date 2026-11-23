"""Kaggle GPU testi: özgün karakterlerle 3D çizgi film kareleri (FLUX.1-schnell) + kısa hareketli klip (LTX-Video / Wan2.2).
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

STYLE = ("high quality 3D animated feature film still, stylized cartoon characters with big expressive eyes, "
         "soft global illumination, warm rim light, vibrant saturated colors, lush detailed background, "
         "cinematic composition, depth of field")
PITIR = ("a small cute young hedgehog boy with a round body covered in soft light-brown spiky quills on his back, "
         "pointy little snout, big shiny green eyes, wearing a yellow knitted scarf and a small brown satchel")
FINDIK = ("a lively red squirrel girl with a huge fluffy orange bushy tail, tufted ears, big amber eyes, "
          "wearing a little green hooded cape")
WORLD = ("in an enchanted forest village with giant old trees that have tiny wooden doors and glowing round windows, "
         "oversized red spotted mushrooms, ferns, giant berries, warm golden afternoon sunlight through leaves, blue sky")
SCENES = [
    (f"{PITIR} and {FINDIK} standing on a stone forest path talking excitedly, {WORLD}", 1024, 576),
    (f"{FINDIK} proudly carrying a giant acorn above her head while {PITIR} laughs, {WORLD}", 1024, 576),
    (f"close-up of {PITIR} looking surprised with wide eyes, {WORLD}", 576, 1024),
]
imgs = []
# ---------------------------------------------------------------- 1) FLUX.1-schnell kareleri
try:
    from diffusers import FluxPipeline
    t0 = time.time()
    pipe = FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-schnell", torch_dtype=torch.float16)
    pipe.enable_model_cpu_offload()
    pipe.vae.enable_tiling()
    log("flux yüklendi", round(time.time() - t0), "s")
    for k, (p, w, h) in enumerate(SCENES):
        t0 = time.time()
        im = pipe(f"{p}. {STYLE}", width=w, height=h, num_inference_steps=4, guidance_scale=0.0,
                  max_sequence_length=256, generator=torch.Generator("cpu").manual_seed(42 + k)).images[0]
        path = os.path.join(OUT, f"flux_{k}.jpg")
        im.save(path, quality=92)
        imgs.append(path)
        log("flux kare", k, round(time.time() - t0), "s")
    del pipe
    torch.cuda.empty_cache()
except Exception:
    log("FLUX HATA", traceback.format_exc()[-2500:])

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
        for k in (0, 2):
            if k >= len(imgs):
                continue
            t0 = time.time()
            img = load_image(imgs[k])
            w, h = (768, 448) if img.width > img.height else (448, 768)
            frames = pipe(image=img.resize((w, h)), prompt=SCENES[k][0] + ", characters move naturally, gentle camera push in",
                          negative_prompt="worst quality, blurry, distorted, jittery, deformed",
                          width=w, height=h, num_frames=97, num_inference_steps=40,
                          generator=torch.Generator("cpu").manual_seed(7)).frames[0]
            export_to_video(frames, os.path.join(OUT, f"ltx_{k}.mp4"), fps=24)
            log("ltx klip", k, round(time.time() - t0), "s")
        del pipe
        torch.cuda.empty_cache()
except Exception:
    log("LTX HATA", traceback.format_exc()[-2500:])

# ---------------------------------------------------------------- 3) Wan2.2 TI2V-5B (süre sınırlı deneme)
try:
    if imgs and os.environ.get("SKIP_WAN") != "1":
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
