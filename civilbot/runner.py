"""Worker-side dispatcher. Heavy work (engines + matplotlib + PDF + OpenCV) runs in a process pool so that
matplotlib is never used from concurrent threads and the bot's event loop stays responsive.
Everything here is importable without python-telegram-bot."""
from __future__ import annotations
import io
import os
import zipfile

_FUNCS = None


def funcs():
    global _FUNCS
    if _FUNCS is None:
        from . import services as S, services2 as S2, services3 as S3, services4 as S4
        _FUNCS = {
            "beam": S.run_beam, "rc": lambda t: S2.enrich_rc(S.run_rc(t), t), "section": S.run_section, "formula": S.run_formula,
            "truss": S2.run_truss, "frame": S2.run_frame, "column": S2.run_column, "slab": S2.run_slab, "punch": S2.run_punch,
            "footing": S2.run_footing, "wall": S2.run_wall, "combo": S2.run_combo, "trib": S2.run_trib,
            "bearing": S3.run_bearing, "mohr": S3.run_mohr, "lateral": S3.run_lateral, "consol": S3.run_consol, "bulb": S3.run_bulb,
            "slope": S3.run_slope, "mix": S3.run_mix, "sieve": S3.run_sieve, "channel": S3.run_channel, "pipe": S3.run_pipe,
            "traverse": S3.run_traverse, "level": S3.run_level, "hcurve": S3.run_hcurve, "vcurve": S3.run_vcurve, "earth": S3.run_earth,
            "pavement": S3.run_pavement, "ssd": S3.run_ssd, "sbeam": S3.run_sbeam, "scol": S3.run_scol, "stab": S3.run_stab,
            "bplate": S3.run_bplate, "il": S3.run_il, "anim": S3.run_anim,
            "codes": S4.run_codes, "schedule": S4.run_schedule, "boq": S4.run_boq,
        }
    return _FUNCS


def run_tool(tool, text):
    return funcs()[tool](text)


def run_photo(kind, data, caption):
    from . import services4 as S4
    if kind == "crack":
        return None, S4.run_crack(data, caption)
    if kind == "layout":
        return None, S4.run_layout(data, caption)
    return S4.read_equation(data)


def pdf(res, user="", logo=None, watermark=None):
    from .reports.pdf import build_pdf
    return build_pdf(res, user, logo=logo, watermark=watermark)


def bbs(bars):
    from . import services2 as S2
    return S2.bbs_files(bars)


def import_xlsx(data):
    from . import services4 as S4
    f = {k: v for k, v in funcs().items() if k not in ("codes",)}
    return S4.import_xlsx(data, f)


def export(rows, user, logo=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        index = ["id,tool,input,result"]
        for cid, tool, inp, summ, at in reversed(rows):
            fn = funcs().get(tool)
            if not fn:
                continue
            try:
                res = fn(inp)
                z.writestr(f"{cid:04d}_{tool}.pdf", pdf(res, user, logo))
                for fname, data in res.files.items():
                    z.writestr(f"{cid:04d}_{fname}", data)
                index.append(f'{cid},{tool},"{inp}","{summ}"')
            except Exception:
                index.append(f'{cid},{tool},"{inp}",ERROR')
        z.writestr("index.csv", "\n".join(index))
    return buf.getvalue()


def execute(job, *args):
    """Single entry point for the process pool."""
    return {"tool": run_tool, "photo": run_photo, "pdf": pdf, "bbs": bbs, "import": import_xlsx, "export": export}[job](*args)


def warmup():
    """Pre-import heavy modules in each worker (cuts first-request latency)."""
    funcs()
    import matplotlib.pyplot  # noqa
    try:  # render once so font caches / text layout are hot before the first real user
        run_tool("beam", "L=6 type=ss w=10 P=20@3")
        run_tool("truss", "type=pratt span=12 h=3 n=6 P=20")
    except Exception:
        pass
    return os.getpid()


def init_worker():
    """One BLAS thread per worker: N processes x N threads on N cores thrashes."""
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[k] = "1"
    try:
        from threadpoolctl import threadpool_limits
        threadpool_limits(1)
    except Exception:
        pass
