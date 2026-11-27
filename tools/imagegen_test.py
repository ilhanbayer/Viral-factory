"""Belgesel tarzı yapay zekâ canlandırma testi (Pollinations flux, ücretsiz): S014 Pamukkale sahneleri."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from factory.imagegen import gen_doc

os.makedirs("imgtest", exist_ok=True)
scenes = [
    "tall ancient eunuch priests of Cybele in long robes walking out of a steaming cave entrance at Hierapolis, a sacrificial bull collapsed on the misty ground, dawn light",
    "1980s hotels and a paved road built directly on top of the white travertine terraces of Pamukkale, tourists and parked cars, faded color photograph",
    "reconstruction of a 3rd century Roman water-powered stone sawmill: a large wooden water wheel driving cranks and connecting rods that move two saw blades through marble blocks, Hierapolis",
    "Queen Cleopatra bathing in a warm turquoise thermal pool among marble Roman columns, steam rising, golden hour",
]
for k, p in enumerate(scenes):
    t0 = time.time()
    r = gen_doc(p, 1088, 1344, 4200 + k, f"imgtest/doc{k}.jpg")
    time.sleep(5)
    print(k, "OK" if r else "FAIL", round(time.time() - t0, 1), "s", flush=True)
