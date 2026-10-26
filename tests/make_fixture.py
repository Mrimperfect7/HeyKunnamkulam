"""TEST DATA ONLY: a made-up street grid in OSM Overpass JSON shape. It is NOT Kunnamkulam. Used to test osm_to_town.py and the game loader."""
import json, math, random, sys
random.seed(3); lat0, lon0 = 10.649, 76.074
def ll(e, n): lat = lat0 + n / 110574; return {"lat": lat, "lon": lon0 + e / (111320 * math.cos(math.radians(lat)))}
els, nid = [], 1
xs = [-1200, -600, 0, 600, 1200]; zs = [-900, -450, 0, 450, 900]
for z in zs:
    els.append({"type": "way", "id": nid, "tags": {"highway": "secondary" if z == 0 else "residential"}, "geometry": [ll(x, z) for x in range(-1200, 1201, 150)]}); nid += 1
for x in xs:
    els.append({"type": "way", "id": nid, "tags": {"highway": "primary" if x == 0 else "tertiary"}, "geometry": [ll(x, z) for z in range(-900, 901, 150)]}); nid += 1
names = ["Althara", "Nayarangadi", "Vylathur", "Anjoor", "Anjoor Palam", "Parkkadi Temple", "Chittannur Pump", "Cheruvathani", "Government High School", "Kanippayur Post", "Unity", "Bus Stand"]
spots = [(-1200, -450), (-1200, 0), (-1200, 450), (-600, 900), (0, 900), (600, 900), (1200, 450), (1200, -450), (600, -900), (0, -900), (0, -450), (0, 0)]
for nm, (x, z) in zip(names, spots):
    p = ll(x + 8, z + 5); els.append({"type": "node", "id": nid, "lat": p["lat"], "lon": p["lon"], "tags": {"highway": "bus_stop", "name": nm}}); nid += 1
for i in range(250):
    x = random.randint(-1100, 1100); z = random.randint(-800, 800)
    if min(abs(x - v) for v in xs) < 40 or min(abs(z - v) for v in zs) < 40: continue
    w, d = random.randint(8, 18), random.randint(8, 18)
    g = [ll(x, z), ll(x + w, z), ll(x + w, z + d), ll(x, z + d), ll(x, z)]
    els.append({"type": "way", "id": nid, "tags": {"building": "yes", **({"building:levels": "2"} if i % 3 == 0 else {})}, "geometry": g}); nid += 1
json.dump({"elements": els}, open(sys.argv[1] if len(sys.argv) > 1 else "fixture_osm.json", "w"))
print("fixture:", len(els), "elements (made up)")
