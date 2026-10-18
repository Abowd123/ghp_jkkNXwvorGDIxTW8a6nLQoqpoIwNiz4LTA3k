"""Load combinations (ASCE 7 / ACI LRFD, BS 8110) and tributary-area load path."""
from __future__ import annotations
import math
from ..core import Result, InputError, fmt

COMBOS = {
    "aci": [
        ("1.4D", {"D": 1.4}),
        ("1.2D + 1.6L + 0.5Lr", {"D": 1.2, "L": 1.6, "Lr": 0.5}),
        ("1.2D + 1.6L + 0.5S", {"D": 1.2, "L": 1.6, "S": 0.5}),
        ("1.2D + 1.6Lr + 1.0L", {"D": 1.2, "Lr": 1.6, "L": 1.0}),
        ("1.2D + 1.6S + 1.0L", {"D": 1.2, "S": 1.6, "L": 1.0}),
        ("1.2D + 1.6Lr + 0.5W", {"D": 1.2, "Lr": 1.6, "W": 0.5}),
        ("1.2D + 1.0W + 1.0L + 0.5Lr", {"D": 1.2, "W": 1.0, "L": 1.0, "Lr": 0.5}),
        ("1.2D − 1.0W + 1.0L + 0.5Lr", {"D": 1.2, "W": -1.0, "L": 1.0, "Lr": 0.5}),
        ("1.2D + 1.0E + 1.0L + 0.2S", {"D": 1.2, "E": 1.0, "L": 1.0, "S": 0.2}),
        ("1.2D − 1.0E + 1.0L + 0.2S", {"D": 1.2, "E": -1.0, "L": 1.0, "S": 0.2}),
        ("0.9D + 1.0W", {"D": 0.9, "W": 1.0}),
        ("0.9D − 1.0W", {"D": 0.9, "W": -1.0}),
        ("0.9D + 1.0E", {"D": 0.9, "E": 1.0}),
        ("0.9D − 1.0E", {"D": 0.9, "E": -1.0}),
    ],
    "bs": [
        ("1.4D + 1.6L", {"D": 1.4, "L": 1.6}),
        ("1.0D + 1.6L", {"D": 1.0, "L": 1.6}),
        ("1.4D + 1.4W", {"D": 1.4, "W": 1.4}),
        ("1.0D + 1.4W", {"D": 1.0, "W": 1.4}),
        ("1.0D − 1.4W", {"D": 1.0, "W": -1.4}),
        ("1.2D + 1.2L + 1.2W", {"D": 1.2, "L": 1.2, "W": 1.2}),
        ("1.2D + 1.2L − 1.2W", {"D": 1.2, "L": 1.2, "W": -1.2}),
    ],
    "asd": [
        ("D", {"D": 1}), ("D + L", {"D": 1, "L": 1}), ("D + Lr", {"D": 1, "Lr": 1}), ("D + S", {"D": 1, "S": 1}),
        ("D + 0.75L + 0.75Lr", {"D": 1, "L": .75, "Lr": .75}), ("D + 0.6W", {"D": 1, "W": .6}),
        ("D + 0.7E", {"D": 1, "E": .7}), ("D + 0.75L + 0.45W + 0.75Lr", {"D": 1, "L": .75, "W": .45, "Lr": .75}),
        ("0.6D + 0.6W", {"D": .6, "W": .6}), ("0.6D − 0.6W", {"D": .6, "W": -.6}), ("0.6D + 0.7E", {"D": .6, "E": .7}),
    ],
}


def combinations(vals: dict, code="aci") -> Result:
    code = code.lower()
    if code not in COMBOS:
        raise InputError("code = aci / bs / asd")
    if not vals:
        raise InputError("أدخل الأحمال مثل D=120 L=80 W=30")
    bad = [k for k in vals if k not in ("D", "L", "Lr", "S", "R", "W", "E")]
    if bad:
        raise InputError(f"رموز غير معروفة: {bad}. المتاح D L Lr S W E")
    r = Result("combos", f"Load combinations ({'ASCE 7 / ACI 318 LRFD' if code == 'aci' else 'BS 8110' if code == 'bs' else 'ASCE 7 ASD'})",
               inputs={k: fmt(v) for k, v in vals.items()})
    rows, seen = [], set()
    for _, fac in COMBOS[code]:
        fac = {k: f for k, f in fac.items() if vals.get(k, 0)}
        if not fac:
            continue
        key = tuple(sorted(fac.items()))
        if key in seen:
            continue
        seen.add(key)
        name = " ".join((("+ " if f > 0 else "− ") if i else ("" if f > 0 else "−")) + f"{fmt(abs(f))}{k}" for i, (k, f) in enumerate(fac.items()))
        rows.append((name, sum(f * vals[k] for k, f in fac.items()), fac))
    mx = max(rows, key=lambda t: t[1])
    mn = min(rows, key=lambda t: t[1])
    for name, U, fac in rows:
        tag = " ⬅ max" if name == mx[0] else (" ⬅ min" if name == mn[0] else "")
        r.add(name, "", " + ".join(f"{fmt(f)}×{fmt(vals[k])}" for k, f in fac.items()), f"U = {fmt(U)}{tag}")
    r.outputs = dict(rows=[(n, u) for n, u, _ in rows], max=mx[:2], min=mn[:2])
    if mn[1] < 0 < mx[1]:
        r.warnings.append("فيه تركيبة تعطي قيمة سالبة: تحقق من الرفع (Uplift) أو انعكاس الإجهاد")
    return r


