"""Highway: AASHTO 93 flexible pavement and stopping sight distance."""
from __future__ import annotations
import math
from ..core import Result, InputError, fmt
from statistics import NormalDist


def aashto93(W18, R=95.0, S0=0.45, MR=30.0, pi=4.2, pt=2.5, a=(0.44, 0.14, 0.11), m=(1.0, 1.0, 1.0), MR_layers=None) -> Result:
    """W18 in ESALs, MR subgrade resilient modulus in MPa."""
    if W18 <= 0 or MR <= 0:
        raise InputError("W18 و MR لازم موجبين")
    ZR = NormalDist().inv_cdf(1 - R / 100)
    dpsi = pi - pt
    MRpsi = MR * 145.038
    r = Result("pavement", "Flexible pavement design (AASHTO 1993)",
               inputs=dict(W18=f"{fmt(W18)} ESAL", R=f"{fmt(R)} %", S0=fmt(S0), MR=f"{fmt(MR)} MPa ({fmt(MRpsi, 0)} psi)", ΔPSI=fmt(dpsi)))

    def lhs(SN):
        return (ZR * S0 + 9.36 * math.log10(SN + 1) - 0.20 + math.log10(dpsi / 2.7) / (0.40 + 1094 / (SN + 1) ** 5.19)
                + 2.32 * math.log10(MRpsi) - 8.07)
    target = math.log10(W18)
    lo, hi = 0.5, 15
    for _ in range(200):
        mid = (lo + hi) / 2
        if lhs(mid) < target:
            lo = mid
        else:
            hi = mid
    SN = (lo + hi) / 2
    r.add("Design equation", "log W18 = ZR·S0 + 9.36log(SN+1) − 0.20 + log(ΔPSI/2.7)/(0.40 + 1094/(SN+1)^5.19) + 2.32log(MR) − 8.07",
          f"ZR = {fmt(ZR, 3)}", f"SN = {fmt(SN, 3)}")
    # layer thicknesses (inches → mm), using minimum AASHTO thickness by traffic
    a1, a2, a3 = a
    m2, m3 = m[1], m[2]
    mins = [(5e4, 1.0, 4), (1.5e5, 2.0, 4), (5e5, 2.5, 4), (2e6, 3.0, 6), (7e6, 3.5, 6), (float("inf"), 4.0, 6)]
    D1min, D2min = next((x[1], x[2]) for x in mins if W18 <= x[0])
    if MR_layers:
        # layered approach: SN1 from base modulus, SN2 from subbase modulus
        def sn_for(mr):
            nonlocal MRpsi
            keep = MRpsi; MRpsi = mr * 145.038
            l, h = 0.5, 15
            for _ in range(200):
                mm = (l + h) / 2
                if lhs(mm) < target: l = mm
                else: h = mm
            MRpsi = keep
            return (l + h) / 2
        SN1 = sn_for(MR_layers[0]); SN2 = sn_for(MR_layers[1])
        D1 = max(D1min, math.ceil(SN1 / a1 * 2) / 2)
        D2 = max(D2min, math.ceil((SN2 - a1 * D1) / (a2 * m2) * 2) / 2)
        D3 = max(4.0, math.ceil((SN - a1 * D1 - a2 * m2 * D2) / (a3 * m3) * 2) / 2)
        r.add("Layered design", "SN1 (over base), SN2 (over subbase), SN (over subgrade)", "", f"SN1 = {fmt(SN1, 2)} , SN2 = {fmt(SN2, 2)}")
    else:
        D1 = max(D1min, 4.0 if W18 > 2e6 else D1min)
        D2 = max(D2min, 6.0)
        D3 = max(4.0, math.ceil((SN - a1 * D1 - a2 * m2 * D2) / (a3 * m3) * 2) / 2)
    SNp = a1 * D1 + a2 * m2 * D2 + a3 * m3 * D3
    r.add("Layer thicknesses", "SN = a1D1 + a2m2D2 + a3m3D3", f"a = {a1}, {a2}, {a3} ; m = {m2}, {m3}",
          f"AC = {fmt(D1 * 25.4, 0)} mm , base = {fmt(D2 * 25.4, 0)} mm , subbase = {fmt(D3 * 25.4, 0)} mm → SN provided = {fmt(SNp, 2)} ≥ {fmt(SN, 2)}")
    r.outputs = dict(SN=SN, D=(D1 * 25.4, D2 * 25.4, D3 * 25.4), SNp=SNp)
    return r


def ssd(V, t=2.5, a=3.4, G=0.0) -> Result:
    """V km/h, t s, a m/s², G grade % (+up)."""
    r = Result("ssd", "Stopping sight distance (AASHTO)", inputs=dict(V=f"{fmt(V)} km/h", t=f"{fmt(t)} s", a=f"{fmt(a)} m/s²", G=f"{fmt(G)} %"))
    d1 = 0.278 * V * t
    d2 = V * V / (254 * (a / 9.81 + G / 100))
    r.add("Brake reaction distance", "d1 = 0.278·V·t", f"0.278×{fmt(V)}×{fmt(t)}", f"d1 = {fmt(d1, 2)} m")
    r.add("Braking distance", "d2 = V²/(254(a/9.81 ± G))", "", f"d2 = {fmt(d2, 2)} m")
    S = d1 + d2
    r.add("Stopping sight distance", "SSD = d1 + d2", "", f"SSD = {fmt(S, 1)} m (design ≈ {fmt(math.ceil(S / 5) * 5)} m)")
    # minimum crest/sag curve length (K) for SSD, h1=1.08, h2=0.6
    Kc = S * S / 658
    Ks = S * S / (120 + 3.5 * S)
    r.add("Vertical curve K for SSD (S < L)", "Kcrest = S²/658 ; Ksag = S²/(120 + 3.5S)", "", f"Kcrest = {fmt(Kc, 1)} , Ksag = {fmt(Ks, 1)}")
    r.outputs = dict(SSD=S, d1=d1, d2=d2, Kc=Kc, Ks=Ks)
    return r
