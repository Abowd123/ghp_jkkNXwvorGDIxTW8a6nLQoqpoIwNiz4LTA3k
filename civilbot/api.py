"""CivilBot web API + PWA host (for the Android APK / browser app).

Run:  python -m civilbot.api            (PORT=8090, WORKERS=2)
Endpoints
  GET  /api/tools                  catalog: categories, names, help (HTML), examples
  POST /api/run    {tool, text}    -> {title, summary_html, steps[], warnings[], images{name: b64png}, files{name: b64}}
  POST /api/pdf    {tool, text}    -> application/pdf
  POST /api/photo  {kind, image, caption}   kind = crack | equation | layout, image = base64
  GET  /health
  GET  /.well-known/assetlinks.json   (Android TWA verification, env TWA_PACKAGE + TWA_SHA256)
  GET  /*                          static PWA from civilbot/webapp/app
Pure stdlib (ThreadingHTTPServer). Heavy work runs in the same process pool design as the bot.
"""
from __future__ import annotations
import base64
import collections
import hashlib
import html
import json
import logging
import mimetypes
import os
import re
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import runner
from .core import InputError

log = logging.getLogger("civilbot.api")
ROOT = os.path.join(os.path.dirname(__file__), "webapp", "app")
WORKERS = int(os.getenv("WORKERS", "2"))
TIMEOUT = float(os.getenv("JOB_TIMEOUT", "60"))
MAX_BODY = 8 * 1024 * 1024
RATE = float(os.getenv("API_RATE", "1.0"))      # tokens / sec / IP
BURST = int(os.getenv("API_BURST", "10"))
DAILY = int(os.getenv("API_DAILY", "500"))      # per IP, abuse guard only
ORIGINS = os.getenv("CORS_ORIGINS", "*")

POOL: ProcessPoolExecutor | None = None
SLOTS = threading.BoundedSemaphore(max(1, WORKERS * 2))
_lock = threading.Lock()
_buckets: dict = {}
_daily: dict = collections.Counter()
_day = [time.strftime("%Y%m%d")]
_cache: "collections.OrderedDict[str, object]" = collections.OrderedDict()
STATS = collections.Counter()


def _pool():
    global POOL
    if POOL is None and WORKERS > 0:
        POOL = ProcessPoolExecutor(max_workers=WORKERS, initializer=runner.init_worker)
        for f in [POOL.submit(runner.warmup) for _ in range(WORKERS)]:
            try:
                f.result(timeout=120)
            except Exception:
                log.exception("warmup failed")
    return POOL


def _exec(job, *args):
    with SLOTS:
        p = _pool()
        if p is None:
            return runner.execute(job, *args)
        return p.submit(runner.execute, job, *args).result(timeout=TIMEOUT)


def _allow(ip):
    now = time.monotonic()
    with _lock:
        today = time.strftime("%Y%m%d")
        if today != _day[0]:
            _day[0] = today
            _daily.clear()
        if _daily[ip] >= DAILY:
            return False
        tok, last = _buckets.get(ip, (BURST, now))
        tok = min(BURST, tok + (now - last) * RATE)
        if tok < 1:
            _buckets[ip] = (tok, now)
            return False
        _buckets[ip] = (tok - 1, now)
        _daily[ip] += 1
        return True


def _run_cached(tool, text):
    key = hashlib.sha1(f"{tool}|{' '.join(text.lower().split())}".encode()).hexdigest()
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            STATS["cache_hit"] += 1
            return _cache[key]
    res = _exec("tool", tool, text)
    with _lock:
        _cache[key] = res
        while len(_cache) > 256:
            _cache.popitem(last=False)
    return res


def catalog():
    from . import catalog as C
    from . import services as S
    tools = {}
    for k, (name, help_html) in C.META.items():
        if k == "formula":
            try:
                help_html = help_html + "<b>القوانين المتاحة:</b>\n" + S.formulas.list_formulas()
            except Exception:
                pass
        ex = [html.unescape(m) for m in re.findall(r"<code>(.*?)</code>", help_html or "", flags=re.S)]
        ex = [e for e in ex if len(e) >= 8 and ("=" in e or " " in e)]
        tools[k] = {"name": name, "help": (help_html or "").replace("\n", "<br>"), "examples": ex[:6],
                    "photo": k in C.PHOTO_TOOLS}
    return {"categories": [{"id": c, "name": n, "tools": [t for t in ts if t in tools]} for c, (n, ts) in C.CATS.items()],
            "tools": tools}


_CATALOG = None


def result_json(res):
    from . import services as S
    return {"title": res.title,
            "summary_html": S.summary_html(res, max_steps=60).replace("\n", "<br>"),
            "steps": [s.__dict__ for s in res.steps], "warnings": res.warnings,
            "images": {k: base64.b64encode(v).decode() for k, v in res.images.items()},
            "files": {k: base64.b64encode(v).decode() for k, v in res.files.items()}}


