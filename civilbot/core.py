"""Unified result object shared by every engine (bot, PDF, future web/API)."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Step:
    title: str          # what we are doing
    formula: str = ""   # symbolic form
    substitution: str = ""  # numbers plugged in
    result: str = ""    # final value with units
    ref: str = ""       # code clause / reference


@dataclass
class Result:
    tool: str
    title: str
    inputs: dict = field(default_factory=dict)
    steps: list[Step] = field(default_factory=list)
    outputs: dict = field(default_factory=dict)
    images: dict[str, bytes] = field(default_factory=dict)  # name -> PNG bytes
    files: dict[str, bytes] = field(default_factory=dict)   # filename -> bytes (DXF, XLSX)
    warnings: list[str] = field(default_factory=list)
    ok: bool = True

    def add(self, *a, **k):
        self.steps.append(Step(*a, **k))


class InputError(ValueError):
    """Raised for invalid user input; message is user-facing (Arabic)."""


def fmt(x: float, n: int = 3) -> str:
    if x is None:
        return "-"
    if abs(x) < 1e-9:
        return "0"
    if abs(x) >= 1e5 or (abs(x) < 1e-3 and x != 0):
        return f"{x:.{n}e}"
    s = f"{x:,.{n}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s
