"""Flow tests for the ride loop. Run: python3 replica/e2e/ride.spec.py <path to heykunnamkulam.html> <path to three.min.js>
three is served from a local npm copy, so the test never depends on a CDN."""
import sys, json
from playwright.sync_api import sync_playwright
html, three = sys.argv[1], sys.argv[2]
res = []
def check(name, ok, info=""):
    res.append((name, ok)); print(("PASS " if ok else "FAIL ") + name + (" - " + str(info) if info and not ok else ""))
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader","--enable-unsafe-swiftshader","--ignore-gpu-blocklist"])
    pg = b.new_page(viewport={"width":844,"height":390})
    errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/three.min.js", lambda r: r.fulfill(path=three, content_type="application/javascript"))
    pg.route("**/fonts.googleapis.com/**", lambda r: r.fulfill(body="", content_type="text/css"))
    pg.goto("file://" + html + "#test"); pg.wait_for_timeout(800)
    check("F02-H1 intro shows", pg.is_visible("#intro"))
    pg.click("#start"); pg.wait_for_timeout(300)
    check("F02-H2 intro closes", not pg.is_visible("#intro"))
    pg.screenshot(path="/mnt/user-data/outputs/replica/screens/clone-driving.png")
    # F01 happy path
    pg.evaluate("__y.fast()"); pg.wait_for_timeout(500)
    check("F01-H1 offer appears", pg.is_visible("#offer"))
    pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
    s = pg.evaluate("__y.get()"); check("F01-H2 accepted -> toPickup", s["st"] == "toPickup", s["st"])
    pg.evaluate(f"__y.tp({s['ride']['a']['x']},{s['ride']['a']['z']})"); pg.wait_for_timeout(400)
    s = pg.evaluate("__y.get()"); check("F01-H3 stopped at pickup -> toDrop", s["st"] == "toDrop", s["st"])
    pg.evaluate(f"__y.tp({s['ride']['b']['x']},{s['ride']['b']['z']})"); pg.wait_for_timeout(500)
    s = pg.evaluate("__y.get()"); check("F01-H4 drop -> cash earned", s["cash"] > 0 and s["st"] == "idle", s)
    check("F01-H5 ride saved to store", pg.evaluate("JSON.parse(localStorage.getItem('heykunnamkulam:rides')||'[]').length") == 1)
    # E: skip, timeout, pause, reload
    pg.evaluate("__y.fast()"); pg.wait_for_timeout(500); pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    check("F01-E1 Esc skips offer", pg.evaluate("__y.get().st") == "idle")
    pg.keyboard.press("p"); pg.wait_for_timeout(200)
    check("F03-H1 P pauses", pg.is_visible("#pause")); pg.click("#resume"); check("F03-H2 resume", not pg.is_visible("#pause"))
    # drive and bump: hold gas, no crash
    pg.keyboard.down("w"); v = 0
    for _ in range(30):
        pg.wait_for_timeout(300); v = pg.evaluate("__y.get().v")
        if v > 3: break
    pg.keyboard.up("w")
    check("F01-H6 gas accelerates", v > 3, v)
    # MAP: live map shows, opens with M, closes with Esc, and is actually drawn
    check("MAP-H1 minimap visible", pg.is_visible("#mapBtn"))
    pg.keyboard.press("m"); pg.wait_for_timeout(300)
    check("MAP-H2 M opens full map", pg.evaluate("document.getElementById('mapBtn').classList.contains('big')"))
    colours = pg.evaluate("(()=>{const c=document.getElementById('mapC'),g=c.getContext('2d'),d=g.getImageData(0,0,c.width,c.height).data,s=new Set();for(let i=0;i<d.length;i+=997*4)s.add(d[i]+','+d[i+1]+','+d[i+2]);return s.size})()")
    check("MAP-H3 map is drawn (not blank)", colours > 3, colours)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    check("MAP-E1 Esc closes map", not pg.evaluate("document.getElementById('mapBtn').classList.contains('big')"))
    # F02-E1 small phone: Start must be reachable (regression for BUG-001)
    sm = b.new_page(viewport={"width":667,"height":375}); sm.route("**/three.min.js", lambda r: r.fulfill(path=three, content_type="application/javascript"))
    sm.route("**/fonts.googleapis.com/**", lambda r: r.fulfill(body="", content_type="text/css")); sm.goto("file://" + html + "#test"); sm.wait_for_timeout(500)
    bb = sm.eval_on_selector("#start", "e=>{const r=e.getBoundingClientRect();return r.bottom<=innerHeight&&r.top>=0}")
    check("F02-E1 Start visible at 667x375", bb)
    sm.close()
    # F04 portrait shows rotate prompt
    pg.set_viewport_size({"width":390,"height":844}); pg.wait_for_timeout(200)
    check("F04-H1 rotate prompt in portrait", pg.is_visible("#rotate"))
    pg.set_viewport_size({"width":844,"height":390}); pg.wait_for_timeout(200)
    check("F04-H2 rotate prompt gone in landscape", not pg.is_visible("#rotate"))
    # buttons keyboard reachable + labelled
    check("A11Y accept/skip are real buttons", pg.evaluate("document.querySelectorAll('#offer button').length") == 2)
    check("NF no console errors", not errs, errs[:3])
    b.close()
print(f"{sum(o for _,o in res)}/{len(res)} passed"); sys.exit(0 if all(o for _,o in res) else 1)
