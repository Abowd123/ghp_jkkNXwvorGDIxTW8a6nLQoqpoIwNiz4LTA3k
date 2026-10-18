"""Structural steel per AISC 360-16 (LRFD): beams (F2/F3 + G2), columns (E3), beam-columns (H1),
bolted single-plate shear connection (J3/J4) and column base plate (DG1). SI units (mm, N, MPa).
Section properties are computed from plate dimensions (fillets ignored → slightly conservative)."""
from __future__ import annotations
import math
from ..core import Result, InputError, fmt

E = 200000.0
G_ = 77200.0
# h, b, tw, tf (mm)
LIB = {}
for k, v in {100: (100, 55, 4.1, 5.7), 120: (120, 64, 4.4, 6.3), 140: (140, 73, 4.7, 6.9), 160: (160, 82, 5.0, 7.4), 180: (180, 91, 5.3, 8.0),
             200: (200, 100, 5.6, 8.5), 220: (220, 110, 5.9, 9.2), 240: (240, 120, 6.2, 9.8), 270: (270, 135, 6.6, 10.2), 300: (300, 150, 7.1, 10.7),
             330: (330, 160, 7.5, 11.5), 360: (360, 170, 8.0, 12.7), 400: (400, 180, 8.6, 13.5), 450: (450, 190, 9.4, 14.6), 500: (500, 200, 10.2, 16.0),
             550: (550, 210, 11.1, 17.2), 600: (600, 220, 12.0, 19.0)}.items():
    LIB[f"IPE{k}"] = v
for k, v in {100: (96, 100, 5.0, 8.0), 120: (114, 120, 5.0, 8.0), 140: (133, 140, 5.5, 8.5), 160: (152, 160, 6.0, 9.0), 180: (171, 180, 6.0, 9.5),
             200: (190, 200, 6.5, 10.0), 220: (210, 220, 7.0, 11.0), 240: (230, 240, 7.5, 12.0), 260: (250, 260, 7.5, 12.5), 280: (270, 280, 8.0, 13.0),
             300: (290, 300, 8.5, 14.0)}.items():
    LIB[f"HEA{k}"] = v
for k, v in {100: (100, 100, 6.0, 10.0), 120: (120, 120, 6.5, 11.0), 140: (140, 140, 7.0, 12.0), 160: (160, 160, 8.0, 13.0), 180: (180, 180, 8.5, 14.0),
             200: (200, 200, 9.0, 15.0), 220: (220, 220, 9.5, 16.0), 240: (240, 240, 10.0, 17.0), 260: (260, 260, 10.0, 17.5), 280: (280, 280, 10.5, 18.0),
             300: (300, 300, 11.0, 19.0)}.items():
    LIB[f"HEB{k}"] = v


RADII = {"IPE": {100: 7, 120: 7, 140: 7, 160: 9, 180: 9, 200: 12, 220: 12, 240: 15, 270: 15, 300: 15, 330: 18, 360: 18, 400: 21,
                  450: 21, 500: 21, 550: 24, 600: 24},
         "HE": {100: 12, 120: 12, 140: 12, 160: 15, 180: 15, 200: 18, 220: 18, 240: 21, 260: 24, 280: 24, 300: 27}}


def props(h, b, tw, tf, r=0.0):
    hw = h - 2 * tf
    af = (1 - math.pi / 4) * r * r          # one root fillet
    yf = h / 2 - tf - 0.2234 * r            # its centroid from the x-axis
    A = 2 * b * tf + hw * tw + 4 * af
    Ix = (b * h**3 - (b - tw) * hw**3) / 12 + 4 * af * yf**2
    Iy = (2 * tf * b**3 + hw * tw**3) / 12 + 4 * af * (tw / 2 + 0.2234 * r) ** 2
    Sx, Sy = Ix / (h / 2), Iy / (b / 2)
    Zx = b * tf * (h - tf) + tw * hw**2 / 4 + 4 * af * yf
    Zy = tf * b**2 / 2 + hw * tw**2 / 4 + 4 * af * (tw / 2 + 0.2234 * r)
    J = (2 * b * tf**3 + (h - tf) * tw**3) / 3
    ho = h - tf
    Cw = Iy * ho**2 / 4
    rts = math.sqrt(math.sqrt(Iy * Cw) / Sx)
    return dict(h=h, b=b, tw=tw, tf=tf, hw=hw, A=A, Ix=Ix, Iy=Iy, Sx=Sx, Sy=Sy, Zx=Zx, Zy=Zy, rx=math.sqrt(Ix / A), ry=math.sqrt(Iy / A),
                J=J, Cw=Cw, ho=ho, rts=rts, mass=A * 7850e-6)


