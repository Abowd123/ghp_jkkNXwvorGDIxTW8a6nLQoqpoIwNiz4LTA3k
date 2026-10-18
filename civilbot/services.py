"""Glue layer: parse user text -> run engine -> Result with images.
Pure functions (no Telegram dependency) so they are unit-testable."""
from __future__ import annotations
import re
from .core import Result, InputError, fmt
from .engines import beam as bm, section as sec, rc_beam, formulas, units
from .drawing import plots

NUM = r"[-+]?\d*\.?\d+(?:e[-+]?\d+)?"


def _kv(text: str) -> list[tuple[str, str]]:
    text = text.replace("،", " ").replace(",", " , ").replace("  ", " ")
    toks = re.findall(r"([A-Za-z_]+)\s*=\s*([^\s=]+(?:\s*,\s*[^\s=]+)*)", text)
    return [(k.strip(), v.replace(" ", "")) for k, v in toks]


def _num(v, name):
    try:
        return float(v)
    except ValueError:
        raise InputError(f"قيمة غير رقمية لـ {name}: {v}")


# ---------------- beam ----------------
BEAM_HELP = (
    "<b>📈 SFD & BMD</b>\nأرسل وصف الكمرة بهذا الشكل (الوحدات kN و m):\n"
    "<code>L=6 S=pin@0 S=roller@6 P=40@2 w=25</code>\n\n"
    "• <code>L=</code> طول الكمرة\n"
    "• <code>S=pin@x</code> / <code>roller@x</code> / <code>fixed@x</code> ركائز (كرر S لأكثر من ركيزة)\n"
    "• اختصارات: <code>type=ss</code> بسيطة، <code>type=cant</code> كابولي، <code>type=ff</code> مثبتة الطرفين\n"
    "• <code>P=40@2</code> حمل مركز (لأسفل موجب)\n"
    "• <code>w=25</code> موزع على كامل الطول، <code>w=25@1-4</code> جزئي، <code>w=0:10@0-6</code> مثلثي/شبه منحرف\n"
    "• <code>M=15@3</code> عزم مركز (مع عقارب الساعة موجب)\n"
    "• <code>EI=50000</code> (kN·m²) اختياري للترخيم\n\n"
    "مثال كمرة مستمرة: <code>L=10 S=pin@0 S=roller@5 S=roller@10 w=20</code>")


def parse_beam(text: str, allow_noload: bool = False) -> bm.Beam:
    kv = _kv(text)
    d = {}
    for k, v in kv:
        d.setdefault(k.lower(), []).append(v)
    if "l" not in d:
        raise InputError("ناقص طول الكمرة L. مثال: L=6")
    L = _num(d["l"][0], "L")
    b = bm.Beam(L=L)
    t = (d.get("type") or [""])[0].lower()
    if t in ("ss", "simple"):
        b.supports += [bm.Support("pin", 0), bm.Support("roller", L)]
    elif t in ("cant", "cantilever"):
        b.supports.append(bm.Support("fixed", 0))
    elif t in ("ff", "fixed"):
        b.supports += [bm.Support("fixed", 0), bm.Support("fixed", L)]
    elif t in ("prop", "propped"):
        b.supports += [bm.Support("fixed", 0), bm.Support("roller", L)]
    for v in d.get("s", []):
        m = re.fullmatch(rf"(pin|roller|fixed|hinge)@({NUM}|L)", v, re.I)
        if not m:
            raise InputError(f"صيغة ركيزة خاطئة: {v}. مثال S=pin@0")
        kind = m.group(1).lower().replace("hinge", "pin")
        x = L if m.group(2).upper() == "L" else float(m.group(2))
        b.supports.append(bm.Support(kind, x))
    for v in d.get("p", []):
        m = re.fullmatch(rf"({NUM})@({NUM}|L)", v, re.I)
        if not m:
            raise InputError(f"صيغة حمل مركز خاطئة: {v}. مثال P=40@2")
        b.points.append(bm.PointLoad(float(m.group(1)), L if m.group(2).upper() == "L" else float(m.group(2))))
    for v in d.get("w", []):
        m = re.fullmatch(rf"({NUM})(?::({NUM}))?(?:@({NUM})-({NUM}|L))?", v, re.I)
        if not m:
            raise InputError(f"صيغة حمل موزع خاطئة: {v}. مثال w=25 أو w=25@0-4 أو w=0:10@0-6")
        w1 = float(m.group(1)); w2 = float(m.group(2)) if m.group(2) else w1
        a = float(m.group(3)) if m.group(3) else 0.0
        bb = (L if m.group(4).upper() == "L" else float(m.group(4))) if m.group(4) else L
        b.dists.append(bm.DistLoad(w1, w2, a, bb))
    for v in d.get("m", []):
        m = re.fullmatch(rf"({NUM})@({NUM}|L)", v, re.I)
        if not m:
            raise InputError(f"صيغة عزم خاطئة: {v}. مثال M=15@3")
        b.moments.append(bm.MomentLoad(float(m.group(1)), L if m.group(2).upper() == "L" else float(m.group(2))))
    if "ei" in d:
        b.EI = _num(d["ei"][0], "EI")
    if not (b.points or b.dists or b.moments) and not allow_noload:
        raise InputError("ما في أحمال على الكمرة. أضف P= أو w= أو M=")
    return b


