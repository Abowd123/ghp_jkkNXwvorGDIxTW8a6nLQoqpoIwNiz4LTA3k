"""Phase-3 services: geotechnics, materials, hydraulics, surveying, roads, steel, influence lines, animations, quiz."""
from __future__ import annotations
import re
from .core import Result, InputError, fmt
from .engines import geotech as gt, materials as mt, hydraulics as hy, survey as sv, roads as rd, steel as st, influence as inf
from .drawing import plots3 as P3, anim, dxf
from .services import parse_beam
from .services2 import _params, _f
from .engines import beam as bm


def _floats(s, name):
    try:
        return [float(v) for v in s.split(",") if v != ""]
    except ValueError:
        raise InputError(f"صيغة {name}: أرقام مفصولة بفواصل")


# ------------------------------------------------------------------ geotech
GEO_HELP = ("<b>🌍 ميكانيكا التربة</b>\n"
            "• قدرة التحمل: <code>/bearing B=2 L=2 Df=1.5 c=0 phi=30 gamma=18 method=meyerhof FS=3</code> (method = terzaghi/meyerhof/hansen/vesic ، gw= عمق المياه)\n"
            "• دائرة مور: <code>/mohr sx=80 sy=-40 txy=25 theta=30</code>\n"
            "• الضغط الجانبي: <code>/lateral H=6 phi=30 gamma=18 c=0 q=10 method=rankine</code> (coulomb: delta= beta= alpha=)\n"
            "• الهبوط بالتصلب: <code>/consol H=4 e0=1.1 Cc=0.36 s0=80 ds=60 cv=1.5 t=1</code> (sp= Cs= للتربة المسبقة التحميل)\n"
            "• بصيلات الإجهاد: <code>/bulb q=150 B=2 L=3</code>\n"
            "• ثبات المنحدرات: <code>/slope H=10 beta=30 c=10 phi=30 gamma=18 ru=0</code>")


def run_bearing(t):
    p = _params(t)
    return gt.bearing(_f(p, "b"), _f(p, "l", 0.0), _f(p, "df"), _f(p, "c", 0.0), _f(p, "phi"), _f(p, "gamma", 18.0), p.get("method", "meyerhof"),
                      _f(p, "fs", 3.0), _f(p, "gw", None, False))


def run_mohr(t):
    p = _params(t)
    r = gt.mohr(_f(p, "sx"), _f(p, "sy"), _f(p, "txy", 0.0), _f(p, "theta", None, False))
    r.images["mohr"] = P3.mohr(r.outputs)
    return r


def run_lateral(t):
    p = _params(t)
    r = gt.lateral(_f(p, "h"), _f(p, "phi"), _f(p, "gamma", 18.0), _f(p, "c", 0.0), _f(p, "q", 0.0), p.get("method", "rankine"),
                   _f(p, "delta", 0.0), _f(p, "beta", 0.0), _f(p, "alpha", 90.0), _f(p, "gw", None, False))
    r.images["pressure"] = P3.lateral(r.outputs)
    return r


def run_consol(t):
    p = _params(t)
    r = gt.consolidation(_f(p, "h"), _f(p, "e0"), _f(p, "cc"), _f(p, "s0"), _f(p, "ds"), _f(p, "cs", None, False), _f(p, "sp", None, False),
                         _f(p, "cv", None, False), _f(p, "t", None, False), int(_f(p, "drain", 2)))
    if "Ts" in r.outputs:
        r.images["time"] = P3.consolidation(r.outputs)
    return r


def run_bulb(t):
    p = _params(t)
    r = gt.boussinesq(_f(p, "q"), _f(p, "b"), _f(p, "l", None, False))
    r.images["bulb"] = P3.bulb(r.outputs)
    return r


def run_slope(t):
    p = _params(t)
    r = gt.bishop(_f(p, "h"), _f(p, "beta"), _f(p, "c", 0.0), _f(p, "phi"), _f(p, "gamma", 18.0), _f(p, "ru", 0.0))
    r.images["slope"] = P3.slope(r.outputs)
    return r


