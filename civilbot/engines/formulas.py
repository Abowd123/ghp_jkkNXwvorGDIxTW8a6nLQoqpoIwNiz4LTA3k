"""Step-by-step formula library with SymPy: show law, symbols, worked example,
and solve for ANY missing variable."""
from __future__ import annotations
import sympy as sp
from ..core import Result, InputError, fmt

S = sp.Symbol


def _f(key, title, lhs, rhs, symbols, example, ref="", ar=""):
    return dict(key=key, title=title, eq=sp.Eq(lhs, rhs), symbols=symbols, example=example, ref=ref, ar=ar)


P, E, I, K, L, w, d, M, y, s, V, Q, b, A, fc, Ec, Pcr = sp.symbols("P E I K L w delta M y sigma V Q b A fc Ec Pcr")
tau, eps, Fy, r, KLr = sp.symbols("tau epsilon Fy r lambda")

LIB = [
    _f("euler", "Euler buckling load", Pcr, sp.pi**2 * E * I / (K * L)**2,
       {"Pcr": ("Critical buckling load", "kN"), "E": ("Modulus of elasticity", "kN/m²"), "I": ("Least moment of inertia", "m⁴"),
        "K": ("Effective length factor (1 pinned-pinned, 0.5 fixed-fixed, 0.7 fixed-pinned, 2 cantilever)", "-"), "L": ("Unbraced length", "m")},
       {"E": 200e6, "I": 8.0e-6, "K": 1, "L": 4}, "Euler (1744)", "حمل الانبعاج الحرج للعمود"),
    _f("defl_ss_udl", "Max deflection, simply supported beam, UDL", d, 5 * w * L**4 / (384 * E * I),
       {"delta": ("Mid-span deflection", "m"), "w": ("Uniform load", "kN/m"), "L": ("Span", "m"), "E": ("Modulus", "kN/m²"), "I": ("Moment of inertia", "m⁴")},
       {"w": 20, "L": 6, "E": 25e6, "I": 5.4e-3}, "", "الترخيم الأقصى لكمرة بسيطة تحت حمل موزع"),
    _f("defl_ss_p", "Max deflection, simply supported beam, central point load", d, P * L**3 / (48 * E * I),
       {"delta": ("Mid-span deflection", "m"), "P": ("Point load", "kN"), "L": ("Span", "m"), "E": ("Modulus", "kN/m²"), "I": ("Moment of inertia", "m⁴")},
       {"P": 50, "L": 6, "E": 25e6, "I": 5.4e-3}, "", "ترخيم كمرة بسيطة بحمل مركز في المنتصف"),
    _f("defl_cant_p", "Tip deflection, cantilever, end point load", d, P * L**3 / (3 * E * I),
       {"delta": ("Tip deflection", "m"), "P": ("End load", "kN"), "L": ("Length", "m"), "E": ("Modulus", "kN/m²"), "I": ("Moment of inertia", "m⁴")},
       {"P": 10, "L": 2, "E": 200e6, "I": 2.0e-5}, "", "ترخيم طرف كابولي بحمل مركز"),
    _f("defl_cant_udl", "Tip deflection, cantilever, UDL", d, w * L**4 / (8 * E * I),
       {"delta": ("Tip deflection", "m"), "w": ("Uniform load", "kN/m"), "L": ("Length", "m"), "E": ("Modulus", "kN/m²"), "I": ("Moment of inertia", "m⁴")},
       {"w": 10, "L": 2, "E": 200e6, "I": 2.0e-5}, "", "ترخيم طرف كابولي بحمل موزع"),
    _f("m_ss_udl", "Max moment, simply supported beam, UDL", M, w * L**2 / 8,
       {"M": ("Max moment", "kN·m"), "w": ("Uniform load", "kN/m"), "L": ("Span", "m")}, {"w": 25, "L": 6}, "", "أقصى عزم لكمرة بسيطة"),
    _f("flexure", "Flexure formula (bending stress)", s, M * y / I,
       {"sigma": ("Bending stress", "kN/m²"), "M": ("Bending moment", "kN·m"), "y": ("Distance from neutral axis", "m"), "I": ("Moment of inertia", "m⁴")},
       {"M": 120, "y": 0.3, "I": 5.4e-3}, "", "قانون إجهاد الانحناء"),
    _f("shear_stress", "Shear stress formula", tau, V * Q / (I * b),
       {"tau": ("Shear stress", "kN/m²"), "V": ("Shear force", "kN"), "Q": ("First moment of area above point", "m³"),
        "I": ("Moment of inertia", "m⁴"), "b": ("Width at the point", "m")},
       {"V": 150, "Q": 0.0135, "I": 5.4e-3, "b": 0.3}, "", "قانون إجهاد القص"),
    _f("axial", "Axial stress", s, P / A, {"sigma": ("Normal stress", "kN/m²"), "P": ("Axial force", "kN"), "A": ("Area", "m²")},
       {"P": 1500, "A": 0.16}, "", "الإجهاد المحوري"),
    _f("ec", "Concrete modulus of elasticity (ACI)", Ec, 4700 * sp.sqrt(fc),
       {"Ec": ("Modulus of elasticity of concrete", "MPa"), "fc": ("Specified compressive strength f'c", "MPa")},
       {"fc": 28}, "ACI 318-19 §19.2.2.1", "معامل مرونة الخرسانة"),
    _f("hooke", "Hooke's law", s, E * eps, {"sigma": ("Stress", "MPa"), "E": ("Modulus", "MPa"), "epsilon": ("Strain", "-")},
       {"E": 200000, "epsilon": 0.0015}, "", "قانون هوك"),
    _f("slender", "Slenderness ratio", KLr, K * L / r, {"lambda": ("Slenderness ratio", "-"), "K": ("Effective length factor", "-"),
                                                         "L": ("Unbraced length", "m"), "r": ("Radius of gyration", "m")},
       {"K": 1, "L": 4, "r": 0.05}, "", "نسبة النحافة"),
]
INDEX = {f["key"]: f for f in LIB}
SYN = {"buckling": "euler", "انبعاج": "euler", "deflection": "defl_ss_udl", "ترخيم": "defl_ss_udl", "bending": "flexure",
       "انحناء": "flexure", "shear": "shear_stress", "قص": "shear_stress", "modulus": "ec", "hooke": "hooke"}


