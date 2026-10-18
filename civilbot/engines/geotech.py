"""Geotechnical engineering: bearing capacity, Mohr circle, lateral earth pressure,
consolidation settlement, Boussinesq stress bulbs, Bishop slope stability."""
from __future__ import annotations
import math
import numpy as np
from ..core import Result, InputError, fmt

rad = math.radians


# ------------------------------------------------------------------ bearing capacity
def bearing_factors(phi, method="meyerhof"):
    p = rad(phi)
    if method == "terzaghi":
        if phi == 0:
            return 5.7, 1.0, 0.0
        a = math.exp((0.75 * math.pi - p / 2) * math.tan(p))
        Nq = a**2 / (2 * math.cos(rad(45 + phi / 2))**2)
        Nc = (Nq - 1) / math.tan(p)
        # Terzaghi Nγ (Kumbhojkar 1993, as tabulated by Das) — log-interpolated
        T = {0: 1e-3, 5: 0.14, 10: 0.56, 15: 1.52, 20: 3.64, 25: 8.11, 30: 19.13, 35: 45.41, 40: 115.31, 45: 325.34, 50: 1072.8}
        ks = sorted(T)
        Ng = float(np.exp(np.interp(phi, ks, [math.log(T[k]) for k in ks]))) if phi > 0 else 0.0
        return Nc, Nq, Ng
    Nq = math.exp(math.pi * math.tan(p)) * math.tan(rad(45 + phi / 2))**2
    Nc = (Nq - 1) / math.tan(p) if phi > 0 else 5.14
    if method == "meyerhof":
        Ng = (Nq - 1) * math.tan(1.4 * p)
    elif method == "hansen":
        Ng = 1.5 * (Nq - 1) * math.tan(p)
    else:  # vesic
        Ng = 2 * (Nq + 1) * math.tan(p)
    return Nc, Nq, Ng


