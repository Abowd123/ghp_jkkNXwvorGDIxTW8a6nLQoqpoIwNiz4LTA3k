"""Section properties for common and arbitrary shapes (units: mm)."""
from __future__ import annotations
import math
from shapely.geometry import Polygon, Point, box
from shapely.ops import unary_union
from shapely import affinity
from ..core import Result, InputError, fmt


def _poly_inertia(poly: Polygon):
    """Ix, Iy, Ixy about origin for polygon with holes (Green's theorem)."""
    def ring(coords):
        ix = iy = ixy = 0.0
        pts = list(coords)
        for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
            c = x0 * y1 - x1 * y0
            ix += (y0**2 + y0 * y1 + y1**2) * c
            iy += (x0**2 + x0 * x1 + x1**2) * c
            ixy += (x0 * y1 + 2 * x0 * y0 + 2 * x1 * y1 + x1 * y0) * c
        return ix / 12, iy / 12, ixy / 24
    from shapely.geometry.polygon import orient
    poly = orient(poly, 1.0)  # exterior ccw, holes cw
    tx, ty, txy = ring(poly.exterior.coords)
    for h in poly.interiors:
        a, b, c = ring(h.coords)
        tx += a; ty += b; txy += c
    return tx, ty, txy


def _inertia(geom):
    geoms = getattr(geom, "geoms", [geom])
    tot = [0.0, 0.0, 0.0]
    for g in geoms:
        a = _poly_inertia(g)
        tot = [t + v for t, v in zip(tot, a)]
    return tot


def build_shape(shape: str, p: dict):
    g = lambda k: _need(p, k)
    s = shape.lower()
    if s in ("rect", "rectangle"):
        b, h = g("b"), g("h")
        return box(0, 0, b, h), f"Rectangle {fmt(b)}x{fmt(h)}"
    if s in ("hrect", "box", "hollow"):
        b, h, t = g("b"), g("h"), g("t")
        if 2 * t >= min(b, h):
            raise InputError("سمك الجدار كبير جداً مقارنة بالأبعاد")
        return box(0, 0, b, h).difference(box(t, t, b - t, h - t)), "Hollow box"
    if s in ("t", "tee"):
        bf, tf, bw, h = g("bf"), g("tf"), g("bw"), g("h")
        if bw > bf or tf >= h:
            raise InputError("أبعاد مقطع T غير منطقية (bw ≤ bf و tf < h)")
        web = box((bf - bw) / 2, 0, (bf + bw) / 2, h - tf)
        fl = box(0, h - tf, bf, h)
        return unary_union([web, fl]), "T-section"
    if s in ("i", "ibeam"):
        bf, tf, tw, h = g("bf"), g("tf"), g("tw"), g("h")
        if 2 * tf >= h or tw > bf:
            raise InputError("أبعاد مقطع I غير منطقية")
        parts = [box(0, 0, bf, tf), box((bf - tw) / 2, tf, (bf + tw) / 2, h - tf), box(0, h - tf, bf, h)]
        return unary_union(parts), "I-section"
    if s in ("l", "angle"):
        b, h, t = g("b"), g("h"), g("t")
        return unary_union([box(0, 0, b, t), box(0, 0, t, h)]), "L-angle"
    if s in ("c", "channel"):
        b, h, tf, tw = g("b"), g("h"), g("tf"), g("tw")
        return unary_union([box(0, 0, b, tf), box(0, 0, tw, h), box(0, h - tf, b, h)]), "Channel"
    if s in ("circle", "o"):
        d = g("d")
        return Point(d / 2, d / 2).buffer(d / 2, resolution=128), "Circle"
    if s in ("pipe", "tube"):
        d, t = g("d"), g("t")
        c = Point(d / 2, d / 2)
        return c.buffer(d / 2, resolution=128).difference(c.buffer(d / 2 - t, resolution=128)), "Pipe"
    if s in ("poly", "polygon"):
        pts = p.get("pts")
        if not pts or len(pts) < 3:
            raise InputError("المضلع يحتاج 3 نقاط على الأقل: pts=0,0;300,0;300,500")
        poly = Polygon(pts)
        if not poly.is_valid:
            raise InputError("المضلع متقاطع مع نفسه. رتب النقاط على المحيط")
        return poly, "Polygon"
    raise InputError(f"شكل غير معروف: {shape}. المتاح: rect, hrect, T, I, L, C, circle, pipe, poly")


def _need(p, k):
    if k not in p:
        raise InputError(f"ناقص البعد {k}")
    v = float(p[k])
    if v <= 0:
        raise InputError(f"البعد {k} لازم يكون موجب")
    return v


