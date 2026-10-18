"""SQLite storage for beta: users, usage log, feedback, daily quota.
(Swap for PostgreSQL in Phase 2 — same function signatures.)"""
from __future__ import annotations
import sqlite3
import datetime as dt
import os

DB = os.getenv("CIVILBOT_DB", "civilbot.sqlite3")


def _c():
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT, joined TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS usage(id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, tool TEXT, ok INTEGER, ms INTEGER, at TEXT)")
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE IF NOT EXISTS subs(uid INTEGER PRIMARY KEY, plan TEXT, expires TEXT, owner INTEGER)")
    con.execute("CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, plan TEXT, stars INTEGER, charge TEXT, at TEXT, refunded INTEGER DEFAULT 0)")
    con.execute("CREATE TABLE IF NOT EXISTS referrals(uid INTEGER PRIMARY KEY, ref_by INTEGER, at TEXT, rewarded INTEGER DEFAULT 0)")
    con.execute("CREATE TABLE IF NOT EXISTS promos(code TEXT PRIMARY KEY, plan TEXT, days INTEGER, uses INTEGER, used INTEGER DEFAULT 0)")
    con.execute("CREATE TABLE IF NOT EXISTS promo_use(code TEXT, uid INTEGER, PRIMARY KEY(code, uid))")
    con.execute("CREATE TABLE IF NOT EXISTS logos(uid INTEGER PRIMARY KEY, png BLOB)")
    con.execute("CREATE INDEX IF NOT EXISTS usage_at ON usage(at)")
    con.execute("CREATE INDEX IF NOT EXISTS usage_uid ON usage(uid, at)")
    con.execute("CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, name TEXT, created TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS calcs(id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, project INTEGER, tool TEXT, input TEXT, summary TEXT, at TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS quiz(id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, topic TEXT, ok INTEGER, at TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, text TEXT, at TEXT)")
    return con


def touch_user(uid: int, name: str):
    with _c() as con:
        con.execute("INSERT OR IGNORE INTO users VALUES(?,?,?)", (uid, name, dt.datetime.utcnow().isoformat()))


def log(uid: int, tool: str, ok: bool, ms: int):
    with _c() as con:
        con.execute("INSERT INTO usage(uid,tool,ok,ms,at) VALUES(?,?,?,?,?)", (uid, tool, int(ok), ms, dt.datetime.utcnow().isoformat()))


def used_today(uid: int) -> int:
    day = dt.datetime.utcnow().date().isoformat()
    with _c() as con:
        return con.execute("SELECT COUNT(*) FROM usage WHERE uid=? AND at>=?", (uid, day)).fetchone()[0]


def feedback(uid: int, text: str):
    with _c() as con:
        con.execute("INSERT INTO feedback(uid,text,at) VALUES(?,?,?)", (uid, text, dt.datetime.utcnow().isoformat()))


def stats() -> dict:
    with _c() as con:
        users = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        runs = con.execute("SELECT tool, COUNT(*), SUM(ok), AVG(ms) FROM usage GROUP BY tool").fetchall()
        fb = con.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
    return {"users": users, "runs": runs, "feedback": fb}


def quiz_log(uid: int, topic: str, ok: bool):
    with _c() as con:
        con.execute("INSERT INTO quiz(uid,topic,ok,at) VALUES(?,?,?,?)", (uid, topic, int(ok), dt.datetime.utcnow().isoformat()))


def quiz_stats(uid: int):
    with _c() as con:
        return con.execute("SELECT topic, COUNT(*), SUM(ok) FROM quiz WHERE uid=? GROUP BY topic", (uid,)).fetchall()


def new_project(uid: int, name: str) -> int:
    with _c() as con:
        cur = con.execute("INSERT INTO projects(uid,name,created) VALUES(?,?,?)", (uid, name[:60], dt.datetime.utcnow().isoformat()))
        return cur.lastrowid


def projects(uid: int):
    with _c() as con:
        return con.execute("SELECT p.id, p.name, p.created, (SELECT COUNT(*) FROM calcs c WHERE c.project=p.id) FROM projects p WHERE uid=? ORDER BY id DESC", (uid,)).fetchall()


def project_name(uid: int, pid: int):
    with _c() as con:
        row = con.execute("SELECT name FROM projects WHERE id=? AND uid=?", (pid, uid)).fetchone()
        return row[0] if row else None


