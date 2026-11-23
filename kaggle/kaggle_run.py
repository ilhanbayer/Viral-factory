"""GitHub Actions'tan Kaggle GPU defteri çalıştırır: kullanıcı adını bulur, push eder, bekler, çıktıyı indirir.
Kullanım: python kaggle/kaggle_run.py <defter_klasörü> <slug> <çıktı_klasörü> [zaman_aşımı_dk]
Ortam: KAGGLE_API_TOKEN (KGAT_...), isteğe bağlı KAGGLE_USERNAME."""
import json, os, re, subprocess, sys, time, shutil

src, slug, out = sys.argv[1], sys.argv[2], sys.argv[3]
limit = int(sys.argv[4]) if len(sys.argv) > 4 else 300


def run(cmd, check=False):
    r = subprocess.run(cmd, capture_output=True, text=True)
    print("$", " ".join(cmd), "\n", r.stdout[-3000:], r.stderr[-3000:], flush=True)
    if check and r.returncode:
        sys.exit(f"komut başarısız: {cmd}")
    return r.stdout + r.stderr


def username():
    u = os.environ.get("KAGGLE_USERNAME", "").strip()
    if u:
        return u
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi(); api.authenticate()
        for k in ("username",):
            v = (getattr(api, "config_values", {}) or {}).get(k) or api.get_config_value(k)
            if v:
                return v
        for name in dir(api):
            if re.search(r"(current_user|whoami|introspect)", name, re.I):
                try:
                    v = getattr(api, name)()
                    print("  ", name, "->", v)
                    m = re.search(r"['\"]?(user_?name)['\"]?\s*[:=]\s*['\"]?([\w-]+)", str(v), re.I)
                    if m:
                        return m.group(2)
                except Exception as e:  # noqa: BLE001
                    print("  ", name, "hata", e)
    except Exception as e:  # noqa: BLE001
        print("api introspeksiyon hatası:", e)
    txt = run(["kaggle", "kernels", "list", "--mine", "--page-size", "5"])
    m = re.search(r"^([\w-]+)/[\w-]+", txt, re.M)
    if m:
        return m.group(1)
    # son çare: push denemesinin hata mesajından
    return None


user = username()
print("Kaggle kullanıcı adı:", user, flush=True)
if not user:
    sys.exit("Kullanıcı adı bulunamadı: GitHub'da KAGGLE_USERNAME değişkeni/secret'ı ekleyin.")
work = os.path.join("/tmp", "kk_" + slug)
shutil.rmtree(work, ignore_errors=True)
shutil.copytree(src, work)
meta = {"id": f"{user}/{slug}", "title": slug, "code_file": "run.py", "language": "python",
        "kernel_type": "script", "is_private": "true", "enable_gpu": "true", "enable_internet": "true",
        "machine_shape": "NvidiaTeslaT4", "dataset_sources": [], "competition_sources": [],
        "kernel_sources": [], "model_sources": []}
json.dump(meta, open(os.path.join(work, "kernel-metadata.json"), "w"), indent=1)
txt = run(["kaggle", "kernels", "push", "-p", work, "--accelerator", "NvidiaTeslaT4"])
if "error" in txt.lower() and "successfully" not in txt.lower():
    txt = run(["kaggle", "kernels", "push", "-p", work])
t0 = time.time()
status = ""
while time.time() - t0 < limit * 60:
    time.sleep(60)
    s = run(["kaggle", "kernels", "status", f"{user}/{slug}"]).lower()
    status = s
    if any(w in s for w in ("complete", "error", "cancel")):
        break
os.makedirs(out, exist_ok=True)
run(["kaggle", "kernels", "output", f"{user}/{slug}", "-p", out, "-o"])
print("durum:", status)
for f in sorted(os.listdir(out)):
    print("  ", f, os.path.getsize(os.path.join(out, f)))
log = os.path.join(out, "log.txt")
if os.path.exists(log):
    print(open(log).read()[-6000:])
