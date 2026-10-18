"""RC slabs (ACI 318-19): one-way, two-way (elastic plate FD analysis), punching shear."""
from __future__ import annotations
import math
import numpy as np
from scipy.sparse import lil_matrix
from scipy.sparse.linalg import spsolve
from ..core import Result, InputError, fmt

BARS = [8, 10, 12, 14, 16]
AR = {d: math.pi * d * d / 4 for d in BARS + [18, 20]}


def flexure_strip(Mu, h, d, fc, fy, b=1000.0):
    """As per metre width (mm²/m) for Mu (kN·m/m) — returns As_req, As_min."""
    Rn = abs(Mu) * 1e6 / (0.9 * b * d * d)
    disc = 1 - 2 * Rn / (0.85 * fc)
    if disc <= 0:
        raise InputError("سماكة البلاطة غير كافية لهذا العزم. زد h")
    rho = 0.85 * fc / fy * (1 - math.sqrt(disc))
    As_min = (0.0018 * 420 / fy if fy > 420 else 0.0020 if fy < 420 else 0.0018) * b * h
    As_min = max(As_min, 0.0014 * b * h)
    return rho * b * d, As_min


def pick_spacing(As, h, prefer=None):
    smax = min(2 * h, 450)   # ACI 8.7.2.2 for two-way; one-way uses 3h — caller adjusts
    for d in ([prefer] if prefer else []) + BARS:
        s = 1000 * AR[d] / As
        s = math.floor(min(s, smax) / 25) * 25
        if s >= 100:
            return d, int(s), 1000 * AR[d] / s
    d = 16
    s = max(75, math.floor(1000 * AR[d] / As / 25) * 25)
    return d, int(s), 1000 * AR[d] / s


def one_way(L, h, fc, fy, wD, wL, cover=20.0, support="ss") -> Result:
    """L in m, loads in kN/m² (superimposed dead wD excludes self weight)."""
    fac = {"ss": 20, "one": 24, "both": 28, "cant": 10}
    if support not in fac:
        raise InputError("support لازم يكون ss / one / both / cant")
    r = Result("slab1", "One-way slab design (ACI 318-19)",
               inputs=dict(L=f"{fmt(L)} m", support=support, fc=f"{fmt(fc)} MPa", fy=f"{fmt(fy)} MPa",
                           wD=f"{fmt(wD)} kN/m² (superimposed)", wL=f"{fmt(wL)} kN/m²"))
    hmin = L * 1000 / fac[support] * (0.4 + fy / 700 if fy != 420 else 1.0)
    if not h:
        h = math.ceil(hmin / 10) * 10
    r.add("Minimum thickness (deflection not computed)", f"h_min = ℓ/{fac[support]}" + (" × (0.4 + fy/700)" if fy != 420 else ""),
          f"{fmt(L*1000)}/{fac[support]}", f"h_min = {fmt(hmin, 1)} mm → use h = {fmt(h)} mm" + ("" if h >= hmin else " ⚠"), "ACI Table 7.3.1.1")
    if h < hmin:
        r.warnings.append("السماكة أقل من الحد الأدنى للترخيم: لازم حساب الترخيم أو زيادة h")
    sw = 24 * h / 1000
    wu = max(1.2 * (wD + sw) + 1.6 * wL, 1.4 * (wD + sw))
    r.add("Factored load", "wu = 1.2(D + γc·h) + 1.6L", f"1.2×({fmt(wD)} + 24×{fmt(h/1000)}) + 1.6×{fmt(wL)}", f"wu = {fmt(wu)} kN/m²", "ACI 5.3.1")
    coef = {"ss": (1 / 8, 0), "one": (1 / 11, -1 / 9), "both": (1 / 16, -1 / 11), "cant": (0, -1 / 2)}[support]
    Mpos, Mneg = coef[0] * wu * L**2, coef[1] * wu * L**2
    r.add("Design moments per metre", "M = C·wu·ℓn² (ACI approximate coefficients)",
          f"C+ = {fmt(coef[0], 4)} , C− = {fmt(coef[1], 4)}", f"M+ = {fmt(Mpos)} , M− = {fmt(Mneg)} kN·m/m", "ACI 6.5.2")
    d = h - cover - 6
    out = {}
    for name, M in (("bottom", Mpos), ("top", Mneg)):
        if abs(M) < 1e-9:
            continue
        As, Asmin = flexure_strip(M, h, d, fc, fy)
        db, s, prov = pick_spacing(max(As, Asmin), h)
        s = min(s, math.floor(min(3 * h, 450) / 25) * 25)
        out[name] = (db, s)
        r.add(f"{name.title()} main steel", "As = ρ·b·d ≥ As,min (0.0018·b·h)", f"d = {fmt(d)} mm , As = {fmt(As)} , As,min = {fmt(Asmin)} mm²/m",
              f"Ø{db} @ {s} mm ({fmt(1000*AR[db]/s, 0)} mm²/m)", "ACI 7.6.1.1")
    As_t = 0.0018 * 1000 * h
    dbt, st, _ = pick_spacing(As_t, h, prefer=8 if h <= 150 else 10)
    st = min(st, math.floor(min(5 * h, 450) / 25) * 25)
    r.add("Shrinkage & temperature steel", "As,st = 0.0018·b·h ; s ≤ min(5h, 450)", f"{fmt(As_t)} mm²/m", f"Ø{dbt} @ {st} mm", "ACI 24.4.3")
    Vu = wu * L * (0.5 if support == "ss" else (1.15 / 2 if support != "cant" else 1.0))
    phiVc = 0.75 * 0.17 * math.sqrt(fc) * 1000 * d / 1e3
    r.add("One-way shear", "φVc = 0.75·0.17√f'c·b·d ≥ Vu", f"Vu ≈ {fmt(Vu)} kN/m", f"φVc = {fmt(phiVc)} kN/m {'✔' if phiVc >= Vu else '✘'}", "ACI 22.5.5.1")
    if phiVc < Vu:
        r.warnings.append("القص أكبر من مقاومة الخرسانة: زد السماكة")
    r.outputs = dict(h=h, d=d, wu=wu, Mpos=Mpos, Mneg=Mneg, bars=out, temp=(dbt, st), L=L, kind="one")
    return r


