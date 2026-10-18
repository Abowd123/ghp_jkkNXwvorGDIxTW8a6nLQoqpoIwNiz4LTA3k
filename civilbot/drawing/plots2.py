"""Phase-2 drawings: truss, frame, P-M interaction, slab contours, footing, wall, tributary plan, BBS."""
from __future__ import annotations
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon as MPoly
from .plots import _png, BLUE, RED, GREEN, GREY, DARK
from ..core import fmt


def _sup(ax, x, y, kind, s):
    if kind == "fixed":
        ax.add_patch(Rectangle((x - 1.2 * s, y - 0.5 * s), 2.4 * s, 0.5 * s, fc="none", ec=DARK, hatch="////"))
        return
    ax.add_patch(MPoly([[x, y], [x - 0.8 * s, y - 1.2 * s], [x + 0.8 * s, y - 1.2 * s]], fc="white", ec=DARK, zorder=4))
    if kind.startswith("roller"):
        for dx in (-0.4, 0.4):
            ax.add_patch(Circle((x + dx * s, y - 1.55 * s), 0.3 * s, fc="white", ec=DARK, zorder=4))


def truss(res) -> bytes:
    m = res.model
    xy = np.array(m.nodes)
    span = max(np.ptp(xy[:, 0]), np.ptp(xy[:, 1]), 1)
    s = span / 40
    fig, ax = plt.subplots(figsize=(10, 6))
    fmax = max(abs(f) for f in res.forces) or 1
    for k, (mem, f, st) in enumerate(zip(m.members, res.forces, res.status)):
        (x1, y1), (x2, y2) = m.nodes[mem.i], m.nodes[mem.j]
        if st == "0":
            ax.plot([x1, x2], [y1, y2], color=GREY, lw=1.5, ls="--", zorder=1)
        else:
            ax.plot([x1, x2], [y1, y2], color=BLUE if st == "T" else RED, lw=1.5 + 4 * abs(f) / fmax, zorder=2)
        ax.text((x1 + x2) / 2, (y1 + y2) / 2, f"{k+1}: {fmt(f, 2)}" if st != "0" else f"{k+1}: 0",
                ha="center", va="center", fontsize=8.5, bbox=dict(fc="white", ec="none", pad=0.5, alpha=0.85), zorder=5)
    ax.scatter(xy[:, 0], xy[:, 1], s=30, color=DARK, zorder=6)
    for k, (x, y) in enumerate(m.nodes):
        ax.text(x + 0.6 * s, y + 0.6 * s, str(k + 1), fontsize=9, color=DARK, fontweight="bold")
    for nd, kind in m.supports.items():
        _sup(ax, *m.nodes[nd], kind, s)
        rx, ry = res.reactions[nd]
        ax.text(m.nodes[nd][0], m.nodes[nd][1] - 3.2 * s, f"Rx={fmt(rx, 2)}\nRy={fmt(ry, 2)}", ha="center", va="top", fontsize=8)
    for nd, ld in m.loads.items():
        x, y = m.nodes[nd]
        fx, fy = ld[0], ld[1]
        mag = math.hypot(fx, fy) or 1
        L = 4 * s
        ax.annotate("", xy=(x + fx / mag * L, y + fy / mag * L), xytext=(x, y), arrowprops=dict(arrowstyle="-|>", color=GREEN, lw=2), zorder=7)
        ax.text(x + fx / mag * L * 1.35, y + fy / mag * L * 1.35, f"{fmt(mag, 2)}", color=GREEN, ha="center", va="center", fontsize=8.5, fontweight="bold")
    ax.plot([], [], color=BLUE, lw=3, label="Tension (+)")
    ax.plot([], [], color=RED, lw=3, label="Compression (−)")
    ax.plot([], [], color=GREY, ls="--", label="Zero-force member")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=3, frameon=False)
    mm, r, j, deg = res.determinacy
    ax.set_title(f"Truss forces [kN]   (m + r = {mm + r}, 2j = {2 * j} → {'determinate' if deg == 0 else f'indeterminate ({deg})'})", fontweight="bold")
    ax.set_aspect("equal"); ax.axis("off")
    ax.margins(0.12)
    return _png(fig)


