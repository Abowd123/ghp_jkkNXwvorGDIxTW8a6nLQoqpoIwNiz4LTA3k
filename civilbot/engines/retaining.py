"""Cantilever retaining wall: stability (overturning, sliding, bearing) + stem/base steel."""
from __future__ import annotations
import math
from ..core import Result, InputError, fmt
from .slab import flexure_strip, pick_spacing


def design(H, phi, gamma=18.0, q=0.0, qa=200.0, mu=None, fc=28, fy=420, B=None, toe=None, t_base=None,
           t_top=0.25, t_bot=None, Dp=0.0, gamma_c=24.0) -> Result:
    """H: total height from bottom of base to top of backfill (m). phi in degrees."""
    if not 1.5 <= H <= 12:
        raise InputError("ارتفاع الجدار لازم بين 1.5 و 12 m للجدار الكابولي")
    if not 15 <= phi <= 45:
        raise InputError("زاوية الاحتكاك φ لازم بين 15° و 45°")
    r = Result("wall", "Cantilever retaining wall design",
               inputs=dict(H=f"{fmt(H)} m", phi=f"{fmt(phi)}°", gamma=f"{fmt(gamma)} kN/m³", q=f"{fmt(q)} kPa surcharge",
                           qa=f"{fmt(qa)} kPa", fc=f"{fmt(fc)} MPa", fy=f"{fmt(fy)} MPa"))
    mu = mu or math.tan(math.radians(2 * phi / 3))
    Ka = (1 - math.sin(math.radians(phi))) / (1 + math.sin(math.radians(phi)))
    Kp = 1 / Ka
    tb = t_base or max(0.3, math.ceil(H / 10 * 20) / 20)
    ts = t_bot or max(0.3, math.ceil(H / 12 * 20) / 20)
    auto = B is None
    B = B or math.ceil(0.5 * H * 10) / 10
    for it in range(80):
        toe_ = toe if toe is not None else round(B / 3, 2)
        heel = B - toe_ - ts
        if heel <= 0:
            raise InputError("عرض القاعدة صغير: الكعب (heel) سالب")
        hs = H - tb
        Pa = 0.5 * Ka * gamma * H**2
        Pq = Ka * q * H
        Mo = Pa * H / 3 + Pq * H / 2
        # weights (per m) and arms from toe
        W = []
        W.append(("stem (rect)", t_top * hs * gamma_c, toe_ + ts - t_top / 2))
        W.append(("stem (taper)", 0.5 * (ts - t_top) * hs * gamma_c, toe_ + (ts - t_top) * 2 / 3))
        W.append(("base", B * tb * gamma_c, B / 2))
        W.append(("soil on heel", heel * hs * gamma, B - heel / 2))
        if q:
            W.append(("surcharge on heel", heel * q, B - heel / 2))
        Wsum = sum(w for _, w, _ in W)
        Mr = sum(w * x for _, w, x in W)
        Pp = 0.5 * Kp * gamma * Dp**2 if Dp else 0.0
        FSo = Mr / Mo
        FSs = (mu * Wsum + Pp) / (Pa + Pq)
        xr = (Mr - Mo) / Wsum
        e = B / 2 - xr
        qmax = Wsum / B * (1 + 6 * e / B) if abs(e) <= B / 6 else 2 * Wsum / (3 * xr)
        qmin = Wsum / B * (1 - 6 * e / B) if abs(e) <= B / 6 else 0
        ok_nosl = FSo >= 2.0 and qmax <= qa and abs(e) <= B / 6
        ok = ok_nosl and (FSs >= 1.5 or B >= 0.7 * H)
        if ok or not auto:
            break
        B = round(B + 0.1, 2)
    r.add("Active earth pressure coefficient (Rankine)", "Ka = (1 − sinφ)/(1 + sinφ)", f"φ = {fmt(phi)}°", f"Ka = {fmt(Ka, 4)}")
    r.add("Proportions", "B ≈ 0.5–0.7H , toe ≈ B/3 , base ≈ H/10 , stem ≈ H/12", "",
          f"B = {fmt(B)} m , toe = {fmt(toe_)} m , heel = {fmt(heel)} m , base t = {fmt(tb)} m , stem = {fmt(t_top)}→{fmt(ts)} m")
    r.add("Lateral thrust", "Pa = ½Ka·γ·H² ; Pq = Ka·q·H", f"½×{fmt(Ka,4)}×{fmt(gamma)}×{fmt(H)}²", f"Pa = {fmt(Pa)} kN/m , Pq = {fmt(Pq)} kN/m")
    r.add("Overturning moment about toe", "Mo = Pa·H/3 + Pq·H/2", "", f"Mo = {fmt(Mo)} kN·m/m")
    r.add("Resisting forces", "ΣW and Mr = ΣW·x (about toe)", "; ".join(f"{n}: {fmt(w)} kN @ {fmt(x)} m" for n, w, x in W),
          f"ΣW = {fmt(Wsum)} kN/m , Mr = {fmt(Mr)} kN·m/m")
    r.add("Factor of safety against overturning", "FSo = Mr/Mo ≥ 2.0", "", f"FSo = {fmt(FSo)} {'✔' if FSo >= 2 else '✘'}")
    r.add("Factor of safety against sliding", "FSs = (μ·ΣW + Pp)/(Pa + Pq) ≥ 1.5", f"μ = {fmt(mu, 3)}" + (f" , Pp = {fmt(Pp)}" if Pp else ""),
          f"FSs = {fmt(FSs)} {'✔' if FSs >= 1.5 else '✘ (add shear key)'}")
    r.add("Bearing pressure", "e = B/2 − (Mr − Mo)/ΣW ; q = ΣW/B(1 ± 6e/B)", f"e = {fmt(e, 3)} m (B/6 = {fmt(B/6, 3)})",
          f"qmax = {fmt(qmax)} kPa , qmin = {fmt(qmin)} kPa {'✔' if qmax <= qa else '✘'} (qa = {fmt(qa)})")
    key = None
    if FSs < 1.5:
        Pp_req = 1.5 * (Pa + Pq) - mu * Wsum
        Dk = math.sqrt(2 * Pp_req / (Kp * gamma))  # passive depth needed in front of key (from base top level)
        key_depth = max(0.3, math.ceil((Dk - tb) * 20) / 20)
        key = key_depth
        r.add("Shear key (sliding)", "Pp,req = 1.5(Pa+Pq) − μΣW ; Pp = ½Kp·γ·D²", f"Pp,req = {fmt(Pp_req)} kN/m , Kp = {fmt(Kp, 3)}",
              f"key depth below base ≈ {fmt(key_depth)} m (width = stem thickness)")
        FSs = 1.5
    for cond, msg in ((FSo < 2, "الانقلاب غير محقق"), (key is not None, "تم إضافة Shear key لتحقيق الانزلاق"),
                      (qmax > qa, "ضغط التربة أكبر من المسموح"), (abs(e) > B / 6, "e > B/6")):
        if cond:
            r.warnings.append(msg)
    # stem design at base of stem (factored 1.6 lateral earth)
    Mu = 1.6 * (Ka * gamma * hs**3 / 6 + Ka * q * hs**2 / 2)
    Vu = 1.6 * (Ka * gamma * hs**2 / 2 + Ka * q * hs)
    h_mm = ts * 1000
    d = h_mm - 50 - 8
    As, Asmin = flexure_strip(Mu, h_mm, d, fc, fy)
    As_use = max(As, 0.0012 * 1000 * h_mm)
    db, s, _ = pick_spacing(As_use, h_mm / 1.5 if h_mm > 300 else h_mm)
    phiVc = 0.75 * 0.17 * math.sqrt(fc) * 1000 * d / 1e3
    r.add("Stem: moment & shear at base", "Mu = 1.6(Ka·γ·h³/6 + Ka·q·h²/2)", f"h = {fmt(hs)} m , d = {fmt(d)} mm",
          f"Mu = {fmt(Mu)} kN·m/m , Vu = {fmt(Vu)} kN/m (φVc = {fmt(phiVc)}) {'✔' if phiVc >= Vu else '✘'}", "ACI 11.5 / 22.5")
    r.add("Stem vertical steel (soil face)", "As ≥ 0.0012·b·h (ACI 11.6.1)", f"As = {fmt(As)} mm²/m", f"Ø{db} @ {s} mm", "ACI 11.6")
    # heel design: downward soil+surcharge+self − upward pressure (conservative: ignore upward)
    wh = 1.2 * (hs * gamma + tb * gamma_c) + 1.6 * q
    Mh = wh * heel**2 / 2
    dh = tb * 1000 - 75 - 8
    Ash, Asminh = flexure_strip(Mh, tb * 1000, dh, fc, fy)
    dbh, sh, _ = pick_spacing(max(Ash, Asminh), tb * 1000)
    r.add("Heel (top steel)", "Mu = wu·heel²/2 (upward pressure ignored)", f"wu = {fmt(wh)} kN/m²", f"Mu = {fmt(Mh)} → Ø{dbh} @ {sh} mm top")
    qtoe = 1.6 * qmax
    Mt = qtoe * toe_**2 / 2 - 1.2 * tb * gamma_c * toe_**2 / 2
    Ast, Asmint = flexure_strip(max(Mt, 1), tb * 1000, dh, fc, fy)
    dbt, st, _ = pick_spacing(max(Ast, Asmint), tb * 1000)
    r.add("Toe (bottom steel)", "Mu = 1.6·qmax·toe²/2 − 1.2·self·toe²/2", "", f"Mu = {fmt(Mt)} → Ø{dbt} @ {st} mm bottom")
    r.outputs = dict(H=H, B=B, toe=toe_, heel=heel, tb=tb, t_top=t_top, ts=ts, FSo=FSo, FSs=FSs, qmax=qmax, qmin=qmin,
                     key=key, stem=(db, s), heel_bar=(dbh, sh), toe_bar=(dbt, st), Ka=Ka, gamma=gamma, q=q)
    return r
