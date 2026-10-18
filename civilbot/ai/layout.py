"""Column layout assistant (educational): detect walls in an architectural sketch, build a structural grid at
wall lines, add intermediate grid lines where spans exceed the limit, and place columns at wall intersections."""
from __future__ import annotations
import math
import numpy as np
import cv2
from ..core import Result, InputError, fmt


def _cluster(vals, tol):
    vals = sorted(vals)
    groups = []
    for v in vals:
        if groups and v - groups[-1][-1] <= tol:
            groups[-1].append(v)
        else:
            groups.append([v])
    return [float(np.median(g)) for g in groups]


def detect_walls(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.GaussianBlur(g, (3, 3), 0)
    m = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 31, 15)
    h, w = m.shape
    kx = cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, w // 25), 1))
    ky = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(15, h // 25)))
    hor = cv2.morphologyEx(m, cv2.MORPH_OPEN, kx)
    ver = cv2.morphologyEx(m, cv2.MORPH_OPEN, ky)
    walls = cv2.bitwise_or(hor, ver)
    return walls, hor, ver


def _lines_from(mask, axis, min_len):
    """Return positions of straight wall lines along axis ('v' -> x positions, 'h' -> y positions)."""
    proj = (mask > 0).sum(axis=0 if axis == "v" else 1)
    pos = np.nonzero(proj >= min_len)[0]
    if not len(pos):
        return []
    return _cluster(pos.tolist(), 6)


def propose(img_bytes: bytes, Lx: float, max_span=6.0, min_span=2.5, col=0.3) -> Result:
    arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise InputError("ما قدرت أقرأ صورة الاسكتش")
    hh, ww = img.shape[:2]
    s = 1100 / max(hh, ww)
    if s < 1:
        img = cv2.resize(img, (int(ww * s), int(hh * s)))
    walls, hor, ver = detect_walls(img)
    ys, xs = np.nonzero(walls)
    if len(xs) < 50:
        raise InputError("ما لقيت جدران واضحة. ارسم الجدران بخطوط داكنة على ورق فاتح وصوّر من فوق")
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    mpp = Lx / max(1, (x1 - x0))   # metres per pixel
    Ly = (y1 - y0) * mpp
    vx = _lines_from(ver, "v", max(20, 0.15 * (y1 - y0)))
    hy = _lines_from(hor, "h", max(20, 0.15 * (x1 - x0)))
    vx = sorted(set([float(x0)] + [x for x in vx if x0 + 3 < x < x1 - 3] + [float(x1)]))
    hy = sorted(set([float(y0)] + [y for y in hy if y0 + 3 < y < y1 - 3] + [float(y1)]))
    # merge grid lines closer than min_span
    def merge(pos):
        out = [pos[0]]
        for p in pos[1:]:
            if (p - out[-1]) * mpp < min_span and p != pos[-1]:
                continue
            if (p - out[-1]) * mpp < min_span and p == pos[-1] and len(out) > 1:
                out[-1] = p
                continue
            out.append(p)
        return out
    gx, gy = merge(vx), merge(hy)
    added = []

    def split(pos, tag):
        out = [pos[0]]
        for p in pos[1:]:
            gap = (p - out[-1]) * mpp
            if gap > max_span:
                k = math.ceil(gap / max_span)
                step = (p - out[-1]) / k
                base = out[-1]
                for j in range(1, k):
                    out.append(base + j * step); added.append((tag, base + j * step))
            out.append(p)
        return out
    gx, gy = split(gx, "x"), split(gy, "y")

    def on_wall(x, y, rad=6):
        x, y = int(round(x)), int(round(y))
        ya, yb, xa, xb = max(0, y - rad), y + rad + 1, max(0, x - rad), x + rad + 1
        return walls[ya:yb, xa:xb].any()
    cols = []
    for i, x in enumerate(gx):
        for j, y in enumerate(gy):
            corner = (i in (0, len(gx) - 1)) and (j in (0, len(gy) - 1))
            vwall = ver[max(0, int(y) - 8):int(y) + 9, max(0, int(x) - 8):int(x) + 9].any()
            hwall = hor[max(0, int(y) - 8):int(y) + 9, max(0, int(x) - 8):int(x) + 9].any()
            if corner or (vwall and hwall) or ((i in (0, len(gx) - 1) or j in (0, len(gy) - 1)) and on_wall(x, y)) or on_wall(x, y):
                cols.append((i, j, x, y, corner))
    sx = [(gx[k + 1] - gx[k]) * mpp for k in range(len(gx) - 1)]
    sy = [(gy[k + 1] - gy[k]) * mpp for k in range(len(gy) - 1)]
    r = Result("layout", "Column layout proposal (educational)", inputs=dict(Lx=f"{fmt(Lx)} m (drawing width)", Ly=f"{fmt(Ly, 2)} m (measured)",
                                                                           max_span=f"{fmt(max_span)} m", min_span=f"{fmt(min_span)} m"))
    r.add("Wall detection", "adaptive threshold → morphological opening (horizontal & vertical kernels)", f"scale = {fmt(mpp * 1000, 2)} mm/px",
          f"{len(vx)} vertical & {len(hy)} horizontal wall lines")
    r.add("Structural grid", "grid lines on walls, merged if < min span, split if > max span", "",
          f"x-spans: {', '.join(fmt(v, 2) for v in sx)} m ; y-spans: {', '.join(fmt(v, 2) for v in sy)} m")
    if added:
        r.add("Intermediate grid lines added (span > max)", "", "", ", ".join(f"{t}-line @ {fmt((p - (x0 if t == 'x' else y0)) * mpp, 2)} m" for t, p in added))
    r.add("Columns", "at grid intersections that fall on walls (hidden in walls) + all corners", "", f"{len(cols)} columns , max span {fmt(max(sx + sy), 2)} m")
    if max(sx + sy) > max_span + 1e-6:
        r.warnings.append("فيه بحور أكبر من الحد: فكّر بكمرات أعمق أو أعمدة إضافية")
    r.warnings.append("اقتراح تعليمي مبدئي: الموقع النهائي يحدده المهندس حسب المعماري والأحمال والزلازل")
    out = img.copy()
    for k, x in enumerate(gx):
        cv2.line(out, (int(x), int(y0) - 30), (int(x), int(y1) + 30), (255, 140, 0), 1, cv2.LINE_AA)
        cv2.circle(out, (int(x), int(y0) - 45), 14, (255, 140, 0), 2)
        cv2.putText(out, str(k + 1), (int(x) - 6, int(y0) - 39), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 140, 0), 2)
    for k, y in enumerate(gy):
        cv2.line(out, (int(x0) - 30, int(y)), (int(x1) + 30, int(y)), (255, 140, 0), 1, cv2.LINE_AA)
        cv2.circle(out, (int(x0) - 45, int(y)), 14, (255, 140, 0), 2)
        cv2.putText(out, chr(65 + k), (int(x0) - 51, int(y) + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 140, 0), 2)
    half = max(5, int(col / mpp / 2))
    for i, j, x, y, corner in cols:
        cv2.rectangle(out, (int(x) - half, int(y) - half), (int(x) + half, int(y) + half), (0, 0, 230), -1)
    for k in range(len(gx) - 1):
        cv2.putText(out, f"{sx[k]:.2f}", (int((gx[k] + gx[k + 1]) / 2) - 18, int(y1) + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (40, 40, 40), 1)
    r.outputs = dict(cols=cols, gx=gx, gy=gy, sx=sx, sy=sy, mpp=mpp)
    r.images["layout"] = cv2.imencode(".png", out)[1].tobytes()
    return r


def synthetic_plan(seed=0) -> bytes:
    """Simple house plan: 15 m × 10 m, interior walls; drawn at 60 px/m with 100 px margin."""
    ppm = 60
    W, H = int(15 * ppm) + 240, int(10 * ppm) + 240
    img = np.full((H, W, 3), 245, np.uint8)
    ox, oy = 120, 120
    th = 6

    def wall(xa, ya, xb, yb):
        cv2.line(img, (ox + int(xa * ppm), oy + int(ya * ppm)), (ox + int(xb * ppm), oy + int(yb * ppm)), (30, 30, 30), th)
    wall(0, 0, 15, 0); wall(15, 0, 15, 10); wall(15, 10, 0, 10); wall(0, 10, 0, 0)
    wall(5, 0, 5, 10); wall(11, 0, 11, 6); wall(0, 6, 15, 6); wall(5, 3, 11, 3)
    # door gap
    cv2.line(img, (ox + int(7 * ppm), oy + int(6 * ppm)), (ox + int(8 * ppm), oy + int(6 * ppm)), (245, 245, 245), th + 2)
    cv2.putText(img, "LIVING", (ox + 6 * ppm, oy + 8 * ppm), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (90, 90, 90), 1)
    return cv2.imencode(".png", img)[1].tobytes()
