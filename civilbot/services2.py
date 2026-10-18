"""Phase-2 services: text parsing -> engines -> Result (images + DXF/XLSX files)."""
from __future__ import annotations
import re
import math
from .core import Result, InputError, fmt
from .engines import frame as fr, rc_column, slab, footing as ft, retaining, loads, bbs, rc_beam
from .drawing import plots2 as P2, dxf
from .services import NUM


def _params(text):
    return {k.lower(): v for k, v in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^\s]+)", text)}


def _f(p, k, default=None, req=True):
    if k in p:
        try:
            return float(p[k])
        except ValueError:
            raise InputError(f"قيمة غير رقمية لـ {k}: {p[k]}")
    if default is None and req:
        raise InputError(f"ناقص {k}")
    return default


def _list(s):
    return [x for x in s.strip(";").split(";") if x]


def _nodes(p):
    if "n" not in p:
        raise InputError("ناقص العقد N=x,y;x,y;...")
    try:
        return [tuple(float(v) for v in t.split(",")) for t in _list(p["n"])]
    except ValueError:
        raise InputError("صيغة العقد: N=0,0;4,0;4,3")


def _members(p, defaults):
    if "m" not in p:
        raise InputError("ناقص الأعضاء M=1-2;2-3;...")
    out = []
    for t in _list(p["m"]):
        m = re.fullmatch(r"(\d+)-(\d+)", t)
        if not m:
            raise InputError(f"صيغة عضو خاطئة: {t}. مثال M=1-2;2-3")
        out.append(fr.Member(int(m.group(1)) - 1, int(m.group(2)) - 1, **defaults))
    return out


def _supports(p):
    if "s" not in p:
        raise InputError("ناقص الركائز S=1:pin;4:roller")
    d = {}
    for t in _list(p["s"]):
        m = re.fullmatch(r"(\d+):([a-z]+)", t, re.I)
        if not m:
            raise InputError(f"صيغة ركيزة خاطئة: {t}. مثال S=1:fixed")
        d[int(m.group(1)) - 1] = m.group(2).lower()
    return d


def _loads(p):
    d = {}
    for t in _list(p.get("f", "")):
        m = re.fullmatch(rf"(\d+):({NUM}),({NUM})(?:,({NUM}))?", t)
        if not m:
            raise InputError(f"صيغة حمل خاطئة: {t}. مثال F=4:0,-50 (Fx,Fy) أو F=2:10,0,5 (Fx,Fy,Mz)")
        d[int(m.group(1)) - 1] = (float(m.group(2)), float(m.group(3)), float(m.group(4) or 0))
    return d


# ---------------------------------------------------------------- truss
TRUSS_HELP = ("<b>🔺 محلل الجمالونات</b>\n<b>جاهز:</b> <code>/truss type=pratt span=12 h=3 n=4 P=40</code>\n"
              "(type = pratt / howe / warren ، P حمل على كل عقدة سفلية)\n\n<b>مخصص:</b>\n"
              "<code>/truss N=0,0;4,0;8,0;4,3 M=1-2;2-3;1-4;4-3;2-4 S=1:pin;3:roller F=4:0,-60</code>\n"
              "• N إحداثيات العقد (m) • M الأعضاء • S ركائز pin/roller/rollerx • F=عقدة:Fx,Fy (kN، لفوق موجب)")


def gen_truss(kind, span, h, n, P):
    if n < 2 or n % 2:
        raise InputError("n لازم زوجي ≥ 2")
    dx = span / n
    bot = [(k * dx, 0.0) for k in range(n + 1)]
    if kind == "warren":
        top = [((k + 0.5) * dx, h) for k in range(n)]
        nodes = bot + top
        T = lambda k: n + 1 + k
        mem = [(k, k + 1) for k in range(n)] + [(T(k), T(k + 1)) for k in range(n - 1)]
        for k in range(n):
            mem += [(k, T(k)), (T(k), k + 1)]
    else:
        top = [(k * dx, h) for k in range(1, n)]
        nodes = bot + top
        T = lambda k: n + k  # top node above bottom k (k=1..n-1)
        mem = [(k, k + 1) for k in range(n)] + [(T(k), T(k + 1)) for k in range(1, n - 1)]
        mem += [(0, T(1)), (n, T(n - 1))]
        mem += [(k, T(k)) for k in range(1, n)]
        half = n // 2
        for k in range(1, n - 1):
            if kind == "pratt":   # diagonals slope down toward the centre (tension)
                mem.append((T(k), k + 1) if k < half else (k, T(k + 1)))
            else:                  # howe
                mem.append((k, T(k + 1)) if k < half else (T(k), k + 1))
    model = fr.Model(nodes, [fr.Member(i, j) for i, j in mem], {0: "pin", n: "roller"},
                     {k: (0.0, -P, 0.0) for k in range(1, n)})
    return model


