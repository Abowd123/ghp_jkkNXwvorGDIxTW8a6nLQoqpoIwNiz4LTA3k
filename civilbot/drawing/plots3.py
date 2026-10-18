"""Phase-3 drawings: geotechnics, materials, hydraulics, surveying, roads, steel, influence lines."""
from __future__ import annotations
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon as MPoly, Arc, Wedge
from .plots import _png, BLUE, RED, GREEN, GREY, DARK
from ..core import fmt


def mohr(o) -> bytes:
    C, R = o["C"], o["R"]
    fig, ax = plt.subplots(figsize=(6.5, 6.5))
    th = np.linspace(0, 2 * np.pi, 300)
    ax.plot(C + R * np.cos(th), R * np.sin(th), color=BLUE, lw=2)
    ax.axhline(0, color=DARK, lw=0.8); ax.axvline(0, color=DARK, lw=0.8)
    X, Y = (o["sx"], o["txy"]), (o["sy"], -o["txy"])
    ax.plot([X[0], Y[0]], [X[1], Y[1]], color=GREY, ls="--")
    ax.plot(*X, "o", color=RED); ax.text(X[0], X[1], "  X(σx, τxy)", color=RED, fontsize=9)
    ax.plot(*Y, "o", color=RED); ax.text(Y[0], Y[1], "  Y(σy, −τxy)", color=RED, fontsize=9)
    ax.plot([o["s1"], o["s3"]], [0, 0], "s", color=GREEN, ms=7)
    ax.text(o["s1"], -0.08 * R, f"σ1 = {fmt(o['s1'], 2)}", ha="center", va="top", color=GREEN, fontweight="bold")
    ax.text(o["s3"], -0.08 * R, f"σ3 = {fmt(o['s3'], 2)}", ha="center", va="top", color=GREEN, fontweight="bold")
    ax.plot([C, C], [R, -R], "^", color=BLUE)
    ax.text(C, R * 1.05, f"τmax = {fmt(R, 2)}", ha="center", color=BLUE)
    ax.text(C, 0.04 * R, f"C = {fmt(C, 2)}", ha="center", fontsize=8.5)
    if "sn" in o:
        ax.plot(o["sn"], -o["tn"], "D", color="#8250df"); ax.text(o["sn"], -o["tn"], f"  θ = {fmt(o['theta'])}°", color="#8250df", fontsize=9)
    ax.add_patch(Arc((C, 0), 0.5 * R, 0.5 * R, theta1=0, theta2=math.degrees(math.atan2(X[1], X[0] - C)), color=DARK))
    ax.text(C + 0.3 * R, 0.08 * R, f"2θp = {fmt(2 * o['tp'], 2)}°", fontsize=8.5)
    ax.set_aspect("equal"); ax.grid(alpha=0.3)
    ax.set_xlabel("σ"); ax.set_ylabel("τ (plotted +down convention: X at +τxy)")
    ax.set_title("Mohr's circle", fontweight="bold")
    ax.margins(0.15)
    return _png(fig)


def lateral(o) -> bytes:
    z, pa, pp, H = o["z"], o["pa"], o["pp"], o["H"]
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.fill_betweenx(z, 0, pa, color=RED, alpha=0.3); ax.plot(pa, z, color=RED, lw=2, label=f"active (Ka = {fmt(o['Ka'], 3)})")
    ax.fill_betweenx(z, 0, -pp, color=BLUE, alpha=0.15); ax.plot(-pp, z, color=BLUE, lw=2, label=f"passive (Kp = {fmt(o['Kp'], 3)})")
    ax.add_patch(Rectangle((-0.03 * max(pp.max(), 1), 0), 0.06 * max(pp.max(), 1), H, color=GREY))
    ax.annotate(f"Pa = {fmt(o['Pa'], 1)} kN/m", xy=(0, H - o["ybar"]), xytext=(pa.max() * 0.6, H - o["ybar"]),
                arrowprops=dict(arrowstyle="-|>", color=RED, lw=2), color=RED, va="center", fontweight="bold")
    ax.text(pa[-1], H, f" {fmt(pa[-1], 1)} kPa", color=RED, va="top")
    ax.text(-pp[-1], H, f"{fmt(pp[-1], 1)} kPa ", color=BLUE, va="top", ha="right")
    ax.invert_yaxis(); ax.set_ylabel("depth z [m]"); ax.set_xlabel("pressure [kPa] (passive drawn to the left)")
    ax.legend(loc="lower left"); ax.grid(alpha=0.3)
    ax.set_title("Lateral earth pressure diagram", fontweight="bold")
    return _png(fig)


