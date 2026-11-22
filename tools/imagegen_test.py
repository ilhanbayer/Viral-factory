import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from factory.imagegen import gen
from factory.cartoon import build_prompt
os.makedirs("imgtest", exist_ok=True)
c1 = json.load(open("topics/queue/C001_nasreddin_hoca_5_fikra.json"))
c2 = json.load(open("topics/queue/C002_ezop_5_masal.json"))
picks = [(c1, 0, 0), (c1, 0, 3), (c1, 4, 1), (c2, 0, 0), (c2, 1, 0), (c2, 4, 1)]
for k, (c, e, b) in enumerate(picks):
    p = build_prompt(c["episodes"][e]["beats"][b], c["characters"])
    for model in ("flux", "turbo"):
        t0 = time.time()
        r = gen(p, 768, 1344, 500 + k, f"imgtest/{k}_{model}.jpg", model=model, tries=3)
        print(k, model, "OK" if r else "FAIL", round(time.time() - t0, 1), "s", flush=True)
