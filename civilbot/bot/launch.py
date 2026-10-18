"""Phase 5 — public launch: process pool + cache + rate limiting, subscription gates, Telegram Stars payments,
referrals & promo codes, admin tools (KPIs, broadcast, grants, refunds, backups), legal pages, bot profile setup."""
from __future__ import annotations
import asyncio
import collections
import datetime as dt
import hashlib
import io
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor

from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup as KB, LabeledPrice, Update, BotCommand
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from .. import runner
from ..drawing import watermark
from . import storage, plans as PL

log = logging.getLogger("civilbot.launch")
ADMINS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()}
WORKERS = int(os.getenv("WORKERS", str(max(1, (os.cpu_count() or 2) - 1))))
TIMEOUT = float(os.getenv("JOB_TIMEOUT", "90"))
SUPPORT = os.getenv("SUPPORT_CONTACT", "@CivilBotSupport")
BACKUP_DIR = os.getenv("BACKUP_DIR", "/data/backups")

POOL: ProcessPoolExecutor | None = None
SEM: asyncio.Semaphore | None = None


# ------------------------------------------------------------------ execution: pool, cache, rate limit
class TTLCache:
    def __init__(self, size=512, ttl=3600):
        self.size, self.ttl, self.d = size, ttl, collections.OrderedDict()
        self.hits = self.miss = 0

    def get(self, k):
        v = self.d.get(k)
        if v and time.time() - v[0] < self.ttl:
            self.d.move_to_end(k); self.hits += 1
            return v[1]
        self.miss += 1
        return None

    def put(self, k, val):
        self.d[k] = (time.time(), val)
        self.d.move_to_end(k)
        while len(self.d) > self.size:
            self.d.popitem(last=False)


CACHE = TTLCache(int(os.getenv("CACHE_SIZE", "512")))


def _norm(text):
    return " ".join(text.strip().lower().split())


def start_pool():
    global POOL, SEM
    if WORKERS > 0 and POOL is None:
        POOL = ProcessPoolExecutor(max_workers=WORKERS, initializer=runner.init_worker)
        for f in [POOL.submit(runner.warmup) for _ in range(WORKERS)]:
            try:
                f.result(timeout=120)
            except Exception:
                log.exception("worker warmup failed")
    SEM = asyncio.Semaphore(max(2, WORKERS * 2)) if WORKERS > 0 else asyncio.Semaphore(1)


async def offload(job, *args, cache=False, priority=False):
    key = None
    if cache and job == "tool":
        key = hashlib.sha1(f"{args[0]}|{_norm(args[1])}".encode()).hexdigest()
        hit = CACHE.get(key)
        if hit is not None:
            return hit
    global SEM
    if SEM is None:
        # WORKERS=0 (tiny hosts): run in a thread, one at a time, because matplotlib is not thread-safe
        SEM = asyncio.Semaphore(max(2, WORKERS * 2)) if WORKERS > 0 else asyncio.Semaphore(1)
    async with SEM:
        loop = asyncio.get_running_loop()
        if POOL is not None:
            res = await asyncio.wait_for(loop.run_in_executor(POOL, runner.execute, job, *args), TIMEOUT)
        else:
            res = await asyncio.wait_for(asyncio.to_thread(runner.execute, job, *args), TIMEOUT)
    if key:
        CACHE.put(key, res)
    return res


class RateLimiter:
    """Token bucket per user: burst N, refill r tokens/sec."""
    def __init__(self, burst=5, rate=0.5):
        self.burst, self.rate, self.b = burst, rate, {}

    def allow(self, uid):
        now = time.monotonic()
        tok, last = self.b.get(uid, (self.burst, now))
        tok = min(self.burst, tok + (now - last) * self.rate)
        if tok < 1:
            self.b[uid] = (tok, now)
            return False
        self.b[uid] = (tok - 1, now)
        return True


RL = RateLimiter(int(os.getenv("RL_BURST", "6")), float(os.getenv("RL_RATE", "0.5")))


# ------------------------------------------------------------------ gates
def plan(uid):
    if PL.FREE_MODE:
        return "open"
    return "office" if uid in ADMINS else storage.plan_of(uid)


def upsell_kb(need="student"):
    return KB([[B(f"⭐ اشترك ({PL.PLANS[need]['name']})", callback_data=f"buy:{need}"), B("📋 الباقات", callback_data="plans")]])


