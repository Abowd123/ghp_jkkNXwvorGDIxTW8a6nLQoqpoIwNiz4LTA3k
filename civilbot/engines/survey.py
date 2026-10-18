"""Surveying: traverse adjustment (Bowditch), levelling (rise & fall), horizontal and vertical curves, earthwork."""
from __future__ import annotations
import math
import numpy as np
from ..core import Result, InputError, fmt


def dms(deg):
    s = "-" if deg < 0 else ""
    deg = abs(deg)
    d = int(deg); m = int((deg - d) * 60); sec = (deg - d - m / 60) * 3600
    if sec >= 59.995:
        sec = 0; m += 1
    if m == 60:
        m = 0; d += 1
    return f"{s}{d}°{m:02d}'{sec:05.2f}\""


def parse_angle(s: str) -> float:
    s = s.strip()
    if "-" in s[1:] or "d" in s.lower():
        parts = [float(p) for p in s.lower().replace("d", "-").replace("m", "-").replace("s", "").split("-") if p]
        parts += [0] * (3 - len(parts))
        return parts[0] + parts[1] / 60 + parts[2] / 3600
    return float(s)


def traverse(az, dist, E0=1000.0, N0=1000.0, closed=True) -> Result:
    if len(az) != len(dist) or len(az) < 3:
        raise InputError("عدد الاتجاهات لازم يساوي عدد الأطوال (3 خطوط على الأقل)")
    r = Result("traverse", "Closed traverse adjustment (Bowditch / compass rule)",
               inputs=dict(azimuths=", ".join(dms(a) for a in az), distances=", ".join(fmt(d) for d in dist) + " m", start=f"E {fmt(E0)} , N {fmt(N0)}"))
    dE = [d * math.sin(math.radians(a)) for a, d in zip(az, dist)]
    dN = [d * math.cos(math.radians(a)) for a, d in zip(az, dist)]
    eE, eN = sum(dE), sum(dN)
    P = sum(dist)
    lin = math.hypot(eE, eN)
    r.add("Latitudes & departures", "ΔE = L·sin(Az) ; ΔN = L·cos(Az)", "\n".join(f"{k+1}: ΔE = {fmt(a, 3)} , ΔN = {fmt(b, 3)}" for k, (a, b) in enumerate(zip(dE, dN))), "")
    r.add("Misclosure", "eE = ΣΔE ; eN = ΣΔN ; e = √(eE² + eN²)", f"eE = {fmt(eE, 4)} m , eN = {fmt(eN, 4)} m",
          f"e = {fmt(lin, 4)} m → precision 1 : {fmt(P / lin, 0) if lin > 0 else '∞'}")
    cE = [-eE * d / P for d in dist]
    cN = [-eN * d / P for d in dist]
    E, N = [E0], [N0]
    for a, b, c1, c2 in zip(dE, dN, cE, cN):
        E.append(E[-1] + a + c1); N.append(N[-1] + b + c2)
    r.add("Bowditch corrections", "cE = −eE·L/ΣL ; cN = −eN·L/ΣL", "", "")
    r.add("Adjusted coordinates", "", "\n".join(f"P{k+1}: E = {fmt(e, 3)} , N = {fmt(n, 3)}" for k, (e, n) in enumerate(zip(E[:-1], N[:-1]))), "")
    area = 0.5 * abs(sum(E[k] * N[k + 1] - E[k + 1] * N[k] for k in range(len(E) - 1)))
    r.add("Enclosed area (coordinates method)", "A = ½|Σ(Ei·Ni+1 − Ei+1·Ni)|", "", f"A = {fmt(area, 2)} m² = {fmt(area / 10000, 4)} ha")
    if lin > 0 and P / lin < 5000:
        r.warnings.append("دقة الإغلاق أقل من 1:5000 (غير مقبولة لأغلب الأعمال)")
    r.outputs = dict(E=E, N=N, eE=eE, eN=eN, prec=P / lin if lin else float("inf"), area=area)
    return r