# ------------------------------------------------------------------ materials
MAT_HELP = ("<b>🧪 الخلطات والتدرج</b>\n"
            "• تصميم خلطة ACI 211: <code>/mix fc=28 slump=75 nmsa=19 fm=2.8 rodded=1600</code>\n"
            "  اختياري: <code>sgc=3.15 sgfa=2.65 sgca=2.68 air=1 exposure=moderate mcfa=3 absfa=1 mcca=1 absca=0.5 s=3.5</code>\n"
            "• تحليل منخلي: <code>/sieve sizes=4.75,2.36,1.18,0.6,0.3,0.15,0.075 mass=20,80,120,150,90,30,10 spec=fine</code> (spec = fine / 57 / 67 / none)")


def run_mix(t):
    p = _params(t)
    r = mt.mix_design(_f(p, "fc"), _f(p, "slump", 75.0), _f(p, "nmsa", 19.0), _f(p, "fm", 2.7), _f(p, "sgc", 3.15), _f(p, "sgfa", 2.65),
                      _f(p, "sgca", 2.68), _f(p, "rodded", 1600.0), _f(p, "s", None, False), bool(_f(p, "air", 0.0)), p.get("exposure", "moderate"),
                      _f(p, "mcfa", 0.0), _f(p, "absfa", 0.0), _f(p, "mcca", 0.0), _f(p, "absca", 0.0), _f(p, "wcmax", None, False))
    r.images["mix"] = P3.mix(r.outputs)
    return r


def run_sieve(t):
    p = _params(t)
    if "sizes" not in p or "mass" not in p:
        raise InputError("أدخل sizes= و mass=")
    r = mt.sieve(_floats(p["sizes"], "sizes"), _floats(p["mass"], "mass"), p.get("spec", "fine").lower())
    r.images["curve"] = P3.gradation(r.outputs)
    return r


# ------------------------------------------------------------------ hydraulics
HYD_HELP = ("<b>💧 الهيدروليكا</b>\n"
            "• قناة مفتوحة (Manning): <code>/channel shape=trap b=3 z=2 n=0.015 S=0.001 Q=10</code>\n"
            "  shape = rect / trap / tri / circle (D=) ، أعط Q لإيجاد العمق أو y لإيجاد التصريف\n"
            "• أنابيب: <code>/pipe Q=0.05 D=0.2 L=500 eps=0.045 K=5 dz=10</code> (method=hw C=130 لهيزن-ويليامز)")


def run_channel(t):
    p = _params(t)
    r = hy.channel(p.get("shape", "rect"), _f(p, "n"), _f(p, "s"), _f(p, "q", None, False), _f(p, "y", None, False),
                   _f(p, "b", 0.0), _f(p, "z", 0.0), _f(p, "d", 0.0))
    r.images["section"] = P3.channel(r.outputs)
    return r


def run_pipe(t):
    p = _params(t)
    return hy.pipe(_f(p, "q"), _f(p, "d"), _f(p, "l"), _f(p, "eps", 0.045), 1e-6, p.get("method", "darcy"), _f(p, "c", 130.0),
                   _f(p, "k", 0.0), 0.0, _f(p, "dz", 0.0))


# ------------------------------------------------------------------ surveying & roads
SUR_HELP = ("<b>📏 المساحة والطرق</b>\n"
            "• مضلع مغلق (Bowditch): <code>/traverse az=45-30-00,135-12-00,225,315-06 d=100,100,100.05,99.98 E0=1000 N0=1000</code>\n"
            "• الميزانية: <code>/level rows=1.5,-,-;-,1.2,-;2.1,-,0.9;-,-,1.7 RL=100</code> (كل صف BS,IS,FS)\n"
            "• منحنى أفقي: <code>/hcurve R=300 delta=40 PI=1000 chord=20</code>\n"
            "• منحنى رأسي: <code>/vcurve g1=3 g2=-2 L=200 PVI=1500 el=100</code>\n"
            "• حفر وردم: <code>/earth st=0,20,40,60 A=10,5,-4,-8</code>\n"
            "• رصف AASHTO 93: <code>/pavement W18=5e6 R=95 S0=0.45 MR=50</code>\n"
            "• مسافة الرؤية: <code>/ssd V=100 t=2.5 G=0</code>")


def run_traverse(t):
    p = _params(t)
    if "az" not in p or "d" not in p:
        raise InputError("أدخل az= (اتجاهات) و d= (أطوال)")
    az = [sv.parse_angle(a) for a in p["az"].split(",")]
    r = sv.traverse(az, _floats(p["d"], "d"), _f(p, "e0", 1000.0), _f(p, "n0", 1000.0))
    r.images["plan"] = P3.traverse(r.outputs)
    return r


