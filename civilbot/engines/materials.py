"""Concrete mix design (ACI 211.1, absolute volume) and sieve analysis / gradation."""
from __future__ import annotations
import math
import numpy as np
from ..core import Result, InputError, fmt

NMSA = [9.5, 12.5, 19, 25, 37.5, 50, 75]
WATER_NA = {1: [207, 199, 190, 179, 166, 154, 130], 2: [228, 216, 205, 193, 181, 169, 145], 3: [243, 228, 216, 202, 190, 178, 160]}
AIR_NA = [3, 2.5, 2, 1.5, 1, 0.5, 0.3]
WATER_AE = {1: [181, 175, 168, 160, 150, 142, 122], 2: [202, 193, 184, 175, 165, 157, 133], 3: [216, 205, 197, 184, 174, 166, 154]}
AIR_AE = {"mild": [4.5, 4.0, 3.5, 3.0, 2.5, 2.0, 1.5], "moderate": [6.0, 5.5, 5.0, 4.5, 4.5, 4.0, 3.5], "severe": [7.5, 7.0, 6.0, 6.0, 5.5, 5.0, 4.5]}
WC_FC = [15, 20, 25, 30, 35, 40, 45]
WC_NA = [0.79, 0.69, 0.61, 0.54, 0.47, 0.42, 0.38]
WC_AE = [0.70, 0.60, 0.52, 0.45, 0.39, 0.34, 0.31]
CA_FM = [2.4, 2.6, 2.8, 3.0]
CA_VOL = {9.5: [.50, .48, .46, .44], 12.5: [.59, .57, .55, .53], 19: [.66, .64, .62, .60], 25: [.71, .69, .67, .65],
          37.5: [.75, .73, .71, .69], 50: [.78, .76, .74, .72], 75: [.82, .80, .78, .76]}


