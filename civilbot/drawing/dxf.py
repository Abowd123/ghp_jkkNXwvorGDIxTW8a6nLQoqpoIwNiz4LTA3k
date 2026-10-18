"""Minimal dependency-free DXF (AutoCAD R12 ASCII) writer + parametric RC detail templates.
Units: millimetres. Opens in AutoCAD, BricsCAD, LibreCAD, DraftSight, ZWCAD."""
from __future__ import annotations
import math

LAYERS = {"CONCRETE": 7, "REBAR": 1, "STIRRUP": 3, "DIM": 4, "TEXT": 2, "HATCH": 8, "SOIL": 30, "AXIS": 5}


class DXF:
    def __init__(self):
        self.e: list[str] = []

    def _g(self, *pairs):
        for code, val in pairs:
            self.e.append(f"{code}\n{val}")

    def line(self, x1, y1, x2, y2, layer="CONCRETE"):
        self._g((0, "LINE"), (8, layer), (10, f"{x1:.3f}"), (20, f"{y1:.3f}"), (30, 0), (11, f"{x2:.3f}"), (21, f"{y2:.3f}"), (31, 0))

    def poly(self, pts, layer="CONCRETE", closed=False):
        pts = list(pts)
        for a, b in zip(pts, pts[1:] + ([pts[0]] if closed else [])):
            self.line(*a, *b, layer=layer)

    def rect(self, x, y, w, h, layer="CONCRETE"):
        self.poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], layer, closed=True)

    def circle(self, x, y, r, layer="REBAR"):
        self._g((0, "CIRCLE"), (8, layer), (10, f"{x:.3f}"), (20, f"{y:.3f}"), (30, 0), (40, f"{r:.3f}"))

    def dot(self, x, y, r, layer="REBAR"):
        """filled bar section (solid donut via concentric circles)."""
        k = r
        while k > 0.5:
            self.circle(x, y, k, layer); k -= max(r / 4, 0.8)

    def arc(self, x, y, r, a1, a2, layer="REBAR"):
        self._g((0, "ARC"), (8, layer), (10, f"{x:.3f}"), (20, f"{y:.3f}"), (30, 0), (40, f"{r:.3f}"), (50, f"{a1:.3f}"), (51, f"{a2:.3f}"))

    def text(self, x, y, s, h=40, layer="TEXT", align="left", rot=0):
        hal = {"left": 0, "center": 1, "right": 2}[align]
        self._g((0, "TEXT"), (8, layer), (10, f"{x:.3f}"), (20, f"{y:.3f}"), (30, 0), (40, f"{h:.3f}"), (1, s), (50, rot), (72, hal))
        if hal:
            self._g((11, f"{x:.3f}"), (21, f"{y:.3f}"), (31, 0))

    def dim(self, x1, y1, x2, y2, off=150, txt=None, h=40):
        """aligned dimension drawn with lines, ticks and text."""
        L = math.hypot(x2 - x1, y2 - y1)
        if L < 1e-9:
            return
        ux, uy = (x2 - x1) / L, (y2 - y1) / L
        nx, ny = -uy, ux
        a = (x1 + nx * off, y1 + ny * off)
        b = (x2 + nx * off, y2 + ny * off)
        self.line(x1 + nx * 20, y1 + ny * 20, a[0] + nx * 40, a[1] + ny * 40, "DIM")
        self.line(x2 + nx * 20, y2 + ny * 20, b[0] + nx * 40, b[1] + ny * 40, "DIM")
        self.line(*a, *b, "DIM")
        t = 35
        for p in (a, b):
            self.line(p[0] - (ux + nx) * t / 1.4, p[1] - (uy + ny) * t / 1.4, p[0] + (ux + nx) * t / 1.4, p[1] + (uy + ny) * t / 1.4, "DIM")
        ang = math.degrees(math.atan2(uy, ux))
        if ang > 90 or ang <= -90:
            ang -= 180
        self.text((a[0] + b[0]) / 2 + nx * 30, (a[1] + b[1]) / 2 + ny * 30, txt or f"{L:.0f}", h, "DIM", "center", ang)

    def hatch_lines(self, x, y, w, h, step=100, layer="HATCH"):
        """45° hatch inside rectangle (for soil / cut concrete)."""
        k = -h
        while k < w:
            x1, y1 = x + max(k, 0), y + max(-k, 0)
            x2 = x + min(k + h, w); y2 = y + min(h, w - k) if k + h > w else y + h
            y2 = y1 + (x2 - x1)
            self.line(x1, y1, x2, y2, layer)
            k += step

    def save(self) -> bytes:
        head = ["0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1009\n9\n$INSUNITS\n70\n4\n0\nENDSEC",
                "0\nSECTION\n2\nTABLES\n0\nTABLE\n2\nLAYER\n70\n%d" % len(LAYERS)]
        for n, c in LAYERS.items():
            head.append(f"0\nLAYER\n2\n{n}\n70\n0\n62\n{c}\n6\nCONTINUOUS")
        head.append("0\nENDTAB\n0\nENDSEC\n0\nSECTION\n2\nENTITIES")
        return ("\n".join(head + self.e + ["0\nENDSEC\n0\nEOF\n"])).encode("ascii", "replace")


