"""Engineering unit converter. Dimensions tracked as (length, force) exponents."""
from __future__ import annotations
import re
from ..core import InputError, fmt

# base: metre, newton
LEN = {"m": 1, "cm": 1e-2, "mm": 1e-3, "km": 1e3, "in": 0.0254, "ft": 0.3048, "yd": 0.9144}
FORCE = {"n": 1, "kn": 1e3, "mn": 1e6, "kgf": 9.80665, "kg": 9.80665, "t": 9806.65, "ton": 9806.65,
         "tf": 9806.65, "lbf": 4.4482216, "lb": 4.4482216, "kip": 4448.2216, "kips": 4448.2216}
NAMED = {  # name: (factor, (L, F))
    "pa": (1, (-2, 1)), "kpa": (1e3, (-2, 1)), "mpa": (1e6, (-2, 1)), "gpa": (1e9, (-2, 1)),
    "bar": (1e5, (-2, 1)), "psi": (6894.757, (-2, 1)), "ksi": (6894757, (-2, 1)),
    "psf": (47.880259, (-2, 1)), "ksf": (47880.259, (-2, 1)), "atm": (101325, (-2, 1)),
    "plf": (14.5939, (-1, 1)), "klf": (14593.9, (-1, 1)),
    "pcf": (157.087464, (-3, 1)),
}
ALIASES = {"tonne": "t", "tons": "ton", "kgs": "kg", "meter": "m", "metre": "m", "inch": "in", "feet": "ft", "foot": "ft"}


def parse_unit(u: str):
    s = u.strip().lower().replace("²", "2").replace("³", "3").replace("⁴", "4").replace("·", ".").replace("*", ".")
    s = s.replace("^", "")
    if not s:
        raise InputError("وحدة فارغة")
    factor, L, F = 1.0, 0, 0
    parts = s.split("/")
    for pi, part in enumerate(parts):
        sign = 1 if pi == 0 else -1
        for tok in filter(None, part.split(".")):
            m = re.fullmatch(r"([a-z]+)(\d*)", tok)
            if not m:
                raise InputError(f"وحدة غير مفهومة: {tok}")
            name, exp = m.group(1), int(m.group(2) or 1)
            name = ALIASES.get(name, name)
            e = sign * exp
            if name in NAMED:
                f, (dl, df) = NAMED[name]
                factor *= f ** e; L += dl * e; F += df * e
            elif name in LEN:
                factor *= LEN[name] ** e; L += e
            elif name in FORCE:
                factor *= FORCE[name] ** e; F += e
            else:
                raise InputError(f"وحدة غير معروفة: {name}")
    return factor, (L, F)


def convert(value: float, src: str, dst: str):
    f1, d1 = parse_unit(src)
    f2, d2 = parse_unit(dst)
    if d1 != d2:
        raise InputError(f"الوحدتين غير متوافقتين: {src} ↔ {dst}")
    return value * f1 / f2


def parse_and_convert(text: str) -> str:
    """'25 kN/m2 to psf'  |  '30 MPa psi'  |  '12 ton.m kN.m'"""
    t = text.strip().replace(" إلى ", " to ").replace(" الى ", " to ")
    m = re.fullmatch(r"\s*([-+]?\d*\.?\d+(?:e[-+]?\d+)?)\s*([^\s]+)\s+(?:to\s+|->\s*|=>\s*)?([^\s]+)\s*", t, re.I)
    if not m:
        raise InputError("الصيغة: 25 kN/m2 to psf")
    v, a, b = float(m.group(1)), m.group(2), m.group(3)
    out = convert(v, a, b)
    return f"{fmt(v, 6)} {a} = <b>{fmt(out, 6)} {b}</b>"


REBAR_TABLE = {d: (3.14159265 * d * d / 4, 0.00617 * d * d) for d in (6, 8, 10, 12, 14, 16, 18, 20, 22, 25, 28, 32, 36, 40)}
