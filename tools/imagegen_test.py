"""Yeni özgün karakterlerle 3D çizgi film kalitesi testi (kullanıcının referans görseli tarzında)."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from factory.imagegen import gen

os.makedirs("imgtest", exist_ok=True)

PITIR = ("Pitir, a small cute young hedgehog boy with a round chubby body, soft light-brown quills, big shiny green eyes, "
         "freckled pink nose, wearing a yellow knitted scarf and a small brown leather satchel, real hedgehog anatomy")
FINDIK = ("Findik, a lively red squirrel girl with a huge fluffy orange tail, big amber eyes, wearing a little green hooded cape "
          "and an acorn-cap hat, real squirrel anatomy")
HUMA = ("Huma, a wise old snowy owl grandmother with round golden spectacles on her beak, soft white feathers "
        "and a knitted purple shawl, real owl anatomy")
WORLD = ("in an enchanted lush forest village with giant old trees that have tiny wooden doors and glowing round windows, "
         "oversized colorful mushrooms, ferns, giant fruits and berries, warm golden afternoon sunlight through the leaves, "
         "blue sky with fluffy clouds, depth of field")

scenes = [
    (f"{PITIR} and {FINDIK} standing on a stone forest path talking excitedly, {WORLD}", 1344, 768),
    (f"{FINDIK} proudly carrying a giant acorn above her head while {PITIR} laughs, {WORLD}", 1344, 768),
    (f"{HUMA} reading an old book to {PITIR} by a glowing lantern on a tree branch at dusk, fireflies, warm magical light", 1344, 768),
    (f"{PITIR} and {FINDIK} sheltering together under a big green leaf umbrella in the rain, puddles, cozy tree house lights behind", 1344, 768),
    (f"close-up of {PITIR} looking surprised with wide eyes, {WORLD}", 768, 1344),
    (f"{FINDIK} jumping between branches with her tail flowing, {WORLD}", 768, 1344),
]
for k, (p, w, h) in enumerate(scenes):
    t0 = time.time()
    r = gen(p, w, h, 900 + k, f"imgtest/{k}_flux.jpg", model="flux", tries=4)
    time.sleep(5)
    print(k, "OK" if r else "FAIL", round(time.time() - t0, 1), "s", flush=True)
