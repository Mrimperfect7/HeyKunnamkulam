#!/usr/bin/env python3
"""Turn OpenStreetMap data into play/town.json for HeyKunnamkulam.

Run it on your own computer (it needs internet access to the Overpass API):
    python3 tools/osm_to_town.py --map kunnamkulam      (writes play/maps/kunnamkulam.json)
    python3 tools/osm_to_town.py --map guruvayoor       (writes play/maps/guruvayoor.json)
Offline, from a file you exported yourself (Overpass Turbo: Export, raw OSM data):
    python3 tools/osm_to_town.py --map guruvayoor --in export.json

Data: (c) OpenStreetMap contributors, ODbL. town.json is a derived database: keep the attribution
and offer it under the same licence (see NOTICE.md). Standard library only.
Coordinates in town.json are metres: x = -east, z = north (so a normal north-up map reads correctly in the game).
"""
import argparse, csv, json, math, re, sys, urllib.parse, urllib.request

STOPS_K = [  # name shown in the game, then lowercase spellings to look for in OSM
    ("Althara / Punnayurkulam", ["althara", "punnayurkulam", "punnayoorkulam"]),
    ("Nayarangadi (Althara)", ["nayarangadi", "nayarangady"]),
    ("Vylathur", ["vylathur", "vailathur", "vilathur"]),
    ("Anjoor", ["anjoor", "anjur"]),
    ("Anjoor Palam", ["anjoor palam", "anjur palam"]),
    ("Parkkadi Temple", ["parkkadi", "parkadi", "parakkadi"]),
    ("Chittannur Pump", ["chittannur", "chittanur"]),
    ("Cheruvathani", ["cheruvathani", "cheruvathani"]),
    ("Kunnamkulam Government High School", ["government high school", "govt high school", "govt. high school", "gvhss", "ghs kunnamkulam"]),
    ("Kanippayur Post", ["kanippayur"]),
    ("Unity", ["unity"]),
    ("Kunnamkulam town / bus stand", ["bus stand", "bus station", "kunnamkulam bus", "ksrtc kunnamkulam"]),
]
STOPS_G = [  # Guruvayoor map: name shown in the game, then lowercase spellings to look for in OSM
    ("Althara", ["althara"]),
    ("Punnayurkulam", ["punnayurkulam", "punnayoorkulam"]),
    ("Vadakkekad", ["vadakkekad", "vadakkekkad", "vadakkekkadu"]),
    ("Vylathur", ["vylathur", "vailathur", "vilathur"]),
    ("Kurukkaspadi", ["kurukkaspadi", "kurukkanpadi", "kurukkas padi", "kurukkan padi"]),
    ("Perakam", ["perakam", "perakom"]),
    ("Iringaprom", ["iringaprom", "iringapram", "iringapuram"]),
    ("Mammiyoor", ["mammiyoor", "mamiyoor", "mammiyur"]),
    ("West Nada", ["west nada", "padinjare nada", "padinjaren ada", "west gate"]),
    ("Guruvayoor Temple", ["guruvayoor temple", "guruvayur temple", "guruvayoor sree krishna", "sree krishna temple"]),
]
MAPDEF = {
    "kunnamkulam": {"stops": STOPS_K, "bbox": "10.53,75.98,10.70,76.16", "center": "10.649,76.074"},
    "guruvayoor": {"stops": STOPS_G, "bbox": "10.53,75.95,10.65,76.08", "center": "10.5946,76.0397"},
}
WIDTH = {"motorway": 12, "trunk": 11, "primary": 10, "secondary": 9, "tertiary": 8, "unclassified": 7, "residential": 6.5, "living_street": 5}
ENDPOINTS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]

def query(bbox, center, rb):
    s, w, n, e = bbox
    cls = "motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street"
    bb = f"({s},{w},{n},{e})"; ar = f"(around:{rb},{center[0]},{center[1]})"
    return f'''[out:json][timeout:180];
(
  way["highway"~"^({cls})(_link)?$"]{bb};
  way["building"]{ar};
  node["highway"="bus_stop"]{bb};
  nw["amenity"]["name"]{bb};
  nw["tourism"]["name"]{bb};
  node["place"]["name"]{bb};
);
out geom;'''