def frame(res) -> bytes:
    m = res.model
    xy = np.array(m.nodes)
    span = max(np.ptp(xy[:, 0]), np.ptp(xy[:, 1]), 1)
    s = span / 40
    fig, axs = plt.subplots(2, 2, figsize=(12, 10))
    names = [("Axial force N [kN] (tension +)", 1, GREEN), ("Shear force V [kN]", 2, BLUE), ("Bending moment M [kN·m] (drawn on tension side)", 3, RED)]
    for ax, (title, k, col) in zip(axs.flat[:3], names):
        allv = np.concatenate([st[k] for st in res.stations])
        vmax = np.max(np.abs(allv)) or 1
        sc = 0.12 * span / vmax
        for mem, st in zip(m.members, res.stations):
            L, c, sn = m.geom(mem)
            (x1, y1) = m.nodes[mem.i]
            xs, val = st[0], st[k]
            sign = -1 if k == 3 else 1
            px = x1 + c * xs + (-sn) * val * sc * sign
            py = y1 + sn * xs + c * val * sc * sign
            bx, by = x1 + c * xs, y1 + sn * xs
            ax.fill(np.concatenate([bx, px[::-1]]), np.concatenate([by, py[::-1]]), color=col, alpha=0.25, lw=0)
            ax.plot(px, py, color=col, lw=1.3)
            for idx in {0, len(xs) - 1, int(np.argmax(np.abs(val)))}:
                if abs(val[idx]) > 1e-3 * vmax:
                    ax.text(px[idx], py[idx], fmt(val[idx], 1), fontsize=7.5, color=col, ha="center",
                            bbox=dict(fc="white", ec="none", pad=0.3, alpha=0.8))
        for mem in m.members:
            (x1, y1), (x2, y2) = m.nodes[mem.i], m.nodes[mem.j]
            ax.plot([x1, x2], [y1, y2], color=DARK, lw=2)
        for nd, kind in m.supports.items():
            _sup(ax, *m.nodes[nd], kind, s)
        ax.set_title(title, fontweight="bold", fontsize=10)
        ax.set_aspect("equal"); ax.axis("off"); ax.margins(0.15)
    ax = axs.flat[3]
    dmax = max(np.max(np.hypot(st[4], st[5])) for st in res.stations) or 1e-12
    sc = 0.1 * span / dmax
    for mem, st in zip(m.members, res.stations):
        L, c, sn = m.geom(mem)
        (x1, y1), (x2, y2) = m.nodes[mem.i], m.nodes[mem.j]
        ax.plot([x1, x2], [y1, y2], color=GREY, lw=1, ls="--")
        xs, u, v = st[0], st[4], st[5]
        gx = x1 + c * (xs + u * sc) - sn * v * sc
        gy = y1 + sn * (xs + u * sc) + c * v * sc
        ax.plot(gx, gy, color=GREEN, lw=2)
    for nd, kind in m.supports.items():
        _sup(ax, *m.nodes[nd], kind, s)
    U = res.disp
    k = int(np.argmax(np.hypot(U[0::3], U[1::3])))
    ax.set_title(f"Deformed shape (×{fmt(sc, 0)}) — max node disp {fmt(math.hypot(U[3*k], U[3*k+1])*1000, 2)} mm @ node {k+1}", fontweight="bold", fontsize=10)
    ax.set_aspect("equal"); ax.axis("off"); ax.margins(0.15)
    for nd, rr in res.reactions.items():
        x, y = m.nodes[nd]
        axs.flat[0].text(x, y - 3 * s, f"Rx={fmt(rr[0], 1)}\nRy={fmt(rr[1], 1)}" + (f"\nM={fmt(rr[2], 1)}" if rr[2] else ""), ha="center", va="top", fontsize=7.5)
    fig.tight_layout()
    return _png(fig)


