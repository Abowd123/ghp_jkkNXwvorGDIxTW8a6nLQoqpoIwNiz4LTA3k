"""PNG drawings (matplotlib, headless). Labels in English for crisp rendering."""
from __future__ import annotations
import io
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyBboxPatch, Polygon as MPoly, FancyArrowPatch
import numpy as np
from ..core import fmt

BLUE, RED, GREEN, GREY, DARK = "#1f6feb", "#d1242f", "#2da44e", "#8c959f", "#24292f"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "font.family": "DejaVu Sans"})


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=int(__import__("os").getenv("PLOT_DPI","140")), bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def _support(ax, kind, x, s):
    if kind == "fixed":
        ax.add_patch(Rectangle((x - 0.04 * s if x > 0 else x - 0.04 * s, -0.35 * s), 0.04 * s, 0.7 * s, color=DARK, hatch="////", fill=False))
        ax.plot([x, x], [-0.35 * s, 0.35 * s], color=DARK, lw=3)
        return
    tri = MPoly([[x, 0], [x - 0.12 * s, -0.22 * s], [x + 0.12 * s, -0.22 * s]], closed=True, fc="white", ec=DARK, lw=1.5)
    ax.add_patch(tri)
    if kind == "roller":
        for dx in (-0.07, 0.07):
            ax.add_patch(Circle((x + dx * s, -0.27 * s), 0.045 * s, fc="white", ec=DARK))
        ax.plot([x - 0.16 * s, x + 0.16 * s], [-0.33 * s, -0.33 * s], color=DARK)
    else:
        ax.plot([x - 0.16 * s, x + 0.16 * s], [-0.24 * s, -0.24 * s], color=DARK)


