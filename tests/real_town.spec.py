"""Pipeline test on made-up data: fixture -> osm_to_town.py -> game loads town.json -> ride works -> map draws.
Run: python3 tests/real_town.spec.py <three.min.js>   (from the repo root)"""
import subprocess, sys, os, shutil, threading, http.server, functools, json
from playwright.sync_api import sync_playwright
three = sys.argv[1]; tmp = "/tmp/rt"; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp + "/play")
subprocess.check_call([sys.executable, "tests/make_fixture.py", tmp + "/fx.json"])
subprocess.check_call([sys.executable, "tools/osm_to_town.py", "--in", tmp + "/fx.json", "-o", tmp + "/play/town.json"])
shutil.copy("play/index.html", tmp + "/play/index.html")
T = json.load(open(tmp + "/play/town.json"))
h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=tmp); h.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8799), h); threading.Thread(target=srv.serve_forever, daemon=True).start()
res = []
def check(n, ok, info=""): res.append(ok); print(("PASS " if ok else "FAIL ") + n + ("" if ok else " - " + str(info)))
check("T1 town.json has 12 stops, roads, buildings", len(T["stops"]) == 12 and len(T["roads"]) > 5 and len(T["buildings"]) > 50, (len(T["stops"]), len(T["roads"]), len(T["buildings"])))
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    pg = b.new_page(viewport={"width": 844, "height": 390}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.route("**/three.min.js", lambda r: r.fulfill(path=three, content_type="application/javascript"))
    pg.route("**/fonts.googleapis.com/**", lambda r: r.fulfill(body="", content_type="text/css"))
    pg.goto("http://127.0.0.1:8799/play/#test"); pg.wait_for_function("!document.getElementById('start').disabled", timeout=15000)
    t = pg.evaluate("__y.town()"); check("T2 game switched to real town", t["real"] and t["stops"] == 12 and t["boxes"] > 50, t)
    pg.click("#start"); pg.wait_for_timeout(400)
    pg.evaluate("__y.fast()"); pg.wait_for_timeout(500); pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
    s = pg.evaluate("__y.get()"); check("T3 accept works", s["st"] == "toPickup", s["st"])
    pg.evaluate(f"__y.tp({s['ride']['a']['x']},{s['ride']['a']['z']})"); pg.wait_for_timeout(300); pg.evaluate("__y.ff(10)")
    s = pg.evaluate("__y.get()"); check("T4 pickup and boarding work", s["st"] == "toDrop", s["st"])
    w = pg.evaluate("__y.world()"); check("T4b traffic, people and lamp posts exist on the real net", len(w["veh"]) >= 8 and len(w["ped"]) >= 12 and w["poles"] > 5, (len(w["veh"]), len(w["ped"]), w["poles"]))
    pg.evaluate(f"__y.tp({s['ride']['b']['x']},{s['ride']['b']['z']})"); pg.wait_for_timeout(500)
    s = pg.evaluate("__y.get()"); check("T5 drop pays", s["cash"] > 0 and s["st"] == "idle", s)
    col = pg.evaluate("(()=>{const c=document.getElementById('mapC'),g=c.getContext('2d'),d=g.getImageData(0,0,c.width,c.height).data;let n=0;for(let i=4;i<d.length;i+=4)if(d[i]!==d[0]||d[i+1]!==d[1]||d[i+2]!==d[2])n++;return n})()")
    check("T6 minimap shows roads and car (pixels differ from background)", col > 300, col)
    pg.keyboard.press("m"); pg.wait_for_timeout(500); pg.screenshot(path="/tmp/rt/map_full.png"); pg.keyboard.press("m"); pg.wait_for_timeout(300)
    pg.screenshot(path="/tmp/rt/drive.png")
    check("T7 no console errors", not errs, errs[:3]); b.close()
print(f"{sum(res)}/{len(res)} passed"); srv.shutdown(); sys.exit(0 if all(res) else 1)