def _t(x) -> str:
    return (sp.sstr(x).replace("**", "^").replace("*", "·").replace("pi", "π")
            .replace("sqrt", "√").replace("delta", "δ").replace("sigma", "σ").replace("tau", "τ")
            .replace("epsilon", "ε").replace("lambda", "λ"))


def list_formulas() -> str:
    return "\n".join(f"• <code>{f['key']}</code>: {f['ar']} ({f['title']})" for f in LIB)


def solve(key: str, values: dict) -> Result:
    key = SYN.get(key, key)
    if key not in INDEX:
        raise InputError("قانون غير معروف. أرسل /formula لعرض القائمة")
    f = INDEX[key]
    eq = f["eq"]
    syms = {str(x): x for x in eq.free_symbols}
    example = False
    if not values:
        values = dict(f["example"]); example = True
    bad = [k for k in values if k not in syms]
    if bad:
        raise InputError(f"رموز غير موجودة في القانون: {', '.join(bad)}. المتاح: {', '.join(syms)}")
    unknown = [k for k in syms if k not in values]
    if len(unknown) != 1:
        raise InputError(f"لازم يكون فيه مجهول واحد بالضبط. المجهول الآن: {', '.join(unknown) or 'لا شيء'}")
    u = syms[unknown[0]]
    r = Result("formula", f["title"] + (" — worked example" if example else ""), inputs={k: fmt(float(v), 6) for k, v in values.items()})
    r.add("Governing equation", f"{_t(eq.lhs)} = {_t(eq.rhs)}", "", "", f["ref"])
    r.add("Symbols", "\n".join(f"{k}: {v[0]} [{v[1]}]" for k, v in f["symbols"].items()))
    sols = sp.solve(eq, u)
    subs = {syms[k]: sp.nsimplify(float(v)) if abs(float(v)) < 1e12 else float(v) for k, v in values.items()}
    sols = [sp.N(sv.subs(subs)) for sv in sols]
    sols = [complex(x) for x in sols]
    sols = [x.real for x in sols if abs(x.imag) < 1e-12 and x.real >= 0] or [x.real for x in sols if abs(x.imag) < 1e-12]
    if not sols:
        raise InputError("ما في حل حقيقي بهذه القيم")
    expr = sp.solve(eq, u)[0]
    r.add(f"Rearrange for {u}", f"{_t(u)} = {_t(expr)}")
    r.add("Substitute", f"{_t(u)} = " + _t(expr.subs({syms[k]: sp.Symbol(f"{float(v):.6g}") for k, v in values.items()})))
    unit = f["symbols"].get(str(u), ("", ""))[1]
    r.add("Result", "", "", f"{_t(u)} = {fmt(sols[0], 5)} {unit}")
    r.outputs = {str(u): sols[0], "unit": unit}
    return r
