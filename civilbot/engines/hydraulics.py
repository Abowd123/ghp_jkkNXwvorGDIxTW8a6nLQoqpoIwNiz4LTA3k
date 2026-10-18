"""Open-channel (Manning) and pressurised pipe flow (Darcy–Weisbach/Colebrook, Hazen–Williams)."""
from __future__ import annotations
import math
from ..core import Result, InputError, fmt

G = 9.81


def geom(shape, y, b=0.0, z=0.0, D=0.0):
    """Return A, P, T for flow depth y."""
    if shape == "rect":
        return b * y, b + 2 * y, b
    if shape == "trap":
        return (b + z * y) * y, b + 2 * y * math.sqrt(1 + z * z), b + 2 * z * y
    if shape == "tri":
        return z * y * y, 2 * y * math.sqrt(1 + z * z), 2 * z * y
    if shape == "circle":
        y = min(y, D * 0.99999)
        th = 2 * math.acos(1 - 2 * y / D)
        return D * D / 8 * (th - math.sin(th)), D * th / 2, D * math.sin(th / 2)
    raise InputError("shape = rect / trap / tri / circle")


def manning_Q(shape, y, n, S, **g):
    A, P, T = geom(shape, y, **g)
    return A / n * (A / P) ** (2 / 3) * math.sqrt(S)


def _solve(f, lo, hi, target):
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def channel(shape, n, S, Q=None, y=None, b=0.0, z=0.0, D=0.0) -> Result:
    shape = shape.lower()
    if n <= 0 or S <= 0:
        raise InputError("n و S لازم موجبين")
    g = dict(b=b, z=z, D=D)
    r = Result("channel", "Open-channel flow (Manning)", inputs=dict(shape=shape, n=fmt(n, 4), S=fmt(S, 6), b=f"{fmt(b)} m", z=f"{fmt(z)} (H:V)",
                                                                 D=f"{fmt(D)} m", Q=f"{fmt(Q)} m³/s" if Q else "-", y=f"{fmt(y)} m" if y else "-"))
    ymax = D * 0.938 if shape == "circle" else 50.0
    if Q and not y:
        if shape == "circle" and Q > manning_Q(shape, ymax, n, S, **g):
            raise InputError(f"التصريف أكبر من سعة الأنبوب الممتلئ جزئياً (Qmax ≈ {fmt(manning_Q(shape, ymax, n, S, **g), 3)} m³/s). كبّر القطر")
        y = _solve(lambda yy: manning_Q(shape, yy, n, S, **g), 1e-6, ymax, Q)
        r.add("Normal depth (iterative)", "Q = (1/n)·A·R^(2/3)·S^(1/2) → solve for yn", f"Q = {fmt(Q)} m³/s", f"yn = {fmt(y, 4)} m")
    elif y:
        Q = manning_Q(shape, y, n, S, **g)
        r.add("Discharge", "Q = (1/n)·A·R^(2/3)·S^(1/2)", f"y = {fmt(y)} m", f"Q = {fmt(Q, 4)} m³/s")
    else:
        raise InputError("أدخل Q (لإيجاد العمق) أو y (لإيجاد التصريف)")
    A, P, T = geom(shape, y, **g)
    R = A / P
    V = Q / A
    Dh = A / T
    Fr = V / math.sqrt(G * Dh)
    r.add("Section properties", "A, P, R = A/P, T", "", f"A = {fmt(A, 4)} m² , P = {fmt(P, 4)} m , R = {fmt(R, 4)} m , T = {fmt(T, 4)} m")
    r.add("Velocity & Froude number", "V = Q/A ; Fr = V/√(g·A/T)", "", f"V = {fmt(V, 3)} m/s , Fr = {fmt(Fr, 3)} → {'subcritical' if Fr < 1 else 'supercritical' if Fr > 1 else 'critical'}")
    yc = _solve(lambda yy: geom(shape, yy, **g)[0] ** 3 / geom(shape, yy, **g)[2], 1e-6, ymax, Q * Q / G)
    Ac, Pc, Tc = geom(shape, yc, **g)
    Sc = (Q * n / (Ac * (Ac / Pc) ** (2 / 3))) ** 2
    r.add("Critical depth & slope", "Q²/g = A³/T at yc ; Sc from Manning at yc", "", f"yc = {fmt(yc, 4)} m , Sc = {fmt(Sc, 6)}")
    E = y + V * V / (2 * G)
    r.add("Specific energy", "E = y + V²/2g", "", f"E = {fmt(E, 4)} m")
    if V < 0.6:
        r.warnings.append("السرعة أقل من 0.6 m/s: احتمال ترسيب")
    if V > 3.0 and shape != "circle":
        r.warnings.append("السرعة عالية (> 3 m/s): تحقق من النحر وتبطين القناة")
    if shape in ("rect", "trap"):
        zz = z if shape == "trap" else 0
        k = 2 * (math.sqrt(1 + zz * zz) - zz) if shape == "trap" else 2.0
        # best section: b = k·y, solve Q
        fy = lambda yy: (lambda A, P: A / n * (A / P) ** (2 / 3) * math.sqrt(S))(*(lambda bb: ((bb + zz * yy) * yy, bb + 2 * yy * math.sqrt(1 + zz * zz)))(k * yy))
        yb = _solve(fy, 1e-6, 50, Q)
        r.add("Most efficient section (R = y/2)", "rect: b = 2y ; trap: b = 2y(√(1+z²) − z)", "", f"y = {fmt(yb, 3)} m , b = {fmt(k * yb, 3)} m")
    r.outputs = dict(shape=shape, y=y, Q=Q, V=V, Fr=Fr, yc=yc, A=A, P=P, R=R, T=T, b=b, z=z, D=D)
    return r


