import psycopg2
import psycopg2.pool
import asyncio
from functools import partial
from config import DATABASE_URL

_pool = None

def get_pool():
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(1, 20, DATABASE_URL)
    return _pool

def _run(func, *args):
    pool = get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            result = func(cur, *args)
        conn.commit()
        return result
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        pool.putconn(conn)

async def db(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_run, func, *args))

# ─── Schema ──────────────────────────────────────────────────────────────────

def init_schema(cur):
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        joined_at TIMESTAMP DEFAULT NOW(),
        last_active TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS accounts (
        id SERIAL PRIMARY KEY,
        user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
        phone TEXT NOT NULL,
        session_string TEXT NOT NULL,
        label TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        is_active BOOLEAN DEFAULT TRUE,
        bio_ok BOOLEAN DEFAULT TRUE,
        UNIQUE(user_id, phone)
    );

    CREATE TABLE IF NOT EXISTS user_settings (
        user_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
        ad_message TEXT,
        interval_minutes INTEGER DEFAULT 60,
        is_running BOOLEAN DEFAULT FALSE,
        auto_reply_message TEXT DEFAULT 'Main abhi available nahi hoon. Thodi der baad message karein.',
        auto_reply_enabled BOOLEAN DEFAULT FALSE,
        smart_delay_seconds INTEGER DEFAULT 3,
        group_blacklist TEXT DEFAULT '',
        rotation_mode BOOLEAN DEFAULT FALSE,
        scheduled_time TEXT DEFAULT NULL,
        message_signature TEXT DEFAULT NULL,
        active_hours_start INTEGER DEFAULT 0,
        active_hours_end INTEGER DEFAULT 23,
        target_filter TEXT DEFAULT 'all',
        ad_count INTEGER DEFAULT 0,
        last_ad_sent TIMESTAMP DEFAULT NULL
    );

    CREATE TABLE IF NOT EXISTS logs (
        id SERIAL PRIMARY KEY,
        user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
        action TEXT NOT NULL,
        details TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS ad_jobs (
        id SERIAL PRIMARY KEY,
        user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
        account_phone TEXT NOT NULL,
        group_count INTEGER DEFAULT 0,
        sent_count INTEGER DEFAULT 0,
        failed_count INTEGER DEFAULT 0,
        ran_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS subscriptions (
        id SERIAL PRIMARY KEY,
        user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
        plan_id TEXT NOT NULL,
        days INTEGER NOT NULL,
        price INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',
        requested_at TIMESTAMP DEFAULT NOW(),
        approved_at TIMESTAMP DEFAULT NULL,
        expires_at TIMESTAMP DEFAULT NULL
    );

    CREATE TABLE IF NOT EXISTS group_cache (
        id SERIAL PRIMARY KEY,
        user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
        account_phone TEXT NOT NULL,
        group_id BIGINT NOT NULL,
        title TEXT,
        is_channel BOOLEAN DEFAULT FALSE,
        excluded BOOLEAN DEFAULT FALSE,
        member_count INTEGER DEFAULT 0,
        last_synced TIMESTAMP DEFAULT NOW(),
        UNIQUE(user_id, account_phone, group_id)
    );
    """)

    migrations = [
        "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS smart_delay_seconds INTEGER DEFAULT 3",
        "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS group_blacklist TEXT DEFAULT ''",
        "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS rotation_mode BOOLEAN DEFAULT FALSE",
        "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS scheduled_time TEXT DEFAULT NULL",
        "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS message_signature TEXT DEFAULT NULL",
        "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS active_hours_start INTEGER DEFAULT 0",
        "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS active_hours_end INTEGER DEFAULT 23",
        "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS target_filter TEXT DEFAULT 'all'",
        "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS ad_count INTEGER DEFAULT 0",
        "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS last_ad_sent TIMESTAMP DEFAULT NULL",
        "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS bio_ok BOOLEAN DEFAULT TRUE",
    ]
    for sql in migrations:
        try:
            cur.execute(sql)
        except Exception:
            pass
    return True

# ─── User helpers ─────────────────────────────────────────────────────────────

def _ensure_user(cur, user_id, username, first_name):
    cur.execute("""
        INSERT INTO users (user_id, username, first_name)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
            SET username = EXCLUDED.username,
                first_name = EXCLUDED.first_name
    """, (user_id, username, first_name))
    cur.execute("""
        INSERT INTO user_settings (user_id) VALUES (%s)
        ON CONFLICT (user_id) DO NOTHING
    """, (user_id,))

async def ensure_user(user_id, username, first_name):
    return await db(_ensure_user, user_id, username, first_name)

def _touch_user(cur, user_id):
    cur.execute("""
        UPDATE users SET last_active = NOW() WHERE user_id = %s
    """, (user_id,))

async def touch_user(user_id):
    return await db(_touch_user, user_id)

def _get_user_last_active(cur, user_id):
    cur.execute("SELECT last_active FROM users WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    return row[0] if row else None

async def get_user_last_active(user_id):
    return await db(_get_user_last_active, user_id)

# ─── Account helpers ─────────────────────────────────────────────────────────

def _add_account(cur, user_id, phone, session_string, label=None):
    cur.execute("""
        INSERT INTO accounts (user_id, phone, session_string, label)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id, phone) DO UPDATE
            SET session_string = EXCLUDED.session_string,
                is_active = TRUE, bio_ok = TRUE
    """, (user_id, phone, session_string, label or phone))

async def add_account(user_id, phone, session_string, label=None):
    return await db(_add_account, user_id, phone, session_string, label)

def _get_accounts(cur, user_id):
    cur.execute("""
        SELECT id, phone, label, is_active, bio_ok, created_at
        FROM accounts WHERE user_id = %s ORDER BY created_at
    """, (user_id,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

async def get_accounts(user_id):
    return await db(_get_accounts, user_id)

def _count_accounts(cur, user_id):
    cur.execute("SELECT COUNT(*) FROM accounts WHERE user_id=%s AND is_active=TRUE", (user_id,))
    return cur.fetchone()[0]

async def count_accounts(user_id):
    return await db(_count_accounts, user_id)

def _get_account_sessions(cur, user_id):
    cur.execute("""
        SELECT phone, session_string FROM accounts
        WHERE user_id = %s AND is_active = TRUE AND bio_ok = TRUE
    """, (user_id,))
    return [(row[0], row[1]) for row in cur.fetchall()]

async def get_account_sessions(user_id):
    return await db(_get_account_sessions, user_id)

def _delete_account(cur, user_id, account_id):
    cur.execute("""
        DELETE FROM accounts WHERE id = %s AND user_id = %s
    """, (account_id, user_id))
    return cur.rowcount > 0

async def delete_account(user_id, account_id):
    return await db(_delete_account, user_id, account_id)

def _set_account_bio_ok(cur, user_id, phone, bio_ok):
    cur.execute("""
        UPDATE accounts SET bio_ok = %s WHERE user_id = %s AND phone = %s
    """, (bio_ok, user_id, phone))

async def set_account_bio_ok(user_id, phone, bio_ok):
    return await db(_set_account_bio_ok, user_id, phone, bio_ok)

def _get_all_active_sessions(cur):
    cur.execute("""
        SELECT user_id, phone, session_string FROM accounts
        WHERE is_active = TRUE
    """)
    return [(row[0], row[1], row[2]) for row in cur.fetchall()]

async def get_all_active_sessions():
    return await db(_get_all_active_sessions)

# ─── Settings helpers ─────────────────────────────────────────────────────────

def _get_settings(cur, user_id):
    cur.execute("""
        SELECT * FROM user_settings WHERE user_id = %s
    """, (user_id,))
    row = cur.fetchone()
    if not row:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))

async def get_settings(user_id):
    return await db(_get_settings, user_id)

def _set_ad_message(cur, user_id, message):
    cur.execute("""
        UPDATE user_settings SET ad_message = %s WHERE user_id = %s
    """, (message, user_id))

async def set_ad_message(user_id, message):
    return await db(_set_ad_message, user_id, message)

def _set_interval(cur, user_id, minutes):
    cur.execute("""
        UPDATE user_settings SET interval_minutes = %s WHERE user_id = %s
    """, (minutes, user_id))

async def set_interval(user_id, minutes):
    return await db(_set_interval, user_id, minutes)

def _set_running(cur, user_id, is_running):
    cur.execute("""
        UPDATE user_settings SET is_running = %s WHERE user_id = %s
    """, (is_running, user_id))

async def set_running(user_id, is_running):
    return await db(_set_running, user_id, is_running)

def _set_auto_reply(cur, user_id, enabled, message=None):
    if message is not None:
        cur.execute("""
            UPDATE user_settings SET auto_reply_message = %s WHERE user_id = %s
        """, (message, user_id))
    if enabled is not None:
        cur.execute("""
            UPDATE user_settings SET auto_reply_enabled = %s WHERE user_id = %s
        """, (enabled, user_id))

async def set_auto_reply(user_id, enabled, message=None):
    return await db(_set_auto_reply, user_id, enabled, message)

def _set_smart_delay(cur, user_id, seconds):
    cur.execute("UPDATE user_settings SET smart_delay_seconds=%s WHERE user_id=%s", (seconds, user_id))

async def set_smart_delay(user_id, seconds):
    return await db(_set_smart_delay, user_id, seconds)

def _set_group_blacklist(cur, user_id, value):
    cur.execute("UPDATE user_settings SET group_blacklist=%s WHERE user_id=%s", (value, user_id))

async def set_group_blacklist(user_id, value):
    return await db(_set_group_blacklist, user_id, value)

def _set_rotation_mode(cur, user_id, enabled):
    cur.execute("UPDATE user_settings SET rotation_mode=%s WHERE user_id=%s", (enabled, user_id))

async def set_rotation_mode(user_id, enabled):
    return await db(_set_rotation_mode, user_id, enabled)

def _set_message_signature(cur, user_id, sig):
    cur.execute("UPDATE user_settings SET message_signature=%s WHERE user_id=%s", (sig, user_id))

async def set_message_signature(user_id, sig):
    return await db(_set_message_signature, user_id, sig)

def _set_active_hours(cur, user_id, start, end):
    cur.execute("UPDATE user_settings SET active_hours_start=%s, active_hours_end=%s WHERE user_id=%s", (start, end, user_id))

async def set_active_hours(user_id, start, end):
    return await db(_set_active_hours, user_id, start, end)

def _set_scheduled_time(cur, user_id, t):
    cur.execute("UPDATE user_settings SET scheduled_time=%s WHERE user_id=%s", (t, user_id))

async def set_scheduled_time(user_id, t):
    return await db(_set_scheduled_time, user_id, t)

def _set_target_filter(cur, user_id, target):
    cur.execute("UPDATE user_settings SET target_filter=%s WHERE user_id=%s", (target, user_id))

async def set_target_filter(user_id, target):
    return await db(_set_target_filter, user_id, target)

def _increment_ad_count(cur, user_id):
    cur.execute("""
        UPDATE user_settings SET ad_count = ad_count + 1, last_ad_sent = NOW()
        WHERE user_id = %s
    """, (user_id,))

async def increment_ad_count(user_id):
    return await db(_increment_ad_count, user_id)

# ─── Premium / Subscriptions ─────────────────────────────────────────────────

def _create_subscription_request(cur, user_id, plan_id, days, price):
    cur.execute("""
        INSERT INTO subscriptions (user_id, plan_id, days, price, status)
        VALUES (%s, %s, %s, %s, 'pending')
        RETURNING id
    """, (user_id, plan_id, days, price))
    return cur.fetchone()[0]

async def create_subscription_request(user_id, plan_id, days, price):
    return await db(_create_subscription_request, user_id, plan_id, days, price)

def _approve_subscription(cur, user_id, plan_id):
    # PostgreSQL does not allow ORDER BY / LIMIT inside UPDATE directly.
    # Use a subquery to target the most-recently-requested pending row by id.
    cur.execute("""
        UPDATE subscriptions
        SET status='active',
            approved_at=NOW(),
            expires_at=NOW() + (days || ' days')::INTERVAL
        WHERE id = (
            SELECT id FROM subscriptions
            WHERE user_id=%s AND plan_id=%s AND status='pending'
            ORDER BY requested_at DESC
            LIMIT 1
        )
    """, (user_id, plan_id))
    return cur.rowcount > 0

async def approve_subscription(user_id, plan_id):
    return await db(_approve_subscription, user_id, plan_id)

def _reject_subscription(cur, user_id, plan_id):
    cur.execute("""
        UPDATE subscriptions SET status='rejected'
        WHERE user_id=%s AND plan_id=%s AND status='pending'
    """, (user_id, plan_id))
    return cur.rowcount > 0

async def reject_subscription(user_id, plan_id):
    return await db(_reject_subscription, user_id, plan_id)

def _is_premium(cur, user_id):
    cur.execute("""
        SELECT COUNT(*) FROM subscriptions
        WHERE user_id=%s AND status='active' AND expires_at > NOW()
    """, (user_id,))
    return cur.fetchone()[0] > 0

async def is_premium(user_id):
    return await db(_is_premium, user_id)

def _get_premium_expiry(cur, user_id):
    cur.execute("""
        SELECT expires_at FROM subscriptions
        WHERE user_id=%s AND status='active' AND expires_at > NOW()
        ORDER BY expires_at DESC LIMIT 1
    """, (user_id,))
    row = cur.fetchone()
    return row[0] if row else None

async def get_premium_expiry(user_id):
    return await db(_get_premium_expiry, user_id)

def _get_pending_subscriptions(cur):
    cur.execute("""
        SELECT s.id, s.user_id, s.plan_id, s.days, s.price, s.requested_at,
               u.username, u.first_name
        FROM subscriptions s
        JOIN users u ON u.user_id = s.user_id
        WHERE s.status='pending'
        ORDER BY s.requested_at
    """)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

async def get_pending_subscriptions():
    return await db(_get_pending_subscriptions)

# ─── Group cache ──────────────────────────────────────────────────────────────

def _upsert_group_cache(cur, user_id, phone, group_id, title, is_channel, member_count):
    cur.execute("""
        INSERT INTO group_cache (user_id, account_phone, group_id, title, is_channel, member_count, last_synced)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (user_id, account_phone, group_id) DO UPDATE
            SET title=EXCLUDED.title, is_channel=EXCLUDED.is_channel,
                member_count=EXCLUDED.member_count, last_synced=NOW()
    """, (user_id, phone, group_id, title, is_channel, member_count))

async def upsert_group_cache(user_id, phone, group_id, title, is_channel, member_count):
    return await db(_upsert_group_cache, user_id, phone, group_id, title, is_channel, member_count)

def _get_group_cache(cur, user_id):
    cur.execute("""
        SELECT group_id, title, is_channel, excluded, member_count, account_phone
        FROM group_cache WHERE user_id=%s ORDER BY title
    """, (user_id,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

async def get_group_cache(user_id):
    return await db(_get_group_cache, user_id)

def _toggle_group_exclude(cur, user_id, group_id):
    cur.execute("""
        UPDATE group_cache SET excluded = NOT excluded
        WHERE user_id=%s AND group_id=%s
    """, (user_id, group_id))

async def toggle_group_exclude(user_id, group_id):
    return await db(_toggle_group_exclude, user_id, group_id)

def _set_all_groups_excluded(cur, user_id, excluded):
    cur.execute("UPDATE group_cache SET excluded=%s WHERE user_id=%s", (excluded, user_id))

async def set_all_groups_excluded(user_id, excluded):
    return await db(_set_all_groups_excluded, user_id, excluded)

def _get_excluded_group_ids(cur, user_id):
    cur.execute("""
        SELECT group_id FROM group_cache WHERE user_id=%s AND excluded=TRUE
    """, (user_id,))
    return [row[0] for row in cur.fetchall()]

async def get_excluded_group_ids(user_id):
    return await db(_get_excluded_group_ids, user_id)

# ─── Stats ────────────────────────────────────────────────────────────────────

def _get_stats(cur, user_id):
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(sent_count),0),
               COALESCE(SUM(failed_count),0), COALESCE(MAX(group_count),0)
        FROM ad_jobs WHERE user_id=%s
    """, (user_id,))
    row = cur.fetchone()
    if not row:
        return {"total_jobs": 0, "total_sent": 0, "total_failed": 0, "max_groups": 0}
    return {
        "total_jobs": row[0],
        "total_sent": int(row[1]),
        "total_failed": int(row[2]),
        "max_groups": int(row[3]),
    }