def run_level(t):
    p = _params(t)
    if "rows" not in p:
        raise InputError("أدخل rows=BS,IS,FS;...")
    rows = []
    for row in p["rows"].strip(";").split(";"):
        vals = row.split(",")
        if len(vals) != 3:
            raise InputError("كل صف لازم 3 قيم BS,IS,FS (استخدم - للفراغ)")
        rows.append(tuple(None if v.strip() in ("-", "") else float(v) for v in vals))
    return sv.levelling(rows, _f(p, "rl"))


def run_hcurve(t):
    p = _params(t)
    r = sv.h_curve(_f(p, "r"), sv.parse_angle(p.get("delta", "")) if "delta" in p else _f(p, "delta"), _f(p, "pi"), _f(p, "chord", 20.0))
    r.images["curve"] = P3.hcurve(r.outputs)
    return r


def run_vcurve(t):
    p = _params(t)
    r = sv.v_curve(_f(p, "g1"), _f(p, "g2"), _f(p, "l"), _f(p, "pvi"), _f(p, "el"), _f(p, "step", 20.0))
    r.images["profile"] = P3.vcurve(r.outputs)
    return r


def run_earth(t):
    p = _params(t)
    r = sv.earthwork(_floats(p.get("st", ""), "st"), _floats(p.get("a", ""), "A"))
    r.images["haul"] = P3.masshaul(r.outputs)
    return r


def run_pavement(t):
    p = _params(t)
    mrl = (_f(p, "mrb"), _f(p, "mrsb")) if "mrb" in p and "mrsb" in p else None
    r = rd.aashto93(_f(p, "w18"), _f(p, "r", 95.0), _f(p, "s0", 0.45), _f(p, "mr"), _f(p, "pi", 4.2), _f(p, "pt", 2.5),
                    (_f(p, "a1", 0.44), _f(p, "a2", 0.14), _f(p, "a3", 0.11)), (1.0, _f(p, "m2", 1.0), _f(p, "m3", 1.0)), mrl)
    r.images["layers"] = P3.pavement(r.outputs)
    return r


def run_ssd(t):
    p = _params(t)
    return rd.ssd(_f(p, "v"), _f(p, "t", 2.5), _f(p, "a", 3.4), _f(p, "g", 0.0))


# ------------------------------------------------------------------ steel
STEEL_HELP = ("<b>🔩 المنشآت المعدنية (AISC 360-16)</b>\n"
              "• كمرة: <code>/sbeam Mu=150 Vu=120 Lb=3 Fy=355</code> (اختيار تلقائي من IPE، أو sec=IPE300 / family=HEA ، L=6 w=15 للترخيم)\n"
              "• عمود: <code>/scol Pu=1500 KL=4 Fy=355</code> (Mux=60 Lb=4 للانحناء المشترك ، family=HEB)\n"
              "• وصلة قص: <code>/stab Vu=250 d=20 grade=A325N tp=10 tw=7.1</code>\n"
              "• لوح القاعدة: <code>/bplate Pu=1500 d=300 bf=300 fc=25 Fy=250</code>\n"
              "المكتبة: IPE100–600 ، HEA100–300 ، HEB100–300")


def run_sbeam(t):
    p = _params(t)
    r = st.beam(_f(p, "mu"), _f(p, "vu", 0.0), _f(p, "lb"), _f(p, "fy", 355.0), _f(p, "cb", 1.0), p.get("sec"), None,
                _f(p, "l", None, False), _f(p, "w", None, False), int(_f(p, "lim", 360)), p.get("family", "IPE"))
    r.images["section"] = P3.steel_section(r.outputs["p"], r.outputs["section"])
    return r


def run_scol(t):
    p = _params(t)
    r = st.column(_f(p, "pu"), _f(p, "kl"), _f(p, "fy", 355.0), _f(p, "mux", 0.0), _f(p, "lb", None, False), p.get("sec"), None,
                  _f(p, "klx", None, False), p.get("family", "HEB"))
    r.images["section"] = P3.steel_section(r.outputs["p"], r.outputs["section"])
    return r


