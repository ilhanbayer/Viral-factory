"""Harita verisi (bir kez): Natural Earth ülke sınırları + Türkiye il sınırları -> assets/geo/*.json (sadeleştirilmiş)."""
import json, urllib.request, os
UA = {"User-Agent": "viral-factory/1.0"}
def get(u):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120).read())
def simp(ring, tol):
    out = [ring[0]]
    for p in ring[1:]:
        if abs(p[0]-out[-1][0]) + abs(p[1]-out[-1][1]) >= tol: out.append(p)
    return [[round(x, 3), round(y, 3)] for x, y in out]
def rings(geom):
    if geom["type"] == "Polygon": return [geom["coordinates"][0]]
    return [poly[0] for poly in geom["coordinates"]]
os.makedirs("assets/geo", exist_ok=True)
ne = get("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson")
want = {"Turkey": "TR", "Greece": "GR", "Bulgaria": "BG", "Cyprus": "CY", "N. Cyprus": "NCY", "Georgia": "GE", "Armenia": "AM",
        "Azerbaijan": "AZ", "Iran": "IR", "Iraq": "IQ", "Syria": "SY", "Italy": "IT", "Egypt": "EG", "Lebanon": "LB",
        "Israel": "IL", "Jordan": "JO", "Russia": "RU", "Ukraine": "UA", "Romania": "RO", "North Macedonia": "MK", "Albania": "AL",
        "Serbia": "RS", "Saudi Arabia": "SA", "Libya": "LY", "Tunisia": "TN", "Moldova": "MD"}
out = {}
for f in ne["features"]:
    n = f["properties"].get("NAME")
    if n in want:
        out[want[n]] = [simp(r, 0.04) for r in rings(f["geometry"]) if len(r) > 8]
json.dump(out, open("assets/geo/countries.json", "w"), separators=(",", ":"))
tr = get("https://raw.githubusercontent.com/cihadturhan/tr-geojson/master/geo/tr-cities-utf8.json")
prov = {}
for f in tr["features"]:
    n = f["properties"].get("name")
    rs = [simp(r, 0.02) for r in rings(f["geometry"]) if len(r) > 8]
    xs = [p[0] for r in rs for p in r]; ys = [p[1] for r in rs for p in r]
    prov[n] = {"rings": rs, "c": [round(sum(xs)/len(xs), 3), round(sum(ys)/len(ys), 3)]}
json.dump(prov, open("assets/geo/tr_provinces.json", "w"), ensure_ascii=False, separators=(",", ":"))
print(len(out), "ülke,", len(prov), "il")
