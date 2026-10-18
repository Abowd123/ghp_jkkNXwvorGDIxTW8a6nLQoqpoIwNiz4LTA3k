"""Tied rectangular RC column design per ACI 318-19 (SI).

Strain-compatibility P–M interaction about the strong axis (bending about the
axis parallel to b; h = depth in bending direction), slenderness via the
non-sway moment-magnifier method, and automatic bar selection.
"""
from __future__ import annotations
import math
import numpy as np
from ..core import Result, InputError, fmt
from .rc_beam import beta1, AREA

ES, ECU = 200000.0, 0.003


def layout(n, b, h, cover, dt, db):
    """Bar coordinates (y measured from top / compression face along h)."""
    if n < 4 or n % 2:
        raise InputError("عدد الأسياخ لازم يكون زوجي و ≥ 4")
    per = 2 * (b + h)
    # bars on the two faces perpendicular to h (top & bottom) vs side faces
    nt = max(2, round((n / 2) * b / (b + h)) + 1)
    nt = min(nt, n // 2)
    ns = (n - 2 * nt) // 2  # intermediate per side
    if 2 * nt + 2 * ns != n:
        nt += 1; ns = (n - 2 * nt) // 2
    e = cover + dt + db / 2
    xs_t = np.linspace(e, b - e, nt)
    ys = [e] * nt + [h - e] * nt
    xs = list(xs_t) * 2
    if ns > 0:
        yi = np.linspace(e, h - e, ns + 2)[1:-1]
        for y in yi:
            ys += [y, y]; xs += [e, b - e]
    clear_t = (xs_t[1] - xs_t[0] - db) if nt > 1 else 1e9
    clear_s = ((h - 2 * e) / (ns + 1) - db) if True else 1e9
    return np.array(xs), np.array(ys), nt, ns, min(clear_t, clear_s)


def interaction(b, h, fc, fy, ys, Ab, npts=120):
    """Return arrays (Pn, Mn, phi) — kN, kN·m — for c from large to small."""
    b1 = beta1(fc)
    Ag = b * h
    Ast = Ab * len(ys)
    P0 = (0.85 * fc * (Ag - Ast) + fy * Ast) / 1e3
    dt = ys.max()
    out = []
    cs = np.concatenate([np.geomspace(5 * h, h, 20), np.linspace(h, 0.02 * h, npts)])
    for c in cs:
        a = min(b1 * c, h)
        Cc = 0.85 * fc * a * b
        P = Cc
        M = Cc * (h / 2 - a / 2)
        for y in ys:
            eps = ECU * (c - y) / c
            fs = max(-fy, min(fy, ES * eps))
            if y < a:
                fs -= 0.85 * fc  # displaced concrete
            F = fs * Ab
            P += F
            M += F * (h / 2 - y)
        eps_t = ECU * (dt - c) / c
        ey = fy / ES
        phi = 0.65 if eps_t <= ey else (0.9 if eps_t >= ey + 0.003 else 0.65 + 0.25 * (eps_t - ey) / 0.003)
        out.append((P / 1e3, M / 1e6, phi, c, eps_t))
    # pure tension point
    out.append((-fy * Ast / 1e3, 0.0, 0.9, 0, 1))
    arr = np.array(out)
    return arr, P0


def phiMn_at(arr, P0, Pu):
    Pn, Mn, phi = arr[:, 0], arr[:, 1], arr[:, 2]
    phiP, phiM = phi * Pn, phi * Mn
    phiP_max = 0.8 * 0.65 * P0
    # curve from compression to tension: phiP decreasing (mostly)
    best = None
    for k in range(len(phiP) - 1):
        p1, p2 = phiP[k], phiP[k + 1]
        if (p1 - Pu) * (p2 - Pu) <= 0 and p1 != p2:
            t = (Pu - p1) / (p2 - p1)
            m = phiM[k] + t * (phiM[k + 1] - phiM[k])
            best = m if best is None else max(best, m)
    return best or 0.0, phiP_max


def design(b, h, fc, fy, Pu, Mu, cover=40.0, dt=10.0, lu=None, k=1.0, M1M2=1.0, beta_dns=0.6,
           n=None, db=None) -> Result:
    if min(b, h) < 200:
        raise InputError("أقل بعد للعمود 200 mm")
    if Pu < 0:
        raise InputError("Pu لازم يكون ضغط موجب")
    r = Result("rc_column", "RC tied column design (ACI 318-19)",
               inputs=dict(b=f"{fmt(b)} mm", h=f"{fmt(h)} mm (bending direction)", fc=f"{fmt(fc)} MPa", fy=f"{fmt(fy)} MPa",
                           Pu=f"{fmt(Pu)} kN", Mu=f"{fmt(Mu)} kN·m", cover=f"{fmt(cover)} mm",
                           lu=f"{fmt(lu)} m" if lu else "-", k=fmt(k)))
    Ag = b * h
    Mu = abs(Mu)
    Mmin = Pu * (15 + 0.03 * h) / 1e3
    r.add("Minimum moment (accidental eccentricity)", "M2,min = Pu(15 + 0.03h)", f"{fmt(Pu)}×(15 + 0.03×{fmt(h)})/1000",
          f"{fmt(Mmin)} kN·m", "ACI 6.6.4.5.4")
    Mc = max(Mu, Mmin)
    if lu:
        rg = 0.3 * h
        slr = k * lu * 1000 / rg
        lim = min(40.0, 34 + 12 * M1M2) if M1M2 <= 0 else min(40.0, 34 - 12 * M1M2)
        r.add("Slenderness ratio (non-sway)", "kℓu/r ≤ 34 − 12(M1/M2) ≤ 40 ; r = 0.3h",
              f"{fmt(k)}×{fmt(lu*1000)}/{fmt(rg)} = {fmt(slr, 2)} , limit = {fmt(lim, 2)}",
              "Short column" if slr <= lim else "Slender → magnify moments", "ACI 6.2.5.1")
        if slr > 100:
            raise InputError("نسبة النحافة > 100: غير مسموح بالطريقة المبسطة. كبّر المقطع")
        if slr > lim:
            Ec = 4700 * math.sqrt(fc)
            Ig = b * h**3 / 12
            EI = 0.4 * Ec * Ig / (1 + beta_dns)
            Pc = math.pi**2 * EI / (k * lu * 1000)**2 / 1e3
            Cm = 0.6 + 0.4 * M1M2
            if Pu >= 0.75 * Pc:
                raise InputError(f"Pu ≥ 0.75Pc ({fmt(0.75*Pc)} kN): العمود سيتعرض للانبعاج. كبّر المقطع")
            delta = max(1.0, Cm / (1 - Pu / (0.75 * Pc)))
            Mc = delta * max(Mu, Mmin)
            r.add("Critical buckling load", "EIeff = 0.4EcIg/(1+βdns) ; Pc = π²EIeff/(kℓu)²",
                  f"Ec = {fmt(Ec)} MPa , EIeff = {fmt(EI/1e9)} kN·m²", f"Pc = {fmt(Pc)} kN", "ACI 6.6.4.4")
            r.add("Moment magnification", "Cm = 0.6 + 0.4M1/M2 ; δ = Cm/(1 − Pu/0.75Pc) ≥ 1",
                  f"Cm = {fmt(Cm)}", f"δ = {fmt(delta)} → Mc = {fmt(Mc)} kN·m", "ACI 6.6.4.5")
    r.add("Design moment", "Mc = max(Mu, M2,min)·δ", "", f"Mc = {fmt(Mc)} kN·m")
    # choose bars
    cands = []
    sizes = [db] if db else [16, 18, 20, 22, 25, 28, 32]
    counts = [n] if n else list(range(4, 41, 2))
    for d_ in sizes:
        for n_ in counts:
            Ast = n_ * AREA[d_]
            rho = Ast / Ag
            if rho < 0.01 - 1e-9 and not n:
                continue
            if rho > 0.08:
                break
            try:
                xs, ys, nt, ns, clear = layout(n_, b, h, cover, dt, d_)
            except InputError:
                continue
            if clear < max(40, 1.5 * d_):
                continue
            arr, P0 = interaction(b, h, fc, fy, ys, AREA[d_])
            pm, pmax = phiMn_at(arr, P0, Pu)
            if Pu <= pmax and pm >= Mc:
                cands.append((Ast, n_, d_, arr, P0, pm, pmax, xs, ys, rho, nt, ns))
                break
    if not cands:
        raise InputError("ما في تسليح يحقق المطلوب ضمن 8%. كبّر مقطع العمود أو المقاومة fc")
    cands.sort(key=lambda c: c[0])
    Ast, n_, d_, arr, P0, pm, pmax, xs, ys, rho, nt, ns = cands[0]
    r.add("Axial capacity (pure compression)", "P0 = 0.85f'c(Ag − Ast) + fy·Ast ; φPn,max = 0.80·0.65·P0",
          f"Ag = {fmt(Ag)} mm² , Ast = {fmt(Ast)} mm²", f"P0 = {fmt(P0)} kN , φPn,max = {fmt(pmax)} kN ≥ Pu = {fmt(Pu)} kN",
          "ACI 22.4.2 / Table 22.4.2.1")
    r.add("Interaction diagram (strain compatibility, εcu = 0.003)", "Pn = 0.85f'c·a·b + ΣAs·fs ; Mn = Σ forces × arm about centroid",
          f"{len(arr)} points, φ varies 0.65 → 0.90 with εt", f"at Pu = {fmt(Pu)} kN: φMn = {fmt(pm)} kN·m ≥ Mc = {fmt(Mc)} kN·m",
          "ACI 22.2 / 21.2.2")
    r.add("Selected longitudinal steel", "1% ≤ ρg ≤ 8%", f"ρg = {fmt(rho*100, 3)} %",
          f"{n_}Ø{d_} ({nt} bars per face × 2 + {ns} intermediate per side)", "ACI 10.6.1.1")
    tie = 10 if d_ <= 32 else 12
    s_tie = min(16 * d_, 48 * tie, min(b, h))
    s_tie = math.floor(s_tie / 25) * 25
    r.add("Ties", "s ≤ min(16Ø_bar, 48Ø_tie, least dimension)", f"min({16*d_}, {48*tie}, {fmt(min(b,h))})",
          f"Ø{tie} @ {s_tie} mm", "ACI 25.7.2")
    util = max(Mc / pm if pm else 9, Pu / pmax)
    r.outputs = dict(n=n_, db=d_, Ast=Ast, rho=rho, xs=xs, ys=ys, b=b, h=h, cover=cover, tie=tie, s_tie=s_tie,
                     curve=arr, P0=P0, Pu=Pu, Mc=Mc, phiMn=pm, phiPmax=pmax, util=util)
    return r