async def check(update: Update, tool: str | None = None, feature: str | None = None) -> bool:
    """Daily quota + rate limit + feature gating. Returns True if allowed."""
    uid = update.effective_user.id
    msg = update.effective_message
    p = plan(uid)
    if uid not in ADMINS and not RL.allow(uid):
        await msg.reply_text("⏳ شوي شوي… استنى ثواني بين الطلبات.")
        return False
    lim = PL.PLANS[p]["daily"]
    if uid not in ADMINS and storage.used_today(uid) >= lim:
        if PL.FREE_MODE:
            await msg.reply_text(f"وصلت للحد اليومي ({lim} عملية) 🌙 هذا الحد فقط لحماية الخدمة من الإساءة، ويتجدد بكرة.")
        else:
            await msg.reply_text(f"وصلت للحد اليومي لباقتك ({lim} عملية). جدد بكرة، أو ارفع باقتك 👇", reply_markup=upsell_kb("student" if p == "free" else "pro"))
        return False
    need = None
    if tool in PL.PRO_TOOLS or feature in ("export", "import", "dxf"):
        need = "pro"
    elif tool in PL.AI_TOOLS or feature in ("pdf", "ai"):
        need = "student"
    elif feature == "logo":
        need = "office"
    if need and not PL.at_least(p, need):
        what = {"pro": "هذي الميزة لباقة المحترف", "student": "هذي الميزة لباقة الطالب وما فوق", "office": "هذي الميزة لباقة المكاتب"}[need]
        await msg.reply_text(f"🔒 {what}.\n{PL.PITCH[need]}", reply_markup=upsell_kb(need))
        return False
    return True


def filter_output(uid, res):
    """Apply watermark / strip gated files. Returns (images, files, notes)."""
    p = plan(uid)
    imgs = {k: (watermark.apply(v) if PL.PLANS[p]["watermark"] else v) for k, v in res.images.items()}
    files, locked = {}, []
    for fn, data in res.files.items():
        ext = os.path.splitext(fn)[1].lower()
        gate = PL.FILE_GATES.get(ext)
        if gate and not PL.PLANS[p][gate]:
            locked.append(fn)
        else:
            files[fn] = data
    return imgs, files, locked


# ------------------------------------------------------------------ plans & payments
def plans_text(uid):
    p = plan(uid)
    exp = storage.expires(uid)
    lines = [f"📋 <b>الباقات</b>  —  باقتك: <b>{PL.PLANS[p]['name']}</b>" + (f" (حتى {exp:%Y-%m-%d})" if exp and p != 'free' else "")]
    lines.append(f"\n🆓 <b>مجاني</b>: الحاسبات الأساسية، {PL.PLANS['free']['daily']} عمليات يومياً، صور بعلامة مائية")
    for k in ("student", "pro", "office"):
        lines.append(f"\n⭐ <b>{PL.PLANS[k]['name']}</b> — {PL.STARS[k]} نجمة / {PL.DAYS} يوم\n{PL.PITCH[k]}")
    lines.append("\n🎁 ادعُ زملاءك بـ /invite وخذ أيام مجانية · عندك كود؟ /redeem CODE")
    return "\n".join(lines)


def plans_kb():
    return KB([[B(f"🎓 طالب {PL.STARS['student']}⭐", callback_data="buy:student"), B(f"💼 محترف {PL.STARS['pro']}⭐", callback_data="buy:pro")],
               [B(f"🏢 مكاتب {PL.STARS['office']}⭐", callback_data="buy:office")]])


FREE_TEXT = ("🎉 <b>CivilBot مجاني بالكامل</b>\nكل الأدوات مفتوحة للجميع: الحاسبات، مذكرات PDF، ملفات DXF و Excel، "
             "جدول الأعمدة، حصر الكميات، الذكاء الاصطناعي، المشاريع والتصدير. بدون اشتراك وبدون علامة مائية.\n\n"
             "أكبر دعم لنا: شارك البوت مع زملائك 👇 /invite")


async def plans_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if PL.FREE_MODE:
        await update.effective_message.reply_text(FREE_TEXT, parse_mode=ParseMode.HTML)
        return
    await update.effective_message.reply_text(plans_text(update.effective_user.id), parse_mode=ParseMode.HTML, reply_markup=plans_kb())