def save_calc(uid: int, project, tool: str, text: str, summary: str):
    with _c() as con:
        con.execute("INSERT INTO calcs(uid,project,tool,input,summary,at) VALUES(?,?,?,?,?,?)",
                    (uid, project, tool, text[:2000], summary[:300], dt.datetime.utcnow().isoformat()))


def history(uid: int, project=None, limit=10):
    with _c() as con:
        if project:
            return con.execute("SELECT id, tool, input, summary, at FROM calcs WHERE uid=? AND project=? ORDER BY id DESC LIMIT ?", (uid, project, limit)).fetchall()
        return con.execute("SELECT id, tool, input, summary, at FROM calcs WHERE uid=? ORDER BY id DESC LIMIT ?", (uid, limit)).fetchall()


def calc(uid: int, cid: int):
    with _c() as con:
        return con.execute("SELECT tool, input FROM calcs WHERE id=? AND uid=?", (cid, uid)).fetchone()


# ---------------------------------------------------------------- subscriptions
def _now():
    return dt.datetime.utcnow()


def plan_of(uid: int) -> str:
    with _c() as con:
        row = con.execute("SELECT plan, expires, owner FROM subs WHERE uid=?", (uid,)).fetchone()
    if not row:
        return "free"
    plan, exp, owner = row
    if exp and dt.datetime.fromisoformat(exp) < _now():
        return "free"
    return plan


def expires(uid: int):
    with _c() as con:
        row = con.execute("SELECT expires FROM subs WHERE uid=?", (uid,)).fetchone()
    return dt.datetime.fromisoformat(row[0]) if row and row[0] else None


def grant(uid: int, plan: str, days: int, owner=None):
    cur_exp = expires(uid)
    cur_plan = plan_of(uid)
    base = cur_exp if (cur_exp and cur_exp > _now() and cur_plan == plan) else _now()
    new = (base + dt.timedelta(days=days)).isoformat()
    with _c() as con:
        con.execute("INSERT INTO subs(uid,plan,expires,owner) VALUES(?,?,?,?) ON CONFLICT(uid) DO UPDATE SET plan=excluded.plan, expires=excluded.expires, owner=excluded.owner",
                    (uid, plan, new, owner))
    return new


def revoke(uid: int):
    with _c() as con:
        con.execute("DELETE FROM subs WHERE uid=?", (uid,))


def record_payment(uid, plan, stars, charge):
    with _c() as con:
        con.execute("INSERT INTO payments(uid,plan,stars,charge,at) VALUES(?,?,?,?,?)", (uid, plan, stars, charge, _now().isoformat()))


def last_payment(uid):
    with _c() as con:
        return con.execute("SELECT id, plan, stars, charge FROM payments WHERE uid=? AND refunded=0 ORDER BY id DESC LIMIT 1", (uid,)).fetchone()


def mark_refunded(pid):
    with _c() as con:
        con.execute("UPDATE payments SET refunded=1 WHERE id=?", (pid,))


def team(owner):
    with _c() as con:
        return [r[0] for r in con.execute("SELECT uid FROM subs WHERE owner=? AND uid<>?", (owner, owner)).fetchall()]


def set_logo(uid, png):
    with _c() as con:
        con.execute("INSERT OR REPLACE INTO logos VALUES(?,?)", (uid, png))


def logo_for(uid):
    with _c() as con:
        row = con.execute("SELECT owner FROM subs WHERE uid=?", (uid,)).fetchone()
        owner = row[0] if row and row[0] else uid
        r2 = con.execute("SELECT png FROM logos WHERE uid=?", (owner,)).fetchone()
    return r2[0] if r2 else None


# ---------------------------------------------------------------- referrals & promo codes
def add_referral(uid, ref_by) -> bool:
    if uid == ref_by:
        return False
    with _c() as con:
        if con.execute("SELECT 1 FROM usage WHERE uid=? LIMIT 1", (uid,)).fetchone():
            return False  # existing user
        cur = con.execute("INSERT OR IGNORE INTO referrals(uid,ref_by,at) VALUES(?,?,?)", (uid, ref_by, _now().isoformat()))
        return cur.rowcount == 1


def referral_count(ref_by):
    with _c() as con:
        return con.execute("SELECT COUNT(*) FROM referrals WHERE ref_by=?", (ref_by,)).fetchone()[0]


def create_promo(code, plan, days, uses):
    with _c() as con:
        con.execute("INSERT OR REPLACE INTO promos(code,plan,days,uses,used) VALUES(?,?,?,?,0)", (code.upper(), plan, days, uses))


