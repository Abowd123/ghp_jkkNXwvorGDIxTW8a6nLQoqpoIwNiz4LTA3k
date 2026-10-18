"""2D frame & truss analysis by the direct stiffness method.

Frame: 3 DOF/node (ux, uy, rz), Euler-Bernoulli members with optional end
hinges (static condensation), nodal loads and gravity UDL on members.
Truss: 2 DOF/node, axial bars only.
Units: kN, m (E in kN/m², A in m², I in m⁴).
Signs: N tension +, M sagging + (looking from local -y side; for left->right
beams this is the usual sagging), member local x from node i to node j.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math
import numpy as np
from ..core import InputError

SUPPORT_DOFS = {"pin": (1, 1, 0), "hinge": (1, 1, 0), "roller": (0, 1, 0), "rollery": (0, 1, 0),
                "rollerx": (1, 0, 0), "fixed": (1, 1, 1), "free": (0, 0, 0)}


@dataclass
class Member:
    i: int
    j: int
    E: float = 200e6
    A: float = 0.01
    I: float = 1e-4
    hinge_i: bool = False
    hinge_j: bool = False
    w: float = 0.0          # gravity load per member length (downward +), kN/m


@dataclass
class Model:
    nodes: list[tuple[float, float]]
    members: list[Member]
    supports: dict[int, str] = field(default_factory=dict)
    loads: dict[int, tuple[float, float, float]] = field(default_factory=dict)  # Fx, Fy (up +), Mz (ccw +)

    def validate(self, truss=False):
        n = len(self.nodes)
        if n < 2 or not self.members:
            raise InputError("لازم عقدتين وعضو واحد على الأقل")
        for k, m in enumerate(self.members, 1):
            if not (0 <= m.i < n and 0 <= m.j < n) or m.i == m.j:
                raise InputError(f"العضو {k} يربط عقد غير موجودة")
            if self._len(m) < 1e-9:
                raise InputError(f"العضو {k} طوله صفر")
        for nd in list(self.supports) + list(self.loads):
            if not 0 <= nd < n:
                raise InputError(f"العقدة {nd + 1} غير موجودة")
        for s in self.supports.values():
            if s not in SUPPORT_DOFS:
                raise InputError(f"نوع ركيزة غير معروف: {s}")
        if not self.supports:
            raise InputError("ما في ركائز")

    def _len(self, m):
        (x1, y1), (x2, y2) = self.nodes[m.i], self.nodes[m.j]
        return math.hypot(x2 - x1, y2 - y1)

    def geom(self, m):
        (x1, y1), (x2, y2) = self.nodes[m.i], self.nodes[m.j]
        L = math.hypot(x2 - x1, y2 - y1)
        return L, (x2 - x1) / L, (y2 - y1) / L


def _singular(Kff) -> bool:
    if Kff.size == 0:
        return False
    d = np.sqrt(np.abs(np.diag(Kff)))
    if np.any(d < 1e-14):
        return True
    Ks = Kff / np.outer(d, d)
    return np.linalg.matrix_rank(Ks, tol=1e-10) < Kff.shape[0]


def _T(c, s):
    t = np.zeros((6, 6))
    r = np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])
    t[:3, :3] = r
    t[3:, 3:] = r
    return t


def _k_local(E, A, I, L):
    a, b, c, d = E * A / L, 12 * E * I / L**3, 6 * E * I / L**2, E * I / L
    return np.array([[a, 0, 0, -a, 0, 0], [0, b, c, 0, -b, c], [0, c, 4 * d, 0, -c, 2 * d],
                     [-a, 0, 0, a, 0, 0], [0, -b, -c, 0, b, -c], [0, c, 2 * d, 0, -c, 4 * d]])


def _member_local(model, m):
    L, c, s = model.geom(m)
    k = _k_local(m.E, m.A, m.I, L)
    qx, qy = -m.w * s, -m.w * c        # gravity load in local axes
    f = np.array([qx * L / 2, qy * L / 2, qy * L**2 / 12, qx * L / 2, qy * L / 2, -qy * L**2 / 12])
    rel = [d for d, h in ((2, m.hinge_i), (5, m.hinge_j)) if h]
    if rel:
        keep = [d for d in range(6) if d not in rel]
        krr = k[np.ix_(rel, rel)]
        kkr = k[np.ix_(keep, rel)]
        inv = np.linalg.inv(krr)
        kc = np.zeros((6, 6))
        kc[np.ix_(keep, keep)] = k[np.ix_(keep, keep)] - kkr @ inv @ kkr.T
        fc = np.zeros(6)
        fc[keep] = f[keep] - kkr @ inv @ f[rel]
        k, f = kc, fc
    return k, f, L, c, s, qx, qy


@dataclass
class FrameResult:
    model: Model
    disp: np.ndarray
    reactions: dict
    end_forces: list           # local [Ni, Vi, Mi, Nj, Vj, Mj] (forces ON member)
    stations: list             # per member: (xs, N, V, M, defl_local_y)


def analyze_frame(model: Model) -> FrameResult:
    model.validate()
    n = len(model.nodes)
    ndof = 3 * n
    K = np.zeros((ndof, ndof))
    F = np.zeros(ndof)
    cache = []
    for m in model.members:
        k, f, L, c, s, qx, qy = _member_local(model, m)
        T = _T(c, s)
        kg = T.T @ k @ T
        fg = T.T @ f
        idx = [3 * m.i, 3 * m.i + 1, 3 * m.i + 2, 3 * m.j, 3 * m.j + 1, 3 * m.j + 2]
        K[np.ix_(idx, idx)] += kg
        F[idx] += fg
        cache.append((k, f, L, c, s, qx, qy, T, idx))
    for nd, (fx, fy, mz) in model.loads.items():
        F[3 * nd:3 * nd + 3] += (fx, fy, mz)
    fixed = []
    for nd, kind in model.supports.items():
        for dof, flag in enumerate(SUPPORT_DOFS[kind]):
            if flag:
                fixed.append(3 * nd + dof)
    # rotational dofs with no stiffness (all members hinged at node, no support) -> fix
    for nd in range(n):
        d = 3 * nd + 2
        if d not in fixed and abs(K[d, d]) < 1e-12:
            fixed.append(d)
    fixed = sorted(set(fixed))
    free = [d for d in range(ndof) if d not in fixed]
    Kff = K[np.ix_(free, free)]
    if _singular(Kff):
        raise InputError("المنشأ غير مستقر (Mechanism): زد الركائز أو قلل المفصلات")
    U = np.zeros(ndof)
    if free:
        U[free] = np.linalg.solve(Kff, F[free])
    R = K @ U - F
    reactions = {}
    for nd, kind in model.supports.items():
        reactions[nd] = tuple(float(R[3 * nd + d]) if SUPPORT_DOFS[kind][d] else 0.0 for d in range(3))
    end_forces, stations = [], []
    for m, (k, f, L, c, s, qx, qy, T, idx) in zip(model.members, cache):
        ul = T @ U[idx]
        fe = k @ ul - f
        end_forces.append(fe)
        xs = np.linspace(0, L, 41)
        N = -fe[0] - qx * xs
        V = fe[1] + qy * xs
        M = -fe[2] + fe[1] * xs + qy * xs**2 / 2
        # local transverse deflection: cubic Hermite of end displacements (rotations from
        # condensed ends recovered via slope compatibility) + particular UDL part
        thi, thj = ul[2], ul[5]
        if m.hinge_i or m.hinge_j:
            # recover true end rotations from end moments = 0 using full stiffness
            kf = _k_local(m.E, m.A, m.I, L)
            ff = np.array([qx * L / 2, qy * L / 2, qy * L**2 / 12, qx * L / 2, qy * L / 2, -qy * L**2 / 12])
            rel = [d for d, h in ((2, m.hinge_i), (5, m.hinge_j)) if h]
            keep = [d for d in range(6) if d not in rel]
            sol = np.linalg.solve(kf[np.ix_(rel, rel)], ff[rel] - kf[np.ix_(rel, keep)] @ ul[keep])
            ul2 = ul.copy(); ul2[rel] = sol
            thi, thj = ul2[2], ul2[5]
        xi = xs / L
        H1, H2 = 1 - 3 * xi**2 + 2 * xi**3, L * (xi - 2 * xi**2 + xi**3)
        H3, H4 = 3 * xi**2 - 2 * xi**3, L * (-xi**2 + xi**3)
        v = H1 * ul[1] + H2 * thi + H3 * ul[4] + H4 * thj + qy * xs**2 * (L - xs)**2 / (24 * m.E * m.I)
        u = ul[0] + (ul[3] - ul[0]) * xi
        stations.append((xs, N, V, M, u, v))
    return FrameResult(model, U, reactions, end_forces, stations)


# ----------------------------- truss -----------------------------
@dataclass
class TrussResult:
    model: Model
    disp: np.ndarray
    forces: list[float]        # tension +
    reactions: dict
    status: list[str]          # T / C / 0
    determinacy: tuple         # (m, r, j, degree)


def analyze_truss(model: Model) -> TrussResult:
    model.validate(truss=True)
    n = len(model.nodes)
    K = np.zeros((2 * n, 2 * n))
    F = np.zeros(2 * n)
    geo = []
    for m in model.members:
        L, c, s = model.geom(m)
        k = m.E * m.A / L * np.outer([-c, -s, c, s], [-c, -s, c, s])
        idx = [2 * m.i, 2 * m.i + 1, 2 * m.j, 2 * m.j + 1]
        K[np.ix_(idx, idx)] += k
        geo.append((L, c, s, idx))
    for nd, ld in model.loads.items():
        F[2 * nd] += ld[0]
        F[2 * nd + 1] += ld[1]
    fixed = []
    r = 0
    for nd, kind in model.supports.items():
        dofs = SUPPORT_DOFS["pin" if kind == "fixed" else kind]
        for d in range(2):
            if dofs[d]:
                fixed.append(2 * nd + d); r += 1
    free = [d for d in range(2 * n) if d not in fixed]
    Kff = K[np.ix_(free, free)]
    mcount = len(model.members)
    degree = mcount + r - 2 * n
    if _singular(Kff):
        raise InputError(f"الجمالون غير مستقر: m + r = {mcount + r} و 2j = {2 * n}. "
                         "أضف أعضاء أو ركائز (أو فيه عقدة حرة الحركة)")
    U = np.zeros(2 * n)
    if free:
        U[free] = np.linalg.solve(Kff, F[free])
    R = K @ U - F
    forces, status = [], []
    fmax = 0
    for m, (L, c, s, idx) in zip(model.members, geo):
        u = U[idx]
        N = m.E * m.A / L * ((u[2] - u[0]) * c + (u[3] - u[1]) * s)
        forces.append(float(N)); fmax = max(fmax, abs(N))
    tol = 1e-6 * max(fmax, 1e-9)
    forces = [0.0 if abs(f) < tol else f for f in forces]
    status = ["0" if f == 0 else ("T" if f > 0 else "C") for f in forces]
    reactions = {nd: (float(R[2 * nd]) if (2 * nd) in fixed else 0.0, float(R[2 * nd + 1]) if (2 * nd + 1) in fixed else 0.0)
                 for nd in model.supports}
    return TrussResult(model, U, forces, reactions, status, (mcount, r, n, degree))