def run_beam(text: str) -> Result:
    beam = parse_beam(text)
    res = bm.analyze(beam)
    r = Result("beam", "Beam analysis: SFD & BMD")
    r.inputs = {"Length L": f"{fmt(beam.L)} m",
                "Supports": ", ".join(f"{s.kind}@{fmt(s.x)}" for s in beam.supports),
                "Point loads": ", ".join(f"{fmt(p.P)} kN @ {fmt(p.a)} m" for p in beam.points) or "-",
                "Distributed loads": ", ".join(f"{fmt(d.w1)}→{fmt(d.w2)} kN/m on [{fmt(d.a)}, {fmt(d.b)}]" for d in beam.dists) or "-",
                "Moments": ", ".join(f"{fmt(m.M)} kN·m @ {fmt(m.a)} m" for m in beam.moments) or "-",
                "EI": f"{fmt(beam.EI)} kN·m²"}
    n_r = len(beam.supports) + sum(1 for s in beam.supports if s.kind == "fixed")
    deg = n_r - 2
    r.add("Determinacy (vertical loads)", "degree = r − 2 (r = reaction components)", f"r = {n_r}",
          "Statically determinate" if deg == 0 else f"Indeterminate to degree {deg} → solved by stiffness method")
    total = sum(p.P for p in beam.points) + sum((d.w1 + d.w2) / 2 * (d.b - d.a) for d in beam.dists)
    for rx in res.reactions:
        r.add(f"Reaction at {rx['kind']} x = {fmt(rx['x'])} m", "", "",
              f"R = {fmt(rx['Ry'], 3)} kN ↑" + (f" , M = {fmt(rx['Mr'], 3)} kN·m ↺" if "Mr" in rx else ""))
    sumR = sum(rx["Ry"] for rx in res.reactions)
    r.add("Equilibrium check", "ΣRy = ΣLoads", f"{fmt(sumR, 3)} = {fmt(total, 3)}", "✔ OK" if abs(sumR - total) < 1e-3 * max(1, abs(total)) else "✘")
    vmax, xv = res.Vmax
    mp, xp = res.Mmax_pos
    mn, xn = res.Mmax_neg
    dm, xd = res.dmax
    r.add("Maximum shear", "|V|max", "", f"{fmt(vmax, 3)} kN @ x = {fmt(xv, 3)} m")
    if mp > 1e-9:
        r.add("Maximum positive (sagging) moment", "V = 0 → M max", "", f"{fmt(mp, 3)} kN·m @ x = {fmt(xp, 3)} m")
    if mn < -1e-9:
        r.add("Maximum negative (hogging) moment", "", "", f"{fmt(mn, 3)} kN·m @ x = {fmt(xn, 3)} m")
    ips = res.inflection_points()
    if ips:
        r.add("Inflection points (M = 0)", "", "", ", ".join(f"x = {fmt(x, 3)} m" for x in ips))
    r.add("Maximum deflection", "EI·v'' = M (FEM, Hermitian elements)", f"EI = {fmt(beam.EI)} kN·m²",
          f"{fmt(abs(dm) * 1000, 3)} mm @ x = {fmt(xd, 3)} m  (L/{fmt(beam.L / abs(dm), 0) if abs(dm) > 0 else '∞'})")
    r.outputs = dict(Vmax=vmax, Mpos=mp, Mneg=mn, dmax_mm=dm * 1000, reactions=res.reactions, inflection=ips)
    r.images["diagrams"] = plots.beam_diagrams(res)
    return r


# ---------------- section ----------------
SECTION_HELP = (
    "<b>📐 خصائص المقاطع</b> (الوحدات mm)\nأرسل الشكل والأبعاد:\n"
    "• <code>rect b=300 h=600</code>\n• <code>T bf=800 tf=120 bw=300 h=600</code>\n"
    "• <code>I bf=200 tf=15 tw=10 h=400</code>\n• <code>L b=100 h=100 t=10</code>\n"
    "• <code>C b=100 h=200 tf=10 tw=8</code>\n• <code>circle d=400</code> · <code>pipe d=200 t=10</code>\n"
    "• <code>hrect b=200 h=300 t=10</code> (صندوقي)\n"
    "• <code>poly pts=0,0;300,0;300,100;100,100;100,500;0,500</code> (أي مضلع)")


