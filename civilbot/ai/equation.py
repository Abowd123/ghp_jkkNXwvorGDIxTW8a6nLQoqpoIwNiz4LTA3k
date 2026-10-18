"""Equation OCR & explainer: vision LLM reads the equation -> we validate it with SymPy
and turn it into an interactive calculator (evaluation is SymPy, never the LLM)."""
from __future__ import annotations
import re
import sympy as sp
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application, convert_xor
from ..core import Result, InputError, fmt
from . import llm

SYSTEM = ("You are a civil/structural engineering assistant. You read engineering equations from images. "
          "Return STRICT JSON only. Never invent an equation that is not in the image.")
PROMPT = ("Read the main equation in this image. Return JSON with keys: "
          "latex (string), lhs (single symbol name, ASCII), rhs_sympy (right-hand side in Python/SymPy syntax using ASCII names, "
          "use sqrt(), pi, exp(), log(), **), variables (list of {symbol, meaning_ar, meaning_en, unit}), "
          "name_ar (short Arabic name of the equation), context_ar (2-3 Arabic sentences: where it is used, which code/textbook), "
          "confidence (0-1). Use the same ASCII symbol names in rhs_sympy and variables.")
TR = standard_transformations + (implicit_multiplication_application, convert_xor)
SAFE = {"sqrt": sp.sqrt, "pi": sp.pi, "exp": sp.exp, "log": sp.log, "ln": sp.log, "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
        "atan": sp.atan, "asin": sp.asin, "acos": sp.acos, "Abs": sp.Abs, "E": sp.Symbol("E"), "I": sp.Symbol("I"),
        "S": sp.Symbol("S"), "N": sp.Symbol("N"), "Q": sp.Symbol("Q"), "beta": sp.Symbol("beta"), "gamma": sp.Symbol("gamma"),
        "lambda": sp.Symbol("lambda_"), "lam": sp.Symbol("lam")}


def safe_parse(expr: str):
    if not re.fullmatch(r"[A-Za-z0-9_+\-*/^().,\s']*", expr or ""):
        raise InputError("المعادلة فيها رموز غير مسموحة")
    if "__" in expr or "lambda " in expr:
        raise InputError("صيغة غير مسموحة")
    try:
        return parse_expr(expr.replace("^", "**"), local_dict=dict(SAFE), transformations=TR, evaluate=True)
    except Exception:
        raise InputError("ما قدرت أفهم المعادلة رياضياً")


def from_json(d: dict) -> dict:
    rhs = safe_parse(d.get("rhs_sympy", ""))
    lhs = str(d.get("lhs") or "y")
    syms = sorted(str(s) for s in rhs.free_symbols)
    return dict(latex=d.get("latex", ""), lhs=lhs, rhs=rhs, symbols=syms, variables=d.get("variables", []),
                name=d.get("name_ar", ""), context=d.get("context_ar", ""), confidence=float(d.get("confidence", 0.0)))


def read_image(img: bytes) -> dict:
    if not llm.enabled():
        raise InputError("قراءة المعادلات من الصور تحتاج تفعيل الذكاء الاصطناعي (LLM_API_KEY)")
    return from_json(llm.parse_json(llm.vision(PROMPT, img, SYSTEM)))


def explain(eq: dict) -> Result:
    r = Result("equation", f"Equation explainer — {eq['name']}" if eq["name"] else "Equation explainer")
    r.add("Equation (as read)", f"{eq['lhs']} = {sp.sstr(eq['rhs'])}", eq["latex"], f"confidence {fmt(eq['confidence'] * 100, 0)} %")
    vs = "\n".join(f"{v.get('symbol')}: {v.get('meaning_ar') or v.get('meaning_en')} [{v.get('unit', '-')}]" for v in eq["variables"])
    r.add("Variables", vs or ", ".join(eq["symbols"]))
    if eq["context"]:
        r.add("Context", eq["context"])
    r.add("Validated symbolically (SymPy)", "free symbols: " + ", ".join(eq["symbols"]), "", "✔ ready as a calculator")
    if eq["confidence"] < 0.7:
        r.warnings.append("ثقة القراءة منخفضة: راجع المعادلة مع المرجع قبل الاستخدام")
    return r


def evaluate(eq: dict, values: dict) -> Result:
    missing = [s for s in eq["symbols"] if s not in values]
    r = Result("equation_eval", f"Evaluate: {eq['lhs']} = {sp.sstr(eq['rhs'])}", inputs={k: fmt(v, 6) for k, v in values.items()})
    target = None
    expr = sp.Eq(sp.Symbol(eq["lhs"]), eq["rhs"])
    if not missing:
        val = eq["rhs"].subs({sp.Symbol(k): v for k, v in values.items()})
        r.add("Substitute", sp.sstr(eq["rhs"].subs({sp.Symbol(k): sp.Symbol(fmt(v, 6)) for k, v in values.items()})), "", f"{eq['lhs']} = {fmt(float(sp.N(val)), 6)}")
        r.outputs = {eq["lhs"]: float(sp.N(val))}
        return r
    if len(missing) == 1 and eq["lhs"] in values:
        target = sp.Symbol(missing[0])
        sols = sp.solve(expr.subs({sp.Symbol(k): v for k, v in values.items() if k != missing[0]}), target)
        sols = [complex(sp.N(x)) for x in sols]
        sols = [x.real for x in sols if abs(x.imag) < 1e-9]
        sols = [x for x in sols if x > 0] or sols
        if not sols:
            raise InputError("ما في حل حقيقي")
        r.add(f"Solve for {target}", "", "", f"{target} = " + " , ".join(fmt(x, 6) for x in sols))
        r.outputs = {str(target): sols[0]}
        return r
    raise InputError("ناقص قيم: " + ", ".join(missing))