def section(name=None, h=None, b=None, tw=None, tf=None):
    if name:
        key = name.upper().replace(" ", "")
        if key not in LIB:
            raise InputError(f"مقطع غير موجود: {name}. المتاح IPE100–600 / HEA100–300 / HEB100–300 أو أدخل h b tw tf")
        fam = "IPE" if key.startswith("IPE") else "HE"
        return key, props(*LIB[key], r=RADII[fam][int(key[3:])])
    if None in (h, b, tw, tf):
        raise InputError("أدخل اسم المقطع (مثل IPE300) أو أبعاده h b tw tf")
    return f"I {fmt(h)}×{fmt(b)}×{fmt(tw)}×{fmt(tf)}", props(h, b, tw, tf)


def _flexure(p, Fy, Lb, Cb):
    lam_f = p["b"] / (2 * p["tf"])
    lam_w = p["hw"] / p["tw"]
    lpf, lrf = 0.38 * math.sqrt(E / Fy), 1.0 * math.sqrt(E / Fy)
    lpw = 3.76 * math.sqrt(E / Fy)
    Mp = Fy * p["Zx"]
    Lp = 1.76 * p["ry"] * math.sqrt(E / Fy)
    c = 1.0
    jc = p["J"] * c / (p["Sx"] * p["ho"])
    Lr = 1.95 * p["rts"] * E / (0.7 * Fy) * math.sqrt(jc + math.sqrt(jc**2 + 6.76 * (0.7 * Fy / E) ** 2))
    if Lb <= Lp:
        Mn_ltb = Mp; zone = "Lb ≤ Lp → yielding"
    elif Lb <= Lr:
        Mn_ltb = min(Mp, Cb * (Mp - (Mp - 0.7 * Fy * p["Sx"]) * (Lb - Lp) / (Lr - Lp))); zone = "Lp < Lb ≤ Lr → inelastic LTB"
    else:
        Fcr = Cb * math.pi**2 * E / (Lb / p["rts"]) ** 2 * math.sqrt(1 + 0.078 * jc * (Lb / p["rts"]) ** 2)
        Mn_ltb = min(Mp, Fcr * p["Sx"]); zone = "Lb > Lr → elastic LTB"
    if lam_f <= lpf:
        Mn_flb = Mp; fl = "compact flange"
    elif lam_f <= lrf:
        Mn_flb = Mp - (Mp - 0.7 * Fy * p["Sx"]) * (lam_f - lpf) / (lrf - lpf); fl = "non-compact flange (F3)"
    else:
        kc = min(0.76, max(0.35, 4 / math.sqrt(lam_w)))
        Mn_flb = 0.9 * E * kc * p["Sx"] / lam_f**2; fl = "slender flange (F3)"
    return dict(Mn=min(Mn_ltb, Mn_flb), Mp=Mp, Lp=Lp, Lr=Lr, zone=zone, flange=fl, lam_f=lam_f, lam_w=lam_w, lpf=lpf, lpw=lpw,
                web_ok=lam_w <= lpw)