# ------------------------------------------------------------------ templates
def _section_bars(D, x0, y0, b, h, cover, ds, bot, top, layers=1, label=True, scale_txt=40):
    D.rect(x0, y0, b, h)
    so = cover + ds / 2
    rr = 2 * ds
    xa, ya, xb, yb = x0 + so, y0 + so, x0 + b - so, y0 + h - so
    D.line(xa + rr, ya, xb - rr, ya, "STIRRUP"); D.line(xb, ya + rr, xb, yb - rr, "STIRRUP")
    D.line(xb - rr, yb, xa + rr, yb, "STIRRUP"); D.line(xa, yb - rr, xa, ya + rr, "STIRRUP")
    for cx, cy, a1 in ((xa + rr, ya + rr, 180), (xb - rr, ya + rr, 270), (xb - rr, yb - rr, 0), (xa + rr, yb - rr, 90)):
        D.arc(cx, cy, rr, a1, a1 + 90, "STIRRUP")
    # 135° hooks at top-left corner
    D.line(xa + rr * 0.3, yb - rr * 0.3, xa + rr + 6 * ds * 0.7, yb - rr - 6 * ds * 0.7, "STIRRUP")

    def row(n, d, y):
        x1, x2 = x0 + cover + ds + d / 2, x0 + b - cover - ds - d / 2
        xs = [x1] if n == 1 else [x1 + k * (x2 - x1) / (n - 1) for k in range(n)]
        for x in xs:
            D.dot(x, y, d / 2)
    n, d = bot
    y1 = y0 + cover + ds + d / 2
    if layers == 2:
        n1 = math.ceil(n / 2); row(n1, d, y1); row(n - n1, d, y1 + d + 25)
    else:
        row(n, d, y1)
    nt, dt = top
    row(nt, dt, y0 + h - cover - ds - dt / 2)
    D.dim(x0, y0, x0 + b, y0, off=-120)
    D.dim(x0, y0 + h, x0, y0, off=-120)
    if label:
        D.text(x0 + b / 2, y0 - 330, f"BOTTOM {n}T{d}" + (" (2 LAYERS)" if layers == 2 else ""), scale_txt, align="center")
        D.text(x0 + b / 2, y0 - 400, f"TOP {nt}T{dt}", scale_txt, align="center")


