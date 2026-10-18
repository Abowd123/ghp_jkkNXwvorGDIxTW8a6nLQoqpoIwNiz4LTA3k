"""Validation against closed-form textbook solutions (Hibbeler / Gere / McCormac)."""
import math
import pytest
from civilbot import services as S
from civilbot.core import InputError
from civilbot.engines import beam as bm
from civilbot.engines.section import properties
from civilbot.engines.rc_beam import design
from civilbot.engines.units import convert
from civilbot.engines.formulas import solve

R = lambda a, b, tol=1e-3: abs(a - b) <= tol * max(1, abs(b))


@pytest.mark.parametrize("txt,Mpos,Mneg", [
    ("L=6 type=ss w=10", 45, 0),                                         # wL²/8
    ("L=6 type=ss P=20@3", 30, 0),                                       # PL/4
    ("L=6 type=ff w=10", 15, -30),                                       # wL²/24, wL²/12
    ("L=6 type=prop w=10", 25.3125, -45),                                # 9wL²/128, wL²/8
    ("L=10 S=pin@0 S=roller@5 S=roller@10 w=10", 9 * 10 * 25 / 128, -31.25),        # 2 equal spans: 9wL²/128, wL²/8
    ("L=3 type=cant P=20@3", 0, -60),
    ("L=6 type=ss w=0:10", 10 * 36 / (9 * math.sqrt(3)), 0),             # triangular load
])
def test_beam_moments(txt, Mpos, Mneg):
    r = S.run_beam(txt).outputs
    if Mpos:
        assert R(r["Mpos"], Mpos, 2e-3)
    if Mneg:
        assert R(r["Mneg"], Mneg, 2e-3)


def test_beam_deflection():
    r = S.run_beam("L=6 type=ss w=10 EI=100000").outputs
    assert R(abs(r["dmax_mm"]), 5 * 10 * 6**4 / (384 * 1e5) * 1000, 1e-3)


def test_unstable():
    with pytest.raises(InputError):
        S.run_beam("L=6 S=roller@0 w=10")


def test_sections():
    assert R(properties("rect", {"b": 300, "h": 600}).outputs["Ix"], 300 * 600**3 / 12)
    o = properties("I", {"bf": 200, "tf": 15, "tw": 10, "h": 400}).outputs
    assert R(o["Ix"], (200 * 400**3 - 190 * 370**3) / 12)
    assert R(properties("circle", {"d": 100}).outputs["Ix"], math.pi * 100**4 / 64, 1e-3)
    assert R(properties("T", {"bf": 800, "tf": 120, "bw": 300, "h": 600}).outputs["cy"], 360)


def test_rc_singly():
    o = design(300, 600, 28, 420, 250, 180).outputs
    assert o["phiMn"] >= 250 and o["eps_t"] >= 0.005 and not o["doubly"]
    assert 1300 < o["As_req"] < 1350


def test_rc_doubly():
    o = design(250, 450, 25, 420, 320, 250).outputs
    assert o["doubly"] and o["phiMn"] >= 320 and o["eps_t"] >= 0.004


def test_units():
    assert R(convert(1, "ksi", "MPa"), 6.894757)
    assert R(convert(1, "kip/ft", "kN/m"), 14.5939, 1e-4)
    with pytest.raises(InputError):
        convert(1, "kN", "m")


def test_formula_any_unknown():
    assert R(solve("euler", {"E": 200e6, "I": 8e-6, "K": 1, "L": 4}).outputs["Pcr"], math.pi**2 * 200e6 * 8e-6 / 16)
    assert R(solve("defl_ss_udl", {"delta": 0.024, "L": 6, "E": 25e6, "I": 5.4e-3}).outputs["w"], 192)


def test_pdf():
    from civilbot.reports.pdf import build_pdf
    pdf = build_pdf(S.run_rc("b=300 h=600 fc=28 fy=420 Mu=250 Vu=180"))
    assert pdf[:4] == b"%PDF"


# ------------------------------------------------------------ phase 2
from civilbot import services2 as S2
from civilbot.engines import frame as fr, slab, rc_column, loads, bbs


def test_truss_simple():
    r = S2.run_truss("N=0,0;4,0;8,0;4,3 M=1-2;2-3;1-4;4-3;2-4 S=1:pin;3:roller F=4:0,-60").outputs
    f = r["forces"]
    assert R(f[0], 40) and R(f[2], -50) and f[4] == 0           # 3-4-5 triangle: T=P·4/(2·3), C=P·5/6