def beam(Mu, Vu, Lb, Fy=355.0, Cb=1.0, name=None, dims=None, L=None, w_service=None, defl_lim=360, family="IPE") -> Result:
    """Mu kN·m, Vu kN, Lb m (unbraced), optional L m + w_service kN/m for deflection."""
    r = Result("steel_beam", "Steel beam design (AISC 360-16 LRFD)",
               inputs=dict(Mu=f"{fmt(Mu)} kN·m", Vu=f"{fmt(Vu)} kN", Lb=f"{fmt(Lb)} m", Fy=f"{fmt(Fy)} MPa", Cb=fmt(Cb),
                           deflection=f"L = {fmt(L)} m , w = {fmt(w_service)} kN/m , L/{defl_lim}" if L and w_service else "-"))
    cands = [name] if name or dims else [k for k in LIB if k.startswith(family.upper())]
    chosen = None
    for nm in cands:
        key, p = section(nm, *(dims or (None,) * 4)) if not dims else section(None, *dims)
        f = _flexure(p, Fy, Lb * 1000, Cb)
        phiMn = 0.9 * f["Mn"] / 1e6
        Aw = p["h"] * p["tw"]
        Cv1 = 1.0 if p["hw"] / p["tw"] <= 2.24 * math.sqrt(E / Fy) else 0.9
        phiv = 1.0 if Cv1 == 1.0 else 0.9
        phiVn = phiv * 0.6 * Fy * Aw * Cv1 / 1e3
        dmax = None
        if L and w_service:
            dmax = 5 * w_service * (L * 1000) ** 4 / (384 * E * p["Ix"])
        ok = phiMn >= Mu and phiVn >= Vu and (dmax is None or dmax <= L * 1000 / defl_lim)
        chosen = (key, p, f, phiMn, phiVn, dmax, Cv1)
        if ok or name or dims:
            break
    else:
        raise InputError("ما في مقطع في المكتبة يحقق المطلوب. جرب HEB أو قلل Lb")
    key, p, f, phiMn, phiVn, dmax, Cv1 = chosen
    r.inputs["section"] = key
    r.add("Section (computed from plates)", "A, Ix, Zx, Sx, ry, J, Cw", f"{key}: h = {fmt(p['h'])} , b = {fmt(p['b'])} , tw = {fmt(p['tw'])} , tf = {fmt(p['tf'])}",
          f"A = {fmt(p['A'], 0)} mm² , Ix = {fmt(p['Ix']/1e6, 2)}×10⁶ mm⁴ , Zx = {fmt(p['Zx']/1e3, 1)}×10³ mm³ , {fmt(p['mass'], 1)} kg/m")
    r.add("Local buckling classification", "λf = bf/2tf ≤ 0.38√(E/Fy) ; λw = h/tw ≤ 3.76√(E/Fy)",
          f"λf = {fmt(f['lam_f'], 2)} (λp = {fmt(f['lpf'], 2)}) , λw = {fmt(f['lam_w'], 2)} (λp = {fmt(f['lpw'], 2)})",
          f"{f['flange']} , web {'compact' if f['web_ok'] else 'non-compact ⚠'}", "AISC Table B4.1b")
    r.add("Limiting unbraced lengths", "Lp = 1.76ry√(E/Fy) ; Lr = 1.95rts(E/0.7Fy)√(Jc/Sxho + √((Jc/Sxho)² + 6.76(0.7Fy/E)²))",
          "", f"Lp = {fmt(f['Lp']/1000, 3)} m , Lr = {fmt(f['Lr']/1000, 3)} m → {f['zone']}", "AISC F2-5, F2-6")
    r.add("Flexural strength", "φMn = 0.9·Mn ≤ 0.9·Fy·Zx", f"Mp = {fmt(f['Mp']/1e6, 2)} kN·m", f"φMn = {fmt(phiMn, 2)} kN·m {'≥' if phiMn >= Mu else '<'} Mu = {fmt(Mu)} ✔" if phiMn >= Mu else f"φMn = {fmt(phiMn, 2)} < Mu ✘", "AISC F2 / F3")
    r.add("Shear strength", "φVn = φ·0.6Fy·Aw·Cv1", f"Aw = h·tw = {fmt(p['h']*p['tw'], 0)} mm² , Cv1 = {fmt(Cv1)}", f"φVn = {fmt(phiVn, 2)} kN {'≥' if phiVn >= Vu else '<'} Vu = {fmt(Vu)}", "AISC G2.1")
    if dmax is not None:
        r.add("Service deflection", "δ = 5wL⁴/384EI", "", f"δ = {fmt(dmax, 2)} mm vs L/{defl_lim} = {fmt(L*1000/defl_lim, 2)} mm {'✔' if dmax <= L*1000/defl_lim else '✘'}")
    for cond, msg in ((phiMn < Mu, "مقاومة الانحناء غير كافية"), (phiVn < Vu, "مقاومة القص غير كافية"),
                      (dmax is not None and dmax > L * 1000 / defl_lim, "الترخيم أكبر من المسموح")):
        if cond:
            r.warnings.append(msg)
    r.outputs = dict(section=key, p=p, phiMn=phiMn, phiVn=phiVn, util=max(Mu / phiMn, Vu / phiVn))
    return r