def beam_detail(out, L_m=6.0, support_w=300, title="BEAM B1") -> bytes:
    """Elevation + cross-section of an RC beam from rc_beam.design outputs."""
    D = DXF()
    b, h, c, ds = out["b"], out["h"], out["cover"], out["stirrup_d"]
    bot, top = out["bars"], out["top_bars"]
    s = out.get("stirrup_s") or 200
    L = L_m * 1000
    # elevation
    D.rect(0, 0, L, h)
    D.rect(-support_w, -h, support_w, 2 * h, "CONCRETE"); D.rect(L, -h, support_w, 2 * h, "CONCRETE")
    yb = c + ds + bot["db"] / 2
    yt = h - c - ds - top["db"] / 2
    hook = 12 * bot["db"]
    D.poly([(-support_w + c, yb + hook), (-support_w + c, yb), (L + support_w - c, yb), (L + support_w - c, yb + hook)], "REBAR")
    D.poly([(-support_w + c, yt - 12 * top["db"]), (-support_w + c, yt), (L + support_w - c, yt), (L + support_w - c, yt - 12 * top["db"])], "REBAR")
    x = 50
    while x <= L - 50 + 1e-6:
        D.line(x, c, x, h - c, "STIRRUP"); x += s
    D.dim(0, 0, L, 0, off=-250, txt=f"{L:.0f}")
    D.dim(0, h, 0, 0, off=-250 - support_w)
    D.text(L / 2, h + 120, f"{bot['n']}T{bot['db']} BOTTOM  |  {top['n']}T{top['db']} TOP  |  T{int(ds)}@{s} LINKS", 60, align="center")
    D.text(L / 2, h + 260, title + " - ELEVATION", 90, align="center")
    # section A-A
    x0 = L + support_w + 900
    _section_bars(D, x0, 0, b, h, c, ds, (bot["n"], bot["db"]), (top["n"], top["db"]), bot["layers"])
    D.text(x0 + b / 2, h + 260, "SECTION A-A", 90, align="center")
    D.text(0, -h - 300, f"CONCRETE COVER {c:.0f} mm | ALL DIMENSIONS IN mm | GENERATED BY CivilBot", 50)
    return D.save()


def column_detail(out, title="COLUMN C1") -> bytes:
    D = DXF()
    b, h, c = out["b"], out["h"], out["cover"]
    dt = out["tie"]
    D.rect(0, 0, b, h)
    so = c + dt / 2
    D.rect(so, so, b - 2 * so, h - 2 * so, "STIRRUP")
    for x, y in zip(out["xs"], out["ys"]):
        D.dot(x, h - y, out["db"] / 2)
    D.dim(0, 0, b, 0, off=-150); D.dim(0, h, 0, 0, off=-150)
    D.text(b / 2, -330, f"{out['n']}T{out['db']}  |  TIES T{dt}@{out['s_tie']}", 45, align="center")
    D.text(b / 2, h + 150, title, 70, align="center")
    return D.save()