async def send_invoice(update: Update, ctx: ContextTypes.DEFAULT_TYPE, plan_key: str):
    if PL.FREE_MODE or plan_key not in PL.STARS:
        await update.effective_message.reply_text(FREE_TEXT, parse_mode=ParseMode.HTML)
        return
    uid = update.effective_user.id
    await ctx.bot.send_invoice(chat_id=update.effective_chat.id, title=f"CivilBot — باقة {PL.PLANS[plan_key]['name']}",
                               description=PL.PITCH[plan_key][:255], payload=f"sub:{plan_key}:{uid}", provider_token="", currency="XTR",
                               prices=[LabeledPrice(f"{PL.PLANS[plan_key]['name']} ({PL.DAYS} يوم)", PL.STARS[plan_key])])


async def precheckout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.pre_checkout_query
    try:
        kind, plan_key, uid = q.invoice_payload.split(":")
        ok = not PL.FREE_MODE and kind == "sub" and plan_key in PL.STARS and int(uid) == q.from_user.id and q.total_amount == PL.STARS[plan_key] and q.currency == "XTR"
    except ValueError:
        ok = False
    await q.answer(ok=ok, error_message=None if ok else "طلب دفع غير صالح، جرّب من /plans")


async def paid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    sp = update.effective_message.successful_payment
    _, plan_key, _ = sp.invoice_payload.split(":")
    uid = update.effective_user.id
    storage.record_payment(uid, plan_key, sp.total_amount, sp.telegram_payment_charge_id)
    exp = storage.grant(uid, plan_key, PL.DAYS)
    await update.effective_message.reply_text(f"🎉 تم تفعيل باقة <b>{PL.PLANS[plan_key]['name']}</b> حتى {exp[:10]}. شكراً لدعمك!",
                                              parse_mode=ParseMode.HTML)
    for a in ADMINS:
        try:
            await ctx.bot.send_message(a, f"💰 {update.effective_user.full_name} ({uid}) اشترى {plan_key} بـ {sp.total_amount}⭐")
        except Exception:
            pass


async def myplan_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if PL.FREE_MODE:
        await update.effective_message.reply_text(
            f"👤 كل الأدوات مفتوحة لك مجاناً\n📊 استخدام اليوم: {storage.used_today(uid)}/{PL.PLANS['open']['daily']}\n👥 دعوت: {storage.referral_count(uid)} شخص")
        return
    p = plan(uid)
    exp = storage.expires(uid)
    used = storage.used_today(uid)
    await update.effective_message.reply_text(
        f"👤 باقتك: <b>{PL.PLANS[p]['name']}</b>" + (f"\n⏳ تنتهي: {exp:%Y-%m-%d}" if exp and p != "free" else "") +
        f"\n📊 استخدام اليوم: {used}/{PL.PLANS[p]['daily']}\n👥 دعوت: {storage.referral_count(uid)} شخص",
        parse_mode=ParseMode.HTML, reply_markup=plans_kb() if p == "free" else None)


# ------------------------------------------------------------------ referrals & promo
REF_DAYS = int(os.getenv("REF_DAYS", "3"))


