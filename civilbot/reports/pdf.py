"""Calculation-sheet PDF (Arabic RTL headings + English technical content)."""
from __future__ import annotations
import base64
import datetime as dt
import html
from ..core import Result, fmt

CSS = """
@page { size: A4; margin: 16mm 14mm 18mm 14mm;
  @bottom-center { content: "CivilBot · " counter(page) " / " counter(pages); font-size: 8pt; color: #888; } }
body { font-family: 'Noto Sans Arabic', 'DejaVu Sans', sans-serif; font-size: 10pt; color: #222; }
.hdr { border-bottom: 3px solid #1f6feb; padding-bottom: 6px; margin-bottom: 10px; display: flex; justify-content: space-between; }
.hdr h1 { font-size: 16pt; margin: 0; color: #1f6feb; }
.meta { font-size: 8.5pt; color: #555; text-align: left; direction: ltr; }
h2 { font-size: 12pt; background: #f0f4fa; padding: 4px 8px; border-right: 4px solid #1f6feb; direction: rtl; }
table { width: 100%; border-collapse: collapse; margin: 6px 0; direction: ltr; }
th, td { border: 1px solid #d0d7de; padding: 3px 6px; vertical-align: top; text-align: left; line-height: 1.3; }
th { background: #f6f8fa; }
.step td.f { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.8pt; white-space: pre-wrap; }
.res { font-weight: bold; color: #0a3069; }
.ref { color: #6e7781; font-size: 8pt; }
.warn { background: #fff8c5; border: 1px solid #d4a72c; padding: 6px 8px; margin: 6px 0; direction: rtl; }
.disc { margin-top: 14px; font-size: 8pt; color: #666; direction: rtl; border-top: 1px solid #ddd; padding-top: 6px; }
img { max-width: 100%; max-height: 165mm; display: block; margin: 6px auto; }
.ltr { direction: ltr; text-align: left; }
"""


def _e(x):
    return html.escape(str(x))


def build_pdf(res: Result, user: str = "", logo: bytes | None = None, watermark: str | None = None) -> bytes:
    from weasyprint import HTML
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    rows_in = "".join(f"<tr><th>{_e(k)}</th><td>{_e(v)}</td></tr>" for k, v in res.inputs.items())
    steps = "".join(
        f"<tr class='step'><td>{i}</td><td>{_e(s.title)}<div class='ref'>{_e(s.ref)}</div></td>"
        f"<td class='f'>{_e(s.formula)}{('<br>' + _e(s.substitution)) if s.substitution else ''}</td>"
        f"<td class='res'>{_e(s.result)}</td></tr>" for i, s in enumerate(res.steps, 1))
    warns = "".join(f"<div class='warn'>⚠️ {_e(w)}</div>" for w in res.warnings)
    imgs = "".join(f"<img src='data:image/png;base64,{base64.b64encode(b).decode()}'/>" for b in res.images.values())
    logo_html = f"<img src='data:image/png;base64,{base64.b64encode(logo).decode()}' style='height:14mm;margin:0'/>" if logo else ""
    wm_css = (f"body::before{{content:'{_e(watermark)}';position:fixed;top:45%;left:5%;font-size:60pt;color:rgba(31,111,235,0.08);"
              "transform:rotate(-30deg);z-index:-1;}}") if watermark else ""
    doc = f"""<html dir='rtl'><head><meta charset='utf-8'><style>{CSS}{wm_css}</style></head><body>
<div class='hdr'><h1>{logo_html} مذكرة حسابية — CivilBot</h1><div class='meta'>{_e(res.title)}<br>{now}{('<br>' + _e(user)) if user else ''}</div></div>
<h2>المدخلات</h2><table>{rows_in}</table>
<h2>خطوات الحل</h2><table><tr><th>#</th><th>Step</th><th>Equation / substitution</th><th>Result</th></tr>{steps}</table>
{('<h2>تنبيهات</h2>' + warns) if warns else ''}
{('<h2>الرسومات</h2>' + imgs) if imgs else ''}
<div class='disc'>هذه المذكرة لأغراض تعليمية ومراجعة أولية فقط، ولا تغني عن مراجعة واعتماد مهندس إنشائي مرخص. المعادلات وفق الكود المذكور في كل خطوة.</div>
</body></html>"""
    return HTML(string=doc).write_pdf()
