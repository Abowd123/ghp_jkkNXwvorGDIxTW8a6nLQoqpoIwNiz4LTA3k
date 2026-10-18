"""Beam analysis: simple, cantilever, overhanging and continuous beams.

Method: Hermitian Euler-Bernoulli beam FEM for reactions & deflections (exact at
nodes), then exact statics for V(x), M(x).
Conventions (input): downward loads positive, applied moments clockwise positive.
Output: reactions upward +, reaction moments counter-clockwise +,
V positive = left part pushed up, M sagging positive.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
from ..core import InputError


@dataclass
class Support:
    kind: str   # pin | roller | fixed
    x: float


@dataclass
class PointLoad:
    P: float
    a: float


@dataclass
class DistLoad:
    w1: float
    w2: float
    a: float
    b: float


@dataclass
class MomentLoad:
    M: float
    a: float


@dataclass
class Beam:
    L: float
    supports: list[Support] = field(default_factory=list)
    points: list[PointLoad] = field(default_factory=list)
    dists: list[DistLoad] = field(default_factory=list)
    moments: list[MomentLoad] = field(default_factory=list)
    EI: float = 1.0e5   # kN.m2

    def validate(self):
        if self.L <= 0:
            raise InputError("طول الكمرة لازم يكون أكبر من صفر")
        if not self.supports:
            raise InputError("ما في ركائز. أضف مثلاً S=pin@0 S=roller@L")
        for s in self.supports:
            if s.kind not in ("pin", "roller", "fixed"):
                raise InputError(f"نوع ركيزة غير معروف: {s.kind}")
            if not 0 <= s.x <= self.L:
                raise InputError(f"الركيزة عند {s.x} خارج طول الكمرة")
        for p in self.points:
            if not 0 <= p.a <= self.L:
                raise InputError(f"الحمل المركز عند {p.a} خارج الكمرة")
        for d in self.dists:
            if not (0 <= d.a < d.b <= self.L):
                raise InputError(f"الحمل الموزع من {d.a} إلى {d.b} غير صحيح")
        for m in self.moments:
            if not 0 <= m.a <= self.L:
                raise InputError(f"العزم المركز عند {m.a} خارج الكمرة")
        if self.EI <= 0:
            raise InputError("EI لازم يكون موجب")


@dataclass
class BeamResult:
    x: np.ndarray
    V: np.ndarray
    M: np.ndarray
    defl: np.ndarray          # m (upward +)
    reactions: list[dict]
    key_x: list[float]
    beam: Beam

    @property
    def Vmax(self):
        i = int(np.argmax(np.abs(self.V)))
        return self.V[i], self.x[i]

    @property
    def Mmax_pos(self):
        i = int(np.argmax(self.M))
        return self.M[i], self.x[i]

    @property
    def Mmax_neg(self):
        i = int(np.argmin(self.M))
        return self.M[i], self.x[i]

    @property
    def dmax(self):
        i = int(np.argmax(np.abs(self.defl)))
        return self.defl[i], self.x[i]

    def inflection_points(self):
        pts = []
        M, x = self.M, self.x
        tol = 1e-6 * max(1.0, np.max(np.abs(M)))
        for i in range(len(x) - 1):
            if (M[i] > tol and M[i + 1] < -tol) or (M[i] < -tol and M[i + 1] > tol):
                xi = x[i] - M[i] * (x[i + 1] - x[i]) / (M[i + 1] - M[i])
                near_moment = any(abs(xi - m.a) < 1e-4 * self.beam.L for m in self.beam.moments)
                if 1e-6 < xi < self.beam.L - 1e-6 and not near_moment:
                    pts.append(float(xi))
        return pts


def _w_at(d: DistLoad, s: float) -> float:
    return d.w1 + (d.w2 - d.w1) * (s - d.a) / (d.b - d.a)


def analyze(beam: Beam, n_el: int = 400) -> BeamResult:
    beam.validate()
    L = beam.L
    key = {0.0, L}
    key |= {s.x for s in beam.supports}
    key |= {p.a for p in beam.points}
    key |= {m.a for m in beam.moments}
    for d in beam.dists:
        key |= {d.a, d.b}
    key = sorted(key)
    grid = set(np.linspace(0, L, n_el + 1).tolist()) | set(key)
    nodes = np.array(sorted(grid))
    # merge near-duplicate nodes
    keep = [nodes[0]]
    for v in nodes[1:]:
        if v - keep[-1] > 1e-9 * L:
            keep.append(v)
    nodes = np.array(keep)
    nn = len(nodes)
    ndof = 2 * nn
    K = np.zeros((ndof, ndof))
    F = np.zeros(ndof)
    EI = beam.EI
    for e in range(nn - 1):
        x1, x2 = nodes[e], nodes[e + 1]
        le = x2 - x1
        k = EI / le**3 * np.array([
            [12, 6 * le, -12, 6 * le],
            [6 * le, 4 * le**2, -6 * le, 2 * le**2],
            [-12, -6 * le, 12, -6 * le],
            [6 * le, 2 * le**2, -6 * le, 4 * le**2]])
        idx = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        K[np.ix_(idx, idx)] += k
        # distributed loads (consistent), upward q = -w
        for d in beam.dists:
            if x1 >= d.a - 1e-12 and x2 <= d.b + 1e-12:
                q1, q2 = -_w_at(d, x1), -_w_at(d, x2)
                fe = np.array([le * (7 * q1 + 3 * q2) / 20,
                               le**2 * (3 * q1 + 2 * q2) / 60,
                               le * (3 * q1 + 7 * q2) / 20,
                               -le**2 * (2 * q1 + 3 * q2) / 60])
                F[idx] += fe

    def node_of(xv):
        i = int(np.argmin(np.abs(nodes - xv)))
        return i
    for p in beam.points:
        F[2 * node_of(p.a)] -= p.P
    for m in beam.moments:
        F[2 * node_of(m.a) + 1] -= m.M   # clockwise -> negative ccw
    fixed = set()
    for s in beam.supports:
        i = node_of(s.x)
        fixed.add(2 * i)
        if s.kind == "fixed":
            fixed.add(2 * i + 1)
    free = [i for i in range(ndof) if i not in fixed]
    Kff = K[np.ix_(free, free)]
    msg = ("الكمرة غير مستقرة (Unstable): الركائز غير كافية لمنع الحركة. "
           "مثلاً كمرة عليها رولر فقط أو ركيزة واحدة مفصلية.")
    # cheap stability check: vertical restraint count + rotation restraint
    n_v = len(fixed & set(range(0, ndof, 2)))
    n_r = len(fixed & set(range(1, ndof, 2)))
    if n_v + n_r < 2 or n_v < 1:
        raise InputError(msg)
    try:
        dfree = np.linalg.solve(Kff, F[free])
    except np.linalg.LinAlgError:
        raise InputError(msg)
    scale = (np.sum(np.abs(F)) + 1e-9) * L**3 / EI
    if not np.all(np.isfinite(dfree)) or np.max(np.abs(dfree)) > 1e6 * scale + 1e-6 or \
            np.linalg.norm(Kff @ dfree - F[free]) > 1e-6 * np.linalg.norm(F[free]) + 1e-9 * np.abs(Kff).max() * np.abs(dfree).max() + 1e-9:
        raise InputError(msg)
    d = np.zeros(ndof)
    d[free] = dfree
    R = K @ d - F
    reactions = []
    for s in sorted(beam.supports, key=lambda s: s.x):
        i = node_of(s.x)
        r = {"kind": s.kind, "x": s.x, "Ry": float(R[2 * i])}
        if s.kind == "fixed":
            r["Mr"] = float(R[2 * i + 1])
        reactions.append(r)

    # exact statics sampling, with points just before/after each key point
    eps = 1e-7 * L
    xs = set(np.linspace(0, L, 801).tolist())
    for k in key:
        xs |= {max(0.0, k - eps), min(L, k + eps)}
    xs = np.array(sorted(xs))
    V = np.zeros_like(xs)
    M = np.zeros_like(xs)
    for j, x in enumerate(xs):
        v = m = 0.0
        for r in reactions:
            if r["x"] < x - 1e-12 or (r["x"] <= 1e-12 and x > 0):
                v += r["Ry"]
                m += r["Ry"] * (x - r["x"])
                m -= r.get("Mr", 0.0)
        for p in beam.points:
            if p.a < x - 1e-12 or (p.a <= 1e-12 and x > 0):
                v -= p.P
                m -= p.P * (x - p.a)
        for mm in beam.moments:
            if mm.a < x - 1e-12 or (mm.a <= 1e-12 and x > 0):
                m += mm.M
        for dl in beam.dists:
            if x > dl.a:
                c = min(dl.b, x)
                Ls = c - dl.a
                wc = _w_at(dl, c)
                kk = (wc - dl.w1) / Ls if Ls > 0 else 0.0
                force = (dl.w1 + wc) / 2 * Ls
                v -= force
                m -= (x - dl.a) * (dl.w1 * Ls + kk * Ls**2 / 2) - (dl.w1 * Ls**2 / 2 + kk * Ls**3 / 3)
        V[j] = v
        M[j] = m
    for arr in (V, M):
        arr[np.abs(arr) < 1e-7 * (np.max(np.abs(arr)) + 1e-12)] = 0.0
    for r in reactions:
        for k in ("Ry", "Mr"):
            if k in r:
                r[k] = round(r[k], 6)
    defl = np.interp(xs, nodes, d[0::2])
    return BeamResult(x=xs, V=V, M=M, defl=defl, reactions=reactions, key_x=key, beam=beam)