def pipe(Q, D, L, eps=0.045, nu=1.0e-6, method="darcy", C=130, minor=0.0, z1=0.0, z2=0.0) -> Result:
    """Q m³/s, D m, L m, eps mm, minor = ΣK."""
    method = method.lower()
    if min(Q, D, L) <= 0:
        raise InputError("Q و D و L لازم موجبة")
    r = Result("pipe", f"Pipe flow ({'Darcy–Weisbach + Colebrook' if method == 'darcy' else 'Hazen–Williams'})",
               inputs=dict(Q=f"{fmt(Q, 4)} m³/s", D=f"{fmt(D*1000)} mm", L=f"{fmt(L)} m", ε=f"{fmt(eps)} mm", C=fmt(C), ΣK=fmt(minor)))
    A = math.pi * D * D / 4
    V = Q / A
    Re = V * D / nu
    r.add("Velocity & Reynolds number", "V = Q/A ; Re = V·D/ν", f"ν = {fmt(nu)} m²/s", f"V = {fmt(V, 3)} m/s , Re = {Re:,.0f} ({'laminar' if Re < 2000 else 'turbulent' if Re > 4000 else 'transitional'})")
    if method == "darcy":
        if Re < 2000:
            f = 64 / Re
        else:
            f = 0.25 / (math.log10(eps / 1000 / (3.7 * D) + 5.74 / Re**0.9)) ** 2
            for _ in range(50):
                f = (-2 * math.log10(eps / 1000 / (3.7 * D) + 2.51 / (Re * math.sqrt(f)))) ** -2
        hf = f * L / D * V * V / (2 * G)
        r.add("Friction factor (Colebrook, iterative)", "1/√f = −2log(ε/3.7D + 2.51/(Re√f))", f"ε/D = {fmt(eps/1000/D, 6)}", f"f = {fmt(f, 5)}")
        r.add("Friction head loss", "hf = f·(L/D)·V²/2g", "", f"hf = {fmt(hf, 4)} m")
    else:
        hf = 10.67 * L * Q**1.852 / (C**1.852 * D**4.8704)
        r.add("Friction head loss", "hf = 10.67·L·Q^1.852/(C^1.852·D^4.87)", "", f"hf = {fmt(hf, 4)} m")
        f = hf / (L / D * V * V / (2 * G))
    hm = minor * V * V / (2 * G)
    if minor:
        r.add("Minor losses", "hm = ΣK·V²/2g", "", f"hm = {fmt(hm, 4)} m")
    H = hf + hm + (z2 - z1)
    r.add("Required head", "H = hf + hm + Δz", f"Δz = {fmt(z2 - z1)} m", f"H = {fmt(H, 3)} m → pump power (η = 0.75) ≈ {fmt(1000 * G * Q * H / 0.75 / 1000, 2)} kW")
    if V > 3:
        r.warnings.append("السرعة > 3 m/s: خطر طرق مائي وضوضاء")
    if V < 0.5:
        r.warnings.append("السرعة < 0.5 m/s: قد يحدث ترسيب")
    r.outputs = dict(V=V, Re=Re, f=f, hf=hf, hm=hm, H=H)
    return r