def run_truss(text) -> Result:
    p = _params(text)
    if "type" in p:
        kind = p["type"].lower()
        if kind not in ("pratt", "howe", "warren"):
            raise InputError("type = pratt / howe / warren")
        model = gen_truss(kind, _f(p, "span"), _f(p, "h"), int(_f(p, "n", 4)), _f(p, "p", 10))
    else:
        model = fr.Model(_nodes(p), _members(p, {}), _supports(p), _loads(p))
    if "e" in p or "a" in p:
        for m in model.members:
            m.E = _f(p, "e", 200e6); m.A = _f(p, "a", 0.002)
    res = fr.analyze_truss(model)
    r = Result("truss", "Truss analysis (direct stiffness method)")
    r.inputs = {"Nodes": len(model.nodes), "Members": len(model.members),
                "Supports": ", ".join(f"{k+1}:{v}" for k, v in model.supports.items()),
                "Loads": ", ".join(f"{k+1}: ({fmt(v[0])}, {fmt(v[1])})" for k, v in model.loads.items())}
    m_, rr, j, deg = res.determinacy
    r.add("Determinacy & stability", "m + r vs 2j", f"m = {m_} , r = {rr} , j = {j} → {m_ + rr} vs {2 * j}",
          "Statically determinate" if deg == 0 else f"Indeterminate to degree {deg} (solved by stiffness)")
    for nd, (rx, ry) in res.reactions.items():
        r.add(f"Reaction at node {nd+1} ({model.supports[nd]})", "", "", f"Rx = {fmt(rx, 3)} kN , Ry = {fmt(ry, 3)} kN")
    rows = []
    for k, (m, f, st) in enumerate(zip(model.members, res.forces, res.status), 1):
        L, _, _ = model.geom(m)
        rows.append(f"{k}: {m.i+1}-{m.j+1}  L={fmt(L, 2)}  F={fmt(f, 3)} kN  {'Tension' if st == 'T' else 'Compression' if st == 'C' else 'ZERO'}")
    r.add("Member forces (tension +)", "\n".join(rows))
    zeros = [str(k) for k, s in enumerate(res.status, 1) if s == "0"]
    if zeros:
        r.add("Zero-force members", "", "", ", ".join(zeros))
    fmax = max(res.forces, key=abs)
    r.outputs = dict(forces=res.forces, status=res.status, reactions=res.reactions, Fmax=fmax)
    r.images["truss"] = P2.truss(res)
    r._res = res
    return r


# ---------------------------------------------------------------- frame
FRAME_HELP = ("<b>🏛 محلل الإطارات 2D</b>\n<b>جاهز:</b> <code>/frame type=portal L=6 H=4 w=15 P=20 base=fixed</code>\n"
              "(P حمل أفقي أعلى العمود الأيسر ، base = fixed / pin ، gable: أضف rise=1.5)\n\n<b>مخصص:</b>\n"
              "<code>/frame N=0,0;0,4;6,4;6,0 M=1-2;2-3;3-4 S=1:fixed;4:fixed W=2:15 F=2:20,0</code>\n"
              "• W=عضو:w حمل جاذبية موزع (kN/m) • F=عقدة:Fx,Fy,Mz\n• hinge=2j (مفصلة في نهاية العضو 2) • E A I (kN/m², m², m⁴)")