def test_truss_pratt_equilibrium():
    r = S2.run_truss("type=pratt span=12 h=3 n=6 P=20").outputs
    assert R(sum(v[1] for v in r["reactions"].values()), 100)
    assert R(r["forces"][7], -60) and R(r["forces"][2], 53.333)   # top chord at mid = M/h = (50·6 − 20·4 − 20·2)/3 = 60


def test_portal_lateral():
    m = fr.Model([(0, 0), (0, 4), (6, 4), (6, 0)], [fr.Member(0, 1, A=10), fr.Member(1, 2, A=10), fr.Member(2, 3, A=10)],
                 {0: "fixed", 3: "fixed"}, {1: (20, 0, 0)})
    res = fr.analyze_frame(m)
    assert R(res.reactions[0][2], 24, 1e-3)                    # Ph/2·(3k+1)/(6k+1), k = 2/3


def test_portal_gravity_pinned():
    m = fr.Model([(0, 0), (0, 4), (6, 4), (6, 0)], [fr.Member(0, 1, A=10), fr.Member(1, 2, A=10, w=10), fr.Member(2, 3, A=10)],
                 {0: "pin", 3: "pin"})
    H = fr.analyze_frame(m).reactions[0][0]
    assert R(abs(H), 10 * 36 / (4 * 4 * (2 * (4 / 6) + 3)), 1e-3)  # wL²/(4h(2k+3))


def test_hinge_release_propped():
    m = fr.Model([(0, 0), (6, 0)], [fr.Member(0, 1, w=10, hinge_j=True)], {0: "fixed", 1: "fixed"})
    M = fr.analyze_frame(m).stations[0][3]
    assert R(M.min(), -45) and R(M.max(), 25.3125)