def beam_diagrams(res) -> bytes:
    b = res.beam
    L = b.L
    s = max(L / 12, 0.25)
    fig, axs = plt.subplots(4, 1, figsize=(9, 11), sharex=True, gridspec_kw={"height_ratios": [1.5, 1, 1, 0.8]})
    ax = axs[0]
    ax.plot([0, L], [0, 0], color=DARK, lw=4, solid_capstyle="butt")
    for sp_ in b.supports:
        _support(ax, sp_.kind, sp_.x, s)
    wmax = max([max(abs(d.w1), abs(d.w2)) for d in b.dists] + [1e-9])
    for d in b.dists:
        h1, h2 = 0.15 * s + 0.6 * s * abs(d.w1) / wmax, 0.15 * s + 0.6 * s * abs(d.w2) / wmax
        ax.add_patch(MPoly([[d.a, 0.05 * s], [d.a, h1], [d.b, h2], [d.b, 0.05 * s]], closed=True, fc=BLUE, alpha=0.15, ec=BLUE))
        for xx in np.linspace(d.a, d.b, max(3, int((d.b - d.a) / L * 14))):
            hh = h1 + (h2 - h1) * (xx - d.a) / (d.b - d.a)
            ax.annotate("", xy=(xx, 0.05 * s), xytext=(xx, hh), arrowprops=dict(arrowstyle="->", color=BLUE, lw=1))
        lab = f"w = {fmt(d.w1)} kN/m" if d.w1 == d.w2 else f"w = {fmt(d.w1)}→{fmt(d.w2)} kN/m"
        ax.text((d.a + d.b) / 2, max(h1, h2) + 0.08 * s, lab, ha="center", color=BLUE, fontsize=9)
    for p in b.points:
        sign = 1 if p.P >= 0 else -1
        ax.annotate("", xy=(p.a, 0.05 * s * sign), xytext=(p.a, 1.1 * s * sign), arrowprops=dict(arrowstyle="-|>", color=RED, lw=2))
        ax.text(p.a, 1.18 * s * sign, f"P = {fmt(abs(p.P))} kN", ha="center", color=RED, fontsize=9, fontweight="bold")
    for m in b.moments:
        arc = FancyArrowPatch((m.a - 0.25 * s, 0.25 * s), (m.a + 0.25 * s, 0.25 * s),
                              connectionstyle="arc3,rad=-0.9" if m.M >= 0 else "arc3,rad=0.9",
                              arrowstyle="-|>", mutation_scale=12, color=GREEN, lw=1.8)
        ax.add_patch(arc)
        ax.text(m.a, -0.75 * s, f"M = {fmt(abs(m.M))} kN·m {'↻' if m.M >= 0 else '↺'}", ha="center", color=GREEN, fontsize=9)
    for r in res.reactions:
        t = f"R = {fmt(r['Ry'], 2)} kN" + (f"\nM = {fmt(r['Mr'], 2)} kN·m" if "Mr" in r else "")
        ax.text(r["x"], -0.55 * s, t, ha="center", va="top", fontsize=8.5, color=DARK)
    ax.set_ylim(-1.1 * s, 1.6 * s)
    ax.set_aspect("auto")
    ax.axis("off")
    ax.set_title("Loading diagram", loc="left", fontweight="bold")

    def panel(ax, y, title, unit, color, invert=False):
        y = np.where(np.abs(y) < 1e-6 * (np.max(np.abs(y)) + 1e-12), 0.0, y)
        ax.fill_between(res.x, y, 0, color=color, alpha=0.25, step=None)
        ax.plot(res.x, y, color=color, lw=1.8)
        ax.axhline(0, color=DARK, lw=1)
        ax.set_title(title, loc="left", fontweight="bold")
        ax.set_ylabel(unit)
        ax.grid(alpha=0.3)
        imax, imin = int(np.argmax(y)), int(np.argmin(y))
        for i in {imax, imin}:
            if abs(y[i]) > 1e-3 * (np.max(np.abs(y)) + 1e-12):
                ax.annotate(f"{fmt(y[i], 2)}\n@ x={fmt(round(res.x[i], 3), 2)}", (res.x[i], y[i]), textcoords="offset points",
                            xytext=(0, 8 if y[i] >= 0 else -24), ha="center", fontsize=8.5, color=color, fontweight="bold")
        pad = 0.25 * (np.max(np.abs(y)) + 1e-9)
        ax.set_ylim(min(y.min(), 0) - pad, max(y.max(), 0) + pad)
        if invert:
            ax.invert_yaxis()
    panel(axs[1], res.V, "Shear force diagram (SFD)", "V [kN]", BLUE)
    panel(axs[2], res.M, "Bending moment diagram (BMD) — sagging +", "M [kN·m]", RED)
    for k, xi in enumerate(res.inflection_points()):
        axs[2].plot([xi], [0], "o", color=DARK, ms=4)
        axs[2].annotate(f"IP {fmt(xi, 2)}", (xi, 0), xytext=(0, -14 - 11 * (k % 2)), textcoords="offset points", ha="center", fontsize=7.5)
    panel(axs[3], res.defl * 1000, f"Deflected shape (EI = {fmt(b.EI)} kN·m²)", "δ [mm]", GREEN)
    axs[3].set_xlabel("x [m]")
    for a in axs[1:]:
        for k in res.key_x:
            a.axvline(k, color=GREY, lw=0.5, ls=":")
    fig.tight_layout()
    return _png(fig)