def levelling(readings, rl0) -> Result:
    """readings: list of (BS, IS, FS) with None for empty; rise & fall method."""
    r = Result("level", "Levelling book (rise & fall)", inputs=dict(BM=f"{fmt(rl0)} m", stations=len(readings)))
    rows = []
    prev = None
    RL = rl0
    sum_bs = sum_fs = rise = fall = 0.0
    rls = [rl0]
    for k, (bs, is_, fs) in enumerate(readings):
        cur = fs if fs is not None else is_
        if prev is not None and cur is not None:
            d = prev - cur
            if d >= 0:
                rise += d
            else:
                fall -= d
            RL += d
            rls.append(RL)
        rows.append(f"{k+1}: BS {fmt(bs) if bs is not None else '-'} | IS {fmt(is_) if is_ is not None else '-'} | FS {fmt(fs) if fs is not None else '-'} → RL {fmt(RL, 3)}")
        if bs is not None:
            sum_bs += bs; prev = bs
        else:
            prev = cur
        if fs is not None:
            sum_fs += fs
    r.add("Reduced levels", "\n".join(rows))
    r.add("Arithmetic check", "ΣBS − ΣFS = ΣRise − ΣFall = Last RL − First RL",
          f"{fmt(sum_bs - sum_fs, 4)} = {fmt(rise - fall, 4)} = {fmt(RL - rl0, 4)}", "✔ OK" if abs((sum_bs - sum_fs) - (rise - fall)) < 1e-6 else "✘")
    r.outputs = dict(RL=rls, last=RL)
    return r


def h_curve(R, delta, pi_ch, chord=20.0) -> Result:
    if R <= 0 or not 0 < delta < 180:
        raise InputError("R موجب و 0 < Δ < 180°")
    d = math.radians(delta)
    T = R * math.tan(d / 2); L = R * d; E = R * (1 / math.cos(d / 2) - 1); M = R * (1 - math.cos(d / 2)); LC = 2 * R * math.sin(d / 2)
    pc = pi_ch - T; pt = pc + L
    r = Result("hcurve", "Simple horizontal curve", inputs=dict(R=f"{fmt(R)} m", Δ=dms(delta), PI=f"{fmt(pi_ch)} m", chord=f"{fmt(chord)} m"))
    r.add("Curve elements", "T = R·tan(Δ/2) ; L = R·Δ ; E = R(sec(Δ/2) − 1) ; M = R(1 − cos(Δ/2)) ; LC = 2R·sin(Δ/2)", "",
          f"T = {fmt(T, 3)} , L = {fmt(L, 3)} , E = {fmt(E, 3)} , M = {fmt(M, 3)} , LC = {fmt(LC, 3)} m")
    r.add("Chainages", "PC = PI − T ; PT = PC + L", "", f"PC = {fmt(pc, 3)} , PT = {fmt(pt, 3)}")
    Dd = 1145.916 / R * (chord / 20)
    r.add("Degree of curve (arc, per 20 m)", "D = 1145.92/R", "", f"D = {dms(1145.916 / R)}")
    first = math.ceil(pc / chord) * chord
    stations = [pc] + [s for s in np.arange(first, pt, chord) if s > pc + 1e-6] + [pt]
    rows, cum = [], 0.0
    table = []
    for k in range(1, len(stations)):
        arc = stations[k] - stations[k - 1]
        defl = math.degrees(arc / (2 * R))
        cum += defl
        c = 2 * R * math.sin(math.radians(defl))
        table.append((stations[k], arc, c, cum))
        rows.append(f"{fmt(stations[k], 3)}: arc {fmt(arc, 3)} , chord {fmt(c, 3)} , total deflection {dms(cum)}")
    r.add("Setting-out table (deflection angles from PC)", "δ = arc/(2R) (rad)", "\n".join(rows), f"check: final deflection = Δ/2 = {dms(delta / 2)}")
    r.outputs = dict(R=R, delta=delta, T=T, L=L, E=E, M=M, PC=pc, PT=pt, table=table)
    return r


