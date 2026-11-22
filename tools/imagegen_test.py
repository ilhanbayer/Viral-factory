import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from factory.imagegen import gen
HOCA = ("Nasreddin Hodja, a cheerful plump elderly Turkish man with a big round white beard, rosy cheeks, bushy "
        "eyebrows, wearing a huge white onion-shaped turban and a long green robe with an orange sash")
DONKEY = "his small grey donkey with long ears and a funny toothy smile"
ANT = "a small red ant boy with round glasses, blue backwards cap and denim overalls"
GRASS = "a tall lanky green grasshopper with long antennae, blue shorts and sandals, carrying a tiny violin"
tests = [
    ("hoca_esek", f"{HOCA} riding {DONKEY} backwards through a colorful Anatolian village square, villagers laughing", 1280, 720, 101),
    ("hoca_kazan", f"{HOCA} in his cozy village kitchen holding a big copper cauldron and a tiny copper pot, surprised neighbor in doorway", 1280, 720, 102),
    ("karinca", f"{ANT} carrying a huge grain of wheat in a sunny autumn forest, while {GRASS} lies on a leaf playing violin", 1280, 720, 103),
    ("kis", f"{GRASS} shivering in a snowy winter night knocking on a warm glowing tree-house door of the ants", 720, 1280, 104),
]
os.makedirs("imgtest", exist_ok=True)
for name, p, w, h, s in tests:
    t0 = time.time()
    r = gen(p, w, h, s, f"imgtest/{name}.jpg")
    print(name, "OK" if r else "FAIL", round(time.time() - t0, 1), "s")