def fetch(q):
    data = urllib.parse.urlencode({"data": q}).encode()
    for url in ENDPOINTS:
        try:
            print("asking", url, "(can take a minute)...")
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers={"User-Agent": "HeyKunnamkulam-osm-to-town/1.0"}), timeout=240) as r:
                return json.load(r)
        except Exception as ex:
            print("  failed:", ex)
    sys.exit("Could not reach Overpass. Try again later, or export the data from Overpass Turbo and use --in.")

def norm(t): return re.sub(r"[^a-z0-9 ]+", " ", (t or "").lower()).strip()
def names(tags): return [norm(tags.get(k)) for k in ("name", "name:en", "alt_name", "official_name", "loc_name", "short_name") if tags.get(k)]
def center_of(el):
    if el["type"] == "node": return el["lat"], el["lon"]
    g = el.get("geometry") or []
    if not g: return None
    return sum(p["lat"] for p in g) / len(g), sum(p["lon"] for p in g) / len(g)

def dp(pts, eps):  # Douglas-Peucker on [(x,z)]
    if len(pts) < 3: return pts
    (x0, z0), (x1, z1) = pts[0], pts[-1]; dx, dz = x1 - x0, z1 - z0; L = math.hypot(dx, dz) or 1e-9
    best, bi = -1, 0
    for i in range(1, len(pts) - 1):
        d = abs(dz * (pts[i][0] - x0) - dx * (pts[i][1] - z0)) / L
        if d > best: best, bi = d, i
    if best <= eps: return [pts[0], pts[-1]]
    return dp(pts[:bi + 1], eps)[:-1] + dp(pts[bi:], eps)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="kunnamkulam", choices=sorted(MAPDEF), help="which map to build")
    ap.add_argument("-o", "--out", default=None, help="default: play/maps/<map>.json")
    ap.add_argument("--in", dest="infile", help="OSM JSON exported from Overpass instead of downloading")
    ap.add_argument("--bbox", default=None, help="south,west,north,east for roads, stops and places (default per map)")
    ap.add_argument("--center", default=None, help="lat,lon where buildings are loaded (default per map)")
    ap.add_argument("--building-radius", type=int, default=1500, help="metres around --center that get buildings")
    ap.add_argument("--stops-file", help="CSV name,lat,lon to override or fill stops OSM does not have")
    ap.add_argument("--max-buildings", type=int, default=4000)
    a = ap.parse_args()
    md = MAPDEF[a.map]; STOPS = md["stops"]; out = a.out or f"play/maps/{a.map}.json"
    bbox = [float(v) for v in (a.bbox or md["bbox"]).split(",")]; center = [float(v) for v in (a.center or md["center"]).split(",")]
    data = json.load(open(a.infile)) if a.infile else fetch(query(bbox, center, a.building_radius))
    els = data.get("elements", []); print(len(els), "OSM elements")

    # ---- match stops
    found = {}
    cands = [e for e in els if e.get("tags") and names(e["tags"])]
    for name, aliases in STOPS:
        best = None
        for e in cands:
            c = center_of(e)
            if not c: continue
            for nm in names(e["tags"]):
                sc = 0
                if nm in aliases: sc = 3
                elif any(al in nm for al in aliases) and not (name == "Anjoor" and "palam" in nm): sc = 2
                if sc and e["tags"].get("highway") == "bus_stop": sc += .5
                if sc:
                    dist = math.hypot(c[0] - center[0], c[1] - center[1])
                    if not best or (sc, -dist) > (best[0], -best[3]): best = (sc, e, c, dist, nm)
        if best: found[name] = (best[2], "osm:" + best[4])
    if a.stops_file:
        for row in csv.reader(open(a.stops_file, encoding="utf-8")):
            if len(row) >= 3 and row[0] != "name":
                try: found[row[0].strip()] = ((float(row[1]), float(row[2])), "manual")
                except ValueError: pass
    miss = [n for n, _ in STOPS if n not in found]
    ref = [c for c, _ in found.values()] or [tuple(center)]
    lat0 = sum(c[0] for c in ref) / len(ref); lon0 = sum(c[1] for c in ref) / len(ref)
    kx = 111320 * math.cos(math.radians(lat0))
    proj = lambda lat, lon: (-(lon - lon0) * kx, (lat - lat0) * 110574)

    # ---- roads
    roads = []
    for e in els:
        t = e.get("tags", {}); hw = (t.get("highway") or "").replace("_link", "")
        if e["type"] == "way" and hw in WIDTH and e.get("geometry"):
            pts = dp([proj(p["lat"], p["lon"]) for p in e["geometry"]], 1.5)
            if len(pts) >= 2: roads.append({"w": WIDTH[hw], "p": [round(v, 1) for q in pts for v in q]})
    if not roads: sys.exit("No roads found. Check --bbox and the data.")

    # ---- snap stops to the nearest point ON a road segment
    def nearest(x, z):
        best = None
        for i, r in enumerate(roads):
            q = r["p"]
            for k in range(0, len(q) - 2, 2):
                x0, z0, x1, z1 = q[k], q[k + 1], q[k + 2], q[k + 3]; dx, dz = x1 - x0, z1 - z0; L2 = dx * dx + dz * dz or 1e-9
                t = max(0, min(1, ((x - x0) * dx + (z - z0) * dz) / L2)); cx, cz = x0 + t * dx, z0 + t * dz; d = (cx - x) ** 2 + (cz - z) ** 2
                if not best or d < best[0]: best = (d, cx, cz, i, k)
        return best
    stops, report = [], []
    for name, _ in STOPS:
        if name not in found: continue
        (lat, lon), src = found[name]; x, z = proj(lat, lon); v = nearest(x, z)
        stops.append({"n": name, "x": round(v[1], 1), "z": round(v[2], 1), "src": src}); report.append((name, src, math.sqrt(v[0])))

    # ---- start at the bus stand, heading along the road
    sp = next((s for s in stops if s["n"] == STOPS[-1][0]), stops[0] if stops else None)
    if not sp: sys.exit("No stops matched. Add a --stops-file CSV (name,lat,lon).")
    v = nearest(sp["x"], sp["z"]); p = roads[v[3]]["p"]; k = v[4]
    hd = math.atan2(p[k + 2] - p[k], p[k + 3] - p[k + 1])
    start = {"x": sp["x"], "z": sp["z"], "hd": round(hd, 3)}

    # ---- buildings
    blds = []
    for e in els:
        t = e.get("tags", {})
        if e["type"] == "way" and "building" in t and e.get("geometry") and len(e["geometry"]) >= 4:
            pts = dp([proj(q["lat"], q["lon"]) for q in e["geometry"][:-1]], .8)
            if len(pts) < 3: continue
            area = abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))) / 2
            if area < 20: continue
            try: h = float(t.get("building:levels", "")) * 3.2
            except ValueError: h = 4.5 + (abs(hash(str(e.get("id")))) % 40) / 10
            blds.append({"h": round(min(max(h, 3), 40), 1), "p": [round(v, 1) for q in pts for v in q], "a": area})
    blds = sorted(blds, key=lambda b: -b["a"])[:a.max_buildings]
    for b in blds: del b["a"]

    allx = [roads[i]["p"][k] for i in range(len(roads)) for k in range(0, len(roads[i]["p"]), 2)]
    allz = [roads[i]["p"][k + 1] for i in range(len(roads)) for k in range(0, len(roads[i]["p"]), 2)]
    town = {"v": 1, "attribution": "(c) OpenStreetMap contributors, ODbL", "origin": [round(lat0, 5), round(lon0, 5)],
            "bounds": [round(min(allx)), round(max(allx)), round(min(allz)), round(max(allz))], "start": start,
            "stops": [{k: s[k] for k in ("n", "x", "z")} for s in stops], "roads": roads, "buildings": blds}
    import os; os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    json.dump(town, open(out, "w"), separators=(",", ":"))
    print(f"\nwrote {out}: {len(roads)} roads, {len(blds)} buildings, {len(stops)}/{len(STOPS)} stops, {os.path.getsize(out)/1e6:.2f} MB")
    for n, src, d in report: print(f"  {n:38} {src:34} {d:6.0f} m from road" + ("  <- check" if d > 40 else ""))
    if miss:
        print("\nNOT FOUND in OSM:", ", ".join(miss)); print("Add them to a CSV (name,lat,lon), e.g. from a map pin, and run again with --stops-file stops.csv")
        print("Until every stop exists the game only offers trips between the stops that were found.")
if __name__ == "__main__": main()