def plate_fd(Lx, Ly, edges="SSSS", nu=0.2, n=24):
    """Kirchhoff plate under unit uniform load, D = 1. edges: left,right,bottom,top each S/F/E(free not supported).
    Returns coefficient grids: w, Mx, My (multiply by q·Lx² for moments)."""
    nx, ny = n, max(6, int(round(n * Ly / Lx)))
    hx, hy = Lx / nx, Ly / ny
    # interior unknowns i=1..nx-1, j=1..ny-1 ; boundary w = 0 ; ghost via edge condition
    N = (nx - 1) * (ny - 1)
    idx = lambda i, j: (i - 1) * (ny - 1) + (j - 1)
    A = lil_matrix((N, N))
    b = np.full(N, 1.0)
    el, er, eb, et = [edges[k].upper() for k in range(4)]

    def val(i, j):
        """return list of (index, coef) representing w(i,j) incl. boundary/ghost."""
        if 1 <= i <= nx - 1 and 1 <= j <= ny - 1:
            return [(idx(i, j), 1.0)]
        if i in (0, nx) or j in (0, ny):
            return []
        # ghost nodes
        if i == -1:
            return [(k, (1.0 if el == "F" else -1.0) * c) for k, c in val(1, j)]
        if i == nx + 1:
            return [(k, (1.0 if er == "F" else -1.0) * c) for k, c in val(nx - 1, j)]
        if j == -1:
            return [(k, (1.0 if eb == "F" else -1.0) * c) for k, c in val(i, 1)]
        if j == ny + 1:
            return [(k, (1.0 if et == "F" else -1.0) * c) for k, c in val(i, ny - 1)]
        return []
    ax, ay = 1 / hx**4, 1 / hy**4
    axy = 1 / (hx**2 * hy**2)
    stencil = [((0, 0), 6 * ax + 6 * ay + 8 * axy), ((1, 0), -4 * ax - 4 * axy), ((-1, 0), -4 * ax - 4 * axy),
               ((0, 1), -4 * ay - 4 * axy), ((0, -1), -4 * ay - 4 * axy), ((2, 0), ax), ((-2, 0), ax),
               ((0, 2), ay), ((0, -2), ay), ((1, 1), 2 * axy), ((1, -1), 2 * axy), ((-1, 1), 2 * axy), ((-1, -1), 2 * axy)]
    for i in range(1, nx):
        for j in range(1, ny):
            row = idx(i, j)
            for (di, dj), c in stencil:
                for k, cc in val(i + di, j + dj):
                    A[row, k] += c * cc
    w_in = spsolve(A.tocsr(), b)
    W = np.zeros((nx + 3, ny + 3))  # offset by 1 for ghosts
    def getw(i, j):
        return sum(w_in[k] * c for k, c in val(i, j))
    for i in range(-1, nx + 2):
        for j in range(-1, ny + 2):
            W[i + 1, j + 1] = getw(i, j)
    wxx = (W[2:, 1:-1] - 2 * W[1:-1, 1:-1] + W[:-2, 1:-1]) / hx**2
    wyy = (W[1:-1, 2:] - 2 * W[1:-1, 1:-1] + W[1:-1, :-2]) / hy**2
    Mx = -(wxx + nu * wyy)
    My = -(wyy + nu * wxx)
    return W[1:-1, 1:-1], Mx, My, nx, ny