def redeem(code, uid):
    code = code.upper()
    with _c() as con:
        row = con.execute("SELECT plan, days, uses, used FROM promos WHERE code=?", (code,)).fetchone()
        if not row:
            return None, "الكود غير صحيح"
        plan, days, uses, used = row
        if used >= uses:
            return None, "الكود انتهى"
        if con.execute("SELECT 1 FROM promo_use WHERE code=? AND uid=?", (code, uid)).fetchone():
            return None, "استخدمت هذا الكود من قبل"
        con.execute("INSERT INTO promo_use VALUES(?,?)", (code, uid))
        con.execute("UPDATE promos SET used=used+1 WHERE code=?", (code,))
    return grant(uid, plan, days), plan


# ---------------------------------------------------------------- KPIs
def kpis():
    now = _now()
    d1 = (now - dt.timedelta(days=1)).isoformat()
    d7 = (now - dt.timedelta(days=7)).isoformat()
    d30 = (now - dt.timedelta(days=30)).isoformat()
    with _c() as con:
        q = lambda sql, *a: con.execute(sql, a).fetchone()[0]
        users = q("SELECT COUNT(*) FROM users")
        dau = q("SELECT COUNT(DISTINCT uid) FROM usage WHERE at>=?", d1)
        wau = q("SELECT COUNT(DISTINCT uid) FROM usage WHERE at>=?", d7)
        mau = q("SELECT COUNT(DISTINCT uid) FROM usage WHERE at>=?", d30)
        runs30 = q("SELECT COUNT(*) FROM usage WHERE at>=?", d30)
        err = q("SELECT COUNT(*) FROM usage WHERE at>=? AND ok=0", d30)
        paid = q("SELECT COUNT(DISTINCT s.uid) FROM subs s JOIN payments p ON p.uid=s.uid AND p.refunded=0 WHERE s.expires>=?", now.isoformat())
        trials = q("SELECT COUNT(*) FROM subs WHERE expires>=? AND uid NOT IN (SELECT uid FROM payments WHERE refunded=0)", now.isoformat())
        stars30 = q("SELECT COALESCE(SUM(stars),0) FROM payments WHERE at>=? AND refunded=0", d30)
        new30 = q("SELECT COUNT(*) FROM users WHERE joined>=?", d30)
        # 7-day retention of users who joined 8-14 days ago
        c0, c1 = (now - dt.timedelta(days=14)).isoformat(), (now - dt.timedelta(days=7)).isoformat()
        cohort = q("SELECT COUNT(*) FROM users WHERE joined BETWEEN ? AND ?", c0, c1)
        retained = q("SELECT COUNT(DISTINCT u.id) FROM users u JOIN usage g ON g.uid=u.id WHERE u.joined BETWEEN ? AND ? AND g.at>=?", c0, c1, c1)
        lat = con.execute("SELECT tool, COUNT(*), AVG(ms), MAX(ms), SUM(ok) FROM usage WHERE at>=? GROUP BY tool ORDER BY COUNT(*) DESC LIMIT 12", (d7,)).fetchall()
        plans = con.execute("SELECT plan, COUNT(*) FROM subs WHERE expires>=? GROUP BY plan", (now.isoformat(),)).fetchall()
        refs = q("SELECT COUNT(*) FROM referrals WHERE at>=?", d30)
    return dict(users=users, dau=dau, wau=wau, mau=mau, runs30=runs30, err_rate=(err / runs30 if runs30 else 0), paid=paid,
                conversion=(paid / mau if mau else 0), trials=trials, stars30=stars30, new30=new30, retention7=(retained / cohort if cohort else None),
                latency=lat, plans=plans, refs30=refs)


def all_user_ids():
    with _c() as con:
        return [r[0] for r in con.execute("SELECT id FROM users").fetchall()]


def backup(dest_dir: str, keep=7):
    import os, sqlite3 as sq, glob
    os.makedirs(dest_dir, exist_ok=True)
    fn = os.path.join(dest_dir, f"civilbot_{_now():%Y%m%d_%H%M}.sqlite3")
    src = sq.connect(DB)
    dst = sq.connect(fn)
    with dst:
        src.backup(dst)
    src.close(); dst.close()
    files = sorted(glob.glob(os.path.join(dest_dir, "civilbot_*.sqlite3")))
    for old in files[:-keep]:
        os.remove(old)
    return fn
