"""Phase 5: plans, subscriptions, referrals, promos, cache, rate limit, watermark, worker runner."""
import io, os, tempfile, time
os.environ["CIVILBOT_DB"] = os.path.join(tempfile.mkdtemp(), "t.sqlite3")
from civilbot.bot import storage as S, plans as P
from civilbot.drawing import watermark
from civilbot import runner


def test_plan_gates():
    assert not P.feature("free", "pdf") and P.feature("student", "pdf")
    assert P.feature("pro", "dxf") and not P.feature("student", "dxf")
    assert P.at_least("office", "pro") and not P.at_least("free", "student")
    assert P.feature("unknown", "daily") == P.PLANS["free"]["daily"]
    assert P.PLANS["office"]["seats"] == 10 and P.STARS["pro"] > P.STARS["student"]


def test_grant_extend_revoke():
    assert S.plan_of(1) == "free"
    e1 = S.grant(1, "pro", 30)
    e2 = S.grant(1, "pro", 30)          # same plan extends from current expiry
    assert S.plan_of(1) == "pro" and e2 > e1
    S.revoke(1)
    assert S.plan_of(1) == "free"


def test_expired_plan_falls_back_to_free():
    S.grant(2, "student", -1)
    assert S.plan_of(2) == "free"


def test_payments_and_refund():
    S.record_payment(3, "pro", 450, "ch_1")
    pid, plan, stars, ch = S.last_payment(3)
    assert (plan, stars, ch) == ("pro", 450, "ch_1")
    S.mark_refunded(pid)
    assert S.last_payment(3) is None


def test_referral_rules():
    assert not S.add_referral(10, 10)            # self referral
    assert S.add_referral(11, 10)
    assert not S.add_referral(11, 12)            # only once
    S.log(13, "beam", True, 100)
    assert not S.add_referral(13, 10)            # existing user
    assert S.referral_count(10) == 1


def test_promo_codes():
    S.create_promo("uni24", "student", 7, 2)
    exp, plan = S.redeem("UNI24", 20)
    assert plan == "student" and S.plan_of(20) == "student"
    assert S.redeem("uni24", 20)[0] is None      # same user twice
    S.redeem("uni24", 21)
    assert S.redeem("uni24", 22)[0] is None      # uses exhausted
    assert S.redeem("nope", 23)[0] is None


def test_office_team_logo():
    S.grant(30, "office", 30)
    S.grant(31, "office", 30, owner=30)
    S.set_logo(30, b"PNG")
    assert S.team(30) == [31] and S.logo_for(31) == b"PNG"


def test_watermark_keeps_size():
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGB", (640, 480), "white").save(buf, "PNG")
    out = watermark.apply(buf.getvalue())
    im = Image.open(io.BytesIO(out))
    assert im.size == (640, 480) and out != buf.getvalue()


def test_ttl_cache_and_rate_limit():
    try:
        from civilbot.bot import launch as L
    except ImportError:          # python-telegram-bot not installed
        return
    c = L.TTLCache(size=2, ttl=60)
    c.put("a", 1); c.put("b", 2); c.put("c", 3)
    assert c.get("a") is None and c.get("c") == 3
    rl = L.RateLimiter(burst=3, rate=0.0)
    assert [rl.allow(1) for _ in range(4)] == [True, True, True, False]
    assert rl.allow(2)


def test_runner_executes_in_process():
    t = time.perf_counter()
    res = runner.execute("tool", "beam", "L=6 type=ss w=10 P=20@3")
    assert res is not None and time.perf_counter() - t < 3
