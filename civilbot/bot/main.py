"""CivilBot — Telegram entry point (python-telegram-bot v21, async).

Run:  BOT_TOKEN=xxx python -m civilbot.bot.main
Env:  BETA_USERS=123,456 (optional whitelist)  ADMIN_IDS=123  DAILY_LIMIT=50
"""
from __future__ import annotations
import asyncio
import re
import io
import logging
import os
import time

from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup as KB, Update, InputFile
from telegram import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from telegram.constants import ParseMode
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters)

from .. import services as S
from .. import services2 as S2
from .. import services3 as S3
from .. import services4 as S4
from ..ai import llm
from ..engines import quiz as QZ
from ..core import InputError
from . import storage
from . import launch as L
from . import plans as PL
from telegram.ext import PreCheckoutQueryHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("civilbot")
logging.getLogger("fontTools").setLevel(logging.WARNING)
logging.getLogger("weasyprint").setLevel(logging.WARNING)

BETA = {int(x) for x in os.getenv("BETA_USERS", "").split(",") if x.strip()}
ADMINS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()}

def _rc(text):
    return S2.enrich_rc(S.run_rc(text), text)


TOOLS = {
    # phase 1
    "beam": ("📈 القص والعزم SFD/BMD", S.BEAM_HELP, S.run_beam),
    "rc": ("🏗 تصميم كمرة خرسانية", S.RC_HELP + "\n• أضف <code>span=6</code> لرسم الواجهة وجدول التفريد", _rc),
    "section": ("📐 خصائص المقاطع", S.SECTION_HELP, S.run_section),
    "formula": ("🧠 القوانين خطوة بخطوة", None, S.run_formula),
    "units": ("🔁 محول الوحدات", S.UNITS_HELP, None),
    # phase 2
    "truss": ("🔺 الجمالونات", S2.TRUSS_HELP, S2.run_truss),
    "frame": ("🏛 الإطارات 2D", S2.FRAME_HELP, S2.run_frame),
    "column": ("🏢 الأعمدة + P-M", S2.COLUMN_HELP, S2.run_column),
    "slab": ("⬜ البلاطات", S2.SLAB_HELP, S2.run_slab),
    "punch": ("🎯 القص الثاقب", S2.SLAB_HELP, S2.run_punch),
    "footing": ("🟫 القواعد", S2.FOOTING_HELP, S2.run_footing),
    "wall": ("🧱 الجدران الساندة", S2.WALL_HELP, S2.run_wall),
    "combo": ("⚖️ تراكيب الأحمال", S2.COMBO_HELP, S2.run_combo),
    "trib": ("🧭 مسار الأحمال", S2.TRIB_HELP, S2.run_trib),
    # phase 3
    "bearing": ("🏔 قدرة التحمل", S3.GEO_HELP, S3.run_bearing),
    "mohr": ("⭕ دائرة مور", S3.GEO_HELP, S3.run_mohr),
    "lateral": ("↔️ الضغط الجانبي", S3.GEO_HELP, S3.run_lateral),
    "consol": ("⬇️ الهبوط", S3.GEO_HELP, S3.run_consol),
    "bulb": ("🫧 بصيلات الإجهاد", S3.GEO_HELP, S3.run_bulb),
    "slope": ("⛰ ثبات المنحدرات", S3.GEO_HELP, S3.run_slope),
    "mix": ("🧪 تصميم الخلطة", S3.MAT_HELP, S3.run_mix),
    "sieve": ("🪣 التحليل المنخلي", S3.MAT_HELP, S3.run_sieve),
    "channel": ("🌊 القنوات المفتوحة", S3.HYD_HELP, S3.run_channel),
    "pipe": ("🚰 الأنابيب", S3.HYD_HELP, S3.run_pipe),
    "traverse": ("📐 المضلعات", S3.SUR_HELP, S3.run_traverse),
    "level": ("📏 الميزانية", S3.SUR_HELP, S3.run_level),
    "hcurve": ("↪️ منحنى أفقي", S3.SUR_HELP, S3.run_hcurve),
    "vcurve": ("⛰ منحنى رأسي", S3.SUR_HELP, S3.run_vcurve),
    "earth": ("🚜 الحفر والردم", S3.SUR_HELP, S3.run_earth),
    "pavement": ("🛣 الرصف AASHTO", S3.SUR_HELP, S3.run_pavement),
    "ssd": ("🚗 مسافة الرؤية", S3.SUR_HELP, S3.run_ssd),
    "sbeam": ("🔩 كمرة معدنية", S3.STEEL_HELP, S3.run_sbeam),
    "scol": ("🏗 عمود معدني", S3.STEEL_HELP, S3.run_scol),
    "stab": ("🔗 وصلة قص", S3.STEEL_HELP, S3.run_stab),
    "bplate": ("🟦 لوح القاعدة", S3.STEEL_HELP, S3.run_bplate),
    "il": ("📉 خطوط التأثير", S3.VIS_HELP, S3.run_il),
    "anim": ("🎬 رسوم متحركة GIF", S3.VIS_HELP, S3.run_anim),
    # phase 4
    "codes": ("📚 مقارنة الأكواد", S4.AI_HELP, S4.run_codes),
    "schedule": ("📋 جدول الأعمدة", S4.SCHED_HELP, S4.run_schedule),
    "boq": ("🧾 حصر الكميات", S4.BOQ_HELP, S4.run_boq),
    "crack": ("🔍 محلل الشروخ (صورة)", S4.AI_HELP, None),
    "equation": ("🧮 قارئ المعادلات (صورة)", S4.AI_HELP, None),
    "layout": ("🏠 توزيع الأعمدة (صورة)", S4.AI_HELP, None),
}
PHOTO_TOOLS = ("crack", "equation", "layout")