def column(Pu, KL, Fy=355.0, Mux=0.0, Lb=None, name=None, dims=None, KLx=None, family="HEB", Cb=1.0) -> Result:
    """Pu kN, KL (weak axis effective length) m."""
    r = Result("steel_col", "Steel column / beam-column (AISC 360-16 LRFD)",
               inputs=dict(Pu=f"{fmt(Pu)} kN", KLy=f"{fmt(KL)} m", KLx=f"{fmt(KLx or KL)} m", Mux=f"{fmt(Mux)} kN·m", Fy=f"{fmt(Fy)} MPa"))
    cands = [name] if name or dims else [k for k in LIB if k.startswith(family.upper())]
    res = None
    for nm in cands:
        key, p = section(None, *dims) if dims else section(nm)
        sl_y = KL * 1000 / p["ry"]; sl_x = (KLx or KL) * 1000 / p["rx"]
        sl = max(sl_x, sl_y)
        Fe = math.pi**2 * E / sl**2
        Fcr = 0.658 ** (Fy / Fe) * Fy if sl <= 4.71 * math.sqrt(E / Fy) else 0.877 * Fe
        phiPn = 0.9 * Fcr * p["A"] / 1e3
        slender = p["b"] / (2 * p["tf"]) > 0.56 * math.sqrt(E / Fy) or p["hw"] / p["tw"] > 1.49 * math.sqrt(E / Fy)
        ratio = None
        if Mux:
            f = _flexure(p, Fy, (Lb or KL) * 1000, Cb)
            phiMn = 0.9 * f["Mn"] / 1e6
            pr = Pu / phiPn
            ratio = pr + 8 / 9 * Mux / phiMn if pr >= 0.2 else pr / 2 + Mux / phiMn
        ok = sl <= 200 and (ratio <= 1.0 if ratio is not None else phiPn >= Pu)
        res = (key, p, sl_x, sl_y, Fe, Fcr, phiPn, slender, ratio, (phiMn if Mux else None))
        if ok or name or dims:
            break
    else:
        raise InputError("ما في مقطع يحقق المطلوب. جرب family=HEB أو قلل الطول")
    key, p, sl_x, sl_y, Fe, Fcr, phiPn, slender, ratio, phiMn = res
    r.inputs["section"] = key
    r.add("Section", "", f"{key}", f"A = {fmt(p['A'], 0)} mm² , rx = {fmt(p['rx'], 1)} , ry = {fmt(p['ry'], 1)} mm , {fmt(p['mass'], 1)} kg/m")
    r.add("Slenderness", "KL/r ≤ 200", f"KLx/rx = {fmt(sl_x, 1)} , KLy/ry = {fmt(sl_y, 1)}", f"governing KL/r = {fmt(max(sl_x, sl_y), 1)}", "AISC E2")
    r.add("Critical stress (flexural buckling)", "Fe = π²E/(KL/r)² ; Fcr = 0.658^(Fy/Fe)·Fy or 0.877Fe",
          f"Fe = {fmt(Fe, 1)} MPa , limit 4.71√(E/Fy) = {fmt(4.71 * math.sqrt(E / Fy), 1)}", f"Fcr = {fmt(Fcr, 1)} MPa", "AISC E3")
    r.add("Axial strength", "φPn = 0.9·Fcr·Ag", "", f"φPn = {fmt(phiPn, 1)} kN {'≥' if phiPn >= Pu else '<'} Pu = {fmt(Pu)}", "AISC E3-1")
    if slender:
        r.warnings.append("المقطع فيه عناصر نحيفة للضغط (AISC E7): المقاومة الفعلية أقل")
    if ratio is not None:
        r.add("Combined axial + flexure", "Pr/Pc ≥ 0.2: Pr/Pc + 8/9·Mr/Mc ≤ 1 ; else Pr/2Pc + Mr/Mc ≤ 1",
              f"Pr/Pc = {fmt(Pu/phiPn, 3)} , φMn = {fmt(phiMn, 1)} kN·m", f"interaction = {fmt(ratio, 3)} {'✔' if ratio <= 1 else '✘'}", "AISC H1-1")
    r.outputs = dict(section=key, p=p, phiPn=phiPn, ratio=ratio)
    return r