def mix_design(fc, slump=75, nmsa=19, fm=2.7, sg_c=3.15, sg_fa=2.65, sg_ca=2.68, rodded=1600, s=None,
               air_entrained=False, exposure="moderate", mc_fa=0.0, abs_fa=0.0, mc_ca=0.0, abs_ca=0.0, wc_max=None) -> Result:
    if nmsa not in NMSA:
        raise InputError(f"المقاس الأكبر للركام لازم واحد من {NMSA} mm")
    if not 2.3 <= fm <= 3.1:
        raise InputError("معامل النعومة FM لازم بين 2.3 و 3.1")
    r = Result("mix", "Concrete mix design (ACI 211.1 — absolute volume method)",
               inputs=dict(fc=f"{fmt(fc)} MPa", slump=f"{fmt(slump)} mm", NMSA=f"{fmt(nmsa)} mm", FM=fmt(fm),
                           SG=f"cement {sg_c}, sand {sg_fa}, gravel {sg_ca}", rodded=f"{fmt(rodded)} kg/m³ (coarse, dry-rodded)",
                           air="entrained (" + exposure + ")" if air_entrained else "non-air-entrained",
                           moisture=f"sand MC {mc_fa}% / abs {abs_fa}% ; gravel MC {mc_ca}% / abs {abs_ca}%"))
    if s:
        fcr = max(fc + 1.34 * s, fc + 2.33 * s - 3.5) if fc <= 35 else max(fc + 1.34 * s, 0.9 * fc + 2.33 * s)
        r.add("Required average strength (with std. dev.)", "f'cr = max(f'c + 1.34s , f'c + 2.33s − 3.5)", f"s = {fmt(s)} MPa", f"f'cr = {fmt(fcr)} MPa", "ACI 318 26.4.3")
    else:
        fcr = fc + 7 if fc < 21 else (fc + 8.3 if fc <= 35 else 1.1 * fc + 5)
        r.add("Required average strength (no records)", "f'cr = f'c + 7 / + 8.3 / 1.1f'c + 5", "", f"f'cr = {fmt(fcr)} MPa", "ACI 318 Table 26.4.3.1")
    k = NMSA.index(nmsa)
    srow = 1 if slump <= 50 else (2 if slump <= 100 else 3)
    W = (WATER_AE if air_entrained else WATER_NA)[srow][k]
    air = (AIR_AE[exposure][k] if air_entrained else AIR_NA[k])
    r.add("Mixing water & air content", "ACI 211.1 Table 6.3.3", f"slump {fmt(slump)} mm , NMSA {fmt(nmsa)} mm", f"W = {W} kg/m³ , air = {fmt(air)} %")
    wc = float(np.interp(fcr, WC_FC, WC_AE if air_entrained else WC_NA))
    if wc_max:
        wc = min(wc, wc_max)
    r.add("Water-cement ratio", "ACI 211.1 Table 6.3.4(a) (interpolated)", f"f'cr = {fmt(fcr)} MPa", f"w/c = {fmt(wc, 3)}")
    C = W / wc
    r.add("Cement content", "C = W/(w/c)", f"{W}/{fmt(wc, 3)}", f"C = {fmt(C, 1)} kg/m³")
    vca = float(np.interp(fm, CA_FM, CA_VOL[nmsa]))
    CA = vca * rodded
    r.add("Coarse aggregate", "Vca (Table 6.3.6) × dry-rodded unit weight", f"Vca = {fmt(vca, 3)} m³/m³", f"CA (dry) = {fmt(CA, 1)} kg/m³")
    Vw, Vc, Vca_, Va = W / 1000, C / (sg_c * 1000), CA / (sg_ca * 1000), air / 100
    Vfa = 1 - (Vw + Vc + Vca_ + Va)
    FA = Vfa * sg_fa * 1000
    r.add("Fine aggregate (absolute volume)", "Vfa = 1 − (Vw + Vc + Vca + Vair)",
          f"1 − ({fmt(Vw, 4)} + {fmt(Vc, 4)} + {fmt(Vca_, 4)} + {fmt(Va, 4)})", f"Vfa = {fmt(Vfa, 4)} m³ → FA (SSD-dry) = {fmt(FA, 1)} kg/m³")
    # moisture adjustment (CA, FA computed as oven-dry for CA from rodded weight, FA as dry from SG bulk-dry assumption)
    FAw = FA * (1 + mc_fa / 100)
    CAw = CA * (1 + mc_ca / 100)
    Wadj = W - FA * (mc_fa - abs_fa) / 100 - CA * (mc_ca - abs_ca) / 100
    r.add("Field (batch) quantities after moisture correction", "Wbatch = W − FA(MC − abs) − CA(MC − abs)", "",
          f"water {fmt(Wadj, 1)} , cement {fmt(C, 1)} , sand {fmt(FAw, 1)} , gravel {fmt(CAw, 1)} kg/m³")
    total = Wadj + C + FAw + CAw
    r.add("Proportions by weight (cement = 1)", "", f"fresh density ≈ {fmt(total, 0)} kg/m³",
          f"1 : {fmt(FAw / C, 2)} : {fmt(CAw / C, 2)}  , w/c = {fmt(wc, 2)}")
    bags = C / 50
    r.add("Per m³ (site)", "", "", f"{fmt(bags, 1)} cement bags (50 kg) , {fmt(FAw / 1600, 2)} m³ sand , {fmt(CAw / 1500, 2)} m³ gravel (loose)")
    r.outputs = dict(fcr=fcr, W=Wadj, C=C, FA=FAw, CA=CAw, wc=wc, air=air, vols=dict(water=Vw, cement=Vc, coarse=Vca_, fine=Vfa, air=Va))
    return r


STD_SIEVES = [75, 37.5, 19, 9.5, 4.75, 2.36, 1.18, 0.6, 0.3, 0.15]  # for FM (ASTM)
C33_FINE = {9.5: (100, 100), 4.75: (95, 100), 2.36: (80, 100), 1.18: (50, 85), 0.6: (25, 60), 0.3: (5, 30), 0.15: (0, 10)}
C33_57 = {37.5: (100, 100), 25: (95, 100), 12.5: (25, 60), 4.75: (0, 10), 2.36: (0, 5)}
C33_67 = {25: (100, 100), 19: (90, 100), 9.5: (20, 55), 4.75: (0, 10), 2.36: (0, 5)}
LIMITS = {"fine": C33_FINE, "57": C33_57, "67": C33_67}