def v_curve(g1, g2, L, pvi_ch, pvi_el, step=20.0) -> Result:
    r = Result("vcurve", "Symmetrical parabolic vertical curve", inputs=dict(g1=f"{fmt(g1)} %", g2=f"{fmt(g2)} %", L=f"{fmt(L)} m", PVI=f"ch {fmt(pvi_ch)} , el {fmt(pvi_el)}"))
    A = g2 - g1
    K = L / abs(A) if A else float("inf")
    bvc = pvi_ch - L / 2; evc = pvi_ch + L / 2
    bel = pvi_el - g1 / 100 * L / 2
    a = A / (200 * L)
    r.add("Curve parameters", "A = g2 − g1 ; K = L/|A| ; y = (g1/100)x + (A/200L)x²", "",
          f"A = {fmt(A)} % ({'crest' if A < 0 else 'sag'}) , K = {fmt(K, 2)} , BVC ch {fmt(bvc)} el {fmt(bel, 3)} , EVC ch {fmt(evc)}")
    xs = sorted(set([0.0, L] + [s - bvc for s in np.arange(math.ceil(bvc / step) * step, evc, step)]))
    rows, tbl = [], []
    for x in xs:
        el = bel + g1 / 100 * x + a * x * x
        tbl.append((bvc + x, el)); rows.append(f"ch {fmt(bvc + x, 2)}: el {fmt(el, 3)}")
    r.add("Elevations along curve", "", "\n".join(rows), "")
    if g1 * g2 < 0:
        xh = -g1 * L / A
        elh = bel + g1 / 100 * xh + a * xh * xh
        r.add("High/low point", "x = −g1·L/A", "", f"ch {fmt(bvc + xh, 3)} , el {fmt(elh, 3)}")
    r.outputs = dict(table=tbl, K=K, A=A, bvc=bvc, evc=evc, pvi=(pvi_ch, pvi_el), g1=g1, g2=g2, L=L, bel=bel)
    return r


def earthwork(stations, areas) -> Result:
    """Cross-section areas (+ cut, − fill) at stations -> volumes (average end area) and mass haul."""
    if len(stations) != len(areas) or len(stations) < 2:
        raise InputError("عدد المحطات لازم يساوي عدد المساحات (2 على الأقل)")
    r = Result("earth", "Earthwork volumes (average end area) & mass haul", inputs=dict(stations=", ".join(map(fmt, stations)), areas=", ".join(map(fmt, areas)) + " m² (+cut / −fill)"))
    cut = fill = 0.0
    mass = [0.0]
    rows = []
    for k in range(1, len(stations)):
        L = stations[k] - stations[k - 1]
        a1, a2 = areas[k - 1], areas[k]
        if a1 * a2 >= 0:
            v = (a1 + a2) / 2 * L
        else:  # transition: split at zero
            x0 = L * abs(a1) / (abs(a1) + abs(a2))
            v = a1 / 2 * x0 + a2 / 2 * (L - x0)
            vc = (max(a1, 0) / 2 * x0 + max(a2, 0) / 2 * (L - x0)); vf = (min(a1, 0) / 2 * x0 + min(a2, 0) / 2 * (L - x0))
            cut += vc; fill -= vf; mass.append(mass[-1] + v); rows.append(f"{fmt(stations[k-1])}–{fmt(stations[k])}: cut {fmt(vc, 1)} , fill {fmt(-vf, 1)} m³ (transition)")
            continue
        if v >= 0:
            cut += v
        else:
            fill -= v
        mass.append(mass[-1] + v)
        rows.append(f"{fmt(stations[k-1])}–{fmt(stations[k])}: {'cut' if v >= 0 else 'fill'} {fmt(abs(v), 1)} m³")
    r.add("Volumes between stations", "V = (A1 + A2)/2 · L", "\n".join(rows), "")
    r.add("Totals", "", "", f"cut = {fmt(cut, 1)} m³ , fill = {fmt(fill, 1)} m³ , net = {fmt(cut - fill, 1)} m³ ({'surplus' if cut > fill else 'borrow needed'})")
    r.outputs = dict(stations=stations, areas=areas, mass=mass, cut=cut, fill=fill)
    return r