def consolidation(o) -> bytes:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    yrs = o["Ts"] * o["Hdr"] ** 2 / o["cv"]
    ax.plot(yrs, o["U"] * o["S"] * 1000, color=BLUE, lw=2)
    ax.axhline(o["S"] * 1000, color=GREY, ls="--"); ax.text(yrs[-1], o["S"] * 1000, f"Sc = {fmt(o['S']*1000, 1)} mm", ha="right", va="bottom")
    ax.invert_yaxis(); ax.set_xlabel("time [years]"); ax.set_ylabel("settlement [mm]"); ax.grid(alpha=0.3)
    ax.set_title("Settlement vs time (Terzaghi 1-D consolidation)", fontweight="bold")
    return _png(fig)


def bulb(o) -> bytes:
    X, Z, G, B = o["X"], o["Z"], o["G"], o["B"]
    fig, ax = plt.subplots(figsize=(7, 7))
    cs = ax.contour(X, Z, G, levels=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9], cmap="viridis")
    ax.clabel(cs, fmt=lambda v: f"{v:.1f}q", fontsize=8)
    ax.add_patch(Rectangle((-B / 2, -0.15), B, 0.15, color=DARK))
    ax.invert_yaxis(); ax.set_aspect("equal"); ax.set_xlabel("x [m]"); ax.set_ylabel("depth z [m]")
    ax.set_title(f"Pressure bulbs Δσz/q under {fmt(B)}×{fmt(o['L'])} m footing", fontweight="bold")
    ax.grid(alpha=0.2)
    return _png(fig)


def slope(o) -> bytes:
    H, Lx = o["H"], o["Lx"]
    fig, ax = plt.subplots(figsize=(9, 6))
    xg = [-1.5 * H, 0, Lx, Lx + 2 * H]
    yg = [0, 0, H, H]
    ax.fill(xg + [xg[-1], xg[0]], yg + [-0.8 * H, -0.8 * H], color="#e9dcc4")
    ax.plot(xg, yg, color=DARK, lw=2)
    th = np.linspace(0, 2 * np.pi, 400)
    cx, cy, R = o["xc"], o["yc"], o["R"]
    xs, ys = cx + R * np.cos(th), cy + R * np.sin(th)
    ground = np.interp(xs, xg, yg)
    m = (ys < ground) & (xs > o["x1"] - 0.01) & (xs < o["x2"] + 0.01)
    ax.plot(xs[m], ys[m], color=RED, lw=2.5)
    ax.plot([cx], [cy], "+", color=RED, ms=12)
    for xx in (o["x1"], o["x2"]):
        ax.plot([cx, xx], [cy, np.interp(xx, xg, yg)], color=RED, lw=0.8, ls=":")
    ax.text(cx, cy + 0.08 * H, f"FS = {fmt(o['FS'], 3)}", ha="center", color=RED, fontsize=12, fontweight="bold")
    ax.set_aspect("equal"); ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]"); ax.grid(alpha=0.2)
    ax.set_title(f"Critical slip circle (Bishop simplified) — slope {fmt(o['beta'])}°, H = {fmt(H)} m", fontweight="bold")
    return _png(fig)


def gradation(o) -> bytes:
    fig, ax = plt.subplots(figsize=(8, 5))
    lim = o.get("limits")
    if lim:
        ss = sorted(lim)
        ax.fill_between(ss, [lim[s][0] for s in ss], [lim[s][1] for s in ss], color=GREEN, alpha=0.15, label="ASTM C33 envelope")
        ax.plot(ss, [lim[s][0] for s in ss], color=GREEN, ls="--", lw=1); ax.plot(ss, [lim[s][1] for s in ss], color=GREEN, ls="--", lw=1)
    ax.plot(o["sizes"], o["passing"], "o-", color=BLUE, lw=2, label="sample")
    for D, nm in ((o["D10"], "D10"), (o["D30"], "D30"), (o["D60"], "D60")):
        if D:
            ax.axvline(D, color=GREY, ls=":", lw=1); ax.text(D, 3, nm, rotation=90, fontsize=8, color=GREY)
    ax.set_xscale("log"); ax.invert_xaxis(); ax.set_ylim(0, 102)
    ax.set_xlabel("sieve size [mm] (log)"); ax.set_ylabel("% passing"); ax.grid(alpha=0.3, which="both")
    ax.legend(); ax.set_title(f"Grain-size distribution — FM = {fmt(o['fm'], 2)}" + (f" , {o['cls']}" if o["cls"] else ""), fontweight="bold")
    return _png(fig)