CATS = {
    "analysis": ("🧮 التحليل الإنشائي", ["beam", "truss", "frame", "trib", "combo"]),
    "design": ("🏗 التصميم الخرساني", ["rc", "column", "slab", "punch", "footing", "wall"]),
    "geo": ("🌍 ميكانيكا التربة", ["bearing", "mohr", "lateral", "consol", "bulb", "slope"]),
    "steel": ("🔩 المنشآت المعدنية", ["sbeam", "scol", "stab", "bplate"]),
    "civil": ("💧 هيدروليكا ومساحة وطرق", ["channel", "pipe", "traverse", "level", "hcurve", "vcurve", "earth", "pavement", "ssd"]),
    "mat": ("🧪 مواد وخلطات", ["mix", "sieve"]),
    "vis": ("🎬 تصور وحركة", ["il", "anim"]),
    "ai": ("🧠 الذكاء الاصطناعي", ["crack", "equation", "layout", "codes"]),
    "prod": ("📦 الإنتاجية", ["schedule", "boq"]),
    "tools": ("🛠 أدوات ومراجع", ["section", "formula", "units"]),
}


def menu() -> KB:
    keys = list(CATS)
    rows = [[B(CATS[c][0], callback_data=f"cat:{c}") for c in keys[i:i + 2]] for i in range(0, len(keys), 2)]
    rows.append([B("🎓 اختبر نفسك (FE)", callback_data="quizmenu"), B("📋 جدول التفريد BBS", callback_data="bbs")])
    rows.append([B("📁 مشاريعي", callback_data="projects"), B("🕘 السجل", callback_data="history")])
    rows.append([B("✏️ المحرر الرسومي", callback_data="editor"), B("📑 قوالب Excel", callback_data="templates")])
    rows.append(([] if PL.FREE_MODE else [B("⭐ الباقات", callback_data="plans")]) +
                [B("🎁 ادعُ زملاءك", callback_data="invite"), B("💬 ملاحظاتك", callback_data="tool:feedback")])
    return KB(rows)


def cat_menu(c) -> KB:
    keys = CATS[c][1]
    rows = [[B(TOOLS[k][0], callback_data=f"tool:{k}") for k in keys[i:i + 2]] for i in range(0, len(keys), 2)]
    rows.append([B("⬅️ رجوع", callback_data="menu")])
    return KB(rows)


def after_kb() -> KB:
    return KB([[B("📄 مذكرة PDF", callback_data="pdf"), B("🔁 نفس الأداة", callback_data="again"),
                B("🏠 القائمة", callback_data="menu")]])


def allowed(update: Update) -> bool:
    return not BETA or update.effective_user.id in BETA or update.effective_user.id in ADMINS


async def gate(update: Update, tool: str | None = None, feature: str | None = None) -> bool:
    if not allowed(update):
        await update.effective_message.reply_text("🔒 البوت حالياً في مرحلة تجريبية مغلقة. تواصل مع الإدارة للانضمام.")
        return False
    storage.touch_user(update.effective_user.id, update.effective_user.full_name)
    return await L.check(update, tool, feature)


