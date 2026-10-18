"""Free edition + web API (APK backend)."""
import base64, json, os, tempfile, threading, urllib.request, urllib.error
os.environ.setdefault("CIVILBOT_DB", os.path.join(tempfile.mkdtemp(), "f.sqlite3"))
from civilbot.bot import plans as P
from civilbot import api, catalog
from civilbot.core import Result


def test_free_mode_unlocks_everything():
    assert P.FREE_MODE
    o = P.PLANS["open"]
    assert o["pdf"] and o["ai"] and o["dxf"] and o["export"] and not o["watermark"]
    for need in ("student", "pro", "office"):
        assert P.at_least("open", need)


def test_free_mode_gates_and_output():
    try:
        from civilbot.bot import launch as L
    except ImportError:
        return
    assert L.plan(123) == "open"
    import io
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGB", (300, 200), "white").save(buf, "PNG"); png = buf.getvalue()
    r = Result(tool="x", title="t", images={"a": png}, files={"f.dxf": b"0", "g.xlsx": b"1"})
    imgs, files, locked = L.filter_output(123, r)
    assert imgs["a"] == png and set(files) == {"f.dxf", "g.xlsx"} and not locked
    P.FREE_MODE = False
    try:
        imgs, files, locked = L.filter_output(123, r)
        assert locked and imgs["a"] != png     # paid mode: watermark + locked DXF for free users
    finally:
        P.FREE_MODE = True


def test_catalog_complete():
    c = api.catalog()
    listed = {t for cat in c["categories"] for t in cat["tools"]}
    assert listed <= set(c["tools"]) and len(listed) >= 40
    assert c["tools"]["beam"]["examples"] and c["tools"]["crack"]["photo"]
    assert all(t in catalog.META for t in listed)


_srv = None


def _server():
    global _srv
    if _srv is None:
        api.WORKERS = 0
        _srv = api.ThreadingHTTPServer(("127.0.0.1", 0), api.H)
        threading.Thread(target=_srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{_srv.server_port}"


def _post(path, body):
    req = urllib.request.Request(_server() + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_api_run_pdf_errors():
    s, b = _post("/api/run", {"tool": "beam", "text": "L=6 type=ss w=20"})
    d = json.loads(b)
    assert s == 200 and "diagrams" in d["images"] and base64.b64decode(d["images"]["diagrams"])[:4] == b"\x89PNG"
    s, b = _post("/api/pdf", {"tool": "beam", "text": "L=6 type=ss w=20"})
    assert s == 200 and b[:4] == b"%PDF"
    assert _post("/api/run", {"tool": "beam", "text": "nonsense"})[0] == 422
    assert _post("/api/run", {"tool": "nope", "text": "x"})[0] == 404


def test_api_static_and_assetlinks():
    base = _server()
    assert b"manifest.webmanifest" in urllib.request.urlopen(base + "/").read()
    m = json.loads(urllib.request.urlopen(base + "/manifest.webmanifest").read())
    assert m["display"] == "standalone" and any(i["purpose"] == "maskable" for i in m["icons"])
    os.environ["TWA_PACKAGE"], os.environ["TWA_SHA256"] = "app.civilbot.twa", "AA:BB"
    al = json.loads(urllib.request.urlopen(base + "/.well-known/assetlinks.json").read())
    assert al[0]["target"]["package_name"] == "app.civilbot.twa"
    # path traversal never leaves the app folder
    assert b"<!doctype html>" in urllib.request.urlopen(base + "/../../etc/passwd").read().lower()