def run_frame(text) -> Result:
    p = _params(text)
    E, A, I = _f(p, "e", 25e6), _f(p, "a", 0.12), _f(p, "i", 1.6e-3)
    if p.get("type", "").lower() in ("portal", "gable"):
        L, H = _f(p, "l"), _f(p, "h")
        base = p.get("base", "fixed").lower()
        w, P = _f(p, "w", 0.0), _f(p, "p", 0.0)
        if p["type"].lower() == "gable":
            rise = _f(p, "rise", 1.5)
            nodes = [(0, 0), (0, H), (L / 2, H + rise), (L, H), (L, 0)]
            mem = [(0, 1, 0), (1, 2, w), (2, 3, w), (3, 4, 0)]
            sup = {0: base, 4: base}
        else:
            nodes = [(0, 0), (0, H), (L, H), (L, 0)]
            mem = [(0, 1, 0), (1, 2, w), (2, 3, 0)]
            sup = {0: base, 3: base}
        model = fr.Model(nodes, [fr.Member(i, j, E, A, I, w=ww) for i, j, ww in mem], sup, {1: (P, 0, 0)} if P else {})
    else:
        model = fr.Model(_nodes(p), _members(p, dict(E=E, A=A, I=I)), _supports(p), _loads(p))
        for t in _list(p.get("w", "")):
            m = re.fullmatch(rf"(\d+):({NUM})", t)
            if not m:
                raise InputError("صيغة الحمل الموزع: W=2:15")
            k = int(m.group(1)) - 1
            if not 0 <= k < len(model.members):
                raise InputError(f"العضو {k+1} غير موجود")
            model.members[k].w = float(m.group(2))
        for t in _list(p.get("hinge", "")):
            m = re.fullmatch(r"(\d+)([ij])", t)
            if not m:
                raise InputError("صيغة المفصلة: hinge=2j;3i")
            mm = model.members[int(m.group(1)) - 1]
            setattr(mm, "hinge_" + m.group(2), True)
    res = fr.analyze_frame(model)
    r = Result("frame", "2D frame analysis (direct stiffness method)")
    r.inputs = {"Nodes": len(model.nodes), "Members": len(model.members), "E, A, I": f"{fmt(E)} kN/m², {fmt(A)} m², {fmt(I)} m⁴",
                "Supports": ", ".join(f"{k+1}:{v}" for k, v in model.supports.items())}
    r.add("Method", "[K]{U} = {F} ; member forces = k·u − f_fixed-end", "3 DOF per node, Euler-Bernoulli members", "")
    for nd, (rx, ry, mz) in res.reactions.items():
        r.add(f"Reaction at node {nd+1} ({model.supports[nd]})", "", "", f"Rx = {fmt(rx, 3)} kN , Ry = {fmt(ry, 3)} kN" + (f" , M = {fmt(mz, 3)} kN·m" if mz else ""))
    for k, (m, st) in enumerate(zip(model.members, res.stations), 1):
        xs, N, V, M, u, v = st
        r.add(f"Member {k} ({m.i+1}→{m.j+1})", "", f"N: {fmt(N[0], 2)} → {fmt(N[-1], 2)} kN ; V: {fmt(V[0], 2)} → {fmt(V[-1], 2)} kN",
              f"M: i = {fmt(M[0], 2)} , j = {fmt(M[-1], 2)} , max+ = {fmt(M.max(), 2)} , max− = {fmt(M.min(), 2)} kN·m")
    U = res.disp
    k = max(range(len(model.nodes)), key=lambda n: math.hypot(U[3 * n], U[3 * n + 1]))
    r.add("Maximum nodal displacement", "", "", f"node {k+1}: ux = {fmt(U[3*k]*1000, 3)} mm , uy = {fmt(U[3*k+1]*1000, 3)} mm")
    r.outputs = dict(reactions=res.reactions, Mmax=max(abs(s[3]).max() for s in res.stations))
    r.images["frame"] = P2.frame(res)
    r._res = res
    return r


# ---------------------------------------------------------------- column
COLUMN_HELP = ("<b>🏢 تصميم عمود خرساني + منحنى التفاعل P-M</b>\n<code>/column b=400 h=500 fc=28 fy=420 Pu=1800 Mu=220</code>\n"
               "اختياري للنحافة: <code>lu=3.5 k=1 M1M2=0.5</code> (M1/M2 موجب لانحناء مفرد)\n"
               "اختياري: <code>n=8 db=20</code> لتثبيت التسليح ، <code>cover=40</code> <code>H=3.2</code> (لجدول التفريد)")