def footing_detail(out, title="FOOTING F1") -> bytes:
    D = DXF()
    L, B, h, c = out["L"] * 1000, out["B"] * 1000, out["h"], out["cover"]
    c1, c2 = out["c1"], out["c2"]
    nL, dL, sL = out["bars"]["long (L)"]
    nB, dB, sB = out["bars"]["short (B)"]
    # plan
    D.rect(0, 0, L, B)
    D.rect((L - c1) / 2, (B - c2) / 2, c1, c2)
    D.hatch_lines((L - c1) / 2, (B - c2) / 2, c1, c2, 60)
    for k in range(nL):   # bars along L, spaced across B
        y = c + dL / 2 + k * (B - 2 * c - dL) / max(nL - 1, 1)
        D.line(c, y, L - c, y, "REBAR")
    for k in range(nB):
        x = c + dB / 2 + k * (L - 2 * c - dB) / max(nB - 1, 1)
        D.line(x, c, x, B - c, "REBAR")
    D.dim(0, 0, L, 0, off=-200); D.dim(0, B, 0, 0, off=-200)
    D.text(L / 2, B + 150, f"{title} - PLAN   {nL}T{dL}@{sL:.0f} (L)  /  {nB}T{dB}@{sB:.0f} (B)", 70, align="center")
    # section
    y0 = -h - 1500
    D.rect(0, y0, L, h)
    hc = 1200
    D.rect((L - c1) / 2, y0 + h, c1, hc)
    D.poly([(c, y0 + h - c), (c, y0 + c), (L - c, y0 + c), (L - c, y0 + h - c)], "REBAR")
    for k in range(nB):
        x = c + dB / 2 + k * (L - 2 * c - dB) / max(nB - 1, 1)
        D.dot(x, y0 + c + dL + dB / 2, dB / 2)
    # column starter bars
    for xx in ((L - c1) / 2 + 60, (L + c1) / 2 - 60):
        D.poly([(xx + (300 if xx < L / 2 else -300), y0 + c + dL + dB), (xx, y0 + c + dL + dB), (xx, y0 + h + hc)], "REBAR")
    D.hatch_lines(0, y0 - 150, L, 150, 120, "SOIL")
    D.dim(L, y0 + h, L, y0, off=200 if False else -200)
    D.dim(0, y0, L, y0, off=-300)
    D.text(L / 2, y0 + h + hc + 120, "SECTION 1-1", 70, align="center")
    D.text(0, y0 - 600, f"COVER {c:.0f} mm | PLAIN CONCRETE BLINDING 100 mm | GENERATED BY CivilBot", 50)
    return D.save()


def wall_detail(out, title="RETAINING WALL") -> bytes:
    D = DXF()
    H, B, toe, tb, tt, ts = (out[k] * 1000 for k in ("H", "B", "toe", "tb", "t_top", "ts"))
    heel = B - toe - ts
    D.poly([(0, 0), (B, 0), (B, tb), (toe + ts, tb), (toe + tt, H), (toe, H), (toe, tb), (0, tb)], closed=True)
    if out.get("key"):
        kd = out["key"] * 1000
        D.poly([(toe, 0), (toe, -kd), (toe + ts, -kd), (toe + ts, 0)], "CONCRETE")
    # backfill
    D.poly([(toe + tt, H), (B + 1000, H)], "SOIL")
    k = 0
    while k < 1000 + heel:
        D.line(toe + ts + k, H, toe + ts + k + 150, H + 150, "SOIL"); k += 300
    c = 50
    d, s = out["stem"]
    D.poly([(toe + ts - c, H - c), (toe + ts - c - (ts - tt) * 0 , tb + 75), (toe + ts - c, 75 + 20), (B - 75, 75 + 20)], "REBAR")
    D.poly([(toe + c, H - c), (toe + c, 75 + 20), (75, 75 + 20)], "REBAR")
    D.line(75, tb - 75, B - 75, tb - 75, "REBAR")
    D.line(75, 95, B - 75, 95, "REBAR")
    D.dim(0, 0, B, 0, off=-250); D.dim(0, 0, 0, H, off=250)
    D.dim(0, -0, toe, 0, off=-450, txt=f"TOE {toe:.0f}")
    D.dim(toe + ts, 0, B, 0, off=-450, txt=f"HEEL {heel:.0f}")
    D.text(toe + ts + 100, H / 2, f"STEM T{d}@{s} (SOIL FACE)", 50)
    db, sb = out["heel_bar"]; dt_, st = out["toe_bar"]
    D.text(B - 100, tb + 80, f"T{db}@{sb} TOP", 45, align="right")
    D.text(80, -150, f"T{dt_}@{st} BOTTOM", 45)
    D.text(B / 2, H + 300, title + " - TYPICAL SECTION", 80, align="center")
    return D.save()


