"""Isolated spread footing design (ACI 318-19) with optional uniaxial moment."""
from __future__ import annotations
import math
from ..core import Result, InputError, fmt
from .slab import flexure_strip
from .rc_beam import AREA


def design(PD, PL, qa, c1, c2, fc, fy, M=0.0, Df=1.5, gamma_s=18.0, ratio=1.0, cover=75.0, db=None) -> Result:
    """PD, PL service kN; qa allowable gross kPa; c1 (along L, moment direction), c2 mm; Df m."""
    if qa <= 0 or PD <= 0:
        raise InputError("qa و PD لازم يكونوا موجبين")
    r = Result("footing", "Isolated footing design (ACI 318-19)",
               inputs=dict(PD=f"{fmt(PD)} kN", PL=f"{fmt(PL)} kN", M=f"{fmt(M)} kN·m (service)", qa=f"{fmt(qa)} kPa (gross allowable)",
                           column=f"{fmt(c1)}×{fmt(c2)} mm", Df=f"{fmt(Df)} m", fc=f"{fmt(fc)} MPa", fy=f"{fmt(fy)} MPa"))
    P = PD + PL
    h = 500.0
    for _ in range(30):
        qnet = qa - (24 * h / 1000 + gamma_s * (Df - h / 1000))
        if qnet <= 0:
            raise InputError("qa صغير جداً مقارنة بوزن التربة فوق القاعدة")
        e = abs(M) / P
        # find L (moment dir) s.t. qmax <= qnet
        A = P / qnet
        L = math.sqrt(A * ratio)
        for _ in range(200):
            B = L / ratio
            qmax = P / (B * L) * (1 + 6 * e / L) if e <= L / 6 else 2 * P / (3 * B * (L / 2 - e))
            if qmax <= qnet * 1.0001:
                break
            L += 0.05
        L = math.ceil(L * 20) / 20
        B = math.ceil(L / ratio * 20) / 20
        Pu = max(1.2 * PD + 1.6 * PL, 1.4 * PD)
        Mu = abs(M) * Pu / P
        qu = Pu / (B * L)
        eu = Mu / Pu
        qu_max = qu * (1 + 6 * eu / L)
        dbb = db or 16
        d = h - cover - dbb
        # punching (use average qu)
        bo = 2 * (c1 + d) + 2 * (c2 + d)
        Vp = Pu - qu * (c1 + d) * (c2 + d) / 1e6
        beta = max(c1, c2) / min(c1, c2)
        lam_s = 1.0  # footings: λs = 1 per ACI 22.6.5.2 note (d ≥ 250 mm uses size effect only for slabs w/o min steel)
        vc = min(0.33, 0.17 * (1 + 2 / beta), 0.083 * (2 + 40 * d / bo)) * math.sqrt(fc) * lam_s
        ok_p = Vp * 1e3 <= 0.75 * vc * bo * d
        # one-way shear at d from face, long direction, with qu_max
        x = (L * 1000 - c1) / 2 - d
        V1 = qu_max * B * max(x, 0) / 1000
        phiVc1 = 0.75 * 0.17 * math.sqrt(fc) * B * 1000 * d / 1e3
        ok_1 = V1 <= phiVc1
        if ok_p and ok_1:
            break
        h += 50
    r.add("Net allowable pressure", "qnet = qa − γc·h − γs·(Df − h)", f"{fmt(qa)} − 24×{fmt(h/1000)} − {fmt(gamma_s)}×{fmt(Df - h/1000)}", f"qnet = {fmt(qnet)} kPa")
    r.add("Footing size (service loads)", "qmax = P/A·(1 + 6e/L) ≤ qnet", f"P = {fmt(P)} kN , e = {fmt(e, 3)} m",
          f"L × B = {fmt(L)} × {fmt(B)} m , qmax = {fmt(P/(B*L)*(1+6*e/L) if e <= L/6 else 2*P/(3*B*(L/2-e)))} kPa")
    if e > L / 6:
        r.warnings.append("e > L/6: جزء من القاعدة لا يلامس التربة (توزيع مثلثي)")
    r.add("Factored loads", "Pu = 1.2PD + 1.6PL ; qu = Pu/A", f"Pu = {fmt(Pu)} kN", f"qu = {fmt(qu)} kPa , qu,max = {fmt(qu_max)} kPa", "ACI 5.3.1")
    r.add("Thickness by punching shear", "Vu = Pu − qu(c1+d)(c2+d) ≤ φ·vc·bo·d",
          f"h = {fmt(h)} mm , d = {fmt(d)} mm , bo = {fmt(bo)} mm", f"Vu = {fmt(Vp)} kN ≤ φVc = {fmt(0.75*vc*bo*d/1e3)} kN {'✔' if ok_p else '✘'}", "ACI 22.6.5.2")
    r.add("One-way shear at d from column face", "Vu = qu,max·B·x ≤ φ0.17√f'c·B·d", f"x = {fmt(x)} mm",
          f"Vu = {fmt(V1)} kN ≤ φVc = {fmt(phiVc1)} kN {'✔' if ok_1 else '✘'}", "ACI 22.5.5.1")
    bars = {}
    for name, span, width, cc in (("long (L)", L, B, c1), ("short (B)", B, L, c2)):
        arm = (span * 1000 - cc) / 2 / 1000
        q_use = qu_max if name.startswith("long") else qu
        Mface = q_use * width * arm**2 / 2
        dd = d if name.startswith("long") else d - dbb
        As, Asmin = flexure_strip(Mface / width, h, dd, fc, fy)
        As_tot = max(As, Asmin) * width
        for dia in ([db] if db else [12, 14, 16, 18, 20, 22, 25]):
            n = math.ceil(As_tot / AREA[dia])
            s = (width * 1000 - 2 * cover - dia) / (n - 1) if n > 1 else 0
            if s >= 125 and s <= min(3 * h, 450):
                break
        n = max(n, math.ceil((width * 1000 - 2 * cover) / min(3 * h, 450)) + 1)
        s = (width * 1000 - 2 * cover - dia) / (n - 1)
        bars[name] = (n, dia, s)
        r.add(f"Moment at column face, {name} direction", "Mu = qu·B·ℓ²/2 , ℓ = (L − c)/2", f"ℓ = {fmt(arm, 3)} m , d = {fmt(dd)} mm",
              f"Mu = {fmt(Mface)} kN·m → As = {fmt(As_tot)} mm² → {n}Ø{dia} @ {fmt(s, 0)} mm", "ACI 13.2.7.1")
    # bearing on concrete
    A1 = c1 * c2
    phiBn = 0.65 * 0.85 * fc * A1 * 2 / 1e3
    r.add("Bearing at column base", "φBn = φ·0.85f'c·A1·√(A2/A1) ≤ 2", "", f"φBn = {fmt(phiBn)} kN ≥ Pu = {fmt(Pu)} kN {'✔' if phiBn >= Pu else '✘ (dowels needed)'}", "ACI 22.8.3")
    ld = max(fy / (1.1 * math.sqrt(fc)) * 1.0 / 2.5 * dbb, 300)
    avail = (min(L * 1000 - c1, B * 1000 - c2)) / 2 - cover
    r.add("Development length check (straight bars)", "ℓd = fy·ψ/(1.1λ√f'c)·db/((cb+Ktr)/db)", f"ℓd ≈ {fmt(ld, 0)} mm",
          f"available = {fmt(avail, 0)} mm {'✔' if avail >= ld else '✘ use hooks'}", "ACI 25.4.2.4")
    r.outputs = dict(L=L, B=B, h=h, d=d, c1=c1, c2=c2, Df=Df, bars=bars, cover=cover, qu=qu, Pu=Pu)
    return r
