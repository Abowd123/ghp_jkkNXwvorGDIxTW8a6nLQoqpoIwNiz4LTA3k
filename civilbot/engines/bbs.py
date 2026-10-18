"""Bar bending schedule (BS 8666:2020 shape codes) + Excel export."""
from __future__ import annotations
import io
import math
from dataclasses import dataclass


def r_min(d):  # min scheduling radius BS 8666 Table 2 (B500)
    return {6: 12, 8: 16, 10: 20, 12: 24, 16: 32, 20: 70, 25: 87, 32: 112, 40: 140}.get(d, 2 * d if d <= 16 else 3.5 * d)


def unit_weight(d):
    return d * d / 162.0  # kg/m (= 0.00617 d²)


SHAPES = {
    "00": ("Straight", lambda A, B, C, d: A),
    "11": ("L-bar", lambda A, B, C, d: A + B - 0.5 * r_min(d) - d),
    "21": ("U-bar", lambda A, B, C, d: A + B + C - r_min(d) - 2 * d),
    "51": ("Closed link", lambda A, B, C, d: 2 * (A + B) + max(16 * d, 160) - 1.6 * r_min(d) - 3.1 * d),
    "33": ("Hooked both ends", lambda A, B, C, d: A + 9.0 * d),
}


@dataclass
class Bar:
    mark: str
    member: str
    shape: str
    d: int
    n: int
    A: float
    B: float = 0
    C: float = 0

    @property
    def length(self):
        return math.ceil(SHAPES[self.shape][1](self.A, self.B, self.C, self.d) / 25) * 25

    @property
    def weight(self):
        return self.n * self.length / 1000 * unit_weight(self.d)


def total_by_dia(bars):
    t = {}
    for b in bars:
        t[b.d] = t.get(b.d, 0) + b.weight
    return dict(sorted(t.items()))


def to_xlsx(bars, title="CivilBot BBS") -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    wb = Workbook()
    ws = wb.active
    ws.title = "BBS"
    ws.sheet_view.rightToLeft = False
    ws.append([title]); ws["A1"].font = Font(bold=True, size=14)
    ws.append([])
    hdr = ["Mark", "Member", "Shape code", "Shape", "Ø (mm)", "No.", "A (mm)", "B (mm)", "C (mm)", "Length (mm)", "Total length (m)", "kg/m", "Weight (kg)"]
    ws.append(hdr)
    thin = Side(style="thin", color="999999")
    for c in ws[3]:
        c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="1F6FEB"); c.alignment = Alignment(horizontal="center")
    for b in bars:
        ws.append([b.mark, b.member, b.shape, SHAPES[b.shape][0], b.d, b.n, b.A or None, b.B or None, b.C or None, b.length,
                   round(b.n * b.length / 1000, 2), round(unit_weight(b.d), 3), round(b.weight, 2)])
    ws.append([])
    ws.append(["Summary by diameter"]); ws.cell(ws.max_row, 1).font = Font(bold=True)
    tot = 0
    for d, w in total_by_dia(bars).items():
        ws.append([f"Ø{d}", "", "", "", "", "", "", "", "", "", "", "", round(w, 2)]); tot += w
    ws.append(["TOTAL (+5% waste)", "", "", "", "", "", "", "", "", "", "", "", round(tot * 1.05, 2)])
    ws.cell(ws.max_row, 1).font = Font(bold=True); ws.cell(ws.max_row, 13).font = Font(bold=True)
    for row in ws.iter_rows(min_row=3, max_row=ws.max_row):
        for c in row:
            c.border = Border(top=thin, bottom=thin, left=thin, right=thin)
    for col, w in zip("ABCDEFGHIJKLM", [7, 16, 10, 16, 7, 6, 9, 9, 9, 11, 14, 8, 11]):
        ws.column_dimensions[col].width = w
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---- generators from designs ----
def from_beam(out, L_m, name="B1", lap_supports=0.0):
    b, h, c = out["b"], out["h"], out["cover"]
    ds = int(out["stirrup_d"])
    Lmm = L_m * 1000
    bars = []
    bot, top = out["bars"], out["top_bars"]
    bars.append(Bar(f"{name}-01", name, "21" if True else "00", bot["db"], bot["n"], 12 * bot["db"], Lmm - 2 * c, 12 * bot["db"]))
    bars.append(Bar(f"{name}-02", name, "21", top["db"], top["n"], 12 * top["db"], Lmm - 2 * c, 12 * top["db"]))
    s = out.get("stirrup_s") or 200
    n_st = int(math.floor((Lmm - 2 * 50) / s)) + 1
    bars.append(Bar(f"{name}-03", name, "51", ds, n_st, b - 2 * c, h - 2 * c))
    return bars


def from_column(out, H_m, name="C1", lap=None):
    d = out["db"]
    lap = lap or 40 * d
    bars = [Bar(f"{name}-01", name, "00", d, out["n"], H_m * 1000 + lap)]
    n_t = int(math.floor(H_m * 1000 / out["s_tie"])) + 1
    bars.append(Bar(f"{name}-02", name, "51", out["tie"], n_t, out["b"] - 2 * out["cover"], out["h"] - 2 * out["cover"]))
    return bars


def from_footing(out, name="F1"):
    bars = []
    c, h = out["cover"], out["h"]
    for k, (key, span) in enumerate((("long (L)", out["L"]), ("short (B)", out["B"])), 1):
        n, d, s = out["bars"][key]
        leg = h - 2 * c
        bars.append(Bar(f"{name}-0{k}", name, "21", d, n, leg, span * 1000 - 2 * c, leg))
    return bars


def from_slab(out, name="S1"):
    bars = []
    Lx, Ly = out["Lx"] * 1000 if "Lx" in out else out["L"] * 1000, out.get("Ly", out.get("L", 1) * 3) * 1000
    k = 1
    for key, (d, s) in out["bars"].items():
        along = Lx if "x" in key or key in ("bottom",) else Ly
        width = Ly if along == Lx else Lx
        if "top" in key:
            along_len = 0.3 * Lx * 2
            n = int(width / s) + 1
            bars.append(Bar(f"{name}-0{k}", name, "21", d, n, out["h"] - 40, along_len, out["h"] - 40))
        else:
            n = int(width / s) + 1
            bars.append(Bar(f"{name}-0{k}", name, "00", d, n, along - 40))
        k += 1
    return bars


def from_wall(out, name="W1", length_m=1.0):
    H, tb = out["H"], out["tb"]
    hs = H - tb
    bars = []
    d, s = out["stem"]
    n = int(length_m * 1000 / s) + 1
    bars.append(Bar(f"{name}-01", name, "11", d, n, hs * 1000 - 50, out["heel"] * 1000 * 0.6))
    d2, s2 = out["heel_bar"]
    bars.append(Bar(f"{name}-02", name, "00", d2, int(length_m * 1000 / s2) + 1, out["B"] * 1000 - 150))
    d3, s3 = out["toe_bar"]
    bars.append(Bar(f"{name}-03", name, "00", d3, int(length_m * 1000 / s3) + 1, out["B"] * 1000 - 150))
    return bars