def bearing(B, L, Df, c, phi, gamma, method="meyerhof", FS=3.0, gw=None, gamma_sat=None) -> Result:
    method = method.lower()
    if method not in ("terzaghi", "meyerhof", "hansen", "vesic"):
        raise InputError("method = terzaghi / meyerhof / hansen / vesic")
    if B <= 0 or Df < 0 or not 0 <= phi <= 50:
        raise InputError("قيم غير منطقية (0 ≤ φ ≤ 50)")
    L = L or B
    if L < B:
        B, L = L, B
    r = Result("bearing", f"Ultimate bearing capacity ({method.title()})",
               inputs=dict(B=f"{fmt(B)} m", L=f"{fmt(L)} m", Df=f"{fmt(Df)} m", c=f"{fmt(c)} kPa", phi=f"{fmt(phi)}°",
                           gamma=f"{fmt(gamma)} kN/m³", GWT=f"{fmt(gw)} m below surface" if gw is not None else "deep", FS=fmt(FS)))
    Nc, Nq, Ng = bearing_factors(phi, method)
    r.add("Bearing capacity factors", {"terzaghi": "Nq = a²/(2cos²(45+φ/2)) ; Nc = (Nq−1)cotφ",
                                      "meyerhof": "Nq = e^(πtanφ)·tan²(45+φ/2) ; Nc = (Nq−1)cotφ ; Nγ = (Nq−1)tan(1.4φ)",
                                      "hansen": "Nγ = 1.5(Nq−1)tanφ", "vesic": "Nγ = 2(Nq+1)tanφ"}[method],
          f"φ = {fmt(phi)}°", f"Nc = {fmt(Nc, 3)} , Nq = {fmt(Nq, 3)} , Nγ = {fmt(Ng, 3)}")
    # water table
    gw_ = 9.81
    q = gamma * Df
    g_eff = gamma
    if gw is not None:
        gs = gamma_sat or gamma + 2
        gp = gs - gw_
        if gw <= Df:
            q = gamma * gw + gp * (Df - gw); g_eff = gp
        elif gw < Df + B:
            g_eff = gp + (gw - Df) / B * (gamma - gp)
        r.add("Groundwater correction", "q = γ·Dw + γ'(Df − Dw) ; γ in Nγ term = γ' or interpolated", f"γ' = {fmt(gp)} kN/m³",
              f"q = {fmt(q)} kPa , γ(Nγ) = {fmt(g_eff)} kN/m³")
    else:
        r.add("Overburden at foundation level", "q = γ·Df", f"{fmt(gamma)}×{fmt(Df)}", f"q = {fmt(q)} kPa")
    BL = B / L
    if method == "terzaghi":
        sc, sg = (1.3, 0.8) if abs(BL - 1) < 1e-9 else ((1.0, 1.0) if L > 5 * B else (1.0 + 0.3 * BL, 1 - 0.2 * BL))
        sq = 1.0; dc = dq = dg = 1.0
        shp = f"sc = {fmt(sc)} , sγ = {fmt(sg)} (square 1.3/0.8, strip 1/1)"
    else:
        p = rad(phi)
        if method == "meyerhof":
            Kp = math.tan(rad(45 + phi / 2))**2
            sc = 1 + 0.2 * Kp * BL; sq = sg = 1 + 0.1 * Kp * BL if phi > 10 else 1.0
            dc = 1 + 0.2 * math.sqrt(Kp) * Df / B; dq = dg = 1 + 0.1 * math.sqrt(Kp) * Df / B if phi > 10 else 1.0
        else:
            sc = 1 + (Nq / Nc) * BL; sq = 1 + BL * math.tan(p); sg = max(0.6, 1 - 0.4 * BL)
            k = Df / B if Df <= B else math.atan(Df / B)
            dc = 1 + 0.4 * k; dq = 1 + 2 * math.tan(p) * (1 - math.sin(p))**2 * k; dg = 1.0
        shp = f"sc = {fmt(sc, 3)} , sq = {fmt(sq, 3)} , sγ = {fmt(sg, 3)} ; dc = {fmt(dc, 3)} , dq = {fmt(dq, 3)} , dγ = {fmt(dg, 3)}"
    r.add("Shape & depth factors", "B/L = " + fmt(BL, 3), "", shp)
    t1 = c * Nc * sc * dc
    t2 = q * Nq * sq * dq
    t3 = 0.5 * g_eff * B * Ng * sg * dg
    qu = t1 + t2 + t3
    r.add("Ultimate bearing capacity", "qu = c·Nc·sc·dc + q·Nq·sq·dq + ½γ·B·Nγ·sγ·dγ",
          f"{fmt(t1)} + {fmt(t2)} + {fmt(t3)}", f"qu = {fmt(qu)} kPa")
    qa = qu / FS
    qnet = (qu - q) / FS
    r.add("Allowable bearing capacity", "qa = qu/FS ; qa,net = (qu − q)/FS", f"FS = {fmt(FS)}",
          f"qa = {fmt(qa)} kPa , qa,net = {fmt(qnet)} kPa → Q_all = {fmt(qa * B * L)} kN")
    r.outputs = dict(Nc=Nc, Nq=Nq, Ng=Ng, qu=qu, qa=qa, qnet=qnet)
    return r


# ------------------------------------------------------------------ Mohr circle
def mohr(sx, sy, txy, theta=None) -> Result:
    r = Result("mohr", "Mohr's circle of stress", inputs=dict(σx=f"{fmt(sx)}", σy=f"{fmt(sy)}", τxy=f"{fmt(txy)}", θ=f"{fmt(theta)}°" if theta is not None else "-"))
    C = (sx + sy) / 2
    R = math.hypot((sx - sy) / 2, txy)
    s1, s3 = C + R, C - R
    tp = 0.5 * math.degrees(math.atan2(2 * txy, sx - sy))
    r.add("Centre & radius", "C = (σx + σy)/2 ; R = √(((σx − σy)/2)² + τxy²)", f"C = ({fmt(sx)} + {fmt(sy)})/2", f"C = {fmt(C)} , R = {fmt(R)}")
    r.add("Principal stresses", "σ1,3 = C ± R", "", f"σ1 = {fmt(s1)} , σ3 = {fmt(s3)}")
    r.add("Principal plane angle", "tan 2θp = 2τxy/(σx − σy)", "", f"θp = {fmt(tp, 3)}° (to σ1, counter-clockwise from x)")
    r.add("Maximum in-plane shear", "τmax = R on planes θp ± 45°", "", f"τmax = {fmt(R)} , σ = {fmt(C)}")
    out = dict(C=C, R=R, s1=s1, s3=s3, tp=tp, sx=sx, sy=sy, txy=txy)
    if theta is not None:
        t2 = rad(2 * theta)
        sn = C + (sx - sy) / 2 * math.cos(t2) + txy * math.sin(t2)
        tn = -(sx - sy) / 2 * math.sin(t2) + txy * math.cos(t2)
        r.add(f"Stresses on plane at θ = {fmt(theta)}°", "σθ = C + (σx−σy)/2·cos2θ + τxy·sin2θ ; τθ = −(σx−σy)/2·sin2θ + τxy·cos2θ", "",
              f"σθ = {fmt(sn)} , τθ = {fmt(tn)}")
        out.update(theta=theta, sn=sn, tn=tn)
    r.outputs = out
    return r