def mix(o) -> bytes:
    v = o["vols"]
    fig, axs = plt.subplots(1, 2, figsize=(10, 4.5))
    labels = ["water", "cement", "fine agg.", "coarse agg.", "air"]
    vals = [v["water"], v["cement"], v["fine"], v["coarse"], v["air"]]
    axs[0].pie(vals, labels=[f"{l}\n{fmt(x*100, 1)}%" for l, x in zip(labels, vals)], colors=["#79c0ff", "#8c959f", "#e3b341", "#a371f7", "#d0d7de"], startangle=90)
    axs[0].set_title("Absolute volumes (1 m³)", fontweight="bold")
    mass = [o["W"], o["C"], o["FA"], o["CA"]]
    axs[1].bar(["water", "cement", "sand", "gravel"], mass, color=["#79c0ff", "#8c959f", "#e3b341", "#a371f7"])
    for k, m in enumerate(mass):
        axs[1].text(k, m, fmt(m, 0), ha="center", va="bottom", fontweight="bold")
    axs[1].set_ylabel("kg/m³"); axs[1].set_title(f"Batch weights — w/c = {fmt(o['wc'], 2)}", fontweight="bold")
    return _png(fig)


def channel(o) -> bytes:
    from ..engines.hydraulics import geom
    fig, ax = plt.subplots(figsize=(7, 4.5))
    y, s = o["y"], o["shape"]
    if s == "circle":
        D = o["D"]
        ax.add_patch(Circle((0, D / 2), D / 2, fc="none", ec=DARK, lw=3))
        th = np.linspace(0, 2 * np.pi, 300)
        xx, yy = D / 2 * np.cos(th), D / 2 + D / 2 * np.sin(th)
        m = yy <= y
        ax.fill(xx[m], yy[m], color="#79c0ff", alpha=0.7)
        top = D
    else:
        b, z = o["b"], (o["z"] if s != "rect" else 0)
        Hh = y * 1.5
        if s == "tri":
            b = 0
        pts = [(-b / 2 - z * Hh, Hh), (-b / 2, 0), (b / 2, 0), (b / 2 + z * Hh, Hh)]
        ax.plot(*zip(*pts), color=DARK, lw=3)
        ax.add_patch(MPoly([(-b / 2 - z * y, y), (-b / 2, 0), (b / 2, 0), (b / 2 + z * y, y)], fc="#79c0ff", alpha=0.7))
        top = Hh
    ax.axhline(o["yc"], color=RED, ls="--", lw=1)
    ax.margins(0.1); ax.autoscale_view()
    ax.text(ax.get_xlim()[1], o["yc"], f"yc = {fmt(o['yc'], 3)} m", color=RED, ha="right", va="bottom", fontsize=9)
    ax.text(0, y / 2, f"yn = {fmt(y, 3)} m\nV = {fmt(o['V'], 2)} m/s\nFr = {fmt(o['Fr'], 2)}", ha="center", va="center", fontsize=10, fontweight="bold")
    ax.set_aspect("equal"); ax.axis("off"); ax.margins(0.1)
    ax.set_title(f"Channel section — Q = {fmt(o['Q'], 3)} m³/s", fontweight="bold")
    return _png(fig)


def traverse(o) -> bytes:
    E, N = o["E"], o["N"]
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.fill(E, N, color=BLUE, alpha=0.08)
    ax.plot(E, N, "o-", color=BLUE, lw=2)
    for k, (e, n) in enumerate(zip(E[:-1], N[:-1])):
        ax.text(e, n, f"  P{k+1}\n  ({fmt(e, 2)}, {fmt(n, 2)})", fontsize=8.5)
    ax.set_aspect("equal"); ax.grid(alpha=0.3); ax.set_xlabel("E [m]"); ax.set_ylabel("N [m]")
    ax.set_title(f"Adjusted traverse — precision 1:{fmt(o['prec'], 0)} , area {fmt(o['area'], 1)} m²", fontweight="bold")
    return _png(fig)