def interaction(out) -> bytes:
    arr = out["curve"]
    fig, ax = plt.subplots(figsize=(6.5, 6.5))
    Pn, Mn, phi = arr[:, 0], arr[:, 1], arr[:, 2]
    ax.plot(Mn, Pn, color=GREY, lw=1.5, ls="--", label="Nominal (Mn, Pn)")
    pp = np.minimum(phi * Pn, out["phiPmax"])
    ax.plot(phi * Mn, pp, color=BLUE, lw=2.2, label="Design (φMn, φPn)")
    ax.fill_betweenx(pp, 0, phi * Mn, color=BLUE, alpha=0.08)
    ax.plot([out["Mc"]], [out["Pu"]], "o", color=RED, ms=9, label=f"(Mc, Pu) = ({fmt(out['Mc'], 1)}, {fmt(out['Pu'], 0)})")
    ax.axhline(out["phiPmax"], color=BLUE, ls=":", lw=1)
    ax.text(0, out["phiPmax"], f" φPn,max = {fmt(out['phiPmax'], 0)} kN", va="bottom", fontsize=8, color=BLUE)
    ax.axhline(0, color=DARK, lw=0.8); ax.axvline(0, color=DARK, lw=0.8)
    ax.set_xlabel("M [kN·m]"); ax.set_ylabel("P [kN]")
    ax.grid(alpha=0.3); ax.legend(fontsize=8.5, loc="upper right")
    ax.set_title(f"P–M interaction: {fmt(out['b'])}×{fmt(out['h'])} mm, {out['n']}Ø{out['db']} (ρ = {fmt(out['rho']*100, 2)}%)\nutilisation = {fmt(out['util']*100, 1)} %",
                 fontweight="bold", fontsize=10)
    return _png(fig)


def column_section(out) -> bytes:
    b, h, c = out["b"], out["h"], out["cover"]
    fig, ax = plt.subplots(figsize=(4.5, 4.5 * h / b if h > b else 4.5))
    ax.add_patch(Rectangle((0, 0), b, h, fc="#d0d7de", ec=DARK, lw=2))
    so = c + out["tie"] / 2
    ax.add_patch(Rectangle((so, so), b - 2 * so, h - 2 * so, fc="none", ec=GREEN, lw=2))
    for x, y in zip(out["xs"], out["ys"]):
        ax.add_patch(Circle((x, h - y), out["db"] / 2, fc=RED, ec="#7a1a1a"))
    ax.annotate("", xy=(b * 1.08, h), xytext=(b * 1.08, 0), arrowprops=dict(arrowstyle="<->"))
    ax.text(b * 1.12, h / 2, f"h = {fmt(h)}\n(bending)", va="center", fontsize=9)
    ax.text(b / 2, -0.08 * h, f"b = {fmt(b)}", ha="center", va="top", fontsize=9)
    ax.text(b / 2, -0.2 * h, f"{out['n']}Ø{out['db']} + ties Ø{out['tie']} @ {out['s_tie']}", ha="center", va="top", fontsize=10, fontweight="bold")
    ax.set_xlim(-0.1 * b, 1.45 * b); ax.set_ylim(-0.32 * h, 1.05 * h); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("Column section", fontweight="bold")
    return _png(fig)


def slab_contours(out) -> bytes:
    Mx, My = out["Mgrid"]
    Lx, Ly = out["Lx"], out["Ly"]
    fig, axs = plt.subplots(1, 2, figsize=(11, 5.2 * Ly / Lx if Ly / Lx < 1.6 else 8))
    for ax, M, t in ((axs[0], Mx, "Mx (short direction)"), (axs[1], My, "My (long direction)")):
        X, Y = np.meshgrid(np.linspace(0, Lx, M.shape[0]), np.linspace(0, Ly, M.shape[1]), indexing="ij")
        lim = np.max(np.abs(M))
        cs = ax.contourf(X, Y, M, levels=21, cmap="RdBu_r", vmin=-lim, vmax=lim)
        ax.contour(X, Y, M, levels=[0], colors="k", linewidths=0.8)
        fig.colorbar(cs, ax=ax, shrink=0.8, label="kN·m/m")
        ax.set_aspect("equal"); ax.set_title(t, fontweight="bold")
        for side, (xx, yy) in zip(out["edges"].upper(), (([0, 0], [0, Ly]), ([Lx, Lx], [0, Ly]), ([0, Lx], [0, 0]), ([0, Lx], [Ly, Ly]))):
            ax.plot(xx, yy, color=DARK, lw=4 if side == "F" else 1.5, ls="-" if side == "F" else "--")
        ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]")
    fig.suptitle(f"Two-way slab {fmt(Lx)}×{fmt(Ly)} m, edges {out['edges']} (thick = continuous)", fontweight="bold")
    fig.tight_layout()
    return _png(fig)