# ------------------------------------------------------------------ lateral pressure
def lateral(H, phi, gamma, c=0.0, q=0.0, method="rankine", delta=0.0, beta=0.0, alpha=90.0, gw=None) -> Result:
    method = method.lower()
    r = Result("lateral", f"Lateral earth pressure ({method.title()})",
               inputs=dict(H=f"{fmt(H)} m", phi=f"{fmt(phi)}°", c=f"{fmt(c)} kPa", gamma=f"{fmt(gamma)} kN/m³", q=f"{fmt(q)} kPa",
                           δ=f"{fmt(delta)}°", β=f"{fmt(beta)}° backfill slope", α=f"{fmt(alpha)}° wall back angle"))
    p, d, b, a = rad(phi), rad(delta), rad(beta), rad(alpha)
    if method == "rankine":
        if beta:
            cb, cp = math.cos(b), math.cos(p)
            Ka = cb * (cb - math.sqrt(cb**2 - cp**2)) / (cb + math.sqrt(cb**2 - cp**2))
            Kp = cb * (cb + math.sqrt(cb**2 - cp**2)) / (cb - math.sqrt(cb**2 - cp**2))
        else:
            Ka = math.tan(rad(45 - phi / 2))**2; Kp = 1 / Ka
        r.add("Rankine coefficients", "Ka = tan²(45 − φ/2) ; Kp = tan²(45 + φ/2)" if not beta else "Ka = cosβ(cosβ − √(cos²β − cos²φ))/(cosβ + √(…))",
              "", f"Ka = {fmt(Ka, 4)} , Kp = {fmt(Kp, 4)} , K0 = 1 − sinφ = {fmt(1 - math.sin(p), 4)}")
    else:
        num = math.sin(a + p)**2
        den = math.sin(a)**2 * math.sin(a - d) * (1 + math.sqrt(math.sin(p + d) * math.sin(p - b) / (math.sin(a - d) * math.sin(a + b))))**2
        Ka = num / den
        nump = math.sin(a - p)**2
        denp = math.sin(a)**2 * math.sin(a + d) * (1 - math.sqrt(math.sin(p + d) * math.sin(p + b) / (math.sin(a + d) * math.sin(a + b))))**2
        Kp = nump / denp
        r.add("Coulomb coefficients", "Ka = sin²(α+φ)/[sin²α·sin(α−δ)(1 + √(sin(φ+δ)sin(φ−β)/(sin(α−δ)sin(α+β))))²]",
              f"α = {fmt(alpha)}°, δ = {fmt(delta)}°, β = {fmt(beta)}°", f"Ka = {fmt(Ka, 4)} , Kp = {fmt(Kp, 4)}")
    z = np.linspace(0, H, 101)
    u = np.zeros_like(z)
    sv = gamma * z + q
    if gw is not None and gw < H:
        gp = gamma + 2 - 9.81
        sv = np.where(z <= gw, gamma * z, gamma * gw + gp * (z - gw)) + q
        u = np.where(z > gw, 9.81 * (z - gw), 0)
    pa = Ka * sv - 2 * c * math.sqrt(Ka)
    zc = 2 * c / (gamma * math.sqrt(Ka)) - q / gamma if c > 0 else 0
    pa_pos = np.maximum(pa, 0) + u
    Pa = np.trapezoid(pa_pos, z) if hasattr(np, "trapezoid") else np.trapz(pa_pos, z)
    ybar = (np.trapezoid(pa_pos * (H - z), z) if hasattr(np, "trapezoid") else np.trapz(pa_pos * (H - z), z)) / Pa if Pa else 0
    if c:
        r.add("Tension crack depth", "zc = 2c/(γ√Ka) − q/γ", "", f"zc = {fmt(max(zc, 0))} m")
    r.add("Active pressure at base", "σa = Ka·σv' − 2c√Ka + u", f"σv = {fmt(sv[-1])} kPa", f"σa = {fmt(pa_pos[-1])} kPa")
    r.add("Total active thrust (ignoring tension zone)", "Pa = ∫σa dz", "", f"Pa = {fmt(Pa)} kN/m acting {fmt(ybar)} m above base")
    pp = Kp * sv + 2 * c * math.sqrt(Kp)
    Pp = 0.5 * Kp * gamma * H**2 + 2 * c * math.sqrt(Kp) * H + Kp * q * H
    r.add("Passive thrust (full height)", "Pp = ½Kp·γ·H² + 2c√Kp·H + Kp·q·H", "", f"Pp = {fmt(Pp)} kN/m")
    r.outputs = dict(Ka=Ka, Kp=Kp, Pa=Pa, ybar=ybar, Pp=Pp, z=z, pa=pa_pos, pp=pp, H=H)
    return r


