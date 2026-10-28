"""GitHub Pages rehearsal: serve site/ under /signaldesk/ on loopback and drive it in Chromium.

Usage (browser container): copy site/ to DIR/signaldesk, then python tests/pages_subpath_browser.py DIR
"""
import functools, http.server, threading, sys
from playwright.sync_api import sync_playwright
root = sys.argv[1]
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f'http://127.0.0.1:{port}/signaldesk/'
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width':1280,'height':900})
    reqs, errs = [], []
    pg.on('request', lambda r: reqs.append(r.url)); pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: m.type == 'error' and errs.append(m.text))
    resp = pg.goto(base); assert resp.status == 200, resp.status
    pg.locator('#tour-start').click()
    assert pg.locator('#case').input_value() == 'H05'
    pg.locator('#source-link').click(); assert pg.url == base + '#source', pg.url
    pg.locator('#tour-stop').click()
    with pg.expect_download() as d: pg.locator('#export').click()
    assert d.value.suggested_filename.startswith('signaldesk-')
    r2 = pg.goto(base + 'showcase/'); assert r2.status == 200
    r3 = pg.goto(base + 'replay.json'); assert r3.status == 200
    outside = [u for u in reqs if not u.startswith(base)]
    print('subpath OK', base, 'requests outside /signaldesk/:', outside, 'errors:', errs)
    assert not outside and not errs