def slab_detail(out, title="SLAB S1") -> bytes:
    D = DXF()
    Lx = out.get("Lx", out.get("L")) * 1000
    Ly = out.get("Ly", out.get("L", 4) * 1.5) * 1000
    D.rect(0, 0, Lx, Ly)
    bars = out["bars"]
    keys = list(bars)
    bx = next((bars[k] for k in keys if "x" in k or k == "bottom"), None)
    by = next((bars[k] for k in keys if "(y)" in k), out.get("temp"))
    # show bars as representative bands
    if bx:
        d, s = bx
        for k in range(int(Ly / s) + 1):
            if k % 4 == 0:
                D.line(50, k * s, Lx - 50, k * s, "REBAR")
        D.text(Lx / 2, Ly / 2 + 60, f"T{d}@{s} BOTTOM (SHORT)", 70, align="center")
    if by:
        d, s = by
        for k in range(int(Lx / s) + 1):
            if k % 4 == 0:
                D.line(k * s, 50, k * s, Ly - 50, "STIRRUP")
        D.text(Lx / 2 + 60, Ly / 2 - 150, f"T{d}@{s} BOTTOM (LONG)", 70, align="center", rot=0)
    for k in keys:
        if "top" in k:
            d, s = bars[k]
            side = k.split()[-2] if "edge" in k else "support"
            ext = 0.3 * Lx
            if "left" in k: D.rect(0, 0, ext, Ly, "TEXT"); D.text(ext / 2, Ly - 200, f"T{d}@{s} TOP", 55, align="center")
            if "right" in k: D.rect(Lx - ext, 0, ext, Ly, "TEXT"); D.text(Lx - ext / 2, Ly - 200, f"T{d}@{s} TOP", 55, align="center")
            if "bottom" in k and "edge" in k: D.rect(0, 0, Lx, ext, "TEXT"); D.text(Lx / 2, 150, f"T{d}@{s} TOP", 55, align="center")
            if "top at top" in k: D.rect(0, Ly - ext, Lx, ext, "TEXT"); D.text(Lx / 2, Ly - ext + 100, f"T{d}@{s} TOP", 55, align="center")
            if k == "top": D.text(Lx / 2, Ly - 200, f"T{d}@{s} TOP AT SUPPORTS", 55, align="center")
    D.dim(0, 0, Lx, 0, off=-200); D.dim(0, Ly, 0, 0, off=-200)
    D.text(Lx / 2, Ly + 200, f"{title} - REINFORCEMENT PLAN  (h = {out['h']:.0f} mm)", 80, align="center")
    return D.save()


def shear_tab_detail(o, title="SHEAR TAB CONNECTION") -> bytes:
    D = DXF()
    n, s, Le, Lp, w, t, d = o["n"], o["s"], o["Le"], o["Lp"], o["width"], o["tp"], o["d"]
    D.rect(-20, -100, 20, Lp + 200)                     # support flange
    D.rect(0, 0, w, Lp)                                 # plate
    for k in range(n):
        D.circle(w - Le, Le + k * s, o["dh"] / 2, "REBAR")
        D.circle(w - Le, Le + k * s, d / 2, "REBAR")
    D.line(0, 0, 0, Lp, "STIRRUP")
    D.dim(0, 0, w, 0, off=-120)
    D.dim(w, Lp, w, 0, off=-120 - 0)
    D.dim(w + 60, 0, w + 60, Le, off=60, txt=f"{Le}")
    if n > 1:
        D.dim(w + 60, Le, w + 60, Le + s, off=60, txt=f"{s}")
    D.text(w / 2, Lp + 150, f"PL {Lp:.0f}x{w:.0f}x{t:.0f} | {n} M{d} BOLTS | FILLET WELD {o['weld']} BOTH SIDES", 30, align="center")
    # side view
    x0 = w + 400
    D.rect(x0 - 20, -100, 20, Lp + 200)
    D.rect(x0, 0, t, Lp)
    D.rect(x0 + t, -100, 8, Lp + 200, "DIM")
    for k in range(n):
        y = Le + k * s
        D.rect(x0 - 10, y - d / 2, t + 8 + 25, d, "REBAR")
    D.text(x0 + 20, Lp + 150, "SIDE VIEW", 30)
    D.text(0, -250, title + " - GENERATED BY CivilBot", 35)
    return D.save()