# ------------------------------------------------------------------ consolidation
def consolidation(H, e0, Cc, s0, ds, Cs=None, sp=None, cv=None, t=None, drainage=2) -> Result:
    """H layer thickness (m), s0 initial effective stress at mid-layer (kPa), ds increase (kPa), sp preconsolidation."""
    r = Result("consol", "Primary consolidation settlement",
               inputs=dict(H=f"{fmt(H)} m", e0=fmt(e0), Cc=fmt(Cc), Cs=fmt(Cs) if Cs else "-", σ0=f"{fmt(s0)} kPa", Δσ=f"{fmt(ds)} kPa",
                           σp=f"{fmt(sp)} kPa" if sp else "NC"))
    s1 = s0 + ds
    if not sp or sp <= s0:
        S = Cc * H / (1 + e0) * math.log10(s1 / s0)
        r.add("Normally consolidated clay", "Sc = Cc·H/(1+e0)·log(σ1/σ0)", f"{fmt(Cc)}×{fmt(H)}/(1+{fmt(e0)})·log({fmt(s1)}/{fmt(s0)})", f"Sc = {fmt(S*1000, 2)} mm")
    else:
        Cs = Cs or Cc / 6
        if s1 <= sp:
            S = Cs * H / (1 + e0) * math.log10(s1 / s0)
            r.add("Over-consolidated (σ1 ≤ σp)", "Sc = Cs·H/(1+e0)·log(σ1/σ0)", "", f"Sc = {fmt(S*1000, 2)} mm")
        else:
            S = Cs * H / (1 + e0) * math.log10(sp / s0) + Cc * H / (1 + e0) * math.log10(s1 / sp)
            r.add("Over-consolidated (σ1 > σp)", "Sc = Cs·H/(1+e0)·log(σp/σ0) + Cc·H/(1+e0)·log(σ1/σp)", f"OCR = {fmt(sp/s0, 3)}", f"Sc = {fmt(S*1000, 2)} mm")
    out = dict(S=S)
    if cv:
        Hdr = H / drainage
        Ts = np.linspace(0, 2, 400)
        U = np.where(Ts < 0.217, np.sqrt(4 * Ts / math.pi), 1 - 10 ** (-(Ts + 0.085) / 0.933))
        t90 = 0.848 * Hdr**2 / cv
        t50 = 0.197 * Hdr**2 / cv
        r.add("Time rate (Terzaghi 1-D)", "t = Tv·Hdr²/cv ; T50 = 0.197 , T90 = 0.848", f"Hdr = {fmt(Hdr)} m , cv = {fmt(cv)} m²/yr",
              f"t50 = {fmt(t50, 3)} yr , t90 = {fmt(t90, 3)} yr")
        out.update(Ts=Ts, U=U, Hdr=Hdr, cv=cv)
        if t:
            Tv = cv * t / Hdr**2
            Uv = math.sqrt(4 * Tv / math.pi) if Tv < 0.217 else 1 - 10 ** (-(Tv + 0.085) / 0.933)
            Uv = min(Uv, 1.0)
            r.add(f"Settlement after t = {fmt(t)} yr", "Tv = cv·t/Hdr² → U", f"Tv = {fmt(Tv, 4)}", f"U = {fmt(Uv*100, 2)} % → S(t) = {fmt(Uv*S*1000, 2)} mm")
    r.outputs = out
    return r


