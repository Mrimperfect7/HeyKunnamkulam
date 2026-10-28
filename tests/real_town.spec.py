"""Pipeline test on made-up data, per map: fixture -> osm_to_town.py -> game loads maps/<id>.json -> landmarks, ride, map.
Run from the repo root: python3 tests/real_town.spec.py <three.min.js>"""
import subprocess, sys, os, shutil, threading, http.server, functools, json, math
from playwright.sync_api import sync_playwright
three = sys.argv[1]; tmp = "/tmp/rt"; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp + "/play/maps")
shutil.copy("play/index.html", tmp + "/play/index.html")
h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=tmp); h.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8799), h); threading.Thread(target=srv.serve_forever, daemon=True).start()
res = []
def check(n, ok, info=""): res.append(ok); print(("PASS " if ok else "FAIL ") + n + ("" if ok else " - " + str(info)))
NEED = {"kunnamkulam": ("bus", "temple", "hospital", "cinema", "restaurant"), "guruvayoor": ("gtemple", "college", "cinema", "restaurant")}
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    for mid, need in NEED.items():
        subprocess.check_call([sys.executable, "tests/make_fixture.py", f"{tmp}/fx_{mid}.json", mid], stdout=subprocess.DEVNULL)
        subprocess.check_call([sys.executable, "tools/osm_to_town.py", "--map", mid, "--in", f"{tmp}/fx_{mid}.json", "-o", f"{tmp}/play/maps/{mid}.json"], stdout=subprocess.DEVNULL)
        T = json.load(open(f"{tmp}/play/maps/{mid}.json"))
        check(f"[{mid}] maps/{mid}.json has stops, roads, buildings", len(T["stops"]) >= 10 and len(T["roads"]) > 5 and len(T["buildings"]) > 50, (len(T["stops"]), len(T["roads"]), len(T["buildings"])))
        ctx = b.new_context(viewport={"width": 844, "height": 390}); ctx.add_init_script(f"localStorage.setItem('hk:map','{mid}')")
        pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and ".json" not in m.text else None)
        pg.route("**/three.min.js", lambda r: r.fulfill(path=three, content_type="application/javascript")); pg.route("**/fonts.googleapis.com/**", lambda r: r.fulfill(body="", content_type="text/css"))
        pg.goto("http://127.0.0.1:8799/play/#test"); pg.wait_for_function("!document.getElementById('start').disabled", timeout=15000)
        t = pg.evaluate("__y.town()"); check(f"[{mid}] game switched to the real streets", t["real"] and t["stops"] == len(T["stops"]) and t["boxes"] > 50, t)
        check(f"[{mid}] map card says OpenStreetMap streets", "OpenStreetMap" in pg.inner_text("#mapSrc"), pg.inner_text("#mapSrc"))
        sites = pg.evaluate("__y.sites()"); check(f"[{mid}] landmarks placed on the real net", all(sites[k] for k in need), sites)
        if "cinema" in need: dd = math.dist(sites["cinema"], sites["restaurant"]); check(f"[{mid}] restaurant across the road from the cinema (28 to 70 m)", 28 < dd < 70, round(dd))
        pg.click("#start"); pg.wait_for_timeout(400); pg.evaluate("__y.fast()"); pg.wait_for_timeout(500); pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
        s = pg.evaluate("__y.get()"); check(f"[{mid}] accept works", s["st"] == "toPickup", s["st"])
        pg.evaluate(f"__y.tp({s['ride']['a']['x']},{s['ride']['a']['z']})"); pg.wait_for_timeout(300); pg.evaluate("__y.ff(10)")
        s = pg.evaluate("__y.get()"); check(f"[{mid}] pickup and boarding work", s["st"] == "toDrop", s["st"])
        w = pg.evaluate("__y.world()"); check(f"[{mid}] traffic, people and lamp posts on the real net", len(w["veh"]) >= 5 and len(w["ped"]) >= 8 and w["poles"] > 5, (len(w["veh"]), len(w["ped"]), w["poles"]))
        pg.evaluate(f"__y.tp({s['ride']['b']['x']},{s['ride']['b']['z']})"); pg.wait_for_timeout(500); pg.evaluate("__y.ff(.2)")
        s = pg.evaluate("__y.get()"); check(f"[{mid}] drop pays", s["cash"] > 0 and s["st"] == "idle", s)
        col = pg.evaluate("(()=>{const c=document.getElementById('mapC'),g=c.getContext('2d'),d=g.getImageData(0,0,c.width,c.height).data;let n=0;for(let i=4;i<d.length;i+=4)if(d[i]!==d[0]||d[i+1]!==d[1]||d[i+2]!==d[2])n++;return n})()")
        check(f"[{mid}] minimap shows roads and car", col > 300, col)
        pg.keyboard.press("m"); pg.wait_for_timeout(500); pg.screenshot(path=f"{tmp}/map_full_{mid}.png"); pg.keyboard.press("m")
        check(f"[{mid}] no console errors", not errs, errs[:3]); ctx.close()
    b.close()
print(f"{sum(res)}/{len(res)} passed"); srv.shutdown(); sys.exit(0 if all(res) else 1)