def _plastic_Z(geom, axis="x"):
    A = geom.area
    minx, miny, maxx, maxy = geom.bounds
    lo, hi = (miny, maxy) if axis == "x" else (minx, maxx)
    for _ in range(80):
        mid = (lo + hi) / 2
        part = geom.intersection(box(minx - 1, miny - 1, maxx + 1, mid) if axis == "x"
                                 else box(minx - 1, miny - 1, mid, maxy + 1))
        if part.area < A / 2:
            lo = mid
        else:
            hi = mid
    pna = (lo + hi) / 2
    if axis == "x":
        below = geom.intersection(box(minx - 1, miny - 1, maxx + 1, pna))
        above = geom.intersection(box(minx - 1, pna, maxx + 1, maxy + 1))
        Z = below.area * (pna - below.centroid.y) + above.area * (above.centroid.y - pna)
    else:
        left = geom.intersection(box(minx - 1, miny - 1, pna, maxy + 1))
        right = geom.intersection(box(pna, miny - 1, maxx + 1, maxy + 1))
        Z = left.area * (pna - left.centroid.x) + right.area * (right.centroid.x - pna)
    return Z, pna


def properties(shape: str, params: dict) -> Result:
    geom, name = build_shape(shape, params)
    A = geom.area
    cx, cy = geom.centroid.x, geom.centroid.y
    Ix0, Iy0, Ixy0 = _inertia(geom)
    Ix = Ix0 - A * cy**2
    Iy = Iy0 - A * cx**2
    Ixy = Ixy0 - A * cx * cy
    minx, miny, maxx, maxy = geom.bounds
    yt, yb = maxy - cy, cy - miny
    xr, xl = maxx - cx, cx - minx
    Zx, pnax = _plastic_Z(geom, "x")
    Zy, pnay = _plastic_Z(geom, "y")
    # principal
    avg = (Ix + Iy) / 2
    R = math.hypot((Ix - Iy) / 2, Ixy)
    I1, I2 = avg + R, avg - R
    theta = 0.5 * math.degrees(math.atan2(-2 * Ixy, Ix - Iy))

    r = Result("section", f"Section properties: {name}", inputs={"shape": name, **{k: v for k, v in params.items() if k != 'pts'}})
    r.add("Area", "A = ∫dA", "", f"{fmt(A)} mm²")
    r.add("Centroid", "x̄ = ΣAx/ΣA ,  ȳ = ΣAy/ΣA", "", f"x̄ = {fmt(cx)} mm , ȳ = {fmt(cy)} mm (from bottom-left)")
    r.add("Moment of inertia about centroidal x-axis", "Ix = Ix,o − A·ȳ²", f"{fmt(Ix0)} − {fmt(A)}×{fmt(cy)}²", f"{fmt(Ix)} mm⁴")
    r.add("Moment of inertia about centroidal y-axis", "Iy = Iy,o − A·x̄²", f"{fmt(Iy0)} − {fmt(A)}×{fmt(cx)}²", f"{fmt(Iy)} mm⁴")
    r.add("Elastic section modulus", "S = I / c", f"Sx,top = {fmt(Ix)}/{fmt(yt)} , Sx,bot = {fmt(Ix)}/{fmt(yb)}",
          f"Sx,top = {fmt(Ix/yt)} , Sx,bot = {fmt(Ix/yb)} mm³")
    r.add("Plastic section modulus (PNA splits area in half)", "Z = A₁·d₁ + A₂·d₂", f"PNA at y = {fmt(pnax)} mm", f"Zx = {fmt(Zx)} mm³ , Zy = {fmt(Zy)} mm³")
    r.add("Radius of gyration", "r = √(I/A)", "", f"rx = {fmt(math.sqrt(Ix/A))} mm , ry = {fmt(math.sqrt(Iy/A))} mm")
    if abs(Ixy) > 1e-6 * max(Ix, Iy):
        r.add("Principal axes (unsymmetric section)", "I1,2 = (Ix+Iy)/2 ± √(((Ix−Iy)/2)² + Ixy²)", f"Ixy = {fmt(Ixy)} mm⁴",
              f"I1 = {fmt(I1)} , I2 = {fmt(I2)} mm⁴ , θp = {fmt(theta, 2)}°")
    r.outputs = dict(A=A, cx=cx, cy=cy, Ix=Ix, Iy=Iy, Ixy=Ixy, Sx_top=Ix/yt, Sx_bot=Ix/yb,
                     Sy=Iy/max(xr, xl), Zx=Zx, Zy=Zy, rx=math.sqrt(Ix/A), ry=math.sqrt(Iy/A),
                     I1=I1, I2=I2, theta_p=theta, shape_factor=Zx/(Ix/max(yt, yb)))
    r._geom = geom  # for drawing
    return r