def run_column(text) -> Result:
    p = _params(text)
    r = rc_column.design(_f(p, "b"), _f(p, "h"), _f(p, "fc"), _f(p, "fy"), _f(p, "pu"), _f(p, "mu", 0.0),
                         cover=_f(p, "cover", 40.0), lu=_f(p, "lu", None, False), k=_f(p, "k", 1.0),
                         M1M2=_f(p, "m1m2", 1.0), n=int(p["n"]) if "n" in p else None, db=int(float(p["db"])) if "db" in p else None)
    o = r.outputs
    r.images["interaction"] = P2.interaction(o)
    r.images["section"] = P2.column_section(o)
    r.files["column_C1.dxf"] = dxf.column_detail(o)
    bars = bbs.from_column(o, _f(p, "height", _f(p, "lu", 3.2, False) or 3.2, False))
    r.outputs["bbs"] = bars
    return r


# ---------------------------------------------------------------- slabs
SLAB_HELP = ("<b>⬜ تصميم البلاطات</b>\n<b>اتجاه واحد:</b> <code>/slab type=one L=4 wD=2 wL=3 fc=28 fy=420 support=both</code>\n"
             "(support = ss / one / both / cant)\n\n<b>اتجاهين:</b> <code>/slab Lx=4 Ly=5 edges=FSFS wD=2 wL=3 fc=28 fy=420</code>\n"
             "edges = يسار،يمين،أسفل،أعلى (F مستمر/مثبت ، S بسيط) • h اختياري (mm)\n\n"
             "<b>قص ثاقب:</b> <code>/punch c1=400 c2=400 d=200 fc=28 Vu=550 pos=interior</code>")


def run_slab(text) -> Result:
    p = _params(text)
    fc, fy = _f(p, "fc", 28.0), _f(p, "fy", 420.0)
    wD, wL = _f(p, "wd", 1.5), _f(p, "wl", 2.0)
    h = _f(p, "h", 0.0)
    if p.get("type", "").lower() == "one":
        r = slab.one_way(_f(p, "l"), h, fc, fy, wD, wL, support=p.get("support", "ss").lower())
        o = r.outputs
        o["Lx"], o["Ly"] = o["L"], o["L"] * 1.5
        o["bars"] = dict(o["bars"]); o["bars"]["(y) temp"] = o["temp"]
    else:
        Lx, Ly = _f(p, "lx"), _f(p, "ly")
        edges = p.get("edges", "SSSS").upper()
        if not re.fullmatch(r"[SF]{4}", edges):
            raise InputError("edges لازم 4 حروف من S و F مثل FSFS")
        if Lx > Ly:
            Lx, Ly = Ly, Lx
            edges = edges[2:] + edges[:2]
        r = slab.two_way(Lx, Ly, h, fc, fy, wD, wL, edges)
        o = r.outputs
        if o.get("kind") == "two":
            r.images["moments"] = P2.slab_contours(o)
        else:
            o["Lx"], o["Ly"] = o["L"], Ly
    r.files["slab_S1.dxf"] = dxf.slab_detail(o)
    try:
        r.outputs["bbs"] = bbs.from_slab(o)
    except Exception:
        pass
    return r


def run_punch(text) -> Result:
    p = _params(text)
    d = _f(p, "d", None, False)
    h = _f(p, "h", None, False)
    if not d and not h:
        raise InputError("أدخل d أو h")
    d = d or h - 30
    return slab.punching(_f(p, "c1"), _f(p, "c2", _f(p, "c1")), h or d + 30, d, _f(p, "fc"), _f(p, "vu"), p.get("pos", "interior").lower())


# ---------------------------------------------------------------- footing
FOOTING_HELP = ("<b>🟫 تصميم قاعدة منفصلة</b>\n<code>/footing PD=800 PL=500 qa=200 c1=400 c2=400 fc=25 fy=420</code>\n"
                "اختياري: <code>M=60</code> (عزم تشغيلي kN·m) <code>Df=1.5</code> <code>ratio=1.2</code> (L/B) <code>db=16</code>")