def footing(out) -> bytes:
    L, B, h = out["L"], out["B"], out["h"] / 1000
    c1, c2 = out["c1"] / 1000, out["c2"] / 1000
    fig, axs = plt.subplots(1, 2, figsize=(11, 5))
    ax = axs[0]
    ax.add_patch(Rectangle((0, 0), L, B, fc="#e8eef7", ec=DARK, lw=2))
    ax.add_patch(Rectangle(((L - c1) / 2, (B - c2) / 2), c1, c2, fc="#8c959f", ec=DARK))
    d = out["d"] / 1000
    ax.add_patch(Rectangle(((L - c1) / 2 - d / 2, (B - c2) / 2 - d / 2), c1 + d, c2 + d, fc="none", ec=RED, ls="--", lw=1.5))
    ax.plot([(L + c1) / 2 + d] * 2, [0, B], color=BLUE, ls="--", lw=1.2)
    nL, dL, sL = out["bars"]["long (L)"]; nB, dB, sB = out["bars"]["short (B)"]
    ax.text(L / 2, -0.12 * B, f"L = {fmt(L)} m  ·  {nL}Ø{dL} @ {fmt(sL, 0)}", ha="center", fontsize=9)
    ax.text(-0.08 * L, B / 2, f"B = {fmt(B)} m  ·  {nB}Ø{dB} @ {fmt(sB, 0)}", rotation=90, va="center", ha="center", fontsize=9)
    ax.plot([], [], color=RED, ls="--", label="punching perimeter (d/2)"); ax.plot([], [], color=BLUE, ls="--", label="one-way shear section (d)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.12), fontsize=8, ncol=2, frameon=False)
    ax.set_xlim(-0.2 * L, 1.1 * L); ax.set_ylim(-0.2 * B, 1.1 * B); ax.set_aspect("equal"); ax.axis("off")
    ax = axs[1]
    Df = out["Df"]
    ax.add_patch(Rectangle((-0.3, -Df - 0.1), L + 0.6, 0.1, fc="#d8c3a5", ec="none"))
    ax.add_patch(Rectangle((0, -Df), L, h, fc="#d0d7de", ec=DARK, lw=2))
    ax.add_patch(Rectangle(((L - c1) / 2, -Df + h), c1, Df - h + 0.6, fc="#d0d7de", ec=DARK, lw=2))
    cv = out["cover"] / 1000
    ax.plot([cv, cv, L - cv, L - cv], [-Df + h - cv, -Df + cv, -Df + cv, -Df + h - cv], color=RED, lw=2)
    ax.axhline(0, color="#8a6d3b", lw=1.5); ax.text(L + 0.05, 0.02, "NGL", fontsize=8)
    ax.annotate("", xy=(L + 0.15, -Df), xytext=(L + 0.15, -Df + h), arrowprops=dict(arrowstyle="<->"))
    ax.text(L + 0.2, -Df + h / 2, f"h = {fmt(out['h'])} mm", va="center", fontsize=9)
    xs = np.linspace(0, L, 30)
    ax.fill_between(xs, -Df - 0.1, -Df - 0.1 - 0.25 * np.ones_like(xs), color=BLUE, alpha=0.2)
    ax.text(L / 2, -Df - 0.45, f"qu = {fmt(out['qu'], 1)} kPa (factored)", ha="center", fontsize=9, color=BLUE)
    ax.set_xlim(-0.4, L + 0.9); ax.set_ylim(-Df - 0.6, 0.8); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("Section", fontweight="bold"); axs[0].set_title("Plan", fontweight="bold", pad=22)
    return _png(fig)


def wall(out) -> bytes:
    H, B, toe, tb, tt, ts = (out[k] for k in ("H", "B", "toe", "tb", "t_top", "ts"))
    fig, ax = plt.subplots(figsize=(8, 7))
    pts = [(0, 0), (B, 0), (B, tb), (toe + ts, tb), (toe + tt, H), (toe, H), (toe, tb), (0, tb)]
    ax.add_patch(MPoly(pts, fc="#d0d7de", ec=DARK, lw=2))
    if out.get("key"):
        ax.add_patch(Rectangle((toe, -out["key"]), ts, out["key"], fc="#d0d7de", ec=DARK, lw=2))
    ax.add_patch(MPoly([(toe + ts, tb), (B + 1.0, tb), (B + 1.0, H), (toe + tt, H)], fc="#e9dcc4", ec="none", zorder=0))
    # pressure diagram
    Ka, g, q = out["Ka"], out["gamma"], out["q"]
    pmax = Ka * g * H + Ka * q
    sc = 0.6 / max(pmax, 1)
    ax.add_patch(MPoly([(B + 1.2, H), (B + 1.2 + Ka * q * sc, H), (B + 1.2 + pmax * sc, 0), (B + 1.2, 0)], fc=RED, alpha=0.25, ec=RED))
    ax.text(B + 1.25 + pmax * sc, 0.1, f"{fmt(pmax, 1)} kPa", color=RED, fontsize=9)
    ax.text(B + 1.2, H + 0.1, "Ka·q" if q else "", color=RED, fontsize=8)
    # rebar
    c = 0.05
    ax.plot([toe + ts - c, toe + ts - c, B - 0.075], [H - c, tb - 0.1, tb - 0.1], color=RED, lw=1.5)
    ax.plot([0.075, B - 0.075], [tb - 0.075, tb - 0.075], color=RED, lw=1.2)
    ax.plot([0.075, B - 0.075], [0.075, 0.075], color=RED, lw=1.2)
    d, s = out["stem"]
    ax.text(toe + ts + 0.1, H * 0.55, f"Ø{d}@{s}", color=RED, fontsize=9, fontweight="bold")
    txt = (f"B = {fmt(B)} m, toe = {fmt(toe)} m, heel = {fmt(out['heel'])} m, base = {fmt(tb)} m\n"
           f"FS overturning = {fmt(out['FSo'], 2)}   FS sliding = {fmt(out['FSs'], 2)}   qmax = {fmt(out['qmax'], 1)} kPa"
           + (f"\nShear key depth = {fmt(out['key'])} m" if out.get("key") else ""))
    ax.text(B / 2, -0.35 - (out.get("key") or 0), txt, ha="center", va="top", fontsize=9)
    ax.set_xlim(-0.4, B + 2.2); ax.set_ylim(-1.4 - (out.get("key") or 0), H + 0.5); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(f"Cantilever retaining wall H = {fmt(H)} m", fontweight="bold")
    return _png(fig)


def tributary(out) -> bytes:
    gx, gy, xs, ys = out["gx"], out["gy"], out["xs"], out["ys"]
    fig, ax = plt.subplots(figsize=(9, 9 * gy[-1] / gx[-1] if gy[-1] < 1.5 * gx[-1] else 12))
    cols = ["#cfe2ff", "#ffe5b4", "#d4f4dd", "#f8d7da"]
    for (i, j, kind, ratio) in out["panels"]:
        x0, x1, y0, y1 = gx[i], gx[i + 1], gy[j], gy[j + 1]
        a, b = x1 - x0, y1 - y0
        if kind == "two-way":
            l = min(a, b) / 2
            p1, p2 = (x0 + l, y0 + l), (x1 - l, y1 - l)
            if a >= b:
                p1, p2 = (x0 + l, y0 + l), (x1 - l, y0 + l)
            else:
                p1, p2 = (x0 + l, y0 + l), (x0 + l, y1 - l)
            A, Bp, C, D = (x0, y0), (x1, y0), (x1, y1), (x0, y1)
            if a >= b:
                zones = [[A, Bp, p2, p1], [Bp, C, p2], [C, D, p1, p2], [D, A, p1]]
            else:
                zones = [[A, Bp, p1], [Bp, C, p2, p1], [C, D, p2], [D, A, p1, p2]]
            for z, colr in zip(zones, cols):
                ax.add_patch(MPoly(z, fc=colr, ec="#555", lw=0.6))
        else:
            if a >= b:
                ax.add_patch(Rectangle((x0, y0), a, b / 2, fc=cols[0], ec="#555", lw=0.6))
                ax.add_patch(Rectangle((x0, y0 + b / 2), a, b / 2, fc=cols[2], ec="#555", lw=0.6))
            else:
                ax.add_patch(Rectangle((x0, y0), a / 2, b, fc=cols[1], ec="#555", lw=0.6))
                ax.add_patch(Rectangle((x0 + a / 2, y0), a / 2, b, fc=cols[3], ec="#555", lw=0.6))
        ax.text((x0 + x1) / 2, (y0 + y1) / 2, f"{kind}\n{fmt(ratio, 2)}", ha="center", va="center", fontsize=8, color="#333")
    for x in gx:
        ax.plot([x, x], [0, gy[-1]], color=DARK, lw=3)
    for y in gy:
        ax.plot([0, gx[-1]], [y, y], color=DARK, lw=3)
    for i, j, A, P in out["cols"]:
        ax.add_patch(Rectangle((gx[i] - 0.15, gy[j] - 0.15), 0.3, 0.3, fc=RED, ec=DARK, zorder=5))
        ax.text(gx[i] + 0.2, gy[j] + 0.2, f"{fmt(P, 0)} kN", fontsize=7.5, color=RED, zorder=6, bbox=dict(fc="white", ec="none", pad=0.2, alpha=0.8))
    for k, x in enumerate(gx):
        ax.text(x, gy[-1] + 0.4, str(k + 1), ha="center", fontweight="bold", bbox=dict(boxstyle="circle", fc="white"))
    for k, y in enumerate(gy):
        ax.text(-0.5, y, chr(65 + k), va="center", fontweight="bold", bbox=dict(boxstyle="circle", fc="white"))
    ax.set_xlim(-1, gx[-1] + 0.8); ax.set_ylim(-0.6, gy[-1] + 0.9); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(f"Load path: tributary areas (q = {fmt(out['q'])} kN/m²) and column loads", fontweight="bold")
    return _png(fig)


def bbs_table(bars) -> bytes:
    from ..engines.bbs import SHAPES, total_by_dia
    n = len(bars)
    fig, ax = plt.subplots(figsize=(11, 0.6 * n + 2.2))
    ax.axis("off")
    hdr = ["Mark", "Member", "Shape", "Ø", "No.", "A", "B", "C", "L (mm)", "Wt (kg)"]
    xs = [0.0, 0.08, 0.2, 0.36, 0.42, 0.49, 0.57, 0.65, 0.73, 0.84, 0.95]
    y = 1.0
    rowh = 1.0 / (n + 3)
    for k, t in enumerate(hdr):
        ax.text((xs[k] + xs[k + 1]) / 2, y - rowh / 2, t, ha="center", va="center", fontweight="bold", color="white", transform=ax.transAxes)
    ax.add_patch(Rectangle((0, y - rowh), 0.95, rowh, color=BLUE, transform=ax.transAxes))
    for r_, b in enumerate(bars):
        yy = y - (r_ + 2) * rowh
        if r_ % 2:
            ax.add_patch(Rectangle((0, yy), 0.95, rowh, color="#f6f8fa", transform=ax.transAxes))
        vals = [b.mark, b.member, None, f"{b.d}", f"{b.n}", fmt(b.A, 0) if b.A else "", fmt(b.B, 0) if b.B else "", fmt(b.C, 0) if b.C else "",
                fmt(b.length, 0), fmt(b.weight, 1)]
        for k, v in enumerate(vals):
            if v is not None:
                ax.text((xs[k] + xs[k + 1]) / 2, yy + rowh / 2, v, ha="center", va="center", fontsize=9, transform=ax.transAxes)
        # shape icon
        cx, cy, w, hh = (xs[2] + xs[3]) / 2, yy + rowh / 2, 0.05, rowh * 0.32
        pts = {"00": [(-w, 0), (w, 0)], "11": [(-w, hh), (-w, -hh), (w, -hh)], "21": [(-w, hh), (-w, -hh), (w, -hh), (w, hh)],
               "51": [(-w * 0.6, hh), (-w * 0.6, -hh), (w * 0.6, -hh), (w * 0.6, hh), (-w * 0.6, hh), (-w * 0.3, hh * 0.4)],
               "33": [(-w, hh * 0.6), (-w, 0), (w, 0), (w, hh * 0.6)]}[b.shape]
        ax.plot([cx + p[0] for p in pts], [cy + p[1] for p in pts], color=RED, lw=2, transform=ax.transAxes)
        ax.text(cx + 0.065, cy, b.shape, fontsize=7, va="center", color=GREY, transform=ax.transAxes)
    tot = total_by_dia(bars)
    s = "   ".join(f"Ø{d}: {fmt(w, 1)} kg" for d, w in tot.items())
    ax.text(0, y - (n + 2.4) * rowh, f"{s}     TOTAL (+5%): {fmt(sum(tot.values()) * 1.05, 1)} kg", fontsize=10, fontweight="bold", transform=ax.transAxes)
    ax.set_title("Bar Bending Schedule (BS 8666)", fontweight="bold", loc="left")
    return _png(fig)