def hcurve(o) -> bytes:
    R, d = o["R"], math.radians(o["delta"])
    fig, ax = plt.subplots(figsize=(7.5, 6))
    T = o["T"]
    PC = np.array([0.0, 0.0])
    Oc = np.array([0.0, R])
    th = np.linspace(-np.pi / 2, -np.pi / 2 + d, 200)
    ax.plot(Oc[0] + R * np.cos(th), Oc[1] + R * np.sin(th), color=RED, lw=3)
    PI = np.array([T, 0.0]); PT = Oc + R * np.array([math.cos(-np.pi / 2 + d), math.sin(-np.pi / 2 + d)])
    ax.plot([-0.3 * T, PI[0]], [0, 0], color=DARK, lw=1.5); ax.plot([PI[0], PI[0] + 1.3 * T * math.cos(d)], [0, 1.3 * T * math.sin(d)], color=DARK, lw=1.5)
    ax.plot([Oc[0], PC[0]], [Oc[1], PC[1]], color=GREY, ls=":"); ax.plot([Oc[0], PT[0]], [Oc[1], PT[1]], color=GREY, ls=":")
    for pnt, nm in ((PC, f"PC {fmt(o['PC'], 2)}"), (PI, "PI"), (PT, f"PT {fmt(o['PT'], 2)}")):
        ax.plot(*pnt, "o", color=DARK); ax.text(pnt[0], pnt[1] - 0.05 * R, nm, ha="center", va="top", fontsize=9)
    for ch, *_ in o["table"][:-1]:
        a = (ch - o["PC"]) / R
        p = Oc + R * np.array([math.cos(-np.pi / 2 + a), math.sin(-np.pi / 2 + a)])
        ax.plot(*p, "|", color=BLUE, ms=10)
    ax.text(PI[0], 0.1 * R, f"Δ = {fmt(o['delta'], 3)}°", ha="center")
    ax.text(T / 2, -0.12 * R, f"T = {fmt(T, 2)}", ha="center", color=BLUE)
    ax.set_aspect("equal"); ax.axis("off"); ax.margins(0.1)
    ax.set_title(f"Horizontal curve R = {fmt(R)} m , L = {fmt(o['L'], 2)} m", fontweight="bold")
    return _png(fig)


def vcurve(o) -> bytes:
    ch = [t[0] for t in o["table"]]; el = [t[1] for t in o["table"]]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    pc, pe = o["pvi"]
    ax.plot([o["bvc"] - 0.3 * o["L"], pc, o["evc"] + 0.3 * o["L"]],
            [o["bel"] - o["g1"] / 100 * 0.3 * o["L"], pe, pe + o["g2"] / 100 * (o["L"] / 2 + 0.3 * o["L"])], color=GREY, ls="--")
    ax.plot(ch, el, "o-", color=RED, lw=2, ms=4)
    ax.plot([pc], [pe], "^", color=DARK); ax.text(pc, pe, "  PVI", fontsize=9)
    ax.set_xlabel("chainage [m]"); ax.set_ylabel("elevation [m]"); ax.grid(alpha=0.3)
    ax.set_title(f"Vertical curve g1 = {fmt(o['g1'])}% → g2 = {fmt(o['g2'])}% , L = {fmt(o['L'])} m , K = {fmt(o['K'], 1)}", fontweight="bold")
    return _png(fig)


def masshaul(o) -> bytes:
    fig, axs = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    st, ar = o["stations"], o["areas"]
    axs[0].bar(st, ar, width=(st[1] - st[0]) * 0.5, color=[RED if a > 0 else BLUE for a in ar])
    axs[0].axhline(0, color=DARK); axs[0].set_ylabel("area [m²] (+cut)"); axs[0].set_title("Cross-section areas", fontweight="bold")
    axs[1].plot(st, o["mass"], "o-", color=GREEN, lw=2); axs[1].axhline(0, color=DARK)
    axs[1].set_ylabel("cumulative volume [m³]"); axs[1].set_xlabel("station [m]"); axs[1].set_title("Mass haul diagram", fontweight="bold")
    for a in axs: a.grid(alpha=0.3)
    return _png(fig)