def run_footing(text) -> Result:
    p = _params(text)
    r = ft.design(_f(p, "pd"), _f(p, "pl", 0.0), _f(p, "qa"), _f(p, "c1"), _f(p, "c2", _f(p, "c1")), _f(p, "fc", 25.0), _f(p, "fy", 420.0),
                  M=_f(p, "m", 0.0), Df=_f(p, "df", 1.5), ratio=_f(p, "ratio", 1.0), db=int(float(p["db"])) if "db" in p else None)
    o = r.outputs
    r.images["footing"] = P2.footing(o)
    r.files["footing_F1.dxf"] = dxf.footing_detail(o)
    r.outputs["bbs"] = bbs.from_footing(o)
    return r


# ---------------------------------------------------------------- wall
WALL_HELP = ("<b>🧱 جدار ساند كابولي</b>\n<code>/wall H=5 phi=30 gamma=18 q=10 qa=200 fc=28 fy=420</code>\n"
             "اختياري: <code>B=3.5 toe=1.1 tb=0.5 ts=0.45 mu=0.5</code> (وإلا يتم التحجيم تلقائياً)")


def run_wall(text) -> Result:
    p = _params(text)
    r = retaining.design(_f(p, "h"), _f(p, "phi"), _f(p, "gamma", 18.0), _f(p, "q", 0.0), _f(p, "qa", 200.0),
                         mu=_f(p, "mu", None, False), fc=_f(p, "fc", 28.0), fy=_f(p, "fy", 420.0), B=_f(p, "b", None, False),
                         toe=_f(p, "toe", None, False), t_base=_f(p, "tb", None, False), t_bot=_f(p, "ts", None, False))
    o = r.outputs
    r.images["wall"] = P2.wall(o)
    r.files["retaining_wall.dxf"] = dxf.wall_detail(o)
    r.outputs["bbs"] = bbs.from_wall(o)
    return r


# ---------------------------------------------------------------- loads
COMBO_HELP = ("<b>⚖️ تراكيب الأحمال</b>\n<code>/combo D=120 L=80 W=40 code=aci</code>\n"
              "الرموز: D L Lr S W E (قيم موجبة أو سالبة) • code = aci (LRFD) / asd / bs")


def run_combo(text) -> Result:
    p = {k: v for k, v in re.findall(r"([A-Za-z]+)\s*=\s*([^\s]+)", text)}
    code = p.pop("code", "aci")
    vals = {}
    for k, v in p.items():
        key = {"d": "D", "l": "L", "lr": "Lr", "s": "S", "w": "W", "e": "E", "r": "R"}.get(k.lower())
        if not key:
            raise InputError(f"رمز غير معروف: {k}")
        vals[key] = float(v)
    return loads.combinations(vals, code)


TRIB_HELP = ("<b>🧭 مسار الأحمال والمساحات التخديمية</b>\n<code>/trib X=5,6 Y=4,4.5 q=12</code>\n"
             "X أطوال البحور في اتجاه x ، Y في اتجاه y (m) ، q حمل البلاطة (kN/m²)")


def run_trib(text) -> Result:
    p = _params(text)
    try:
        xs = [float(v) for v in p["x"].split(",")]
        ys = [float(v) for v in p["y"].split(",")]
    except (KeyError, ValueError):
        raise InputError("مثال: X=5,6 Y=4,4.5 q=12")
    r = loads.tributary(xs, ys, _f(p, "q"))
    r.images["plan"] = P2.tributary(r.outputs)
    return r


# ---------------------------------------------------------------- beam (phase-1 rc) + DXF/BBS
def enrich_rc(r: Result, text: str):
    p = _params(text)
    L = _f(p, "span", None, False) or _f(p, "l", None, False)
    o = r.outputs
    r.files["beam_B1.dxf"] = dxf.beam_detail(o, L or 6.0)
    if L:
        r.outputs["bbs"] = bbs.from_beam(o, L)
    return r


def bbs_files(bars):
    return {"BBS.xlsx": bbs.to_xlsx(bars)}, P2.bbs_table(bars)