EXAMPLES = {"beam": "L=6 type=ss w=20 P=40@2", "rc": "b=300 h=600 fc=28 fy=420 Mu=250 Vu=180", "truss": "type=pratt span=12 h=3 n=6 P=20"}


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        await update.effective_message.reply_text("🔒 البوت حالياً في مرحلة تجريبية مغلقة.")
        return
    uid = update.effective_user.id
    new = storage.used_today(uid) == 0 and not storage.history(uid, None, 1)
    note = await L.handle_start_payload(update, ctx)
    storage.touch_user(uid, update.effective_user.full_name)
    ctx.user_data.clear()
    if note:
        await update.effective_message.reply_text(note)
    if new:
        await update.effective_message.reply_text(
            "أهلاً بك في <b>CivilBot</b> 👷‍♂️\nأكثر من 60 أداة للمهندس المدني: حسابات، رسومات، DXF، مذكرات PDF وذكاء اصطناعي.\n\n"
            "جرّب مثال بضغطة 👇 أو اكتب المدخلات مباشرة مثل:\n<code>/beam L=6 type=ss w=20</code>",
            parse_mode=ParseMode.HTML, reply_markup=KB([[B("📈 كمرة بسيطة", callback_data="ex:beam"), B("🏗 تصميم كمرة", callback_data="ex:rc")],
                                                        [B("🔺 جمالون", callback_data="ex:truss"), B("📋 القائمة الكاملة", callback_data="menu")]]))
        return
    await update.effective_message.reply_text(
        "أهلاً بك في <b>CivilBot</b> 👷‍♂️\nمساعدك في الحسابات الإنشائية والرسم.\n\nاختر الأداة:",
        parse_mode=ParseMode.HTML, reply_markup=menu())


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = ("<b>الأوامر</b>\n<b>التحليل:</b> /beam /truss /frame /trib /combo\n"
           "<b>التصميم:</b> /rc /column /slab /punch /footing /wall\n"
           "<b>التربة:</b> /bearing /mohr /lateral /consol /bulb /slope\n"
           "<b>المعدني:</b> /sbeam /scol /stab /bplate\n"
           "<b>هيدروليكا/مساحة/طرق:</b> /channel /pipe /traverse /level /hcurve /vcurve /earth /pavement /ssd\n"
           "<b>مواد:</b> /mix /sieve  ·  <b>تصور:</b> /il /anim\n"
           "<b>ذكاء اصطناعي:</b> أرسل صورة (شرخ/معادلة/اسكتش) · /codes\n"
           "<b>إنتاجية:</b> /schedule /boq /projects /history /export /editor /templates\n"
           "<b>أدوات:</b> /section /formula /convert /bbs /quiz /score /feedback\n"
           + ("<b>عام:</b> /invite /myplan /terms /privacy /deleteme\n\n" if PL.FREE_MODE else
              "<b>الحساب:</b> /plans /myplan /invite /redeem /team /terms /privacy /paysupport\n\n") +
           "تقدر تكتب المدخلات مباشرة بعد الأمر، مثل:\n<code>/beam L=6 type=ss w=20</code>")
    await update.effective_message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=menu())


def tool_help(tool: str) -> str:
    if tool == "formula":
        return S.FORMULA_HELP + "<b>القوانين المتاحة:</b>\n" + S.formulas.list_formulas()
    if tool == "feedback":
        return "💬 اكتب ملاحظتك أو المشكلة اللي واجهتك وأرسلها:"
    return TOOLS[tool][1]


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    if data == "menu":
        ctx.user_data.pop("tool", None)
        await q.message.reply_text("اختر الأداة:", reply_markup=menu())
    elif data.startswith("cat:"):
        c = data.split(":", 1)[1]
        await q.message.reply_text(CATS[c][0], reply_markup=cat_menu(c))
    elif data == "bbs":
        await send_bbs(update, ctx)
    elif data.startswith("ex:"):
        t = data.split(":")[1]
        ctx.user_data["tool"] = t
        await run_tool(update, ctx, t, EXAMPLES[t])
    elif data == "plans":
        await L.plans_cmd(update, ctx)
    elif data.startswith("buy:"):
        await L.send_invoice(update, ctx, data.split(":")[1])
    elif data == "invite":
        await L.invite_cmd(update, ctx)
    elif data == "projects":
        await projects_cmd(update, ctx)
    elif data == "newproject":
        ctx.user_data["tool"] = "newproject"
        await q.message.reply_text("📁 اكتب اسم المشروع الجديد:")
    elif data.startswith("proj:"):
        pid = int(data.split(":")[1])
        name = storage.project_name(update.effective_user.id, pid)
        if name:
            ctx.user_data["project"] = pid
            await q.message.reply_text(f"✅ المشروع الحالي: <b>{name}</b>. كل الحسابات الجاية بتنحفظ فيه.", parse_mode=ParseMode.HTML)
    elif data == "history":
        await history_cmd(update, ctx)
    elif data.startswith("rerun:"):
        row = storage.calc(update.effective_user.id, int(data.split(":")[1]))
        if row:
            ctx.user_data["tool"] = row[0]
            await run_tool(update, ctx, row[0], row[1])
    elif data == "export":
        await export_cmd(update, ctx)
    elif data == "editor":
        await editor_cmd(update, ctx)
    elif data == "templates":
        await templates_cmd(update, ctx)
    elif data.startswith("photo:"):
        await run_photo(update, ctx, data.split(":", 1)[1], ctx.user_data.get("photo_caption", ""))
    elif data == "quizmenu":
        await q.message.reply_text("🎓 اختر الموضوع:", reply_markup=quiz_kb())
    elif data.startswith("quiz:"):
        await ask_question(update, ctx, data.split(":", 1)[1])
    elif data == "quiz_show":
        qq = ctx.user_data.pop("quiz", None)
        if qq:
            storage.quiz_log(update.effective_user.id, qq["topic_key"], False)
            await q.message.reply_text(f"💡 الجواب ≈ <b>{S.fmt(qq['ans'], 4)} {qq['unit']}</b>\n<code>{qq['sol']}</code>", parse_mode=ParseMode.HTML,
                                       reply_markup=KB([[B("➡️ السؤال التالي", callback_data=f"quiz:{qq['topic_key']}")]]))
    elif data == "score":
        await score_cmd(update, ctx)
    elif data == "bbs_clear":
        ctx.user_data["bbs"] = []
        await q.message.reply_text("🗑 تم تفريغ جدول التفريد.")
    elif data.startswith("tool:"):
        tool = data.split(":", 1)[1]
        ctx.user_data["tool"] = tool
        await q.message.reply_text(tool_help(tool), parse_mode=ParseMode.HTML)
    elif data == "again":
        tool = ctx.user_data.get("tool")
        if tool:
            await q.message.reply_text(tool_help(tool), parse_mode=ParseMode.HTML)
    elif data == "pdf":
        res = ctx.user_data.get("last")
        if not res:
            await q.message.reply_text("ما في نتيجة محفوظة. شغّل حساب أولاً.")
            return
        if not await gate(update, feature="pdf"):
            return
        await q.message.chat.send_action("upload_document")
        uid_ = update.effective_user.id
        pdf = await L.offload("pdf", res, update.effective_user.full_name, storage.logo_for(uid_) if L.plan(uid_) == "office" else None, None)
        await q.message.reply_document(InputFile(io.BytesIO(pdf), filename=f"CivilBot_{res.tool}.pdf"),
                                       caption="📄 المذكرة الحسابية")