async def handle_start_payload(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> str | None:
    """Deep links: /start ref_123 , /start promo_CODE. Returns a welcome note or None."""
    if not ctx.args:
        return None
    arg = ctx.args[0]
    uid = update.effective_user.id
    if arg.startswith("ref_"):
        try:
            ref = int(arg[4:])
        except ValueError:
            return None
        if not storage.add_referral(uid, ref):
            return None
        if PL.FREE_MODE:
            try:
                await ctx.bot.send_message(ref, "🙌 انضم زميل عن طريق رابطك، شكراً إنك تنشر CivilBot!")
            except Exception:
                pass
            return None
        storage.grant(uid, "student", REF_DAYS)
        if storage.plan_of(ref) in ("free", "student"):
            storage.grant(ref, "student", REF_DAYS)
        try:
            await ctx.bot.send_message(ref, f"🎁 انضم زميل عن طريق رابطك! أضفنا لك {REF_DAYS} أيام باقة طالب.")
        except Exception:
            pass
        return f"🎁 هديتك: {REF_DAYS} أيام باقة طالب مجاناً."
    if arg.startswith("promo_") and PL.FREE_MODE:
        return None
    if arg.startswith("promo_"):
        exp, res = storage.redeem(arg[6:], uid)
        return f"🎟 تم تفعيل باقة {PL.PLANS[res]['name']} حتى {exp[:10]}" if exp else f"🎟 {res}"
    return None


async def invite_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    me = await ctx.bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{update.effective_user.id}"
    if PL.FREE_MODE:
        await update.effective_message.reply_text(
            f"🙌 CivilBot مجاني، وانتشاره يعتمد عليكم. شارك رابطك مع زملائك:\n{link}\n\nدعوت حتى الآن: {storage.referral_count(update.effective_user.id)}",
            disable_web_page_preview=True)
        return
    await update.effective_message.reply_text(
        f"🎁 شارك رابطك مع زملائك. كل واحد ينضم يعطيك ويعطيه <b>{REF_DAYS} أيام</b> باقة طالب:\n{link}\n\nدعوت حتى الآن: {storage.referral_count(update.effective_user.id)}",
        parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def redeem_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.effective_message.reply_text("اكتب: /redeem CODE")
        return
    exp, res = storage.redeem(ctx.args[0], update.effective_user.id)
    await update.effective_message.reply_text(f"🎟 تم تفعيل باقة {PL.PLANS[res]['name']} حتى {exp[:10]}" if exp else f"⚠️ {res}")


# ------------------------------------------------------------------ office: team & logo
async def team_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if PL.FREE_MODE:
        await update.effective_message.reply_text("كل زملائك يقدرون يستخدمون كل الأدوات مجاناً، ما تحتاج فريق 🙂 شاركهم /invite")
        return
    if plan(uid) != "office":
        await update.effective_message.reply_text("🔒 إدارة الفريق لباقة المكاتب.", reply_markup=upsell_kb("office"))
        return
    members = storage.team(uid)
    if ctx.args and ctx.args[0] == "add" and len(ctx.args) > 1:
        if len(members) + 1 >= PL.PLANS["office"]["seats"]:
            await update.effective_message.reply_text("وصلت للحد الأقصى للمقاعد (10).")
            return
        try:
            mid = int(ctx.args[1])
        except ValueError:
            await update.effective_message.reply_text("اكتب رقم المستخدم: /team add 123456")
            return
        exp = storage.expires(uid)
        days = max(1, (exp - dt.datetime.utcnow()).days) if exp else 30
        storage.grant(mid, "office", days, owner=uid)
        await update.effective_message.reply_text(f"✅ أضفت {mid} لفريقك.")
        return
    if ctx.args and ctx.args[0] == "remove" and len(ctx.args) > 1:
        storage.revoke(int(ctx.args[1]))
        await update.effective_message.reply_text("✅ تم الحذف.")
        return
    await update.effective_message.reply_text(f"👥 فريقك ({len(members) + 1}/{PL.PLANS['office']['seats']}): {', '.join(map(str, members)) or 'أنت فقط'}\n"
                                              "إضافة: /team add USER_ID (المستخدم يعرف رقمه من /myid)\nحذف: /team remove USER_ID\nالشعار: /logo ثم أرسل صورة الشعار")


async def myid_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(f"🆔 {update.effective_user.id}")


# ------------------------------------------------------------------ admin
def is_admin(update):
    return update.effective_user.id in ADMINS


async def kpi_text():
    k = await asyncio.to_thread(storage.kpis)
    ok = lambda c: "✅" if c else "⚠️"
    ret = "-" if k["retention7"] is None else f"{k['retention7'] * 100:.0f}%"
    lines = ["📈 <b>مؤشرات CivilBot</b>",
             f"👥 المستخدمين: {k['users']} (جدد 30 يوم: {k['new30']})",
             f"DAU {k['dau']} · WAU {k['wau']} · MAU {k['mau']} {ok(k['mau'] >= 1000)} (الهدف 1,000)",
             *([] if PL.FREE_MODE else [f"💳 مشتركين مدفوعين: {k['paid']} (+ {k['trials']} تجربة/كود/إحالة) · التحويل {k['conversion']*100:.1f}% {ok(k['conversion'] >= 0.05)} (الهدف 5%)",
             f"⭐ إيرادات 30 يوم: {k['stars30']} نجمة"]),
             f"🔁 احتفاظ 7 أيام: {ret}",
             f"🧯 نسبة الأخطاء: {k['err_rate']*100:.2f}% {ok(k['err_rate'] <= 0.01)}",
             f"🎁 إحالات 30 يوم: {k['refs30']}",
             f"🗂 الكاش: {CACHE.hits} hit / {CACHE.miss} miss",
             "\n⏱ <b>زمن الاستجابة (7 أيام)</b>"]
    for tool, n, avg, mx, okc in k["latency"]:
        lines.append(f"• {tool}: {n} · avg {avg/1000:.2f}s · max {mx/1000:.1f}s {ok(avg <= 3000)}")
    if k["plans"]:
        lines.append("\n📋 " + " · ".join(f"{p}: {n}" for p, n in k["plans"]))
    return "\n".join(lines)


async def stats_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.effective_message.reply_text(await kpi_text(), parse_mode=ParseMode.HTML)


async def grant_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    try:
        uid, p, days = int(ctx.args[0]), ctx.args[1], int(ctx.args[2])
        assert p in PL.PLANS
    except Exception:
        await update.effective_message.reply_text("/grant USER_ID student|pro|office DAYS")
        return
    await update.effective_message.reply_text(f"✅ {uid} → {p} حتى {storage.grant(uid, p, days)[:10]}")


async def revoke_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if is_admin(update) and ctx.args:
        storage.revoke(int(ctx.args[0]))
        await update.effective_message.reply_text("✅ تم")


async def promo_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    try:
        code, p, days, uses = ctx.args[0], ctx.args[1], int(ctx.args[2]), int(ctx.args[3])
        assert p in PL.PLANS
    except Exception:
        await update.effective_message.reply_text("/promo CODE student|pro|office DAYS USES")
        return
    storage.create_promo(code, p, days, uses)
    me = await ctx.bot.get_me()
    await update.effective_message.reply_text(f"🎟 {code.upper()}: {p} × {days} يوم × {uses} استخدام\nرابط مباشر: https://t.me/{me.username}?start=promo_{code.upper()}")


async def refund_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update) or not ctx.args:
        return
    uid = int(ctx.args[0])
    row = storage.last_payment(uid)
    if not row:
        await update.effective_message.reply_text("ما في دفعة قابلة للاسترجاع")
        return
    pid, p, stars, charge = row
    try:
        await ctx.bot.refund_star_payment(user_id=uid, telegram_payment_charge_id=charge)
        storage.mark_refunded(pid); storage.revoke(uid)
        await update.effective_message.reply_text(f"↩️ تم استرجاع {stars}⭐ وإلغاء الباقة")
    except Exception as e:
        await update.effective_message.reply_text(f"فشل الاسترجاع: {e}")


async def broadcast_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    raw = update.effective_message.text or ""
    text = raw.split(None, 1)[1] if len(raw.split(None, 1)) > 1 else ""
    if not text:
        await update.effective_message.reply_text("/broadcast النص (يدعم HTML)")
        return
    ids = storage.all_user_ids()
    sent = fail = 0
    for k, uid in enumerate(ids):
        try:
            await ctx.bot.send_message(uid, text, parse_mode=ParseMode.HTML)
            sent += 1
        except Exception:
            fail += 1
        if k % 25 == 24:
            await asyncio.sleep(1.1)   # stay under Telegram's ~30 msg/s limit
    await update.effective_message.reply_text(f"📣 أُرسلت لـ {sent} · فشل {fail}")


async def backup_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    fn = await asyncio.to_thread(storage.backup, BACKUP_DIR)
    await update.effective_message.reply_document(open(fn, "rb"), filename=os.path.basename(fn))


# ------------------------------------------------------------------ legal / support (required for Stars payments)
TERMS_FREE_3 = "3. الخدمة مجانية بالكامل، وقد يُطبق حد يومي معقول لحماية السيرفر من الإساءة.\n"
TERMS = ("📜 <b>شروط الاستخدام</b>\n1. CivilBot أداة تعليمية ومساعدة للمراجعة الأولية، والنتائج لا تغني عن مراجعة واعتماد مهندس مرخص.\n"
         "2. المستخدم مسؤول عن صحة المدخلات وعن أي استخدام للنتائج في مشاريع فعلية.\n"
         "3. الاشتراكات رقمية تُدفع بنجوم تلجرام لمدة 30 يوماً، ولا تتجدد تلقائياً.\n"
         "4. يمكن طلب الاسترجاع خلال 7 أيام من الشراء عبر /paysupport إذا لم تستخدم الباقة بشكل جوهري.\n"
         "5. يُمنع إساءة الاستخدام أو محاولة تعطيل الخدمة، ويحق لنا إيقاف الحسابات المخالفة.")
PRIVACY = ("🔒 <b>سياسة الخصوصية</b>\n• نحفظ: معرف تلجرام والاسم، مدخلات الحسابات وسجلها، وبيانات الدفع (رقم العملية فقط).\n"
           "• الصور التي ترسلها تُعالج لحظياً ولا تُخزن، وإذا كان الذكاء الاصطناعي مفعلاً تُرسل لمزود النموذج للتحليل فقط.\n"
           "• لا نبيع بياناتك ولا نشاركها. لحذف بياناتك اكتب /deleteme.")


async def terms_cmd(update, ctx):
    t = TERMS
    if PL.FREE_MODE:
        lines = [l for l in t.split("\n") if not l.startswith(("3.", "4."))]
        lines.insert(3, TERMS_FREE_3.strip())
        t = "\n".join(lines).replace("5.", "4.")
    await update.effective_message.reply_text(t, parse_mode=ParseMode.HTML)


async def privacy_cmd(update, ctx):
    await update.effective_message.reply_text(PRIVACY, parse_mode=ParseMode.HTML)


async def paysupport_cmd(update, ctx):
    await update.effective_message.reply_text(f"💳 للدعم في المدفوعات أو طلب استرجاع تواصل مع {SUPPORT} واذكر رقمك: {update.effective_user.id}")


async def deleteme_cmd(update, ctx):
    uid = update.effective_user.id
    def wipe():
        with storage._c() as con:
            for t, col in (("usage", "uid"), ("feedback", "uid"), ("calcs", "uid"), ("projects", "uid"), ("quiz", "uid"), ("users", "id"), ("logos", "uid")):
                con.execute(f"DELETE FROM {t} WHERE {col}=?", (uid,))
    await asyncio.to_thread(wipe)
    ctx.user_data.clear()
    await update.effective_message.reply_text("🗑 حذفنا بياناتك (عدا سجل المدفوعات المطلوب محاسبياً).")


# ------------------------------------------------------------------ startup & jobs
COMMANDS = [("start", "القائمة الرئيسية"), ("help", "كل الأوامر"), ("beam", "القص والعزم"), ("rc", "تصميم كمرة خرسانية"),
            ("column", "تصميم عمود + P-M"), ("footing", "تصميم قاعدة"), ("slab", "البلاطات"), ("frame", "تحليل الإطارات"),
            ("truss", "الجمالونات"), ("sbeam", "كمرة معدنية"), ("bearing", "قدرة تحمل التربة"), ("mix", "تصميم خلطة"),
            ("schedule", "جدول الأعمدة"), ("boq", "حصر الكميات"), ("codes", "مقارنة الأكواد"), ("quiz", "اختبر نفسك"),
            ("plans", "الباقات والاشتراك"), ("myplan", "باقتي"), ("invite", "ادعُ زملاءك"), ("projects", "مشاريعي"),
            ("terms", "شروط الاستخدام"), ("paysupport", "دعم المدفوعات")]
if PL.FREE_MODE:
    COMMANDS = [c for c in COMMANDS if c[0] not in ("plans", "myplan", "paysupport")] + [("feedback", "ملاحظاتك واقتراحاتك")]


HEARTBEAT = os.getenv("HEARTBEAT_FILE", "/tmp/civilbot.alive")


async def _heartbeat(ctx):
    """Docker HEALTHCHECK reads this file's age: proves the event loop and job queue are alive."""
    try:
        with open(HEARTBEAT, "w") as f:
            f.write(str(time.time()))
    except OSError:
        pass


async def post_init(app):
    await asyncio.to_thread(start_pool)
    try:
        await app.bot.set_my_commands([BotCommand(c, d) for c, d in COMMANDS])
        await app.bot.set_my_short_description("حاسبات إنشائية، رسم DXF، مذكرات PDF وذكاء اصطناعي للمهندس المدني 👷‍♂️")
        await app.bot.set_my_description("CivilBot: أكثر من 60 أداة للمهندس المدني والطالب: القص والعزم، تصميم الكمرات والأعمدة والقواعد، "
                                         "الإطارات والجمالونات، ميكانيكا التربة، الهيدروليكا والمساحة، الحديد المعدني، ملفات أوتوكاد، "
                                         "جداول التفريد وحصر الكميات، وتحليل الشروخ بالذكاء الاصطناعي.")
    except Exception:
        log.warning("could not set bot profile")
    jq = getattr(app, "job_queue", None)
    if jq:
        jq.run_daily(daily_report, time=dt.time(hour=int(os.getenv("REPORT_HOUR_UTC", "5"))))
        jq.run_repeating(lambda c: asyncio.to_thread(storage.backup, BACKUP_DIR), interval=24 * 3600, first=600)
        jq.run_repeating(_heartbeat, interval=60, first=1)
    log.info("CivilBot ready: %s workers", WORKERS)


async def post_shutdown(app):
    if POOL:
        POOL.shutdown(wait=False, cancel_futures=True)


async def daily_report(ctx):
    txt = await kpi_text()
    for a in ADMINS:
        try:
            await ctx.bot.send_message(a, txt, parse_mode=ParseMode.HTML)
        except Exception:
            pass