def sieve(sizes, retained, spec="fine") -> Result:
    if len(sizes) != len(retained) or len(sizes) < 3:
        raise InputError("عدد المناخل لازم يساوي عدد الأوزان (3 على الأقل)")
    order = np.argsort(sizes)[::-1]
    sizes = [float(sizes[i]) for i in order]
    retained = [float(retained[i]) for i in order]
    total = sum(retained)
    if total <= 0:
        raise InputError("مجموع الأوزان صفر")
    cum = np.cumsum(retained)
    pret = cum / total * 100
    passing = 100 - pret
    r = Result("sieve", "Sieve analysis & gradation",
               inputs=dict(sieves=", ".join(fmt(s) for s in sizes) + " mm", retained=", ".join(fmt(m) for m in retained) + " g", spec=spec))
    rows = [f"{fmt(s)} mm: retained {fmt(m)} g , cum {fmt(c, 1)} % , passing {fmt(p, 1)} %" for s, m, c, p in zip(sizes, retained, pret, passing)]
    r.add("Gradation table", "\n".join(rows))
    fm_sum = sum(float(np.interp(math.log(s), np.log(sizes[::-1]), pret[::-1])) for s in STD_SIEVES if min(sizes) <= s <= max(sizes))
    fm = fm_sum / 100
    r.add("Fineness modulus", "FM = Σ(cumulative % retained on standard sieves)/100", "", f"FM = {fmt(fm, 3)}" + (" (ASTM C33 sand: 2.3–3.1)" if spec == "fine" else ""))

    def D(pct):
        ls = np.log10(sizes[::-1]); pp = passing[::-1]
        if pct < pp.min() or pct > pp.max():
            return None
        return float(10 ** np.interp(pct, pp, ls))
    D10, D30, D60 = D(10), D(30), D(60)
    cls = ""
    if D10 and D30 and D60:
        Cu, Cc = D60 / D10, D30**2 / (D10 * D60)
        p4 = float(np.interp(math.log(4.75), np.log(sizes[::-1]), passing[::-1])) if min(sizes) <= 4.75 <= max(sizes) else None
        sand = p4 is not None and p4 > 50
        good = (Cu >= 6 and 1 <= Cc <= 3) if sand else (Cu >= 4 and 1 <= Cc <= 3)
        cls = ("SW (well-graded sand)" if good else "SP (poorly-graded sand)") if sand else ("GW (well-graded gravel)" if good else "GP (poorly-graded gravel)")
        r.add("Grain-size parameters", "Cu = D60/D10 ; Cc = D30²/(D10·D60)", f"D10 = {fmt(D10, 3)} , D30 = {fmt(D30, 3)} , D60 = {fmt(D60, 3)} mm",
              f"Cu = {fmt(Cu, 2)} , Cc = {fmt(Cc, 2)} → {cls} (assuming fines < 5%)")
    lim = LIMITS.get(spec)
    fails = []
    if lim:
        for s, (lo, hi) in lim.items():
            if min(sizes) <= s <= max(sizes):
                p = float(np.interp(math.log(s), np.log(sizes[::-1]), passing[::-1]))
                if not lo - 1e-6 <= p <= hi + 1e-6:
                    fails.append(f"{fmt(s)} mm: {fmt(p, 1)}% (limit {lo}–{hi})")
        r.add(f"ASTM C33 compliance ({'fine aggregate' if spec == 'fine' else 'size No. ' + spec})", "", "",
              "✔ within limits" if not fails else "✘ " + " ; ".join(fails))
        if fails:
            r.warnings.append("التدرج خارج حدود المواصفة")
    r.outputs = dict(sizes=sizes, passing=list(passing), fm=fm, D10=D10, D30=D30, D60=D60, cls=cls, spec=spec, limits=lim)
    return r
