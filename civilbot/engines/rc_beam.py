"""Reinforced-concrete rectangular beam design per ACI 318-19 (SI units).

Flexure (singly / doubly reinforced) + shear (stirrups) + bar selection.
Inputs: b, h [mm], cover [mm] (clear to stirrup), fc, fy, fyt [MPa], Mu [kN.m], Vu [kN].
"""
from __future__ import annotations
import math
from ..core import Result, InputError, fmt

BARS = [10, 12, 14, 16, 18, 20, 22, 25, 28, 32]
AREA = {d: math.pi * d * d / 4 for d in BARS}
AGG = 20.0  # max aggregate size, mm


def beta1(fc):
    if fc <= 28:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc - 28) / 7)


def _fits(n, db, b, cover, ds):
    if n < 2:
        return False
    clear = (b - 2 * cover - 2 * ds - n * db) / (n - 1)
    return clear >= max(25.0, db, 4 / 3 * AGG)


def select_bars(As_req, b, cover, ds, min_n=2):
    """Pick bar size & count (single layer if possible, else two layers)."""
    best = None
    for layers in (1, 2):
        for db in BARS[1:]:
            n = max(min_n, math.ceil(As_req / AREA[db]))
            per_layer = math.ceil(n / layers)
            if not _fits(per_layer, db, b, cover, ds):
                continue
            prov = n * AREA[db]
            cand = (prov, layers, db, n)
            if best is None or (cand[1], cand[0]) < (best[1], best[0]):
                best = cand
        if best:
            break
    if not best:
        return None
    prov, layers, db, n = best
    return {"n": n, "db": db, "As": prov, "layers": layers}


def _flexure(r, b, h, d, dp, fc, fy, Mu, cover, ds):
    r.add("Effective depth (to centroid of tension steel)", "d = h − cover − Ø_stirrup − Ø_bar/2 (− layer offset)",
          f"h = {fmt(h)} , cover = {fmt(cover)} , Ø_stirrup = {fmt(ds)}", f"d = {fmt(d)} mm")
    b1 = beta1(fc)
    r.add("Stress block factor β₁", "β₁ = 0.85 − 0.05(f'c − 28)/7 , 0.65 ≤ β₁ ≤ 0.85",
          f"f'c = {fmt(fc)} MPa", f"β₁ = {fmt(b1)}", "ACI 22.2.2.4.3")
    Mu_n = Mu * 1e6
    phi = 0.9
    Rn = Mu_n / (phi * b * d * d)
    r.add("Required strength coefficient (assume φ = 0.9)", "Rn = Mu / (φ·b·d²)",
          f"Rn = {fmt(Mu)}×10⁶ / (0.9×{fmt(b)}×{fmt(d)}²)", f"{fmt(Rn)} MPa")
    rho_min = max(0.25 * math.sqrt(fc) / fy, 1.4 / fy)
    rho_tc = 0.85 * b1 * fc / fy * (0.003 / (0.003 + 0.005))
    r.add("Minimum steel ratio", "ρmin = max(0.25√f'c / fy , 1.4/fy)", f"max({fmt(0.25*math.sqrt(fc)/fy,5)} , {fmt(1.4/fy,5)})",
          f"ρmin = {fmt(rho_min, 5)}", "ACI 9.6.1.2")
    r.add("Max ratio for tension-controlled section (εt = 0.005)", "ρtc = 0.85β₁(f'c/fy)·(0.003/0.008)",
          f"0.85×{fmt(b1)}×({fmt(fc)}/{fmt(fy)})×0.375", f"ρtc = {fmt(rho_tc, 5)}", "ACI 21.2.2")
    disc = 1 - 2 * Rn / (0.85 * fc)
    doubly = False
    As_comp = 0.0
    if disc > 0:
        rho = 0.85 * fc / fy * (1 - math.sqrt(disc))
        r.add("Required steel ratio", "ρ = (0.85f'c/fy)·[1 − √(1 − 2Rn/(0.85f'c))]",
              f"(0.85×{fmt(fc)}/{fmt(fy)})·[1 − √(1 − 2×{fmt(Rn)}/(0.85×{fmt(fc)}))]", f"ρ = {fmt(rho, 5)}")
    else:
        rho = float("inf")
    if rho <= rho_tc:
        if rho < rho_min:
            r.warnings.append("ρ المطلوب أقل من الحد الأدنى، تم استخدام ρmin")
        rho_use = max(rho, rho_min)
        As_req = rho_use * b * d
        r.add("Required tension steel", "As = ρ·b·d", f"{fmt(rho_use,5)}×{fmt(b)}×{fmt(d)}", f"As = {fmt(As_req)} mm²")
    else:
        doubly = True
        r.warnings.append("القطاع يحتاج تسليح ضغط (Doubly reinforced). يفضل زيادة العمق إذا أمكن")
        As1 = rho_tc * b * d
        a1 = As1 * fy / (0.85 * fc * b)
        Mn1 = As1 * fy * (d - a1 / 2)
        c1 = a1 / b1
        Mn2 = Mu_n / phi - Mn1
        fsp = min(fy, 600 * (c1 - dp) / c1)
        if fsp <= 0:
            raise InputError("القطاع صغير جداً لهذا العزم. زد الارتفاع h")
        As_comp = Mn2 / ((fsp - 0.85 * fc) * (d - dp))
        As_req = As1 + As_comp * fsp / fy
        r.add("Part 1: singly reinforced at ρtc", "As1 = ρtc·b·d ; Mn1 = As1·fy·(d − a/2)",
              f"As1 = {fmt(As1)} mm², a = {fmt(a1)} mm", f"Mn1 = {fmt(Mn1/1e6)} kN·m")
        r.add("Part 2: remaining moment by compression steel", "Mn2 = Mu/φ − Mn1 ; f's = 600(c − d')/c ≤ fy",
              f"Mn2 = {fmt(Mn2/1e6)} kN·m , c = {fmt(c1)} mm , d' = {fmt(dp)} mm", f"f's = {fmt(fsp)} MPa")
        r.add("Compression & total tension steel", "A's = Mn2/((f's − 0.85f'c)(d − d')) ; As = As1 + A's·f's/fy",
              "", f"A's = {fmt(As_comp)} mm² , As = {fmt(As_req)} mm²")
    sel = select_bars(As_req, b, cover, ds)
    if not sel:
        raise InputError("ما قدرت أرتب الحديد داخل عرض الكمرة حتى على طبقتين. زد العرض b")
    d_act = h - cover - ds - sel["db"] / 2 - (0 if sel["layers"] == 1 else (sel["db"] / 2 + 12.5))
    r.add("Bar selection", "n = ⌈As / A_bar⌉ with clear spacing ≥ max(25, Ø, 4/3·dagg)",
          f"use {sel['n']}Ø{sel['db']} in {sel['layers']} layer(s)", f"As,prov = {fmt(sel['As'])} mm²", "ACI 25.2.1")
    comp = None
    if doubly:
        # keep the section tension-controlled with the *provided* tension steel
        c_tc = 0.375 * d
        fsp_tc = min(fy, 600 * (c_tc - dp) / c_tc)
        As_comp = max(As_comp, (sel["As"] * fy - 0.85 * fc * b * b1 * c_tc) / (fsp_tc - 0.85 * fc))
        comp = select_bars(As_comp, b, cover, ds)
        if comp:
            r.add("Compression bars", "A's ≥ (As,prov·fy − 0.85f'c·b·β₁·c_tc)/(f's − 0.85f'c)", "",
                  f"use {comp['n']}Ø{comp['db']} top , A's,prov = {fmt(comp['As'])} mm²")
    hangers = comp or {"n": 2, "db": 12, "As": 2 * AREA[12], "layers": 1}

    return sel, hangers, doubly, As_req, As_comp, b1, rho_min, rho_tc


