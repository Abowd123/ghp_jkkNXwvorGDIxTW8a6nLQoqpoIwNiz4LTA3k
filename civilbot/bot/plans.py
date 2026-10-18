"""Subscription plans, feature gates and Telegram Stars prices."""
from __future__ import annotations
import os

STARS = {"student": int(os.getenv("PRICE_STUDENT", "150")), "pro": int(os.getenv("PRICE_PRO", "450")), "office": int(os.getenv("PRICE_OFFICE", "1500"))}
DAYS = 30

PLANS = {
    "free":    dict(name="مجاني", daily=int(os.getenv("FREE_DAILY", "10")), pdf=False, ai=False, dxf=False, pro_tools=False, export=False, watermark=True, seats=1, logo=False),
    "student": dict(name="طالب", daily=300, pdf=True, ai=True, dxf=False, pro_tools=False, export=False, watermark=False, seats=1, logo=False),
    "pro":     dict(name="محترف", daily=2000, pdf=True, ai=True, dxf=True, pro_tools=True, export=True, watermark=False, seats=1, logo=False),
    "office":  dict(name="مكاتب", daily=10000, pdf=True, ai=True, dxf=True, pro_tools=True, export=True, watermark=False, seats=10, logo=True),
}
# FREE_MODE=1 (default): everything unlocked for everyone, no payments, no watermark.
# Paid plans stay in the code and come back with FREE_MODE=0 if you ever need them.
FREE_MODE = os.getenv("FREE_MODE", "1").lower() not in ("0", "false", "no")
PLANS["open"] = dict(name="مجاني بالكامل", daily=int(os.getenv("OPEN_DAILY", "300")), pdf=True, ai=True, dxf=True, pro_tools=True,
                     export=True, watermark=False, seats=1, logo=True)
ORDER = ["free", "student", "pro", "office", "open"]
PRO_TOOLS = {"schedule", "boq"}
AI_TOOLS = {"crack", "equation", "layout"}
FILE_GATES = {".dxf": "dxf", ".xlsx": "dxf", ".html": None, ".gif": None}

PITCH = {
    "student": "كل الحاسبات بدون حد تقريباً، مذكرات PDF، الكويزات، قراءة المعادلات وتحليل الشروخ بالذكاء الاصطناعي، وبدون علامة مائية",
    "pro": "كل مزايا الطالب + ملفات DXF و Excel، جدول الأعمدة، حصر الكميات، المشاريع والتصدير ZIP",
    "office": "كل مزايا المحترف + 10 حسابات لفريقك + شعار مكتبك على المذكرات + أولوية في المعالجة",
}


def feature(plan: str, key: str):
    return PLANS.get(plan, PLANS["free"])[key]


def at_least(plan: str, need: str) -> bool:
    return ORDER.index(plan if plan in ORDER else "free") >= ORDER.index(need)
