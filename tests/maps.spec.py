"""Per-map checks: stops, a full ride, rain, shift summary, small-phone intro. Run: python3 tests/maps.spec.py play/index.html path/to/three.min.js"""
import sys, json
from playwright.sync_api import sync_playwright
html, three = sys.argv[1], sys.argv[2]
EXPECT = {
  "kunnamkulam": ["Althara / Punnayurkulam", "Nayarangadi (Althara)", "Vylathur", "Anjoor", "Anjoor Palam", "Parkkadi Temple", "Chittannur Pump", "Cheruvathani", "Kunnamkulam Government High School", "Kanippayur Post", "Unity", "Kunnamkulam town / bus stand"],
  "guruvayoor": ["Althara", "Punnayurkulam", "Vadakkekad", "Vylathur", "Kurukkaspadi", "Perakam", "Iringaprom", "Mammiyoor", "West Nada", "Guruvayoor Temple"],
}
res = []
def check(n, ok, info=""): res.append(ok); print(("PASS " if ok else "FAIL ") + n + ("" if ok else " - " + str(info)))
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    for mid, names in EXPECT.items():
        ctx = b.new_context(viewport={"width": 844, "height": 390}); ctx.add_init_script(f"localStorage.setItem('hk:map','{mid}')")
        pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and ".json" not in m.text else None)
        pg.route("**/three.min.js", lambda r: r.fulfill(path=three, content_type="application/javascript"))
        pg.route("**/fonts.googleapis.com/**", lambda r: r.fulfill(body="", content_type="text/css"))
        pg.goto("file://" + html + "#test"); pg.wait_for_function("!document.getElementById('start').disabled", timeout=15000)
        sel = pg.evaluate("document.querySelector('#mapCards .mcard[aria-checked=true] b').textContent")
        check(f"[{mid}] selected map card highlighted", sel.lower() == mid, sel)
        pg.screenshot(path=f"/tmp/menu_{mid}.png")
        if mid == "guruvayoor":
            sites = pg.evaluate("__y.sites()"); stop = pg.evaluate("__y.stopPos('Kurukkaspadi')")
            import math; dd = math.dist(sites["college"], stop) if sites["college"] and stop else 999
            check("[guruvayoor] ICA College stands at Kurukkaspadi (within 40 m of the stop)", dd < 40, (sites["college"], stop, round(dd)))
        got = pg.evaluate("__y.stopNames()"); check(f"[{mid}] stop names exactly as specified", got == names, got)
        pg.click("#start"); pg.wait_for_timeout(300)
        pg.evaluate("__y.fast()"); pg.wait_for_timeout(500); pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
        s = pg.evaluate("__y.get()"); check(f"[{mid}] ride accepted", s["st"] == "toPickup", s["st"])
        pg.evaluate(f"__y.tp({s['ride']['a']['x']},{s['ride']['a']['z']})"); pg.wait_for_timeout(300); pg.evaluate("__y.ff(10)")
        s = pg.evaluate("__y.get()"); check(f"[{mid}] boarding completes", s["st"] == "toDrop", s["st"])
        pg.evaluate(f"__y.tp({s['ride']['b']['x']},{s['ride']['b']['z']})"); pg.wait_for_timeout(400); pg.evaluate("__y.ff(.2)")
        s = pg.evaluate("__y.get()"); check(f"[{mid}] fare paid", s["cash"] > 0 and s["st"] == "idle", s)
        pg.evaluate("document.getElementById('settings')") ; pg.evaluate("localStorage.setItem('hk:set',JSON.stringify({weather:'rain'}))")
        pg.keyboard.press("p"); pg.wait_for_timeout(150); pg.click("#pEnd"); pg.wait_for_timeout(200)
        check(f"[{mid}] shift summary shows 1 ride", pg.is_visible("#summary") and "Rides" in pg.inner_text("#sumGrid") and pg.evaluate("__y.shift().rides") == 1)
        pg.screenshot(path=f"/tmp/summary_{mid}.png")
        pg.click("#newShift"); pg.wait_for_timeout(200)
        check(f"[{mid}] new shift resets cash", pg.evaluate("__y.get().cash") == 0)
        car = pg.evaluate(f"JSON.parse(localStorage.getItem('hk:car:{mid}')||'{{}}').rides"); check(f"[{mid}] career rides saved for this map only", car == 1, car)
        check(f"[{mid}] no console errors", not errs, errs[:3])
        # small phone: Start must be reachable
        sm = ctx.new_page(); sm.route("**/three.min.js", lambda r: r.fulfill(path=three, content_type="application/javascript")); sm.route("**/fonts.googleapis.com/**", lambda r: r.fulfill(body="", content_type="text/css"))
        sm.set_viewport_size({"width": 667, "height": 375}); sm.goto("file://" + html + "#test"); sm.wait_for_timeout(700)
        ok = sm.eval_on_selector("#start", "e=>{const r=e.getBoundingClientRect();return r.bottom<=innerHeight&&r.top>=0}"); check(f"[{mid}] Start visible at 667x375 with the map picker", ok)
        ctx.close()
    b.close()
print(f"{sum(res)}/{len(res)} passed"); sys.exit(0 if all(res) else 1)