def rc_section(out: dict) -> bytes:
    b, h, cv, ds = out["b"], out["h"], out["cover"], out["stirrup_d"]
    bars, top = out["bars"], out["top_bars"]
    fig, ax = plt.subplots(figsize=(5.2, 5.2 * min(1.6, h / b) if h > b else 5.2))
    ax.add_patch(Rectangle((0, 0), b, h, fc="#d0d7de", ec=DARK, lw=2))
    so = cv + ds / 2
    ax.add_patch(FancyBboxPatch((so, so), b - 2 * so, h - 2 * so, boxstyle=f"round,pad=0,rounding_size={2*ds}",
                                fc="none", ec=GREEN, lw=max(1.5, ds / 5)))

    def row(n, db, y):
        x0, x1 = cv + ds + db / 2, b - cv - ds - db / 2
        xs = [x0] if n == 1 else np.linspace(x0, x1, n)
        for x in xs:
            ax.add_patch(Circle((x, y), db / 2, fc=RED, ec="#7a1a1a", lw=1))
        return xs
    n, db, layers = bars["n"], bars["db"], bars["layers"]
    y1 = cv + ds + db / 2
    if layers == 1:
        xs = row(n, db, y1)
    else:
        n1 = math.ceil(n / 2)
        xs = row(n1, db, y1)
        row(n - n1, db, y1 + db + 25)
    yt = h - cv - ds - top["db"] / 2
    row(top["n"], top["db"], yt)
    clear = (xs[1] - xs[0] - db) if len(xs) > 1 else 0
    # dimensions
    def dim(x1, y1_, x2, y2, txt, off=(0, 0)):
        ax.annotate("", xy=(x1, y1_), xytext=(x2, y2), arrowprops=dict(arrowstyle="<->", color=DARK, lw=0.8))
        ax.text((x1 + x2) / 2 + off[0], (y1_ + y2) / 2 + off[1], txt, ha="center", va="center", fontsize=9,
                bbox=dict(fc="white", ec="none", pad=1))
    dim(0, -0.08 * h, b, -0.08 * h, f"b = {fmt(b)}")
    dim(-0.1 * b, 0, -0.1 * b, h, f"h = {fmt(h)}")
    ax.text(b + 0.11 * b, out["d"] / 2 + (h - out["d"]), f"d = {fmt(out['d'], 1)}", rotation=90, va="center", fontsize=9)
    ax.annotate("", xy=(b + 0.08 * b, h), xytext=(b + 0.08 * b, h - out["d"]), arrowprops=dict(arrowstyle="<->", color=DARK, lw=0.8))
    lines = [f"Bottom: {n}Ø{db}" + (" (2 layers)" if layers == 2 else "") + f"  As = {fmt(bars['As'], 0)} mm²",
             f"Top: {top['n']}Ø{top['db']}" + (" (compression)" if out.get("doubly") else " (hangers)"),
             f"Stirrups: Ø{int(ds)} @ {out['stirrup_s']} mm" if out.get("stirrup_s") else f"Stirrups: Ø{int(ds)}",
             f"Clear cover = {fmt(cv)} mm, bar clear spacing = {fmt(clear, 0)} mm"]
    ax.text(b / 2, -0.2 * h, "\n".join(lines), ha="center", va="top", fontsize=9)
    ax.set_xlim(-0.25 * b, 1.3 * b)
    ax.set_ylim(-0.48 * h, 1.05 * h)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Beam cross-section", fontweight="bold")
    return _png(fig)


def section_shape(geom, out: dict, title: str) -> bytes:
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    geoms = getattr(geom, "geoms", [geom])
    for g in geoms:
        ax.add_patch(MPoly(np.array(g.exterior.coords), closed=True, fc="#c6dbf7", ec=BLUE, lw=1.8))
        for hole in g.interiors:
            ax.add_patch(MPoly(np.array(hole.coords), closed=True, fc="white", ec=BLUE, lw=1.2))
    minx, miny, maxx, maxy = geom.bounds
    cx, cy = out["cx"], out["cy"]
    w, h = maxx - minx, maxy - miny
    ax.axhline(cy, color=RED, ls="--", lw=1)
    ax.axvline(cx, color=RED, ls="--", lw=1)
    ax.plot(cx, cy, "o", color=RED)
    ax.text(maxx + 0.04 * w, cy, "x", color=RED, va="center", fontweight="bold")
    ax.text(cx, maxy + 0.04 * h, "y", color=RED, ha="center", fontweight="bold")
    ax.text(cx + 0.03 * w, cy + 0.03 * h, f"C ({fmt(cx, 1)}, {fmt(cy, 1)})", color=RED, fontsize=9)
    if abs(out.get("Ixy", 0)) > 1e-6 * max(out["Ix"], out["Iy"]):
        t = math.radians(out["theta_p"])
        R = 0.6 * max(w, h)
        ax.plot([cx - R * math.cos(t), cx + R * math.cos(t)], [cy - R * math.sin(t), cy + R * math.sin(t)], color=GREEN, lw=1, ls="-.")
        ax.text(cx + R * math.cos(t), cy + R * math.sin(t), " 1", color=GREEN)
    txt = (f"A = {fmt(out['A'], 1)} mm²\nIx = {fmt(out['Ix'])} mm⁴\nIy = {fmt(out['Iy'])} mm⁴\n"
           f"Zx = {fmt(out['Zx'])} mm³\nrx = {fmt(out['rx'], 1)} , ry = {fmt(out['ry'], 1)} mm")
    ax.text(minx, miny - 0.08 * h, txt, va="top", fontsize=9, family="DejaVu Sans Mono")
    ax.set_xlim(minx - 0.15 * w, maxx + 0.2 * w)
    ax.set_ylim(miny - 0.5 * h, maxy + 0.15 * h)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontweight="bold")
    return _png(fig)
