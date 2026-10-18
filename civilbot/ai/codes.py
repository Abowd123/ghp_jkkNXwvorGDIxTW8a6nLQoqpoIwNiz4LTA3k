"""Curated cross-code comparison database (ACI 318-19, BS 8110-1:1997, EN 1992-1-1 (EC2), SBC 304-2018).
Only equations/limits + clause numbers are stored (no verbatim code text). The LLM (if enabled) may only
re-phrase retrieved rows — it is never allowed to add values."""
from __future__ import annotations
import re
from ..core import Result, InputError
from . import llm

CODES = ["ACI 318-19", "BS 8110-1:1997", "EC2 (EN 1992-1-1)", "SBC 304-2018"]
SBC_NOTE = "SBC 304-2018 is based on ACI 318-14; values are the same as ACI unless noted."

DB = [
    dict(key="load_comb", ar="تراكيب الأحمال معاملات الأمان للأحمال حمل ميت حي", en="load combination factor dead live ultimate",
         title="Basic ultimate load combination (dead + live)",
         rows=["1.2D + 1.6L (and 1.4D) — ASCE 7 §2.3 / ACI 5.3.1", "1.4Gk + 1.6Qk — Table 2.1", "1.35Gk + 1.5Qk — EN 1990 Eq. 6.10 (6.10a/b alternatives)",
               "1.2D + 1.6L (and 1.4D) — SBC 301 §2.3.2"]),
    dict(key="material", ar="معامل تخفيض المقاومة معامل أمان المواد فاي جاما", en="strength reduction factor phi partial safety factor gamma material",
         title="Material / strength reduction factors",
         rows=["φ: flexure tension-controlled 0.90, shear 0.75, tied column 0.65, spiral 0.75 — Table 21.2.1/21.2.2",
               "γm: concrete flexure/axial 1.5, shear 1.25, bond 1.4; steel 1.05 (1.15 after 2005 amendment) — Table 2.2",
               "γc = 1.5 , γs = 1.15 (persistent & transient) — Table 2.1N",
               "Same as ACI 318-14 (φ = 0.90 / 0.75 / 0.65 / 0.75)"]),
    dict(key="stress_block", ar="كتلة الإجهاد المستطيلة عمق المحور المحايد", en="stress block rectangular neutral axis depth",
         title="Concrete stress block",
         rows=["0.85f'c over a = β1·c ; β1 = 0.85 → 0.65 — §22.2.2.4", "0.67fcu/γm = 0.45fcu over 0.9x — Fig. 3.3 / §3.4.4.4",
               "η·fcd over λ·x ; λ = 0.8, η = 1.0 for fck ≤ 50 MPa ; fcd = αcc·fck/γc (αcc = 1.0 rec., 0.85 UK NA) — §3.1.7", "Same as ACI"]),
    dict(key="strength", ar="مقاومة الخرسانة مكعب اسطوانة", en="concrete strength cube cylinder characteristic",
         title="Specified concrete strength",
         rows=["f'c — cylinder 150×300 mm, specified compressive strength", "fcu — 150 mm cube characteristic strength",
               "fck — cylinder characteristic (fck,cube also listed, e.g. C30/37) — Table 3.1", "f'c (cylinder) as ACI"]),
    dict(key="min_steel_beam", ar="الحد الأدنى لحديد التسليح في الكمرات حديد الشد", en="minimum tension reinforcement beam",
         title="Minimum flexural tension steel (beams)",
         rows=["As,min = max(0.25√f'c/fy , 1.4/fy)·bw·d — §9.6.1.2", "100As/Ac ≥ 0.13 % (fy = 460, rectangular) / 0.24 % (fy = 250) — Table 3.25",
               "As,min = max(0.26·fctm/fyk , 0.0013)·bt·d — Eq. 9.1N", "Same as ACI"]),
    dict(key="max_steel_beam", ar="الحد الأقصى لحديد التسليح في الكمرات", en="maximum reinforcement beam ductility",
         title="Maximum flexural steel (beams)",
         rows=["Net tensile strain εt ≥ 0.004 (εt ≥ 0.005 for φ = 0.9) — §9.3.3.1", "As ≤ 4 % Ac (tension or compression) — §3.12.6.1",
               "As,max = 0.04Ac outside laps (recommended) — §9.2.1.1(3)", "εt ≥ 0.004 as ACI 318-14"]),
    dict(key="shear", ar="مقاومة القص للخرسانة قص الكمرات", en="shear strength concrete beam Vc",
         title="Concrete shear strength (members with stirrups)",
         rows=["Vc = 0.17λ√f'c·bw·d (simplified; detailed Vc = 0.66λ(ρw)^(1/3)√f'c·bw·d for Av < Av,min) — Table 22.5.5.1",
               "vc = 0.79·(100As/bd)^(1/3)·(400/d)^(1/4)/γm × (fcu/25)^(1/3), γm = 1.25 — Table 3.8",
               "VRd,c = [CRd,c·k·(100ρl·fck)^(1/3)]·bw·d ≥ vmin·bw·d ; CRd,c = 0.18/γc, k = 1 + √(200/d) ≤ 2, vmin = 0.035k^1.5·fck^0.5 — §6.2.2",
               "Vc = 0.17λ√f'c·bw·d (ACI 318-14 Eq. 22.5.5.1)"]),
    dict(key="max_shear", ar="الحد الأقصى لقص الخرسانة تهشم الضلوع", en="maximum shear crushing limit",
         title="Upper limit on shear",
         rows=["Vs ≤ 0.66√f'c·bw·d — §22.5.1.2", "v ≤ min(0.8√fcu , 5 MPa) — §3.4.5.2", "VRd,max = αcw·bw·z·ν1·fcd/(cotθ + tanθ) — §6.2.3", "As ACI"]),
    dict(key="deflection", ar="الترخيم نسبة البحر إلى العمق السماكة الدنيا", en="deflection span depth ratio minimum thickness",
         title="Deflection control without calculation",
         rows=["Beams h,min: SS ℓ/16, one end cont. ℓ/18.5, both cont. ℓ/21, cantilever ℓ/8 ; one-way slabs ℓ/20, 24, 28, 10 (fy = 420) — Tables 9.3.1.1 & 7.3.1.1",
               "Basic span/effective depth (rect.): cantilever 7, SS 20, continuous 26, × modification factors — Table 3.9",
               "ℓ/d = K·[11 + 1.5√fck·ρ0/ρ + …] ; K = 1.0 SS, 1.3 end span, 1.5 interior, 0.4 cantilever — Eq. 7.16, Table 7.4N",
               "Same as ACI 318-14"]),
    dict(key="column_steel", ar="نسبة حديد الأعمدة الحد الأدنى والأقصى", en="column longitudinal reinforcement ratio minimum maximum",
         title="Column longitudinal steel limits",
         rows=["0.01Ag ≤ Ast ≤ 0.08Ag — §10.6.1.1", "0.4 % ≤ 100Asc/Ac ≤ 6 % (vertically cast) — §3.12.5.3 / 3.12.6.2",
               "As,min = max(0.10NEd/fyd , 0.002Ac) ; As,max = 0.04Ac (outside laps) — §9.5.2", "1 % – 8 % as ACI"]),
    dict(key="ties", ar="كانات الأعمدة تباعد الكانات", en="column ties links spacing transverse",
         title="Column ties / links",
         rows=["s ≤ min(16db, 48dtie, least dimension) ; tie ≥ Ø10 for bars ≤ Ø32 — §25.7.2", "s ≤ 12 × smallest compression bar ; link Ø ≥ ¼ largest bar — §3.12.7.1",
               "scl,tmax = min(20φl,min , b , 400 mm), reduced ×0.6 near beams/slabs & laps ; Ø ≥ max(6, φl,max/4) — §9.5.3", "As ACI"]),
    dict(key="slab_spacing", ar="أقصى تباعد حديد البلاطات حديد الانكماش", en="slab bar spacing maximum shrinkage temperature",
         title="Slab reinforcement spacing",
         rows=["Main: s ≤ min(3h, 450) one-way, min(2h, 450) two-way ; shrinkage As = 0.0018bh, s ≤ min(5h, 450) — §7.7.2.3, 8.7.2.2, 24.4.3",
               "Clear spacing ≤ 3d or 750 mm (h ≤ 200 with fy = 460 — check Table 3.28) ; min 0.13 % bh — §3.12.11.2.7",
               "Main: s ≤ min(3h, 400) (2h ≤ 250 at max moments) ; secondary min(3.5h, 450) — §9.3.1.1(3)", "As ACI"]),
    dict(key="modulus", ar="معامل المرونة للخرسانة", en="modulus of elasticity concrete Ec",
         title="Concrete modulus of elasticity",
         rows=["Ec = 4700√f'c (MPa) — §19.2.2.1", "Ec,28 = 20 + 0.2fcu (GPa), mean value — BS 8110-2 Eq. 17",
               "Ecm = 22·(fcm/10)^0.3 (GPa), fcm = fck + 8 — Table 3.1", "Ec = 4700√f'c"]),
    dict(key="development", ar="طول التماسك طول التثبيت طول الرباط", en="development length anchorage bond lap",
         title="Development (anchorage) length in tension",
         rows=["ℓd = fy·ψt·ψe·ψg/(2.1λ√f'c)·db (≤ Ø19) , /(1.7λ√f'c) (≥ Ø22) ≥ 300 mm — Table 25.4.2.3",
               "ℓ = 0.87fy·φ/(4·fbu) with fbu = β√fcu (β = 0.5 deformed type 2, tension) — §3.12.8.4, Table 3.26",
               "ℓb,rqd = (φ/4)(σsd/fbd) ; fbd = 2.25·η1·η2·fctd — §8.4.2–8.4.3", "As ACI 318-14 §25.4.2"]),
    dict(key="punching", ar="القص الثاقب محيط حرج", en="punching shear critical perimeter flat slab",
         title="Punching shear",
         rows=["Critical perimeter at d/2 ; vc = min(0.33 , 0.17(1+2/β) , 0.083(2 + αs·d/bo))·λs·λ√f'c — §22.6.4, Table 22.6.5.2",
               "First perimeter at 1.5d ; vc from Table 3.8 ; v ≤ min(0.8√fcu, 5) at column face — §3.7.7",
               "Basic control perimeter u1 at 2d ; vRd,c = CRd,c·k(100ρl·fck)^(1/3) ≥ vmin — §6.4.2, 6.4.4", "As ACI 318-14 (without λs size factor)"]),
    dict(key="cover", ar="الغطاء الخرساني", en="concrete cover nominal",
         title="Concrete cover (examples)",
         rows=["Not exposed: slabs 20 mm, beams/columns 40 mm ; exposed to weather 50 mm (≥ Ø19) / 40 mm (≤ Ø16) ; cast against earth 75 mm — Table 20.5.1.3.1",
               "By exposure class × concrete grade — Table 3.3 (+ fire Table 3.4)", "cnom = cmin + Δcdev (10 mm) ; cmin,dur by exposure class (e.g. XC1 → 15 mm, S4) — §4.4.1",
               "As ACI ; SBC adds Saudi exposure classes"]),
]