class H(BaseHTTPRequestHandler):
    server_version = "CivilBotAPI/1.0"

    def log_message(self, fmt, *a):
        log.info("%s %s", self.address_string(), fmt % a)

    def _ip(self):
        return (self.headers.get("X-Forwarded-For") or self.client_address[0]).split(",")[0].strip()

    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", ORIGINS)
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode())

    def do_OPTIONS(self):
        self._send(204, b"", extra={"Access-Control-Allow-Methods": "GET, POST, OPTIONS"})

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        global _CATALOG
        path = self.path.split("?")[0]
        if path == "/health":
            return self._json(200, {"ok": True, "workers": WORKERS, **STATS})
        if path == "/api/tools":
            if _CATALOG is None:
                _CATALOG = json.dumps(catalog(), ensure_ascii=False).encode()
            return self._send(200, _CATALOG, extra={"Cache-Control": "public, max-age=3600"})
        if path == "/.well-known/assetlinks.json":
            pkg, sha = os.getenv("TWA_PACKAGE", ""), os.getenv("TWA_SHA256", "")
            body = [{"relation": ["delegate_permission/common.handle_all_urls"],
                     "target": {"namespace": "android_app", "package_name": pkg, "sha256_cert_fingerprints": [s.strip() for s in sha.split(",") if s.strip()]}}] if pkg else []
            return self._json(200, body)
        # static PWA
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        full = os.path.realpath(os.path.join(ROOT, rel))
        if not full.startswith(os.path.realpath(ROOT)) or not os.path.isfile(full):
            full = os.path.join(ROOT, "index.html")   # SPA fallback
        with open(full, "rb") as f:
            data = f.read()
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if full.endswith(".webmanifest"):
            ctype = "application/manifest+json"
        cache = "no-cache" if full.endswith(("index.html", "sw.js")) else "public, max-age=86400"
        self._send(200, data, ctype, {"Cache-Control": cache})

    def do_POST(self):
        path = self.path.split("?")[0]
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            return self._json(413, {"error": "الملف كبير جداً"})
        if not _allow(self._ip()):
            return self._json(429, {"error": "طلبات كثيرة، استنى ثواني"})
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self._json(400, {"error": "bad json"})
        t0 = time.perf_counter()
        try:
            if path == "/api/run":
                tool, text = str(body.get("tool", "")), str(body.get("text", ""))[:4000]
                if tool == "units":
                    from . import services as S
                    return self._json(200, {"title": "تحويل الوحدات", "summary_html": S.run_units(text).replace("\n", "<br>"),
                                            "steps": [], "warnings": [], "images": {}, "files": {}})
                if tool not in runner.funcs():
                    return self._json(404, {"error": "أداة غير معروفة"})
                res = _run_cached(tool, text)
                STATS["run"] += 1
                return self._json(200, result_json(res) | {"ms": int((time.perf_counter() - t0) * 1000)})
            if path == "/api/pdf":
                tool, text = str(body.get("tool", "")), str(body.get("text", ""))[:4000]
                if tool not in runner.funcs():
                    return self._json(404, {"error": "أداة غير معروفة"})
                pdf = _exec("pdf", _run_cached(tool, text), str(body.get("user", ""))[:60], None, None)
                STATS["pdf"] += 1
                return self._send(200, pdf, "application/pdf", {"Content-Disposition": f'attachment; filename="CivilBot_{tool}.pdf"'})
            if path == "/api/photo":
                kind = body.get("kind")
                if kind not in ("crack", "equation", "layout"):
                    return self._json(404, {"error": "نوع غير معروف"})
                img = base64.b64decode(body.get("image", ""))
                eq, res = _exec("photo", kind, img, str(body.get("caption", ""))[:500])
                STATS["photo"] += 1
                out = result_json(res)
                if eq is not None:
                    out["equation"] = str(eq)
                return self._json(200, out)
            return self._json(404, {"error": "not found"})
        except InputError as e:
            return self._json(422, {"error": str(e)})
        except TimeoutError:
            return self._json(504, {"error": "الحساب أخذ وقت طويل، بسّط المدخلات"})
        except Exception:
            log.exception("api failure %s", path)
            STATS["error"] += 1
            return self._json(500, {"error": "خطأ غير متوقع، جرّب مدخلات مختلفة"})


def serve(port=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    _pool()
    srv = ThreadingHTTPServer(("0.0.0.0", int(port or os.getenv("API_PORT") or os.getenv("PORT", "8090"))), H)
    srv.daemon_threads = True
    log.info("CivilBot API on :%s (%s workers)", srv.server_port, WORKERS)
    try:
        srv.serve_forever()
    finally:
        if POOL:
            POOL.shutdown(cancel_futures=True)


if __name__ == "__main__":
    serve()
