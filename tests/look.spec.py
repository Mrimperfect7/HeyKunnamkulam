"""Graphics tiers: what each one turns on, and that the picture is not blank. Run: python3 tests/look.spec.py <abs path to play/index.html> <three.min.js>"""
import sys, io, os
from playwright.sync_api import sync_playwright
from PIL import Image, ImageStat
html, three = sys.argv[1], sys.argv[2]
def jsd(r):
    rest = r.request.url.split("three@0.128.0/")[1]
    r.fulfill(path=os.path.join(os.path.dirname(os.path.dirname(three)), rest), content_type="application/javascript")
res = []
def check(n, ok, info=""): res.append(ok); print(("PASS " if ok else "FAIL ") + n + ("" if ok else " - " + str(info)))
WANT = {"low": (False, False, 0), "med": (False, True, 1100), "high": (True, True, 2600)}
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    for tier, (post, env, grass) in WANT.items():
        ctx = b.new_context(viewport={"width": 844, "height": 390}); ctx.add_init_script(f"localStorage.setItem('hk:set',JSON.stringify({{gfx:'{tier}'}}))")
        pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and ".json" not in m.text and "404" not in m.text else None)
        pg.route("**/three.min.js", lambda r: r.fulfill(path=three, content_type="application/javascript")); pg.route("**/cdn.jsdelivr.net/**", jsd); pg.route("**/fonts.googleapis.com/**", lambda r: r.fulfill(body="", content_type="text/css"))
        pg.goto("file://" + html + "#test", timeout=150000); pg.wait_for_function("window.__y!==undefined", timeout=150000); pg.click("#start"); pg.wait_for_timeout(400)
        g = pg.evaluate("__y.gfx()"); check(f"[{tier}] tier features: post={post} env={env} grass={grass}", g["post"] == post and g["env"] == env and g["grass"] == grass, g)
        pg.add_style_tag(content="#hud,#offer,#toast{display:none!important}"); pg.evaluate("__y.ff(.5)"); pg.wait_for_timeout(1800)
        im = Image.open(io.BytesIO(pg.screenshot())).convert("RGB"); st = ImageStat.Stat(im)
        check(f"[{tier}] picture is neither blank nor blown out (mean brightness 40 to 215)", 40 < sum(st.mean) / 3 < 215, st.mean)
        check(f"[{tier}] picture has detail (contrast)", sum(st.stddev) / 3 > 18, st.stddev)
        pg.evaluate("__y.night('night')"); pg.evaluate("__y.ff(.5)"); pg.wait_for_timeout(1200); g2 = pg.evaluate("__y.gfx()")
        if env: check(f"[{tier}] night swaps the sky lighting", g2["night"], g2)
        check(f"[{tier}] no console errors", not errs, errs[:3]); ctx.close()
    b.close()
print(f"{sum(res)}/{len(res)} passed"); sys.exit(0 if all(res) else 1)