def test_plate_timoshenko():
    W, Mx, My, nx, ny = slab.plate_fd(1, 1, "SSSS", nu=0.3, n=30)
    assert R(Mx[nx // 2, ny // 2], 0.0479, 5e-3) and R(W.max(), 0.00406, 5e-3)
    W, Mx, My, nx, ny = slab.plate_fd(1, 1, "FFFF", nu=0.3, n=30)
    assert R(Mx[0, ny // 2], -0.0513, 1.5e-2)


def test_column_axial_capacity():
    import numpy as np
    arr, P0 = rc_column.interaction(400, 400, 28, 420, np.array([60.0] * 4 + [340.0] * 4), rc_column.AREA[20])
    assert R(P0, (0.85 * 28 * (160000 - 8 * rc_column.AREA[20]) + 420 * 8 * rc_column.AREA[20]) / 1e3)


def test_column_design_passes():
    o = rc_column.design(400, 500, 28, 420, 1800, 220).outputs
    assert o["util"] <= 1.0 and 0.01 <= o["rho"] <= 0.08


def test_combos():
    o = loads.combinations({"D": 100, "L": 50}).outputs
    assert R(o["max"][1], 200)                                   # 1.2·100 + 1.6·50


def test_tributary_trapezoid():
    o = loads.tributary([5], [4], 12).outputs
    weq = {b[0]: b[3] for b in o["beams"]}
    assert any(R(v, 24 * (1 - 0.64 / 3)) for v in weq.values())  # long beam trapezoid
    assert any(R(v, 16) for v in weq.values())                   # short beam triangle 2/3·w0


def test_footing_wall_run():
    assert S2.run_footing("PD=800 PL=500 qa=200 c1=400 c2=400 fc=25 fy=420").files
    o = S2.run_wall("H=5 phi=30 q=10 qa=200").outputs
    assert o["FSo"] >= 2 and o["qmax"] <= 200


def test_dxf_and_bbs():
    r = S2.run_column("b=400 h=400 fc=28 fy=420 Pu=1500 Mu=150")
    d = r.files["column_C1.dxf"].decode()
    assert d.startswith("0\nSECTION") and d.rstrip().endswith("EOF") and "CIRCLE" in d
    x = bbs.to_xlsx(r.outputs["bbs"])
    assert x[:2] == b"PK"


# ------------------------------------------------------------ phase 3
from civilbot.engines import geotech as gt, materials as mt, hydraulics as hy, survey as sv, roads as rd, steel as stl, influence as infl, quiz as qz


def test_bearing_factors():
    assert all(R(a, b, 2e-3) for a, b in zip(gt.bearing_factors(30, "meyerhof"), (30.14, 18.40, 15.67)))
    assert all(R(a, b, 2e-3) for a, b in zip(gt.bearing_factors(30, "terzaghi"), (37.16, 22.46, 19.13)))
    assert R(gt.bearing_factors(30, "vesic")[2], 22.40, 2e-3)


def test_mohr_and_lateral():
    o = gt.mohr(80, -40, 25).outputs
    assert R(o["s1"], 85) and R(o["s3"], -45) and R(o["R"], 65)
    assert R(gt.lateral(6, 30, 18, 0, 10).outputs["Pa"], 0.5 / 3 * 18 * 36 + 10 / 3 * 6, 1e-3)
    assert R(gt.lateral(6, 30, 18, method="coulomb", delta=20).outputs["Ka"], 0.297, 3e-3)


def test_consolidation_and_newmark():
    import math
    S = gt.consolidation(4, 1.1, 0.36, 80, 60).outputs["S"]
    assert R(S, 0.36 * 4 / 2.1 * math.log10(140 / 80))
    assert R(gt.stress_rect(100, 2, 2, 0, 0, 2), 33.6, 3e-3)            # 4·I(0.5,0.5)=4·0.084


def test_slope_trend():
    f1 = gt.bishop(10, 30, 5, 30, 18).outputs["FS"]
    f2 = gt.bishop(10, 30, 20, 30, 18).outputs["FS"]
    assert 1.0 < f1 < f2


def test_mix_volumes():
    v = mt.mix_design(28).outputs["vols"]
    assert R(sum(v.values()), 1.0, 1e-9)


def test_sieve_fm():
    o = mt.sieve([4.75, 2.36, 1.18, 0.6, 0.3, 0.15, 0.075], [20, 80, 120, 150, 90, 30, 10]).outputs
    assert R(o["fm"], 3.32, 1e-3)


def test_manning_and_pipe():
    o = hy.channel("rect", 0.015, 0.001, y=1.0, b=3).outputs
    assert R(o["Q"], 3 / 0.015 * (3 / 5) ** (2 / 3) * 0.001 ** 0.5, 1e-6)
    yb = hy.channel("rect", 0.015, 0.001, Q=o["Q"], b=3).outputs["y"]
    assert R(yb, 1.0, 1e-4)
    f = hy.pipe(0.05, 0.2, 500, 0.045).outputs["f"]
    assert 0.015 < f < 0.018                                                # Moody: Re≈3.2e5, ε/D≈2.3e-4


def test_survey():
    o = sv.traverse([0, 90, 180, 270], [100, 100, 100, 100]).outputs
    assert R(o["area"], 10000) and abs(o["eE"]) < 1e-9
    h = sv.h_curve(300, 40, 1000).outputs
    assert R(h["T"], 300 * 0.36397, 1e-4) and R(h["L"], 209.44, 1e-4)
    v = sv.v_curve(3, -2, 200, 1500, 100)
    assert "1,520" in v.steps[-1].result and "98.8" in v.steps[-1].result     # high point x = −g1·L/A = 120 m


def test_aashto_guide_example():
    SN = rd.aashto93(5e6, 95, 0.35, 5000 / 145.038, 4.4, 2.5).outputs["SN"]   # AASHTO Fig 3.1 example → SN ≈ 5.0
    assert abs(SN - 5.0) < 0.15


def test_steel_section_props():
    key, p = stl.section("IPE300")
    assert R(p["A"], 5381, 2e-3) and R(p["Ix"], 83.56e6, 2e-3) and R(p["Zx"], 628.4e3, 2e-3)
    key, p = stl.section("HEB200")
    assert R(p["A"], 7808, 2e-3) and R(p["Ix"], 56.96e6, 2e-3)


def test_steel_member_checks():
    assert stl.beam(150, 120, 3).outputs["util"] <= 1
    assert stl.column(1500, 4).outputs["phiPn"] >= 1500
    assert stl.shear_tab(250).outputs["cap"] >= 250


def test_influence_ss_moment():
    b = bm.Beam(10, [bm.Support("pin", 0), bm.Support("roller", 10)])
    il = infl.influence(b, "M", 4).outputs["il"]
    assert R(max(il), 4 * 6 / 10, 2e-3)


def test_quiz_grading():
    q = qz.new_question("mixed")
    assert qz.grade(q, q["ans"] * 1.01) and not qz.grade(q, q["ans"] * 1.2 + 1)


# ------------------------------------------------------------ phase 4
import json
from civilbot.ai import cracks as crk, layout as lay, codes as cds, equation as eqm, llm as llmm
from civilbot.engines import schedule as schm, boq as boqm
from civilbot import services4 as S4


@pytest.mark.parametrize("kind,element,expect", [("shear", "beam", "Shear"), ("flexural", "beam", "Flexural"), ("map", "slab", "Map"),
                                                 ("horizontal", "beam", "Longitudinal"), ("flexural", "column", "Vertical"), ("shear", "wall", "Diagonal")])
def test_crack_patterns(kind, element, expect):
    for seed in (1, 2):
        assert expect in crk.analyze(crk.synthetic(kind, seed=seed), element, scale=0.1).outputs["type"]


def test_crack_orientation():
    o = crk.analyze(crk.synthetic("shear"), "beam").outputs
    assert 40 < o["dominant"] < 65 and o["coherence"] > 0.8


def test_layout_synthetic_plan():
    o = lay.propose(lay.synthetic_plan(), 15, 6, 2.5).outputs
    assert max(o["sx"] + o["sy"]) <= 6.05 and len(o["cols"]) >= 12
    assert R(sum(o["sx"]), 15, 1e-2) and R(sum(o["sy"]), 10, 2e-2)


def test_layout_adds_gridlines():
    o = lay.propose(lay.synthetic_plan(), 15, 4.0, 2.0).outputs
    assert max(o["sx"] + o["sy"]) <= 4.05


def test_codes_retrieval():
    assert cds.search("الحد الأدنى للحديد في الكمرات")[0]["key"] == "min_steel_beam"
    assert cds.search("punching shear")[0]["key"] == "punching"
    assert cds.search("كانات الأعمدة")[0]["key"] == "ties"
    assert all(len(e["rows"]) == len(cds.CODES) for e in cds.DB)


def test_equation_pipeline_mocked():
    llmm._test_hook = lambda m, model, j: json.dumps({"lhs": "Pcr", "rhs_sympy": "pi**2*E*I/(K*L)**2", "variables": [], "confidence": 0.9})
    try:
        eq = eqm.read_image(b"fake")
        v = eqm.evaluate(eq, {"E": 200e6, "I": 8e-6, "K": 1, "L": 4}).outputs["Pcr"]
        assert R(v, 986.96, 1e-4)
        L = eqm.evaluate(eq, {"Pcr": 986.96, "E": 200e6, "I": 8e-6, "K": 1}).outputs["L"]
        assert R(L, 4.0, 1e-4)
    finally:
        llmm._test_hook = None


def test_equation_rejects_code():
    with pytest.raises(InputError):
        eqm.safe_parse("__import__('os').system('x')")


def test_schedule_grouping():
    r = schm.design_all(schm.parse("C1 Pu=1500 Mu=80; C2 Pu=1550 Mu=70; C3 Pu=3000 Mu=100"))
    types = r.outputs["types"]
    assert len(types) == 2 and all(t["rho"] <= 0.03 for t in types)


def test_boq_quantities():
    it, pr = boqm.parse("column 0.4x0.4x3 n=10\nslab 10x10x0.2\nwall 10x3\nprice concrete=100")
    t = boqm.compute(it, pr).outputs["totals"]
    assert R(t["concrete"], (0.4 * 0.4 * 3 * 10 + 20) * 1.03) and R(t["block"], 30 / 0.08)


def test_webapp_roundtrip():
    k, t = S4.webapp_to_text(json.dumps({"kind": "frame", "nodes": [[0, 0], [0, 4], [6, 4], [6, 0]], "members": [[0, 1], [1, 2], [2, 3]],
                                         "supports": {"0": "fixed", "3": "fixed"}, "loads": {"1": [20, 0]}, "udl": {"1": 15}}))
    r = S2.run_frame(t)
    assert k == "frame" and R(r._res.reactions[0][0] + r._res.reactions[3][0], -20, 1e-6)
    html = S4.viewer_html(S4.model3d(r._res, "frame")).decode()
    assert "window.__MODEL__" in html


def test_excel_import():
    runners = {"rc": lambda t: S2.enrich_rc(S.run_rc(t), t), "column": S2.run_column, "footing": S2.run_footing, "beam": S.run_beam,
               "sbeam": __import__("civilbot.services3", fromlist=["x"]).run_sbeam, "bearing": __import__("civilbot.services3", fromlist=["x"]).run_bearing}
    out, summary, specials = S4.import_xlsx(S4.templates_xlsx(), runners)
    assert out[:2] == b"PK" and len(specials) == 2 and not any("ignored" in s for s in summary)