def run_stab(t):
    p = _params(t)
    r = st.shear_tab(_f(p, "vu"), int(_f(p, "d", 20)), p.get("grade", "A325N"), _f(p, "tp", 10.0), _f(p, "fy", 250.0), _f(p, "fu", 400.0),
                     _f(p, "tw", 7.1), _f(p, "fub", 490.0), _f(p, "weld", 6.0), _f(p, "fexx", 490.0))
    r.images["detail"] = P3.shear_tab(r.outputs)
    r.files["shear_tab.dxf"] = dxf.shear_tab_detail(r.outputs)
    return r


def run_bplate(t):
    p = _params(t)
    r = st.base_plate(_f(p, "pu"), _f(p, "d"), _f(p, "bf"), _f(p, "fc", 25.0), _f(p, "fy", 250.0), _f(p, "a2a1", 1.0))
    r.images["plate"] = P3.base_plate(r.outputs)
    return r


# ------------------------------------------------------------------ influence lines & animations
VIS_HELP = ("<b>🎬 التصور والحركة</b>\n"
            "• خطوط التأثير: <code>/il L=20 S=pin@0 S=roller@10 S=roller@20 qty=M x=5</code>\n"
            "  qty = R (أضف support=2) / V / M ، شاحنة: <code>truck=145@4.3,145@4.3,35</code> ، حمل موزع: <code>w=10</code>\n"
            "• GIF الانبعاج: <code>/anim type=buckling E=200e6 I=8e-6 L=4</code>\n"
            "• GIF الترخيم: <code>/anim type=beam L=6 type2=ss w=20</code> (نفس صيغة /beam)\n"
            "• GIF الاهتزاز: <code>/anim type=vibration L=6 EI=50000 m=500</code>")


def run_il(t):
    p = _params(t)
    b = parse_beam(t, allow_noload=True)
    b.points, b.dists, b.moments = [], [], []
    axles = None
    if "truck" in p:
        axles = []
        for part in p["truck"].split(","):
            m = re.fullmatch(r"([\d.]+)(?:@([\d.]+))?", part)
            if not m:
                raise InputError("صيغة الشاحنة: truck=145@4.3,145@4.3,35 (حمل@المسافة للمحور التالي)")
            axles.append((float(m.group(1)), float(m.group(2) or 0)))
    r = inf.influence(b, p.get("qty", "M"), _f(p, "x", None, False), int(_f(p, "support", 1)), axles, _f(p, "w", None, False))
    r.images["il"] = P3.influence(r.outputs)
    return r


def run_anim(t):
    p = _params(t)
    kind = p.get("type", "buckling").lower()
    r = Result("anim", f"Animation: {kind}")
    if kind == "buckling":
        E, I, L = _f(p, "e", 200e6), _f(p, "i", 8e-6), _f(p, "l", 4.0)
        r.inputs = dict(E=fmt(E), I=fmt(I), L=f"{fmt(L)} m")
        for nm, K in (("pinned-pinned", 1.0), ("fixed-free", 2.0), ("fixed-pinned", 0.699), ("fixed-fixed", 0.5)):
            import math
            r.add(f"Pcr {nm} (K = {K})", "Pcr = π²EI/(KL)²", "", f"{fmt(math.pi**2 * E * I / (K * L)**2, 2)} kN")
        r.files["buckling.gif"] = anim.buckling_gif(E, I, L)
    elif kind == "beam":
        tt = re.sub(r"\btype=beam\b", "", t, flags=re.I).replace("type2=", "type=")
        b = parse_beam(tt)
        res = bm.analyze(b)
        r.add("Max deflection", "", "", f"{fmt(abs(res.dmax[0]) * 1000, 3)} mm @ x = {fmt(res.dmax[1], 3)} m")
        r.files["deflection.gif"] = anim.beam_deflection_gif(res)
    elif kind == "vibration":
        import math
        L, EI, m = _f(p, "l", 6.0), _f(p, "ei", 5e4), _f(p, "m", 500.0)
        for n in (1, 2, 3):
            w = (n * math.pi / L) ** 2 * math.sqrt(EI * 1e3 / m)
            r.add(f"Mode {n}", "ωn = (nπ/L)²·√(EI/m) ; f = ω/2π", "", f"f{n} = {fmt(w / (2 * math.pi), 3)} Hz")
        r.files["vibration.gif"] = anim.vibration_gif(L, EI, m)
    else:
        raise InputError("type = buckling / beam / vibration")
    return r