def pavement(o) -> bytes:
    D = o["D"]
    fig, ax = plt.subplots(figsize=(6, 5))
    cols = ["#24292f", "#8c959f", "#d4a72c", "#e9dcc4"]
    names = ["Asphalt concrete", "Granular base", "Subbase", "Subgrade"]
    y = 0
    for d, c, n in zip(list(D) + [250], cols, names):
        ax.add_patch(Rectangle((0, y - d), 1, d, color=c))
        ax.text(0.5, y - d / 2, f"{n}\n{fmt(d, 0)} mm" if n != "Subgrade" else n, ha="center", va="center", color="white" if c in ("#24292f", "#8c959f") else DARK, fontweight="bold")
        y -= d
    ax.set_xlim(0, 1); ax.set_ylim(y, 10); ax.axis("off")
    ax.set_title(f"Pavement structure (SN = {fmt(o['SN'], 2)})", fontweight="bold")
    return _png(fig)


def influence(o) -> bytes:
    xs, il = o["xs"], o["il"]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.fill_between(xs, il, 0, where=il >= 0, color=BLUE, alpha=0.25, interpolate=True)
    ax.fill_between(xs, il, 0, where=il < 0, color=RED, alpha=0.25, interpolate=True)
    ax.plot(xs, il, color=DARK, lw=2)
    ax.axhline(0, color=DARK, lw=1)
    for k, x in o["supports"]:
        ax.plot([x], [0], marker="^", ms=12, color=DARK, clip_on=False, zorder=5)
    if o["qty"] != "R":
        ax.axvline(o["x0"], color=GREEN, ls="--"); ax.text(o["x0"], ax.get_ylim()[1], f" x = {fmt(o['x0'])}", color=GREEN, va="top")
    i, j = int(np.argmax(il)), int(np.argmin(il))
    for k in {i, j}:
        if abs(il[k]) > 1e-6:
            ax.annotate(fmt(il[k], 3), (xs[k], il[k]), xytext=(0, 8 if il[k] > 0 else -14), textcoords="offset points", ha="center", fontweight="bold")
    if "axles" in o:
        loads, offs = o["axles"]
        lead = o["best"][1]
        top = max(abs(il).max(), 1e-9)
        for P, of in zip(loads, offs):
            xa = lead - of
            if 0 <= xa <= o["L"]:
                ax.annotate("", xy=(xa, 0), xytext=(xa, top * 1.0), arrowprops=dict(arrowstyle="-|>", color=GREEN, lw=1.8))
                ax.text(xa, top * 1.03, fmt(P), ha="center", color=GREEN, fontsize=8)
    ax.set_xlabel("unit load position [m]"); ax.grid(alpha=0.3)
    ax.set_title(f"Influence line — {o['name']}", fontweight="bold")
    return _png(fig)


def steel_section(p, title) -> bytes:
    h, b, tw, tf = p["h"], p["b"], p["tw"], p["tf"]
    fig, ax = plt.subplots(figsize=(4.5, 5))
    ax.add_patch(Rectangle((0, 0), b, tf, color="#57606a")); ax.add_patch(Rectangle((0, h - tf), b, tf, color="#57606a"))
    ax.add_patch(Rectangle(((b - tw) / 2, tf), tw, h - 2 * tf, color="#57606a"))
    ax.text(b / 2, -0.06 * h, f"b = {fmt(b)}", ha="center", va="top"); ax.text(b * 1.06, h / 2, f"h = {fmt(h)}", va="center")
    ax.text(b / 2 + tw, h / 2, f" tw = {fmt(tw)}", va="center", fontsize=8); ax.text(b * 1.02, h - tf / 2, f"tf = {fmt(tf)}", va="center", fontsize=8)
    ax.set_xlim(-0.1 * b, 1.5 * b); ax.set_ylim(-0.15 * h, 1.05 * h); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(title, fontweight="bold")
    return _png(fig)