def design(b, h, fc, fy, Mu, Vu=0.0, cover=40.0, ds=10.0, fyt=None, d_prime=None, lam=1.0) -> Result:
    fyt = fyt or fy
    for name, v in dict(b=b, h=h, fc=fc, fy=fy).items():
        if v is None or v <= 0:
            raise InputError(f"القيمة {name} لازم تكون موجبة")
    if not 17 <= fc <= 100:
        raise InputError("مقاومة الخرسانة fc خارج المدى المنطقي (17–100 MPa)")
    if not 240 <= fy <= 550:
        raise InputError("إجهاد خضوع الحديد fy خارج المدى المنطقي (240–550 MPa)")
    if h <= b / 4 or h > 3000 or b < 150:
        raise InputError("أبعاد الكمرة غير منطقية (b ≥ 150 mm)")
    Mu, Vu = abs(Mu), abs(Vu)
    r = Result("rc_beam", "RC rectangular beam design (ACI 318-19)",
               inputs=dict(b=f"{fmt(b)} mm", h=f"{fmt(h)} mm", cover=f"{fmt(cover)} mm", fc=f"{fmt(fc)} MPa",
                           fy=f"{fmt(fy)} MPa", fyt=f"{fmt(fyt)} MPa", Mu=f"{fmt(Mu)} kN·m", Vu=f"{fmt(Vu)} kN"))
    base_steps = list(r.steps)
    d = h - cover - ds - 10.0
    dp = d_prime or (cover + ds + 8)
    for _it in range(4):
        r.steps = list(base_steps)
        r.warnings = []
        sel, hangers, doubly, As_req, As_comp, b1, rho_min, rho_tc = _flexure(r, b, h, d, dp, fc, fy, Mu, cover, ds)
        d_act = h - cover - ds - sel["db"] / 2 - (0 if sel["layers"] == 1 else (sel["db"] / 2 + 12.5))
        if abs(d_act - d) < 1.0:
            break
        d = d_act
    d = d_act
    Mu_n = Mu * 1e6
    # verify capacity with provided steel
    As = sel["As"]
    if doubly:
        Asp = hangers["As"]
        # iterate c with strain compatibility
        lo, hi = 1.0, h
        for _ in range(100):
            c = (lo + hi) / 2
            fsp = max(min(600 * (c - dp) / c, fy), -fy)
            Cc = 0.85 * fc * b1 * c * b
            Cs = Asp * (fsp - 0.85 * fc if fsp > 0 else fsp)
            T = As * fy
            if Cc + Cs > T:
                hi = c
            else:
                lo = c
        a = b1 * c
        Mn = (0.85 * fc * a * b * (d_act - a / 2) + Cs * (d_act - dp))
    else:
        a = As * fy / (0.85 * fc * b)
        c = a / b1
        Mn = As * fy * (d_act - a / 2)
    eps_t = 0.003 * (d_act - c) / c
    phi_act = 0.65 if eps_t <= fy / 200000 else (0.9 if eps_t >= 0.005 else
                                                   0.65 + 0.25 * (eps_t - fy / 200000) / (0.005 - fy / 200000))
    phiMn = phi_act * Mn / 1e6
    r.add("Capacity check with provided steel", "a = As·fy/(0.85f'c·b) ; c = a/β₁ ; εt = 0.003(d − c)/c",
          f"d = {fmt(d_act)} mm , a = {fmt(a)} mm , c = {fmt(c)} mm", f"εt = {fmt(eps_t,5)} → φ = {fmt(phi_act)}", "ACI 21.2.2")
    r.add("Design flexural strength", "φMn = φ·As·fy·(d − a/2)", "", f"φMn = {fmt(phiMn)} kN·m  {'≥' if phiMn >= Mu else '<'} Mu = {fmt(Mu)} kN·m",
          "ACI 9.5.1.1")
    if phiMn < Mu * 0.999:
        r.warnings.append("السعة أقل من المطلوب بعد اختيار الحديد. زد عدد الأسياخ أو العمق")
    if eps_t < 0.004:
        r.warnings.append("εt < 0.004: القطاع غير مسموح به للكمرات حسب ACI 9.3.3.1")
    # ---------- shear ----------
    sh = {}
    if Vu > 0:
        Av = 2 * AREA[int(ds)] if int(ds) in AREA else 2 * math.pi * ds * ds / 4
        Vc = 0.17 * lam * math.sqrt(fc) * b * d_act / 1e3
        phiv = 0.75
        r.add("Concrete shear strength", "Vc = 0.17λ√f'c·b·d", f"0.17×{fmt(lam)}×√{fmt(fc)}×{fmt(b)}×{fmt(d_act)}/1000",
              f"Vc = {fmt(Vc)} kN , φVc = {fmt(phiv*Vc)} kN", "ACI 22.5.5.1")
        s_max = min(d_act / 2, 600)
        avs_min = max(0.062 * math.sqrt(fc) * b / fyt, 0.35 * b / fyt)
        s_min_req = Av / avs_min
        if Vu <= 0.5 * phiv * Vc:
            s = None
            note = "Vu ≤ 0.5φVc → stirrups not required by strength (use nominal stirrups)"
            s = min(s_max, s_min_req)
        else:
            Vs = max(Vu / phiv - Vc, 0.0)
            Vs_lim = 0.66 * math.sqrt(fc) * b * d_act / 1e3
            if Vs > Vs_lim:
                raise InputError(f"القص كبير جداً: Vs = {fmt(Vs)} kN > 0.66√f'c·b·d = {fmt(Vs_lim)} kN. كبّر القطاع")
            if Vs > 0.33 * math.sqrt(fc) * b * d_act / 1e3:
                s_max = min(d_act / 4, 300)
            s_req = Av * fyt * d_act / (Vs * 1e3) if Vs > 0 else float("inf")
            s = min(s_req, s_max, s_min_req)
            note = f"Vs = Vu/φ − Vc = {fmt(Vs)} kN ; s = Av·fyt·d/Vs = {fmt(s_req)} mm"
            r.add("Required steel shear strength", "Vs = Vu/φ − Vc ≤ 0.66√f'c·b·d", f"{fmt(Vu)}/0.75 − {fmt(Vc)}", f"Vs = {fmt(Vs)} kN", "ACI 22.5.1.2")
        s_use = max(75, math.floor(s / 25) * 25)
        r.add("Stirrup spacing", "s ≤ min(Av·fyt·d/Vs , smax , Av/(Av/s)min)",
              f"{note} ; smax = {fmt(s_max)} mm ; s(Av,min) = {fmt(s_min_req)} mm",
              f"Use Ø{int(ds)} @ {s_use} mm (2 legs)", "ACI 9.7.6.2 / 9.6.3")
        sh = dict(Vc=Vc, phiVc=phiv * Vc, s=s_use, Av=Av)
    r.outputs = dict(d=d_act, As_req=As_req, bars=sel, top_bars=hangers, doubly=doubly, As_comp=As_comp,
                     a=a, c=c, eps_t=eps_t, phi=phi_act, phiMn=phiMn, rho_min=rho_min, rho_tc=rho_tc,
                     stirrup_d=ds, stirrup_s=sh.get("s"), shear=sh, b=b, h=h, cover=cover)
    return r
