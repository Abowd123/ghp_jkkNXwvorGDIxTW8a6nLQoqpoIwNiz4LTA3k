"""Influence lines (by moving a unit load across the beam engine) and moving-load envelopes."""
from __future__ import annotations
import numpy as np
from ..core import Result, InputError, fmt
from . import beam as bm


def _effect(beam, a, qty, x0, k_support):
    b = bm.Beam(beam.L, beam.supports, [bm.PointLoad(1.0, a)], [], [], beam.EI)
    res = bm.analyze(b, n_el=120)
    if qty == "R":
        return res.reactions[k_support]["Ry"]
    i = int(np.argmin(np.abs(res.x - x0)))
    # pick the right side value of a discontinuity for V when load is exactly at x0
    if qty == "V":
        j = np.searchsorted(res.x, x0 + 1e-6 * beam.L)
        return float(res.V[min(j, len(res.x) - 1)])
    return float(np.interp(x0, res.x, res.M))


def influence(beam: bm.Beam, qty="M", x0=None, support=1, axles=None, w=None, npts=81) -> Result:
    qty = qty.upper()
    if qty not in ("R", "V", "M"):
        raise InputError("qty = R / V / M")
    beam.validate() if beam.points or beam.dists else None
    L = beam.L
    sups = sorted(beam.supports, key=lambda s: s.x)
    if qty == "R" and not 1 <= support <= len(sups):
        raise InputError("رقم الركيزة غير موجود")
    x0 = L / 2 if x0 is None else x0
    xs = np.linspace(0, L, npts)
    if qty in ("V", "M"):
        xs = np.unique(np.concatenate([xs, [max(0, x0 - 1e-4 * L), min(L, x0 + 1e-4 * L)]]))
    il = np.array([_effect(beam, a, qty, x0, support - 1) for a in xs])
    name = {"R": f"reaction R{support} (x = {fmt(sups[support-1].x)} m)", "V": f"shear at x = {fmt(x0)} m", "M": f"moment at x = {fmt(x0)} m"}[qty]
    r = Result("influence", f"Influence line for {name}", inputs=dict(L=f"{fmt(L)} m", supports=", ".join(f"{s.kind}@{fmt(s.x)}" for s in sups),
                                                                      quantity=name))
    r.add("Method", "Müller-Breslau principle / moving unit load (stiffness solution for each position)", f"{npts} load positions", "")
    imax, imin = int(np.argmax(il)), int(np.argmin(il))
    r.add("Ordinates", "", "", f"max = {fmt(il[imax], 4)} @ {fmt(xs[imax], 2)} m , min = {fmt(il[imin], 4)} @ {fmt(xs[imin], 2)} m")
    pos_area = float(np.trapezoid(np.maximum(il, 0), xs)) if hasattr(np, "trapezoid") else float(np.trapz(np.maximum(il, 0), xs))
    neg_area = float(np.trapezoid(np.minimum(il, 0), xs)) if hasattr(np, "trapezoid") else float(np.trapz(np.minimum(il, 0), xs))
    r.add("Areas under the influence line", "∫IL dx", "", f"positive = {fmt(pos_area, 4)} , negative = {fmt(neg_area, 4)}")
    out = dict(xs=xs, il=il, qty=qty, x0=x0, L=L, name=name, supports=[(s.kind, s.x) for s in sups])
    if w:
        r.add(f"Max effect of UDL w = {fmt(w)} kN/m (pattern loading)", "max+ = w·A+ ; max− = w·A−", "",
              f"+{fmt(w * pos_area, 2)} / {fmt(w * neg_area, 2)}")
        out["w"] = w
    if axles:
        offs = np.cumsum([0] + [d for _, d in axles[:-1]])
        loads = [P for P, _ in axles]
        span = offs[-1]
        best_p, best_n = (-1e18, 0), (1e18, 0)
        for lead in np.linspace(0, L + span, 300):
            tot = 0.0
            for P, o in zip(loads, offs):
                xa = lead - o
                if 0 <= xa <= L:
                    tot += P * np.interp(xa, xs, il)
            if tot > best_p[0]: best_p = (tot, lead)
            if tot < best_n[0]: best_n = (tot, lead)
        r.add("Moving axle train", "Σ Pi·yi maximised over all positions",
              "axles: " + " — ".join(f"{fmt(P)} kN" for P in loads) + " ; spacings " + ", ".join(fmt(d) for _, d in axles[:-1]) + " m",
              f"max = {fmt(best_p[0], 2)} (lead axle at {fmt(best_p[1], 2)} m) , min = {fmt(best_n[0], 2)}")
        out.update(axles=(loads, list(offs)), best=best_p)
    r.outputs = out
    return r