# ------------------------------------------------------------------ Boussinesq
def _rect_corner(q, B, L, z):
    """Stress under corner of uniformly loaded rectangle (Newmark)."""
    if z <= 0:
        return q / 4
    m, n = B / z, L / z
    m2, n2 = m * m, n * n
    V = m2 + n2 + 1
    a = 2 * m * n * math.sqrt(V) / (V + m2 * n2)
    t = math.atan(2 * m * n * math.sqrt(V) / (V - m2 * n2))
    if V < m2 * n2:
        t += math.pi
    return q / (4 * math.pi) * (a * (V + 1) / V + t)


def stress_rect(q, B, L, x, y, z):
    """Vertical stress at (x, y, z) below a rectangle centred at origin (superposition)."""
    xs = (x + B / 2, B / 2 - x)
    ys = (y + L / 2, L / 2 - y)
    s = 0.0
    for bx in xs:
        for ly in ys:
            sg = (1 if bx >= 0 else -1) * (1 if ly >= 0 else -1)
            s += sg * _rect_corner(q, abs(bx), abs(ly), z)
    return s


def boussinesq(q, B, L=None, zmax=None) -> Result:
    L = L or B
    zmax = zmax or 3 * B
    r = Result("bous", "Stress distribution below a footing (Boussinesq / Newmark)",
               inputs=dict(q=f"{fmt(q)} kPa", B=f"{fmt(B)} m", L=f"{fmt(L)} m"))
    zs = [B / 2, B, 1.5 * B, 2 * B, 3 * B]
    vals = [stress_rect(q, B, L, 0, 0, z) for z in zs]
    r.add("Vertical stress below centre", "Δσz = 4·q·I(m, n) ; m = (B/2)/z , n = (L/2)/z", "",
          " , ".join(f"z={fmt(z, 2)}: {fmt(v, 2)} ({fmt(v/q*100, 1)}%)" for z, v in zip(zs, vals)))
    z10 = next((z for z in np.linspace(0.05, 10 * B, 2000) if stress_rect(q, B, L, 0, 0, z) <= 0.1 * q), None)
    r.add("Depth of influence (Δσ = 10% q)", "", "", f"≈ {fmt(z10, 2)} m ({fmt(z10/B, 2)}B)")
    X = np.linspace(-1.5 * B, 1.5 * B, 61)
    Z = np.linspace(0.02, zmax, 61)
    G = np.array([[stress_rect(q, B, L, x, 0, z) / q for x in X] for z in Z])
    r.outputs = dict(X=X, Z=Z, G=G, B=B, L=L, q=q, z10=z10)
    return r