async def get_stats(user_id):
    return await db(_get_stats, user_id)

def _get_recent_jobs(cur, user_id, limit=10):
    cur.execute("""
        SELECT account_phone, group_count, sent_count, failed_count, ran_at
        FROM ad_jobs WHERE user_id=%s ORDER BY ran_at DESC LIMIT %s
    """, (user_id, limit))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

async def get_recent_jobs(user_id, limit=10):
    return await db(_get_recent_jobs, user_id, limit)

# ─── Logs ─────────────────────────────────────────────────────────────────────

def _add_log(cur, user_id, action, details=None):
    cur.execute("""
        INSERT INTO logs (user_id, action, details) VALUES (%s, %s, %s)
    """, (user_id, action, details))

async def add_log(user_id, action, details=None):
    try:
        await db(_add_log, user_id, action, details)
    except Exception:
        pass

def _get_logs(cur, user_id, limit=20):
    cur.execute("""
        SELECT action, details, created_at FROM logs
        WHERE user_id=%s ORDER BY created_at DESC LIMIT %s
    """, (user_id, limit))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

async def get_logs(user_id, limit=20):
    return await db(_get_logs, user_id, limit)

def _add_job_log(cur, user_id, phone, group_count, sent, failed):
    cur.execute("""
        INSERT INTO ad_jobs (user_id, account_phone, group_count, sent_count, failed_count)
        VALUES (%s, %s, %s, %s, %s)
    """, (user_id, phone, group_count, sent, failed))

async def add_job_log(user_id, phone, group_count, sent, failed):
    try:
        await db(_add_job_log, user_id, phone, group_count, sent, failed)
    except Exception:
        pass