BOLT_FNV = {"A325N": 372, "A325X": 469, "A490N": 469, "A490X": 579, "8.8N": 372, "10.9N": 469}


def shear_tab(Vu, d=20, grade="A325N", tp=10, Fy=250, Fu=400, tw_beam=7.1, Fu_beam=490, weld=6, FEXX=490) -> Result:
    """Single-plate (shear tab) connection: one vertical row of bolts, standard holes, s = 3d, Le = 1.5d."""
    if grade.upper() not in BOLT_FNV:
        raise InputError(f"درجة البراغي: {', '.join(BOLT_FNV)}")
    Fnv = BOLT_FNV[grade.upper()]
    dh = d + (2 if d < 24 else 3)
    s = math.ceil(3 * d / 5) * 5
    Le = math.ceil(1.5 * d / 5) * 5
    Ab = math.pi * d * d / 4
    phi_rv = 0.75 * Fnv * Ab / 1e3
    r = Result("shear_tab", "Bolted single-plate shear connection (AISC 360-16 J3/J4)",
               inputs=dict(Vu=f"{fmt(Vu)} kN", bolts=f"M{d} {grade}", plate=f"t = {fmt(tp)} mm , Fy {fmt(Fy)} / Fu {fmt(Fu)} MPa",
                           beam_web=f"tw = {fmt(tw_beam)} mm , Fu = {fmt(Fu_beam)} MPa", weld=f"{fmt(weld)} mm E{int(FEXX/6.89)}"))

    def bearing(t, Fu_, n):
        lc_end = Le - dh / 2
        lc_in = s - dh
        rn_end = min(1.2 * lc_end * t * Fu_, 2.4 * d * t * Fu_)
        rn_in = min(1.2 * lc_in * t * Fu_, 2.4 * d * t * Fu_)
        return 0.75 * (rn_end + (n - 1) * rn_in) / 1e3
    def caps(n):
        Lp = 2 * Le + (n - 1) * s
        Rb_bolt = n * phi_rv
        Rb_p, Rb_w = bearing(tp, Fu, n), bearing(tw_beam, Fu_beam, n)
        Agv, Anv = Lp * tp, (Lp - n * dh) * tp
        phiY, phiR = 1.0 * 0.6 * Fy * Agv / 1e3, 0.75 * 0.6 * Fu * Anv / 1e3
        Lv = Lp - Le
        Anv_b, Agv_b, Ant = (Lv - (n - 0.5) * dh) * tp, Lv * tp, (Le - 0.5 * dh) * tp
        bs = 0.75 * min(0.6 * Fu * Anv_b + Fu * Ant, 0.6 * Fy * Agv_b + Fu * Ant) / 1e3
        wcap = 2 * 0.75 * 0.6 * FEXX * 0.707 * weld * Lp / 1e3
        return dict(Lp=Lp, bolt=Rb_bolt, bp=Rb_p, bw=Rb_w, yld=phiY, rup=phiR, bs=bs, weld=wcap)
    n = 2
    while True:
        c = caps(n)
        cap = min(v for k, v in c.items() if k != "Lp")
        if cap >= Vu or n >= 12:
            break
        n += 1
    Lp = c["Lp"]
    r.add("Geometry", "s = 3d ; Le = 1.5d ; standard hole dh = d + 2", f"s = {s} , Le = {Le} , dh = {dh} mm", f"n = {n} bolts , plate {fmt(Lp)} × {fmt(2*Le + 10)} × {fmt(tp)} mm")
    r.add("Bolt shear", "φRn = 0.75·Fnv·Ab per bolt", f"Fnv = {Fnv} MPa , Ab = {fmt(Ab, 1)} mm²", f"φRn = {fmt(phi_rv, 2)} kN/bolt → {fmt(c['bolt'], 1)} kN", "AISC J3.6")
    r.add("Bearing / tear-out (plate & beam web)", "φRn = 0.75·min(1.2·lc·t·Fu , 2.4·d·t·Fu)", "",
          f"plate: {fmt(c['bp'], 1)} kN , web: {fmt(c['bw'], 1)} kN", "AISC J3.10")
    r.add("Plate shear yielding & rupture", "φRn = 1.0·0.6Fy·Agv ; 0.75·0.6Fu·Anv", "", f"yield {fmt(c['yld'], 1)} kN , rupture {fmt(c['rup'], 1)} kN", "AISC J4.2")
    r.add("Block shear (plate)", "φRn = 0.75[0.6Fu·Anv + Ubs·Fu·Ant] ≤ 0.75[0.6Fy·Agv + Ubs·Fu·Ant]", "", f"φRn = {fmt(c['bs'], 1)} kN", "AISC J4.3")
    r.add("Fillet welds to support (both sides)", "φRn = 0.75·0.6FEXX·0.707w·L × 2", f"w = {weld} mm , L = {fmt(Lp)} mm", f"φRn = {fmt(c['weld'], 1)} kN", "AISC J2.4")
    r.add("Connection capacity", "min of all limit states", "", f"φRn = {fmt(cap, 1)} kN {'≥' if cap >= Vu else '<'} Vu = {fmt(Vu)} {'✔' if cap >= Vu else '✘'}")
    if cap < Vu:
        r.warnings.append("الوصلة غير كافية: زد سمك اللوح أو عدد البراغي")
    if tp > d / 2 + 2:
        r.warnings.append("سمك اللوح > d/2 + 2 mm: لا يحقق شرط المرونة للوصلة البسيطة (AISC Part 10)")
    r.outputs = dict(n=n, d=d, s=s, Le=Le, dh=dh, Lp=Lp, tp=tp, weld=weld, cap=cap, width=2 * Le + 10)
    return r