def two_way(Lx, Ly, h, fc, fy, wD, wL, edges="SSSS", cover=20.0) -> Result:
    if Lx > Ly:
        raise InputError("خلي Lx الاتجاه القصير (Lx ≤ Ly)")
    if Ly / Lx > 2:
        r = one_way(Lx, h, fc, fy, wD, wL, cover, "ss")
        r.warnings.insert(0, "Ly/Lx > 2: البلاطة تعمل في اتجاه واحد، تم التصميم كبلاطة اتجاه واحد")
        return r
    r = Result("slab2", "Two-way slab design (elastic plate analysis, ACI 318-19)",
               inputs=dict(Lx=f"{fmt(Lx)} m", Ly=f"{fmt(Ly)} m", edges=f"{edges} (left,right,bottom,top: S=simple, F=continuous/fixed)",
                           fc=f"{fmt(fc)} MPa", fy=f"{fmt(fy)} MPa", wD=f"{fmt(wD)} kN/m²", wL=f"{fmt(wL)} kN/m²"))
    nF = edges.upper().count("F")
    if not h:
        perim = 2 * (Lx + Ly) * 1000
        h = max(90, math.ceil(perim / (180 if nF >= 2 else 160) / 10) * 10)
        r.add("Trial thickness", "h ≈ perimeter/180 (continuous) or /160", f"perimeter = {fmt(perim)} mm", f"h = {fmt(h)} mm")
    sw = 24 * h / 1000
    wu = max(1.2 * (wD + sw) + 1.6 * wL, 1.4 * (wD + sw))
    r.add("Factored load", "wu = 1.2(D + γc·h) + 1.6L", f"1.2×({fmt(wD)} + {fmt(sw)}) + 1.6×{fmt(wL)}", f"wu = {fmt(wu)} kN/m²")
    W, Mx, My, nx, ny = plate_fd(Lx, Ly, edges)
    ci, cj = nx // 2, ny // 2
    ax_pos = Mx[1:-1, 1:-1].max(); ay_pos = My[1:-1, 1:-1].max()
    neg = {}
    E = edges.upper()
    if E[0] == "F": neg["left"] = Mx[0, :].min()
    if E[1] == "F": neg["right"] = Mx[-1, :].min()
    if E[2] == "F": neg["bottom"] = My[:, 0].min()
    if E[3] == "F": neg["top"] = My[:, -1].min()
    r.add("Plate analysis", "D∇⁴w = q (finite differences, ν = 0.2) ; Mx = −D(wxx + ν·wyy)",
          f"grid {nx}×{ny}", f"αx+ = {fmt(ax_pos/Lx**2, 4)} , αy+ = {fmt(ay_pos/Lx**2, 4)} (M = α·wu·Lx²)")
    Mxp, Myp = ax_pos * wu, ay_pos * wu
    d_x = h - cover - 5
    d_y = d_x - 10
    outs = {}
    r.add("Positive moments", "M = α·wu·Lx²", "", f"Mx+ = {fmt(Mxp)} , My+ = {fmt(Myp)} kN·m/m")
    for name, M, d in (("short (x) bottom", Mxp, d_x), ("long (y) bottom", Myp, d_y)):
        As, Asmin = flexure_strip(M, h, d, fc, fy)
        db, s, prov = pick_spacing(max(As, Asmin), h)
        outs[name] = (db, s)
        r.add(f"Steel {name}", "As ≥ As,min ; s ≤ 2h", f"d = {fmt(d)} , As = {fmt(As)} , As,min = {fmt(Asmin)} mm²/m",
              f"Ø{db} @ {s} mm", "ACI 8.6.1 / 8.7.2.2")
    for side, m in neg.items():
        M = m * wu
        As, Asmin = flexure_strip(M, h, d_x, fc, fy)
        db, s, prov = pick_spacing(max(As, Asmin), h)
        outs[f"top at {side} edge"] = (db, s)
        r.add(f"Negative moment at {side} edge", "M− = α−·wu·Lx²", f"α− = {fmt(m/Lx**2, 4)}", f"M− = {fmt(M)} kN·m/m → Ø{db} @ {s} mm top")
    Ec = 4700 * math.sqrt(fc)
    D = Ec * 1e3 * (h / 1000)**3 / (12 * (1 - 0.04))
    wmax = W.max() * (1.0 * (wD + sw) + wL) / D * 1000 * 2.5  # ×2.5 cracking + long-term approx
    r.add("Deflection estimate (service, ×2.5 for cracking/long-term)", "δ = β·w·Lx⁴/D , D = Ec·h³/12(1−ν²)", "",
          f"δ ≈ {fmt(wmax, 2)} mm (limit ℓ/240 = {fmt(Lx*1000/240, 1)} mm) {'✔' if wmax <= Lx*1000/240 else '✘'}", "ACI Table 24.2.2")
    if wmax > Lx * 1000 / 240:
        r.warnings.append("الترخيم التقريبي أكبر من ℓ/240: زد السماكة")
    r.outputs = dict(h=h, wu=wu, Mx=Mxp, My=Myp, neg={k: v * wu for k, v in neg.items()}, bars=outs, Lx=Lx, Ly=Ly,
                     edges=edges, kind="two", Mgrid=(Mx * wu, My * wu))
    return r