def _score(entry, q):
    words = set(re.findall(r"[\w']+", q.lower()))
    text = (entry["ar"] + " " + entry["en"] + " " + entry["title"]).lower()
    return sum(1 for w in words if len(w) > 2 and w in text)


def search(q: str, k=2):
    sc = sorted(DB, key=lambda e: -_score(e, q))
    top = _score(sc[0], q) if sc else 0
    return [e for e in sc[:k] if _score(e, q) > 0 and _score(e, q) >= 0.75 * top]


def compare(q: str) -> Result:
    hits = search(q) if q.strip() else []
    if not hits:
        topics = "\n".join(f"• {e['title']}" for e in DB)
        raise InputError("ما لقيت موضوع مطابق. المواضيع المتاحة:\n" + topics)
    r = Result("codes", "Cross-code comparison: " + " / ".join(h["title"] for h in hits), inputs=dict(question=q))
    for h in hits:
        r.add(h["title"], "\n".join(f"{c}: {row}" for c, row in zip(CODES, h["rows"])))
    r.warnings.append(SBC_NOTE)
    r.warnings.append("الأرقام مختصرة من بنود الأكواد مع رقم البند. ارجع للنص الرسمي للكود قبل الاعتماد.")
    if llm.enabled():
        try:
            ctx = "\n\n".join(h["title"] + ":\n" + "\n".join(f"{c}: {row}" for c, row in zip(CODES, h["rows"])) for h in hits)
            ans = llm.chat([{"role": "system", "content": "You are a structural code expert. Answer in Arabic ONLY using the provided rows. "
                                                       "Do not add any number, equation or clause not present in the rows. If the rows don't answer, say so."},
                            {"role": "user", "content": f"Question: {q}\n\nRows:\n{ctx}"}], max_tokens=600)
            r.add("AI summary (restricted to the rows above)", ans.strip())
        except Exception as e:
            r.warnings.append(f"تعذر تلخيص الذكاء الاصطناعي: {e}")
    r.outputs = dict(hits=hits)
    return r