def base_plate(Pu, d, bf, fc=25.0, Fy=250.0, A2_A1=1.0) -> Result:
    """Concentrically loaded column base plate (AISC Design Guide 1)."""
    r = Result("base_plate", "Column base plate (AISC Design Guide 1, concentric)",
               inputs=dict(Pu=f"{fmt(Pu)} kN", column=f"d = {fmt(d)} , bf = {fmt(bf)} mm", fc=f"{fmt(fc)} MPa", Fy=f"{fmt(Fy)} MPa"))
    phi = 0.65
    k = min(math.sqrt(A2_A1), 2.0)
    A1 = Pu * 1e3 / (phi * 0.85 * fc * k)
    A1 = max(A1, (d + 100) * (bf + 100))
    delta = (0.95 * d - 0.8 * bf) / 2
    N = math.ceil((math.sqrt(A1) + delta) / 10) * 10
    N = max(N, d + 100)
    B = math.ceil(max(A1 / N, bf + 100) / 10) * 10
    r.add("Required area", "A1 = Pu/(φ·0.85f'c·√(A2/A1))", f"√(A2/A1) = {fmt(k)}", f"A1 ≥ {A1:,.0f} mm² → N × B = {fmt(N)} × {fmt(B)} mm", "AISC J8")
    m = (N - 0.95 * d) / 2
    n = (B - 0.8 * bf) / 2
    X = 4 * d * bf / (d + bf) ** 2 * Pu * 1e3 / (phi * 0.85 * fc * k * N * B)
    lam = min(1.0, 2 * math.sqrt(X) / (1 + math.sqrt(1 - X))) if X < 1 else 1.0
    lnp = lam * math.sqrt(d * bf) / 4
    l = max(m, n, lnp)
    t = l * math.sqrt(2 * Pu * 1e3 / (0.9 * Fy * B * N))
    t_use = math.ceil(t / 5) * 5
    r.add("Cantilever lengths", "m = (N − 0.95d)/2 ; n = (B − 0.8bf)/2 ; λn' = λ√(d·bf)/4", f"X = {fmt(X, 3)} , λ = {fmt(lam, 3)}",
          f"m = {fmt(m, 1)} , n = {fmt(n, 1)} , λn' = {fmt(lnp, 1)} → ℓ = {fmt(l, 1)} mm")
    r.add("Plate thickness", "t = ℓ·√(2Pu/(0.9·Fy·B·N))", "", f"t,req = {fmt(t, 1)} mm → use {t_use} mm")
    r.outputs = dict(N=N, B=B, t=t_use, d=d, bf=bf, m=m, n=n)
    return r