# ----------------------------- tributary areas -----------------------------
def tributary(xs: list[float], ys: list[float], q: float) -> Result:
    """Grid with bay sizes xs (along x) and ys (along y); slab load q (kN/m²).
    Two-way panels (ratio ≤ 2): 45° lines; one-way: load to the long beams."""
    if not xs or not ys or min(xs + ys) <= 0:
        raise InputError("مثال: X=5,6 Y=4,4.5 q=12")
    r = Result("trib", "Load path & tributary areas", inputs=dict(X=", ".join(map(fmt, xs)) + " m", Y=", ".join(map(fmt, ys)) + " m", q=f"{fmt(q)} kN/m²"))
    gx = [0.0]
    for v in xs: gx.append(gx[-1] + v)
    gy = [0.0]
    for v in ys: gy.append(gy[-1] + v)
    beams = {}   # key ('x', j, i) beam along x on grid line y=gy[j] between gx[i]..gx[i+1]

    def add(key, shape, peak, L):
        beams.setdefault(key, []).append((shape, peak, L))
    panels = []
    for i, a in enumerate(xs):
        for j, b in enumerate(ys):
            lx, ly = min(a, b), max(a, b)
            ratio = ly / lx
            short_is_x = a <= b
            if ratio <= 2:
                kind = "two-way"
                peak = q * lx / 2
                # beams spanning the short side get triangles; long side trapezoids
                tri = (("x", j, i), ("x", j + 1, i)) if short_is_x else (("y", i, j), ("y", i + 1, j))
                trap = (("y", i, j), ("y", i + 1, j)) if short_is_x else (("x", j, i), ("x", j + 1, i))
                for k in tri: add(k, "tri", peak, lx)
                for k in trap: add(k, "trap", peak, ly)
            else:
                kind = "one-way"
                # one-way spans the short direction -> load goes to beams parallel to long direction
                longs = (("x", j, i), ("x", j + 1, i)) if b < a else (("y", i, j), ("y", i + 1, j))
                for k in longs: add(k, "rect", q * lx / 2, ly)
            panels.append((i, j, kind, ratio))
    r.add("Panel classification", "Ly/Lx ≤ 2 → two-way (45° lines) ; > 2 → one-way", "",
          ", ".join(f"P{i+1}{chr(65+j)}: {k} ({fmt(rt, 2)})" for i, j, k, rt in panels))
    table = []
    for key, items in sorted(beams.items()):
        L = items[0][2]
        weq_M = weq_V = 0.0
        desc = []
        for shape, peak, LL in items:
            lx = 2 * peak / q
            if shape == "tri":
                weq_M += 2 * peak / 3; weq_V += peak / 2; desc.append(f"△ {fmt(peak)}")
            elif shape == "trap":
                beta = lx / LL
                weq_M += peak * (1 - beta**2 / 3); weq_V += peak * (1 - beta / 2); desc.append(f"⏢ {fmt(peak)}")
            else:
                weq_M += peak; weq_V += peak; desc.append(f"▭ {fmt(peak)}")
        d, a, b = key
        name = (f"B-x{a+1}:{chr(65+b)}" if d == "x" else f"B-y{chr(65+a)}:{b+1}")
        name = f"{'X' if d == 'x' else 'Y'}-beam line {a+1}, bay {b+1}"
        table.append((name, L, " + ".join(desc), weq_M, weq_V))
        r.add(name, "w_eq(M): △ = 2/3·w₀ ; ⏢ = w₀(1 − β²/3) ; w_eq(V): △ = w₀/2 ; ⏢ = w₀(1 − β/2)",
              f"L = {fmt(L)} m , peaks: {' + '.join(desc)} kN/m", f"w_eq,M = {fmt(weq_M)} kN/m , w_eq,V = {fmt(weq_V)} kN/m")
    cols = []
    for i, x in enumerate(gx):
        for j, y in enumerate(gy):
            ax = (xs[i - 1] if i > 0 else 0) / 2 + (xs[i] if i < len(xs) else 0) / 2
            ay = (ys[j - 1] if j > 0 else 0) / 2 + (ys[j] if j < len(ys) else 0) / 2
            cols.append((i, j, ax * ay, ax * ay * q))
    r.add("Column tributary areas", "A = (half bays x) × (half bays y)", "",
          ", ".join(f"C{chr(65+j)}{i+1}: {fmt(A, 2)} m² → {fmt(P, 1)} kN" for i, j, A, P in cols))
    r.outputs = dict(xs=xs, ys=ys, gx=gx, gy=gy, q=q, panels=panels, beams=table, cols=cols)
    return r