def run_section(text: str) -> Result:
    t = text.strip()
    m = re.match(r"\s*([A-Za-z]+)\b(.*)", t)
    if not m:
        raise InputError("ابدأ باسم الشكل، مثال: rect b=300 h=600")
    shape, rest = m.group(1), m.group(2)
    params = {}
    pm = re.search(r"pts\s*=\s*([\d.;,\s-]+)", rest)
    if pm:
        try:
            params["pts"] = [tuple(float(c) for c in p.split(",")) for p in pm.group(1).strip().strip(";").split(";")]
        except ValueError:
            raise InputError("صيغة النقاط: pts=0,0;300,0;300,500;0,500")
        rest = rest[:pm.start()] + rest[pm.end():]
    for k, v in re.findall(r"([A-Za-z]+)\s*=\s*(" + NUM + ")", rest):
        params[k.lower()] = float(v)
    r = sec.properties(shape, params)
    r.images["section"] = plots.section_shape(r._geom, r.outputs, r.title)
    return r


# ---------------- RC beam ----------------
RC_HELP = (
    "<b>🏗 تصميم كمرة خرسانية (ACI 318-19)</b>\nأرسل:\n"
    "<code>b=300 h=600 fc=28 fy=420 Mu=250 Vu=180</code>\n\n"
    "• b, h بالمليمتر · fc, fy بالـ MPa · Mu بالـ kN·m · Vu بالـ kN\n"
    "• اختياري: <code>cover=40</code> <code>stirrup=10</code> <code>fyt=420</code>")


def run_rc(text: str) -> Result:
    p = {k.lower(): _num(v, k) for k, v in re.findall(r"([A-Za-z]+)\s*=\s*(" + NUM + ")", text)}
    need = [k for k in ("b", "h", "fc", "fy", "mu") if k not in p]
    if need:
        raise InputError("ناقص: " + ", ".join(need) + ". مثال: b=300 h=600 fc=28 fy=420 Mu=250 Vu=180")
    r = rc_beam.design(p["b"], p["h"], p["fc"], p["fy"], p["mu"], p.get("vu", 0.0), cover=p.get("cover", 40.0),
                       ds=p.get("stirrup", 10.0), fyt=p.get("fyt"))
    r.images["section"] = plots.rc_section(r.outputs)
    return r


# ---------------- formulas / units ----------------
FORMULA_HELP = ("<b>🧠 دليل القوانين خطوة بخطوة</b>\nأرسل اسم القانون وحده لمثال محلول، أو مع القيم لحل أي مجهول:\n"
                "<code>euler E=200e6 I=8e-6 K=1 L=4</code>\n<code>defl_ss_udl delta=0.024 L=6 E=25e6 I=5.4e-3</code> (يحسب w)\n\n")


def run_formula(text: str) -> Result:
    t = text.strip().split(None, 1)
    if not t:
        raise InputError("اكتب اسم القانون")
    key = t[0]
    vals = {k: _num(v, k) for k, v in re.findall(r"([A-Za-z]+)\s*=\s*(" + NUM + ")", t[1] if len(t) > 1 else "")}
    return formulas.solve(key, vals)


UNITS_HELP = ("<b>🔁 محول الوحدات</b>\nأمثلة:\n<code>25 kN/m2 to psf</code>\n<code>30 MPa psi</code>\n"
              "<code>12 t.m kN.m</code>\n<code>1 kip/ft kN/m</code>\n<code>5 kg/cm2 MPa</code>")


def run_units(text: str) -> str:
    return units.parse_and_convert(text)


# ---------------- text summary for chat ----------------
def summary_html(r: Result, max_steps: int = 30) -> str:
    import html as h
    lines = [f"<b>{h.escape(r.title)}</b>"]
    for i, s in enumerate(r.steps[:max_steps], 1):
        part = f"\n<b>{i}. {h.escape(s.title)}</b>"
        if s.formula:
            part += f"\n<code>{h.escape(s.formula)}</code>"
        if s.substitution:
            part += f"\n{h.escape(s.substitution)}"
        if s.result:
            part += f"\n➜ <b>{h.escape(s.result)}</b>"
        if s.ref:
            part += f"  <i>({h.escape(s.ref)})</i>"
        lines.append(part)
    for w in r.warnings:
        lines.append(f"\n⚠️ {h.escape(w)}")
    return "\n".join(lines)