def quiz_kb() -> KB:
    ks = list(QZ.TOPIC_AR)
    rows = [[B(QZ.TOPIC_AR[k], callback_data=f"quiz:{k}") for k in ks[i:i + 2]] for i in range(0, len(ks), 2)]
    rows.append([B("📊 نتيجتي", callback_data="score"), B("⬅️ رجوع", callback_data="menu")])
    return KB(rows)


async def ask_question(update: Update, ctx: ContextTypes.DEFAULT_TYPE, topic: str):
    q = QZ.new_question(topic)
    q["topic_key"] = topic
    ctx.user_data["quiz"] = q
    ctx.user_data["tool"] = "quiz"
    await update.effective_message.reply_text(f"🎓 <b>{q['topic']}</b>\n\n{q['q']}\n\nأرسل الجواب رقم فقط ({q['unit']}). سماحية ±2%",
                                              parse_mode=ParseMode.HTML, reply_markup=KB([[B("💡 الحل", callback_data="quiz_show"), B("⏭ سؤال آخر", callback_data=f"quiz:{topic}")]]))


async def answer_quiz(update: Update, ctx: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    q = ctx.user_data.get("quiz")
    if not q:
        return False
    m = re.search(r"[-+]?\d[\d,]*\.?\d*(?:e[-+]?\d+)?", text.replace("٫", ".").translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
    if not m:
        return False
    val = float(m.group(0).replace(",", ""))
    ok = QZ.grade(q, val)
    storage.quiz_log(update.effective_user.id, q["topic_key"], ok)
    ctx.user_data.pop("quiz", None)
    head = "✅ صح! " if ok else f"❌ مو دقيق. الجواب الصحيح ≈ <b>{S.fmt(q['ans'], 4)} {q['unit']}</b>\n"
    await update.effective_message.reply_text(head + f"\n<b>الحل:</b>\n<code>{q['sol']}</code>", parse_mode=ParseMode.HTML,
                                              reply_markup=KB([[B("➡️ السؤال التالي", callback_data=f"quiz:{q['topic_key']}"), B("📊 نتيجتي", callback_data="score")]]))
    return True


async def send_bbs(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    bars = ctx.user_data.get("bbs") or []
    if not bars:
        await msg.reply_text("جدول التفريد فاضي. صمّم عناصر (كمرة مع span، عمود، قاعدة، بلاطة، جدار) وبتنضاف تلقائياً.")
        return
    if not await gate(update, feature="dxf"):
        return
    files, png = await L.offload("bbs", bars)
    await msg.reply_photo(io.BytesIO(png), caption=f"📋 جدول تفريد الحديد ({len(bars)} بند)")
    for name, data in files.items():
        await msg.reply_document(InputFile(io.BytesIO(data), filename=name))
    await msg.reply_text("تبي تفرغ الجدول وتبدأ مشروع جديد؟", reply_markup=KB([[B("🗑 تفريغ", callback_data="bbs_clear")]]))


async def run_tool(update: Update, ctx: ContextTypes.DEFAULT_TYPE, tool: str, text: str):
    if not await gate(update, tool=tool):
        return
    msg = update.effective_message
    uid = update.effective_user.id
    t0 = time.perf_counter()
    ok = False
    try:
        if tool == "units":
            out = S.run_units(text)
            await msg.reply_text(out, parse_mode=ParseMode.HTML)
            ok = True
            return
        await msg.chat.send_action("upload_photo")
        res = await L.offload("tool", tool, text, cache=True)
        ctx.user_data["last"] = res
        summary = S.summary_html(res)
        imgs, files, locked = L.filter_output(uid, res)
        for name, png in imgs.items():
            await msg.reply_photo(io.BytesIO(png))
        if locked:
            await msg.reply_text(f"🔒 ملفات {', '.join(locked)} (أوتوكاد/Excel) متاحة في باقة المحترف.", reply_markup=L.upsell_kb("pro"))
        for fname, data in files.items():
            if fname.endswith(".gif"):
                await msg.reply_animation(InputFile(io.BytesIO(data), filename=fname))
            else:
                await msg.reply_document(InputFile(io.BytesIO(data), filename=fname),
                                         caption="📐 ملف أوتوكاد DXF" if fname.endswith(".dxf") else None)
        new_bars = res.outputs.get("bbs") if isinstance(res.outputs, dict) else None
        if new_bars:
            import copy
            new_bars = copy.deepcopy(new_bars)   # cached results must not be mutated
            store = ctx.user_data.setdefault("bbs", [])
            idx = len({b.member for b in store}) + 1
            for b in new_bars:
                b.member = f"{b.member[0]}{idx}"
                b.mark = f"{b.member}-{b.mark.split('-')[-1]}"
            store.extend(new_bars)
        # Telegram message limit = 4096 chars
        chunks = [summary[i:i + 3900] for i in range(0, len(summary), 3900)] if len(summary) > 4000 else [summary]
        for i, ch in enumerate(chunks):
            await msg.reply_text(ch, parse_mode=ParseMode.HTML, reply_markup=after_kb() if i == len(chunks) - 1 else None)
        if new_bars:
            await msg.reply_text(f"➕ انضاف {len(new_bars)} بند لجدول التفريد. اضغط BBS من القائمة أو /bbs لتصديره.")
        raw = getattr(res, "_res", None)
        if raw is not None and tool in ("frame", "truss"):
            model = S4.model3d(raw, tool)
            url = S4.viewer_url(model)
            if url:
                await msg.reply_text("🧊 شوف المنشأ ثلاثي الأبعاد مع التشوه المتحرك:", reply_markup=KB([[B("🧊 عرض 3D", web_app=WebAppInfo(url=url))]]))
            else:
                await msg.reply_document(InputFile(io.BytesIO(S4.viewer_html(model)), filename=f"{tool}_3d.html"),
                                         caption="🧊 افتح الملف في المتصفح لعرض 3D تفاعلي")
        storage.save_calc(uid, ctx.user_data.get("project"), tool, text, res.steps[-1].result if res.steps else "")
        ok = True
    except InputError as e:
        await msg.reply_text(f"⚠️ {e}\n\nاكتب /help أو اضغط القائمة لعرض الأمثلة.", reply_markup=KB([[B("🏠 القائمة", callback_data="menu")]]))
    except asyncio.TimeoutError:
        await msg.reply_text("⌛ الحساب أخذ وقت أطول من المسموح. بسّط النموذج أو قلل الدقة وجرب مرة ثانية.")
    except Exception:
        log.exception("tool %s failed for input %r", tool, text)
        await msg.reply_text("صار خطأ غير متوقع 😕 تم تسجيله وبنصلحه. جرّب مدخلات مختلفة أو أرسل /feedback.")
    finally:
        storage.log(uid, tool, ok, int((time.perf_counter() - t0) * 1000))


def _cmd(tool):
    async def h(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        ctx.user_data["tool"] = tool
        raw = update.effective_message.text or ""
        args = raw.split(None, 1)[1] if (raw.startswith("/") and len(raw.split(None, 1)) > 1) else (" ".join(ctx.args) if ctx.args else "")
        if args.strip():
            await run_tool(update, ctx, tool, args)
        else:
            await update.effective_message.reply_text(tool_help(tool), parse_mode=ParseMode.HTML)
    return h


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tool = ctx.user_data.get("tool")
    text = update.effective_message.text or ""
    if tool == "feedback":
        storage.feedback(update.effective_user.id, text)
        ctx.user_data.pop("tool", None)
        await update.effective_message.reply_text("🙏 شكراً! وصلت ملاحظتك.", reply_markup=menu())
        for a in ADMINS:
            try:
                await ctx.bot.send_message(a, f"💬 Feedback from {update.effective_user.full_name} ({update.effective_user.id}):\n{text}")
            except Exception:
                pass
        return
    if tool == "newproject":
        pid = storage.new_project(update.effective_user.id, text.strip() or "مشروع")
        ctx.user_data["project"] = pid
        ctx.user_data.pop("tool", None)
        await update.effective_message.reply_text(f"✅ أنشأت المشروع <b>{text.strip()}</b> وصار هو الحالي.", parse_mode=ParseMode.HTML)
        return
    if tool == "eqcalc" and ctx.user_data.get("eq"):
        try:
            res = S4.eval_equation(ctx.user_data["eq"], text)
            await update.effective_message.reply_text(S.summary_html(res), parse_mode=ParseMode.HTML)
        except InputError as e:
            await update.effective_message.reply_text(f"⚠️ {e}")
        return
    if tool in PHOTO_TOOLS:
        await update.effective_message.reply_text("📷 أرسل صورة (مع وصف اختياري). " + ("مثال الوصف: element=beam coin=25" if tool == "crack" else "مثال الوصف: L=15 span=6" if tool == "layout" else ""))
        return
    if tool == "quiz":
        if await answer_quiz(update, ctx, text):
            return
        ctx.user_data.pop("tool", None)
        tool = None
    if not tool:
        # smart routing: guess tool from text
        low = " " + text.lower()
        has = lambda k: re.search(r"(?<![a-z0-9_])" + k + r"\s*=", low) is not None
        if has("pu"):
            tool = "column"
        elif has("pd"):
            tool = "footing"
        elif has("phi") and has("h"):
            tool = "wall"
        elif has("mu"):
            tool = "rc"
        elif has("n") and has("m") and has("s"):
            tool = "frame" if (has("w") or has("i") or has("hinge")) else "truss"
        elif has("sx") and has("sy"):
            tool = "mohr"
        elif has("phi") and has("df"):
            tool = "bearing"
        elif has("cc") and has("e0"):
            tool = "consol"
        elif has("sizes") and has("mass"):
            tool = "sieve"
        elif has("az") and has("d"):
            tool = "traverse"
        elif has("rows") and has("rl"):
            tool = "level"
        elif has("g1") and has("g2"):
            tool = "vcurve"
        elif has("w18"):
            tool = "pavement"
        elif has("n") and has("s") and (has("q") or has("y")) and has("shape"):
            tool = "channel"
        elif has("x") and has("y") and has("q"):
            tool = "trib"
        elif has("lx") and has("ly"):
            tool = "slab"
        elif has("d") and (has("l") or has("w")) and not has("p"):
            tool = "combo"
        elif has("l") and (has("p") or has("w") or has("m")):
            tool = "beam"
        elif low.split()[:1] and low.split()[0] in ("rect", "t", "i", "l", "c", "circle", "pipe", "hrect", "poly"):
            tool = "section"
        else:
            await update.effective_message.reply_text("اختر الأداة أولاً:", reply_markup=menu())
            return
        ctx.user_data["tool"] = tool
    await run_tool(update, ctx, tool, text)


async def score_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = storage.quiz_stats(update.effective_user.id)
    if not rows:
        await update.effective_message.reply_text("ما حليت أي سؤال بعد. جرب /quiz")
        return
    lines = ["📊 <b>نتيجتك</b>"]
    tot = cor = 0
    for topic, n, ok in rows:
        ok = ok or 0
        tot += n; cor += ok
        bar = "🟩" * round(10 * ok / n) + "⬜" * (10 - round(10 * ok / n))
        lines.append(f"{QZ.TOPIC_AR.get(topic, topic)}: {ok}/{n} {bar}")
    weak = min(rows, key=lambda t: (t[2] or 0) / t[1])
    lines.append(f"\nالإجمالي: {cor}/{tot} ({round(100 * cor / tot)}%)\n🎯 ركّز على: {QZ.TOPIC_AR.get(weak[0], weak[0])}")
    await update.effective_message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def quiz_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await gate(update):
        return
    topic = (ctx.args[0].lower() if ctx.args else "")
    if topic in QZ.TOPIC_AR:
        await ask_question(update, ctx, topic)
    else:
        await update.effective_message.reply_text("🎓 اختر الموضوع:", reply_markup=quiz_kb())


async def projects_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = storage.projects(update.effective_user.id)
    cur = ctx.user_data.get("project")
    kb = [[B(("✅ " if pid == cur else "📁 ") + f"{name} ({n})", callback_data=f"proj:{pid}")] for pid, name, created, n in rows[:10]]
    kb.append([B("➕ مشروع جديد", callback_data="newproject"), B("📦 تصدير الحالي", callback_data="export")])
    await update.effective_message.reply_text("📁 <b>مشاريعك</b>" if rows else "ما عندك مشاريع. أنشئ واحد:", parse_mode=ParseMode.HTML, reply_markup=KB(kb))


async def newproject_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = " ".join(ctx.args) if ctx.args else ""
    if not name:
        ctx.user_data["tool"] = "newproject"
        await update.effective_message.reply_text("📁 اكتب اسم المشروع:")
        return
    ctx.user_data["project"] = storage.new_project(update.effective_user.id, name)
    await update.effective_message.reply_text(f"✅ المشروع الحالي: {name}")


async def history_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = storage.history(update.effective_user.id, ctx.user_data.get("project"), 10)
    if not rows:
        await update.effective_message.reply_text("السجل فاضي.")
        return
    lines, kb = ["🕘 <b>آخر الحسابات</b>"], []
    for cid, tool, inp, summ, at in rows:
        lines.append(f"#{cid} <b>{TOOLS.get(tool, (tool,))[0]}</b>\n<code>{inp[:70]}</code>\n➜ {summ[:80]}")
        kb.append([B(f"🔁 إعادة #{cid}", callback_data=f"rerun:{cid}")])
    await update.effective_message.reply_text("\n\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=KB(kb[:8]))


async def export_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await gate(update, feature="export"):
        return
    pid = ctx.user_data.get("project")
    rows = storage.history(update.effective_user.id, pid, 60)
    if not rows:
        await update.effective_message.reply_text("ما في حسابات للتصدير.")
        return
    await update.effective_message.chat.send_action("upload_document")

    uid_ = update.effective_user.id
    data = await L.offload("export", rows, update.effective_user.full_name, storage.logo_for(uid_) if L.plan(uid_) == "office" else None)
    name = storage.project_name(update.effective_user.id, pid) if pid else "history"
    await update.effective_message.reply_document(InputFile(io.BytesIO(data), filename=f"CivilBot_{name}.zip"), caption="📦 كل المذكرات والملفات")


async def editor_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    base = os.getenv("WEBAPP_URL")
    if not base:
        await update.effective_message.reply_text("✏️ المحرر الرسومي يحتاج استضافة ملفات webapp وضبط WEBAPP_URL. راجع README.")
        return
    kb = ReplyKeyboardMarkup([[KeyboardButton("✏️ افتح المحرر", web_app=WebAppInfo(url=base.rstrip("/") + "/editor.html"))]], resize_keyboard=True, one_time_keyboard=True)
    await update.effective_message.reply_text("ارسم الإطار أو الجمالون ثم اضغط «حلّل في البوت»:", reply_markup=kb)


async def on_webapp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        kind, text = S4.webapp_to_text(update.effective_message.web_app_data.data)
    except InputError as e:
        await update.effective_message.reply_text(f"⚠️ {e}")
        return
    ctx.user_data["tool"] = kind
    await update.effective_message.reply_text(f"📥 استلمت النموذج:\n<code>{text}</code>", parse_mode=ParseMode.HTML)
    await run_tool(update, ctx, kind, text)


async def templates_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_document(InputFile(io.BytesIO(S4.templates_xlsx()), filename="CivilBot_templates.xlsx"),
                                                  caption="📑 كل ورقة = أداة، وكل صف = حساب. عدّل وارفع الملف هنا وبرجع لك النتائج.")


async def on_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    doc = update.effective_message.document
    name = (doc.file_name or "").lower()
    f = await doc.get_file()
    data = bytes(await f.download_as_bytearray())
    if name.endswith((".png", ".jpg", ".jpeg", ".webp")):
        await on_photo_bytes(update, ctx, data, update.effective_message.caption or "")
        return
    if not name.endswith(".xlsx"):
        await update.effective_message.reply_text("أدعم ملفات Excel (.xlsx) والصور حالياً.")
        return
    if not await gate(update, feature="import"):
        return
    try:
        out, summary, specials = await L.offload("import", data)
    except InputError as e:
        await update.effective_message.reply_text(f"⚠️ {e}")
        return
    await update.effective_message.reply_text("📥 <b>نتيجة الاستيراد</b>\n" + "\n".join(summary), parse_mode=ParseMode.HTML)
    if out:
        await update.effective_message.reply_document(InputFile(io.BytesIO(out), filename="CivilBot_results.xlsx"))
    for res in specials:
        for png in res.images.values():
            await update.effective_message.reply_photo(io.BytesIO(png))
        for fname, d in res.files.items():
            await update.effective_message.reply_document(InputFile(io.BytesIO(d), filename=fname))


async def on_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data.get("tool") == "logo":
        if not await gate(update, feature="logo"):
            return
        f = await update.effective_message.photo[-1].get_file()
        storage.set_logo(update.effective_user.id, bytes(await f.download_as_bytearray()))
        ctx.user_data.pop("tool", None)
        await update.effective_message.reply_text("✅ حفظت شعار مكتبك، بيظهر على كل المذكرات.")
        return
    if not allowed(update):
        return
    ph = update.effective_message.photo[-1]
    f = await ph.get_file()
    data = bytes(await f.download_as_bytearray())
    await on_photo_bytes(update, ctx, data, update.effective_message.caption or "")


async def on_photo_bytes(update, ctx, data: bytes, caption: str):
    ctx.user_data["photo"] = data
    ctx.user_data["photo_caption"] = caption
    first = caption.strip().split()[0].lower() if caption.strip() else ""
    kind = first if first in PHOTO_TOOLS else (ctx.user_data.get("tool") if ctx.user_data.get("tool") in PHOTO_TOOLS else None)
    if kind:
        await run_photo(update, ctx, kind, caption)
        return
    await update.effective_message.reply_text("📷 وش تبي أسوي بالصورة؟", reply_markup=KB([
        [B("🔍 تحليل شرخ", callback_data="photo:crack"), B("🧮 قراءة معادلة", callback_data="photo:equation")],
        [B("🏠 توزيع أعمدة على اسكتش", callback_data="photo:layout")]]))


async def run_photo(update, ctx, kind: str, caption: str):
    msg = update.effective_message
    if not await gate(update, tool=kind):
        return
    data = ctx.user_data.get("photo")
    if not data:
        await msg.reply_text("أرسل الصورة أول.")
        return
    uid = update.effective_user.id
    t0 = time.perf_counter()
    ok = False
    try:
        await msg.chat.send_action("typing")
        eq, res = await L.offload("photo", kind, data, caption)
        if kind == "equation":
            ctx.user_data["eq"] = eq
            ctx.user_data["tool"] = "eqcalc"
        ctx.user_data["last"] = res
        imgs, _, _ = L.filter_output(uid, res)
        for png in imgs.values():
            await msg.reply_photo(io.BytesIO(png))
        tail = "\n\n🧮 أرسل القيم الآن (مثل E=200e6 I=8e-6) وبحسبها لك، أو قيمة الطرف الأيسر مع البقية لحل المجهول." if kind == "equation" else ""
        await msg.reply_text(S.summary_html(res) + tail, parse_mode=ParseMode.HTML, reply_markup=after_kb())
        ok = True
    except InputError as e:
        await msg.reply_text(f"⚠️ {e}")
    except llm.LLMError as e:
        await msg.reply_text(f"🤖 {e}")
    except Exception:
        log.exception("photo tool %s failed", kind)
        await msg.reply_text("صار خطأ غير متوقع أثناء تحليل الصورة 😕")
    finally:
        storage.log(uid, kind, ok, int((time.perf_counter() - t0) * 1000))


def build_app() -> Application:
    token = os.environ["BOT_TOKEN"]
    app = (Application.builder().token(token).concurrent_updates(True)
           .post_init(L.post_init).post_shutdown(L.post_shutdown).build())
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, L.paid), group=-1)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("beam", _cmd("beam")))
    app.add_handler(CommandHandler("rc", _cmd("rc")))
    app.add_handler(CommandHandler("section", _cmd("section")))
    app.add_handler(CommandHandler("formula", _cmd("formula")))
    app.add_handler(CommandHandler("convert", _cmd("units")))
    for t in ("truss", "frame", "column", "slab", "punch", "footing", "wall", "combo", "trib",
              "bearing", "mohr", "lateral", "consol", "bulb", "slope", "mix", "sieve", "channel", "pipe", "traverse", "level",
              "hcurve", "vcurve", "earth", "pavement", "ssd", "sbeam", "scol", "stab", "bplate", "il", "anim"):
        app.add_handler(CommandHandler(t, _cmd(t)))
    app.add_handler(CommandHandler("bbs", send_bbs))
    app.add_handler(CommandHandler("quiz", quiz_cmd))
    for t in ("codes", "schedule", "boq"):
        app.add_handler(CommandHandler(t, _cmd(t)))
    app.add_handler(CommandHandler("projects", projects_cmd))
    app.add_handler(CommandHandler("newproject", newproject_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(CommandHandler("export", export_cmd))
    app.add_handler(CommandHandler("editor", editor_cmd))
    app.add_handler(CommandHandler("templates", templates_cmd))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, on_webapp))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(CommandHandler("score", score_cmd))
    app.add_handler(CommandHandler("feedback", lambda u, c: on_button_feedback(u, c)))
    app.add_handler(CommandHandler("stats", L.stats_cmd))
    for name, fn in (("plans", L.plans_cmd), ("myplan", L.myplan_cmd), ("invite", L.invite_cmd), ("redeem", L.redeem_cmd),
                     ("team", L.team_cmd), ("myid", L.myid_cmd), ("grant", L.grant_cmd), ("revoke", L.revoke_cmd), ("promo", L.promo_cmd),
                     ("refund", L.refund_cmd), ("broadcast", L.broadcast_cmd), ("backup", L.backup_cmd), ("terms", L.terms_cmd),
                     ("privacy", L.privacy_cmd), ("paysupport", L.paysupport_cmd), ("deleteme", L.deleteme_cmd), ("logo", logo_cmd)):
        app.add_handler(CommandHandler(name, fn))
    app.add_handler(PreCheckoutQueryHandler(L.precheckout))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return app


async def logo_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await gate(update, feature="logo"):
        return
    ctx.user_data["tool"] = "logo"
    await update.effective_message.reply_text("🖼 أرسل صورة شعار مكتبك (PNG بخلفية بيضاء أو شفافة).")


async def on_button_feedback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["tool"] = "feedback"
    await update.effective_message.reply_text(tool_help("feedback"))


def main():
    app = build_app()
    url = os.getenv("WEBHOOK_URL")
    if url:  # production
        app.run_webhook(listen="0.0.0.0", port=int(os.getenv("PORT", "8080")), url_path="tg",
                        webhook_url=f"{url.rstrip('/')}/tg", secret_token=os.getenv("WEBHOOK_SECRET"))
    else:    # local dev
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