# ------------------------------------------------------------------ slope stability
def bishop(H, beta, c, phi, gamma, ru=0.0, n_slices=30, grid=14) -> Result:
    """Homogeneous simple slope, Bishop simplified, grid search of circles through the toe region."""
    if not 5 < beta < 80:
        raise InputError("زاوية الميل β لازم بين 5° و 80°")
    r = Result("slope", "Slope stability (Bishop simplified, circular slip)",
               inputs=dict(H=f"{fmt(H)} m", β=f"{fmt(beta)}°", c=f"{fmt(c)} kPa", φ=f"{fmt(phi)}°", γ=f"{fmt(gamma)} kN/m³", ru=fmt(ru)))
    Lx = H / math.tan(rad(beta))
    toe, crest = (0.0, 0.0), (Lx, H)

    def ground(x):
        return np.where(x <= 0, 0.0, np.where(x >= Lx, H, x * math.tan(rad(beta))))

    tp = math.tan(rad(phi))

    def fs_circle(xc, yc, R):
        # intersections with ground
        xs = np.linspace(-3 * H, Lx + 4 * H, 3000)
        yb = yc - np.sqrt(np.maximum(R**2 - (xs - xc)**2, 0))
        inside = (np.abs(xs - xc) < R) & (yb < ground(xs) - 1e-6)
        if inside.sum() < 5:
            return None
        xi = xs[inside]
        x1, x2 = xi.min(), xi.max()
        if x2 - x1 < 0.2 * H or x2 < Lx * 0.5:
            return None
        edges = np.linspace(x1, x2, n_slices + 1)
        xm = (edges[:-1] + edges[1:]) / 2
        b = np.diff(edges)
        ybase = yc - np.sqrt(np.maximum(R**2 - (xm - xc)**2, 1e-12))
        h = np.maximum(ground(xm) - ybase, 0)
        W = gamma * b * h
        alpha = np.arcsin(np.clip((xm - xc) / R, -0.999, 0.999))
        u = ru * gamma * h
        drive = np.sum(W * np.sin(alpha))
        if drive <= 1e-6:
            return None
        F = 1.5
        for _ in range(60):
            ma = np.cos(alpha) * (1 + np.tan(alpha) * tp / F)
            if np.any(ma <= 0.05):
                return None
            Fn = np.sum((c * b + (W - u * b) * tp) / ma) / drive
            if abs(Fn - F) < 1e-5:
                break
            F = Fn
        return F, (x1, x2)
    best = None
    for xc in np.linspace(-0.5 * H, Lx + 0.5 * H, grid):
        for yc in np.linspace(H * 1.05, 3 * H, grid):
            for depth in np.linspace(0, 0.6 * H, 6):
                R = math.hypot(xc - 0, yc - (-depth))  # through point below toe
                res = fs_circle(xc, yc, R)
                if res and (best is None or res[0] < best[0]):
                    best = (res[0], xc, yc, R, res[1])
    if not best:
        raise InputError("ما لقيت دائرة انهيار صالحة. راجع الأبعاد")
    F, xc, yc, R, (x1, x2) = best
    # refine around best
    for _ in range(3):
        d = 0.15 * H
        for dx in np.linspace(-d, d, 5):
            for dy in np.linspace(-d, d, 5):
                for dR in np.linspace(-d, d, 5):
                    res = fs_circle(xc + dx, yc + dy, R + dR)
                    if res and res[0] < best[0]:
                        best = (res[0], xc + dx, yc + dy, R + dR, res[1])
        F, xc, yc, R, (x1, x2) = best
    Nc = c / (gamma * H) if c else 0
    r.add("Method", "F = Σ[c'b + (W − ub)tanφ'] / mα ÷ ΣW·sinα ; mα = cosα(1 + tanα·tanφ'/F)", f"{n_slices} slices, iterative",
          "grid search over centres & radii")
    r.add("Critical slip circle", "", f"centre = ({fmt(xc, 2)}, {fmt(yc, 2)}) m , R = {fmt(R, 2)} m", f"exits at x = {fmt(x1, 2)} → {fmt(x2, 2)} m")
    r.add("Minimum factor of safety", "FS ≥ 1.5 (static, long-term)", f"stability number c/γH = {fmt(Nc, 4)}", f"FS = {fmt(F, 3)} {'✔' if F >= 1.5 else '✘'}")
    if F < 1.5:
        r.warnings.append("معامل الأمان أقل من 1.5: خفف الميل أو أضف تدعيم/تصريف")
    r.outputs = dict(FS=F, xc=xc, yc=yc, R=R, x1=x1, x2=x2, H=H, Lx=Lx, beta=beta)
    return r
