"""Bill of quantities: concrete, reinforcement (by ratio or BBS), formwork, blockwork, plaster, tiles + cost."""
from __future__ import annotations
import re
from ..core import Result, InputError, fmt

RATIO = {"footing": 80, "column": 160, "beam": 140, "slab": 90, "wall": 0, "tie_beam": 120, "stair": 110, "rwall": 100}
PRICES = {"concrete": 0.0, "steel": 0.0, "formwork": 0.0, "block": 0.0, "plaster": 0.0, "tiles": 0.0}
ALIAS = {"f": "footing", "footing": "footing", "قاعدة": "footing", "c": "column", "column": "column", "عمود": "column",
         "b": "beam", "beam": "beam", "كمرة": "beam", "s": "slab", "slab": "slab", "بلاطة": "slab", "wall": "wall", "جدار": "wall",
         "tb": "tie_beam", "tiebeam": "tie_beam", "stair": "stair", "درج": "stair", "rwall": "rwall"}


def parse(text: str):
    items, prices = [], dict(PRICES)
    for line in re.split(r"[;\n]+", text.strip()):
        t = line.strip()
        if not t:
            continue
        if t.lower().startswith("price"):
            for k, v in re.findall(r"([a-z]+)\s*=\s*([\d.]+)", t.lower()):
                prices[k] = float(v)
            continue
        m = re.match(r"(\S+)\s+([\d.]+)\s*[x×*]\s*([\d.]+)(?:\s*[x×*]\s*([\d.]+))?(.*)", t, re.I)
        if not m:
            raise InputError(f"سطر غير مفهوم: {t}\nمثال: footing 2.5x2.5x0.6 n=12")
        kind = ALIAS.get(m.group(1).lower())
        if not kind:
            raise InputError(f"عنصر غير معروف: {m.group(1)} (footing/column/beam/slab/wall/tiebeam/stair)")
        a, b, c = float(m.group(2)), float(m.group(3)), float(m.group(4)) if m.group(4) else None
        n = float(re.search(r"n\s*=\s*([\d.]+)", m.group(5)).group(1)) if re.search(r"n\s*=", m.group(5)) else 1
        ratio = re.search(r"kg\s*=\s*([\d.]+)", m.group(5))
        items.append(dict(kind=kind, a=a, b=b, c=c, n=n, ratio=float(ratio.group(1)) if ratio else RATIO[kind], raw=t))
    if not items:
        raise InputError("أدخل عناصر المشروع")
    return items, prices


def compute(items, prices, waste_conc=0.03, waste_steel=0.05) -> Result:
    r = Result("boq", "Bill of quantities (BOQ)")
    rows = []
    tot = dict(concrete=0.0, steel=0.0, formwork=0.0, block=0.0, plaster=0.0, tiles=0.0)
    for it in items:
        k, a, b, c, n = it["kind"], it["a"], it["b"], it["c"], it["n"]
        conc = form = blk = pl = tl = 0.0
        if k == "wall":   # length × height [× thickness], blocks 0.4×0.2 face
            L, H = a, b
            blk = L * H * n / (0.4 * 0.2)
            pl = 2 * L * H * n
            desc = f"wall {fmt(L)}×{fmt(H)} m ×{fmt(n)}"
        elif k == "slab":
            t = c or 0.2
            conc = a * b * t * n
            form = a * b * n
            tl = a * b * n
            pl = a * b * n
            desc = f"slab {fmt(a)}×{fmt(b)}×{fmt(t)} ×{fmt(n)}"
        elif c is None:
            raise InputError(f"{it['raw']}: يحتاج 3 أبعاد (مثل 0.4x0.4x3.2)")
        else:
            conc = a * b * c * n
            if k == "column":
                form = 2 * (a + b) * c * n
            elif k in ("beam", "tie_beam"):
                form = (a + 2 * b) * c * n   # bottom + two sides (a = width, b = depth, c = length)
            elif k == "footing":
                form = 2 * (a + b) * c * n
            else:
                form = (a + 2 * b) * c * n
            desc = f"{k} {fmt(a)}×{fmt(b)}×{fmt(c)} ×{fmt(n)}"
        steel = conc * it["ratio"]
        rows.append(dict(desc=desc, kind=k, conc=conc, steel=steel, form=form, block=blk, plaster=pl, tiles=tl))
        for kk, v in (("concrete", conc), ("steel", steel), ("formwork", form), ("block", blk), ("plaster", pl), ("tiles", tl)):
            tot[kk] += v
        r.add(desc, "", f"steel ratio {fmt(it['ratio'])} kg/m³" if conc else "",
              " , ".join(x for x in [f"concrete {fmt(conc, 2)} m³" if conc else "", f"steel {fmt(steel, 0)} kg" if steel else "",
                                      f"formwork {fmt(form, 1)} m²" if form else "", f"blocks {fmt(blk, 0)} pcs" if blk else "",
                                      f"plaster {fmt(pl, 1)} m²" if pl else ""] if x))
    tot["concrete"] *= 1 + waste_conc
    tot["steel"] *= 1 + waste_steel
    unit = dict(concrete="m³", steel="kg", formwork="m²", block="pcs", plaster="m²", tiles="m²")
    cost = {k: tot[k] * prices.get(k, 0) for k in tot}
    r.add("Totals (incl. waste: concrete 3 %, steel 5 %)", "", "", " , ".join(f"{k} {fmt(v, 1)} {unit[k]}" for k, v in tot.items() if v))
    if any(prices.values()):
        r.add("Cost estimate", "Σ quantity × unit price", " , ".join(f"{k}: {fmt(cost[k], 0)}" for k in cost if cost[k]), f"TOTAL = {fmt(sum(cost.values()), 0)}")
    cement = tot["concrete"] * 7.0
    r.add("Materials for concrete (≈ 350 kg/m³)", "", "", f"cement ≈ {fmt(cement, 0)} bags , sand ≈ {fmt(tot['concrete'] * 0.45, 1)} m³ , gravel ≈ {fmt(tot['concrete'] * 0.85, 1)} m³")
    r.outputs = dict(rows=rows, totals=tot, cost=cost, unit=unit, prices=prices)
    return r


def to_xlsx(r) -> bytes:
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook(); ws = wb.active; ws.title = "BOQ"
    ws.append(["Item", "Concrete (m³)", "Steel (kg)", "Formwork (m²)", "Blocks (pcs)", "Plaster (m²)", "Tiles (m²)"])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="1F6FEB")
    for x in r.outputs["rows"]:
        ws.append([x["desc"], round(x["conc"], 3), round(x["steel"], 1), round(x["form"], 2), round(x["block"]), round(x["plaster"], 2), round(x["tiles"], 2)])
    t = r.outputs["totals"]
    ws.append(["TOTAL (+waste)", round(t["concrete"], 2), round(t["steel"], 0), round(t["formwork"], 1), round(t["block"]), round(t["plaster"], 1), round(t["tiles"], 1)])
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
    ws2 = wb.create_sheet("Cost")
    ws2.append(["Item", "Quantity", "Unit", "Unit price", "Amount"])
    for k, v in t.items():
        ws2.append([k, round(v, 2), r.outputs["unit"][k], r.outputs["prices"].get(k, 0), f"=B{ws2.max_row + 1}*D{ws2.max_row + 1}"])
    ws2.append(["TOTAL", "", "", "", f"=SUM(E2:E{ws2.max_row})"])
    ws.column_dimensions["A"].width = 34
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()
