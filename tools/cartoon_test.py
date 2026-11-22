"""Çizgi film hattı uçtan uca testi: C001'in 1. bölümünü dikey Short olarak üretir."""
import json, os, sys, time, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from factory.cartoon import produce_cartoon

def main():
  src = sorted(glob.glob("topics/queue/C001_*.json"))[0]
  s = json.load(open(src))
  s["episodes"] = s["episodes"][:1]
  s.pop("long", None)
  s["id"] = "TEST_" + s["id"]
  os.makedirs("cizgitest", exist_ok=True)
  t = time.time()
  out = produce_cartoon(s, "cizgitest")
  print("ÇIKTI", out, f"{time.time() - t:.0f} sn")
# tetik Sun Nov 22 23:47:02 +03 2026


if __name__ == "__main__":
    main()