def shear_tab(o) -> bytes:
    n, s, Le, Lp, w = o["n"], o["s"], o["Le"], o["Lp"], o["width"]
    fig, axs = plt.subplots(1, 2, figsize=(9, 6), gridspec_kw={"width_ratios": [1.2, 1]})
    ax = axs[0]
    ax.add_patch(Rectangle((-40, -60), 40, Lp + 120, color="#8c959f"))           # supporting column flange
    ax.add_patch(Rectangle((0, 0), w, Lp, fc="#d0d7de", ec=DARK, lw=2))         # plate
    ax.add_patch(Rectangle((10, -80), 260, Lp + 160, fc="none", ec=BLUE, ls="--"))  # beam web outline
    xb = w - Le
    for k in range(n):
        y = Le + k * s
        ax.add_patch(Circle((xb, y), o["d"] / 2, fc=RED, ec=DARK))
    ax.plot([0, 0], [0, Lp], color=GREEN, lw=5)
    ax.text(-50, Lp / 2, f"weld {o['weld']} mm (both sides)", rotation=90, ha="right", va="center", color=GREEN, fontsize=9)
    for k in range(n - 1):
        ax.annotate("", xy=(xb + 40, Le + k * s), xytext=(xb + 40, Le + (k + 1) * s), arrowprops=dict(arrowstyle="<->", lw=0.8))
        ax.text(xb + 46, Le + (k + 0.5) * s, f"{s}", fontsize=8, va="center")
    ax.text(w / 2, -110, f"PL {fmt(Lp)}×{fmt(w)}×{fmt(o['tp'])}  ·  {n} M{o['d']} bolts", ha="center", fontweight="bold")
    ax.set_aspect("equal"); ax.axis("off"); ax.set_title("Elevation", fontweight="bold"); ax.margins(0.15)
    ax = axs[1]
    t = o["tp"]
    ax.add_patch(Rectangle((-40, -60), 40, Lp + 120, color="#8c959f"))
    ax.add_patch(Rectangle((0, 0), w, Lp, fc="none", ec="none"))
    ax.add_patch(Rectangle((0, 0), w, Lp, fc="none", ec="none"))
    ax.add_patch(Rectangle((0, 0), t, Lp, fc="#d0d7de", ec=DARK))
    ax.add_patch(Rectangle((t, -80), 8, Lp + 160, fc="none", ec=BLUE, ls="--"))
    for k in range(n):
        y = Le + k * s
        ax.add_patch(Rectangle((-8, y - o["d"] / 2), t + 8 + 8 + 16, o["d"], fc=RED, ec=DARK))
    ax.set_xlim(-80, 120); ax.set_ylim(-150, Lp + 150); ax.set_aspect("equal"); ax.axis("off"); ax.set_title("Side view", fontweight="bold")
    fig.suptitle(f"Single-plate shear connection — φRn = {fmt(o['cap'], 1)} kN", fontweight="bold")
    return _png(fig)


def base_plate(o) -> bytes:
    N, B, d, bf = o["N"], o["B"], o["d"], o["bf"]
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.add_patch(Rectangle((-B / 2, -N / 2), B, N, fc="#d0d7de", ec=DARK, lw=2))
    tf = 0.06 * d; tw = 0.035 * d
    ax.add_patch(Rectangle((-bf / 2, d / 2 - tf), bf, tf, color="#57606a")); ax.add_patch(Rectangle((-bf / 2, -d / 2), bf, tf, color="#57606a"))
    ax.add_patch(Rectangle((-tw / 2, -d / 2), tw, d, color="#57606a"))
    for sx in (-1, 1):
        for sy in (-1, 1):
            ax.add_patch(Circle((sx * (B / 2 - 50), sy * (N / 2 - 50)), 12, fc="white", ec=DARK))
    ax.text(0, -N / 2 - 30, f"B = {fmt(B)} mm", ha="center", va="top"); ax.text(B / 2 + 20, 0, f"N = {fmt(N)} mm", rotation=90, va="center")
    ax.text(0, N / 2 + 20, f"PL t = {o['t']} mm  (m = {fmt(o['m'], 0)}, n = {fmt(o['n'], 0)})", ha="center", fontweight="bold")
    ax.set_aspect("equal"); ax.axis("off"); ax.margins(0.15)
    ax.set_title("Column base plate", fontweight="bold")
    return _png(fig)