def punching(c1, c2, h, d, fc, Vu, position="interior", Mu=0.0) -> Result:
    alpha = {"interior": 40, "edge": 30, "corner": 20}
    if position not in alpha:
        raise InputError("position = interior / edge / corner")
    r = Result("punch", "Two-way (punching) shear check (ACI 318-19)",
               inputs=dict(c1=f"{fmt(c1)} mm", c2=f"{fmt(c2)} mm", h=f"{fmt(h)} mm", d=f"{fmt(d)} mm", fc=f"{fmt(fc)} MPa",
                           Vu=f"{fmt(Vu)} kN", position=position))
    if position == "interior":
        bo = 2 * (c1 + d) + 2 * (c2 + d)
    elif position == "edge":
        bo = 2 * (c1 + d / 2) + (c2 + d)
    else:
        bo = (c1 + d / 2) + (c2 + d / 2)
    r.add("Critical perimeter at d/2", "bo", "", f"bo = {fmt(bo)} mm", "ACI 22.6.4")
    beta = max(c1, c2) / min(c1, c2)
    lam_s = min(1.0, math.sqrt(2 / (1 + 0.004 * d)))
    v1 = 0.33 * lam_s * math.sqrt(fc)
    v2 = 0.17 * (1 + 2 / beta) * lam_s * math.sqrt(fc)
    v3 = 0.083 * (2 + alpha[position] * d / bo) * lam_s * math.sqrt(fc)
    vc = min(v1, v2, v3)
    r.add("Concrete punching stress", "vc = min(0.33λs√f'c , 0.17(1+2/β)λs√f'c , 0.083(2+αs·d/bo)λs√f'c)",
          f"β = {fmt(beta)} , αs = {alpha[position]} , λs = {fmt(lam_s)}", f"vc = min({fmt(v1)}, {fmt(v2)}, {fmt(v3)}) = {fmt(vc)} MPa", "ACI 22.6.5.2")
    vu = Vu * 1e3 / (bo * d)
    ok = vu <= 0.75 * vc
    r.add("Check", "vu = Vu/(bo·d) ≤ φvc", f"vu = {fmt(Vu)}×1000/({fmt(bo)}×{fmt(d)})",
          f"vu = {fmt(vu)} MPa {'≤' if ok else '>'} φvc = {fmt(0.75*vc)} MPa {'✔' if ok else '✘'}")
    if not ok:
        dreq = d
        while True:
            dreq += 5
            bo2 = bo + (8 if position == "interior" else 4 if position == "edge" else 2) * (dreq - d) / 2
            vc2 = min(0.33, 0.17 * (1 + 2 / beta), 0.083 * (2 + alpha[position] * dreq / bo2)) * math.sqrt(fc) * min(1, math.sqrt(2 / (1 + 0.004 * dreq)))
            if Vu * 1e3 / (bo2 * dreq) <= 0.75 * vc2 or dreq > 3 * d:
                break
        r.warnings.append(f"القص الثاقب غير محقق. d المطلوب تقريباً {fmt(dreq)} mm أو استخدم drop panel / حديد قص")
    r.outputs = dict(bo=bo, vc=vc, vu=vu, ok=ok)
    return r
