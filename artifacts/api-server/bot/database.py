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
        last_active TIMESTAMP DEFAULT NOW(),
        language TEXT DEFAULT 'en',
        is_banned BOOLEAN DEFAULT FALSE,
        ban_reason TEXT DEFAULT NULL,
        log_chat_id BIGINT DEFAULT NULL
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
        auto_reply_inactive_minutes INTEGER DEFAULT 30,
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
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'en'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS ban_reason TEXT DEFAULT NULL",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS log_chat_id BIGINT DEFAULT NULL",
        "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS auto_reply_inactive_minutes INTEGER DEFAULT 30",
    ]
    migration_errors = []
    for index, m in enumerate(migrations):
        savepoint = f"schema_migration_{index}"
        try:
            cur.execute(f"SAVEPOINT {savepoint}")
            cur.execute(m)
            cur.execute(f"RELEASE SAVEPOINT {savepoint}")
        except Exception as exc:
            migration_errors.append((m, exc))
            cur.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            cur.execute(f"RELEASE SAVEPOINT {savepoint}")

    # CREATE TABLE IF NOT EXISTS does not update tables created by an older
    # version of the bot. Verify the columns required by current handlers
    # before allowing the bot to start serving updates.
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'users'
          AND column_name IN ('is_banned', 'ban_reason', 'language', 'log_chat_id')
    """)
    user_columns = {row[0] for row in cur.fetchall()}
    required_user_columns = {"is_banned", "ban_reason", "language", "log_chat_id"}
    missing_columns = required_user_columns - user_columns
    if missing_columns:
        raise RuntimeError(
            "Database schema is incomplete; missing users columns: "
            + ", ".join(sorted(missing_columns))
        )
    if migration_errors:
        failed = "; ".join(migration for migration, _ in migration_errors)
        raise RuntimeError(f"Database migrations failed: {failed}")


# ─── Users ────────────────────────────────────────────────────────────────────

def _ensure_user(cur, user_id, username, first_name):
    cur.execute("""
        INSERT INTO users (user_id, username, first_name)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            username = EXCLUDED.username,
            first_name = EXCLUDED.first_name
    """, (user_id, username, first_name))
    cur.execute("""
        INSERT INTO user_settings (user_id) VALUES (%s)
        ON CONFLICT (user_id) DO NOTHING
    """, (user_id,))

async def ensure_user(user_id, username, first_name):
    await db(_ensure_user, user_id, username, first_name)


def _touch_user(cur, user_id):
    cur.execute("UPDATE users SET last_active=NOW() WHERE user_id=%s", (user_id,))

async def touch_user(user_id):
    await db(_touch_user, user_id)


def _get_user(cur, user_id):
    cur.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    return dict(zip(cols, row)) if row else None

async def get_user(user_id):
    return await db(_get_user, user_id)


def _get_all_users(cur, limit=200, offset=0):
    cur.execute("""
        SELECT u.user_id, u.username, u.first_name, u.joined_at, u.last_active,
               u.is_banned, u.language,
               (SELECT COUNT(*) FROM accounts a WHERE a.user_id=u.user_id) as account_count,
               (SELECT COUNT(*) FROM subscriptions s WHERE s.user_id=u.user_id AND s.status='approved') as sub_count
        FROM users u
        ORDER BY u.joined_at DESC
        LIMIT %s OFFSET %s
    """, (limit, offset))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

async def get_all_users(limit=200, offset=0):
    return await db(_get_all_users, limit, offset)


def _count_users(cur):
    cur.execute("SELECT COUNT(*) FROM users")
    return cur.fetchone()[0]

async def count_users():
    return await db(_count_users)


def _get_user_last_active(cur, user_id):
    cur.execute("SELECT last_active FROM users WHERE user_id=%s", (user_id,))
    row = cur.fetchone()
    return row[0] if row else None

async def get_user_last_active(user_id):
    return await db(_get_user_last_active, user_id)


# ─── Ban / Unban ──────────────────────────────────────────────────────────────

def _ban_user(cur, user_id, reason=""):
    cur.execute("""
        UPDATE users SET is_banned=TRUE, ban_reason=%s WHERE user_id=%s
    """, (reason, user_id))
    # Stop any running ads
    cur.execute("UPDATE user_settings SET is_running=FALSE WHERE user_id=%s", (user_id,))

async def ban_user(user_id, reason=""):
    await db(_ban_user, user_id, reason)


def _unban_user(cur, user_id):
    cur.execute("UPDATE users SET is_banned=FALSE, ban_reason=NULL WHERE user_id=%s", (user_id,))

async def unban_user(user_id):
    await db(_unban_user, user_id)


def _is_banned(cur, user_id):
    cur.execute("SELECT is_banned FROM users WHERE user_id=%s", (user_id,))
    row = cur.fetchone()
    return bool(row[0]) if row else False

async def is_banned(user_id):
    return await db(_is_banned, user_id)


# ─── Language ─────────────────────────────────────────────────────────────────

def _get_language(cur, user_id):
    cur.execute("SELECT language FROM users WHERE user_id=%s", (user_id,))
    row = cur.fetchone()
    return row[0] if row else "en"

async def get_language(user_id):
    return await db(_get_language, user_id)


def _set_language(cur, user_id, lang):
    cur.execute("UPDATE users SET language=%s WHERE user_id=%s", (lang, user_id))

async def set_language(user_id, lang):
    await db(_set_language, user_id, lang)


# ─── Log Chat ─────────────────────────────────────────────────────────────────

def _set_log_chat_id(cur, user_id, chat_id):
    cur.execute("UPDATE users SET log_chat_id=%s WHERE user_id=%s", (chat_id, user_id))

async def set_log_chat_id(user_id, chat_id):
    await db(_set_log_chat_id, user_id, chat_id)


def _get_log_chat_id(cur, user_id):
    cur.execute("SELECT log_chat_id FROM users WHERE user_id=%s", (user_id,))
    row = cur.fetchone()
    return row[0] if row else None

async def get_log_chat_id(user_id):
    return await db(_get_log_chat_id, user_id)


# ─── Accounts ─────────────────────────────────────────────────────────────────

def _get_accounts(cur, user_id):
    cur.execute("""
        SELECT id, phone, label, is_active, bio_ok
        FROM accounts WHERE user_id=%s ORDER BY created_at ASC
    """, (user_id,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

async def get_accounts(user_id):
    return await db(_get_accounts, user_id)


def _get_account_sessions(cur, user_id):
    cur.execute("""
        SELECT phone, session_string FROM accounts
        WHERE user_id=%s AND is_active=TRUE AND bio_ok=TRUE
    """, (user_id,))
    return cur.fetchall()

async def get_account_sessions(user_id):
    return await db(_get_account_sessions, user_id)


def _get_all_active_sessions(cur):
    cur.execute("""
        SELECT user_id, phone, session_string FROM accounts
        WHERE is_active=TRUE AND bio_ok=TRUE
    """)
    return cur.fetchall()

async def get_all_active_sessions():
    return await db(_get_all_active_sessions)


def _count_accounts(cur, user_id):
    cur.execute("SELECT COUNT(*) FROM accounts WHERE user_id=%s", (user_id,))
    return cur.fetchone()[0]

async def count_accounts(user_id):
    return await db(_count_accounts, user_id)


def _add_account(cur, user_id, phone, session_string, label=""):
    cur.execute("""
        INSERT INTO accounts (user_id, phone, session_string, label)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id, phone) DO UPDATE SET
            session_string = EXCLUDED.session_string,
            label = EXCLUDED.label,
            is_active = TRUE,
            bio_ok = TRUE
    """, (user_id, phone, session_string, label))

async def add_account(user_id, phone, session_string, label=""):
    await db(_add_account, user_id, phone, session_string, label)


def _get_account_by_id(cur, account_id):
    cur.execute("""
        SELECT id, user_id, phone, session_string, label, is_active, bio_ok
        FROM accounts WHERE id=%s
    """, (account_id,))
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    return dict(zip(cols, row)) if row else None

async def get_account_by_id(account_id):
    return await db(_get_account_by_id, account_id)


def _delete_account(cur, user_id, account_id):
    cur.execute("DELETE FROM accounts WHERE id=%s AND user_id=%s", (account_id, user_id))

async def delete_account(user_id, account_id):
    await db(_delete_account, user_id, account_id)


def _set_account_bio_ok(cur, user_id, phone, bio_ok):
    cur.execute("UPDATE accounts SET bio_ok=%s WHERE user_id=%s AND phone=%s",
                (bio_ok, user_id, phone))

async def set_account_bio_ok(user_id, phone, bio_ok):
    await db(_set_account_bio_ok, user_id, phone, bio_ok)


# ─── Settings ─────────────────────────────────────────────────────────────────

def _get_settings(cur, user_id):
    cur.execute("SELECT * FROM user_settings WHERE user_id=%s", (user_id,))
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    return dict(zip(cols, row)) if row else None

async def get_settings(user_id):
    return await db(_get_settings, user_id)


def _set_ad_message(cur, user_id, message):
    cur.execute("""
        INSERT INTO user_settings (user_id, ad_message) VALUES (%s, %s)
        ON CONFLICT (user_id) DO UPDATE SET ad_message = EXCLUDED.ad_message
    """, (user_id, message))

async def set_ad_message(user_id, message):
    await db(_set_ad_message, user_id, message)


def _set_interval(cur, user_id, minutes):
    cur.execute("""
        INSERT INTO user_settings (user_id, interval_minutes) VALUES (%s, %s)
        ON CONFLICT (user_id) DO UPDATE SET interval_minutes = EXCLUDED.interval_minutes
    """, (user_id, minutes))

async def set_interval(user_id, minutes):
    await db(_set_interval, user_id, minutes)


def _set_running(cur, user_id, running):
    cur.execute("UPDATE user_settings SET is_running=%s WHERE user_id=%s", (running, user_id))

async def set_running(user_id, running):
    await db(_set_running, user_id, running)


def _set_auto_reply(cur, user_id, enabled, message=None):
    if enabled is not None and message is not None:
        cur.execute("""
            UPDATE user_settings SET auto_reply_enabled=%s, auto_reply_message=%s
            WHERE user_id=%s
        """, (enabled, message, user_id))
    elif enabled is not None:
        cur.execute("UPDATE user_settings SET auto_reply_enabled=%s WHERE user_id=%s",
                    (enabled, user_id))
    elif message is not None:
        cur.execute("UPDATE user_settings SET auto_reply_message=%s WHERE user_id=%s",
                    (message, user_id))

async def set_auto_reply(user_id, enabled, message=None):
    await db(_set_auto_reply, user_id, enabled, message)


def _set_auto_reply_inactive_minutes(cur, user_id, minutes):
    cur.execute("""
        INSERT INTO user_settings (user_id, auto_reply_inactive_minutes)
        VALUES (%s, %s)
        ON CONFLICT (user_id) DO UPDATE
        SET auto_reply_inactive_minutes = EXCLUDED.auto_reply_inactive_minutes
    """, (user_id, minutes))


async def set_auto_reply_inactive_minutes(user_id, minutes):
    await db(_set_auto_reply_inactive_minutes, user_id, minutes)


def _set_smart_delay(cur, user_id, seconds):
    cur.execute("UPDATE user_settings SET smart_delay_seconds=%s WHERE user_id=%s",
                (seconds, user_id))

async def set_smart_delay(user_id, seconds):
    await db(_set_smart_delay, user_id, seconds)


def _set_group_blacklist(cur, user_id, blacklist):
    cur.execute("UPDATE user_settings SET group_blacklist=%s WHERE user_id=%s",
                (blacklist, user_id))

async def set_group_blacklist(user_id, blacklist):
    await db(_set_group_blacklist, user_id, blacklist)


def _set_rotation_mode(cur, user_id, enabled):
    cur.execute("UPDATE user_settings SET rotation_mode=%s WHERE user_id=%s",
                (enabled, user_id))

async def set_rotation_mode(user_id, enabled):
    await db(_set_rotation_mode, user_id, enabled)


def _set_scheduled_time(cur, user_id, time_str):
    cur.execute("UPDATE user_settings SET scheduled_time=%s WHERE user_id=%s",
                (time_str, user_id))

async def set_scheduled_time(user_id, time_str):
    await db(_set_scheduled_time, user_id, time_str)


def _set_message_signature(cur, user_id, sig):
    cur.execute("UPDATE user_settings SET message_signature=%s WHERE user_id=%s",
                (sig, user_id))

async def set_message_signature(user_id, sig):
    await db(_set_message_signature, user_id, sig)


def _set_active_hours(cur, user_id, start, end):
    cur.execute("UPDATE user_settings SET active_hours_start=%s, active_hours_end=%s WHERE user_id=%s",
                (start, end, user_id))

async def set_active_hours(user_id, start, end):
    await db(_set_active_hours, user_id, start, end)


def _set_target_filter(cur, user_id, target):
    cur.execute("UPDATE user_settings SET target_filter=%s WHERE user_id=%s",
                (target, user_id))

async def set_target_filter(user_id, target):
    await db(_set_target_filter, user_id, target)


def _increment_ad_count(cur, user_id):
    cur.execute("""
        UPDATE user_settings SET ad_count=ad_count+1, last_ad_sent=NOW()
        WHERE user_id=%s
    """, (user_id,))

async def increment_ad_count(user_id):
    await db(_increment_ad_count, user_id)


# ─── Premium / Subscriptions ──────────────────────────────────────────────────

def _is_premium(cur, user_id):
    cur.execute("""
        SELECT COUNT(*) FROM subscriptions
        WHERE user_id=%s AND status='approved' AND expires_at > NOW()
    """, (user_id,))
    return cur.fetchone()[0] > 0

async def is_premium(user_id):
    return await db(_is_premium, user_id)


def _get_premium_expiry(cur, user_id):
    cur.execute("""
        SELECT expires_at FROM subscriptions
        WHERE user_id=%s AND status='approved' AND expires_at > NOW()
        ORDER BY expires_at DESC LIMIT 1
    """, (user_id,))
    row = cur.fetchone()
    return row[0] if row else None

async def get_premium_expiry(user_id):
    return await db(_get_premium_expiry, user_id)


def _create_subscription_request(cur, user_id, plan_id, days, price):
    cur.execute("""
        INSERT INTO subscriptions (user_id, plan_id, days, price, status)
        VALUES (%s, %s, %s, %s, 'pending')
    """, (user_id, plan_id, days, price))

async def create_subscription_request(user_id, plan_id, days, price):
    await db(_create_subscription_request, user_id, plan_id, days, price)


def _approve_subscription(cur, user_id, plan_id):
    cur.execute("""
        SELECT id, days FROM subscriptions
        WHERE user_id=%s AND plan_id=%s AND status='pending'
        ORDER BY requested_at DESC LIMIT 1
    """, (user_id, plan_id))
    row = cur.fetchone()
    if not row:
        return False
    sub_id, days = row
    cur.execute("""
        UPDATE subscriptions
        SET status='approved', approved_at=NOW(),
            expires_at=NOW() + (%s || ' days')::INTERVAL
        WHERE id=%s
    """, (days, sub_id))
    return True

async def approve_subscription(user_id, plan_id):
    return await db(_approve_subscription, user_id, plan_id)


def _reject_subscription(cur, user_id, plan_id):
    cur.execute("""
        UPDATE subscriptions SET status='rejected'
        WHERE user_id=%s AND plan_id=%s AND status='pending'
    """, (user_id, plan_id))
    return True

async def reject_subscription(user_id, plan_id):
    return await db(_reject_subscription, user_id, plan_id)


def _grant_premium(cur, user_id, days):
    """Admin grants premium directly."""
    cur.execute("""
        INSERT INTO subscriptions (user_id, plan_id, days, price, status, approved_at, expires_at)
        VALUES (%s, 'admin_grant', %s, 0, 'approved', NOW(), NOW() + (%s || ' days')::INTERVAL)
    """, (user_id, days, days))

async def grant_premium(user_id, days):
    await db(_grant_premium, user_id, days)


def _revoke_premium(cur, user_id):
    """Admin revokes all active subscriptions."""
    cur.execute("""
        UPDATE subscriptions
        SET status='revoked', expires_at=NOW()
        WHERE user_id=%s AND status='approved' AND expires_at > NOW()
    """, (user_id,))

async def revoke_premium(user_id):
    await db(_revoke_premium, user_id)


def _count_premium_users(cur):
    cur.execute("""
        SELECT COUNT(DISTINCT user_id) FROM subscriptions
        WHERE status='approved' AND expires_at > NOW()
    """)
    return cur.fetchone()[0]

async def count_premium_users():
    return await db(_count_premium_users)


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


def _get_logs(cur, user_id, limit=20, offset=0):
    cur.execute("""
        SELECT action, details, created_at FROM logs
        WHERE user_id=%s ORDER BY created_at DESC LIMIT %s OFFSET %s
    """, (user_id, limit, offset))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

async def get_logs(user_id, limit=20, offset=0):
    return await db(_get_logs, user_id, limit, offset)


def _count_logs(cur, user_id):
    cur.execute("SELECT COUNT(*) FROM logs WHERE user_id=%s", (user_id,))
    return cur.fetchone()[0]

async def count_logs(user_id):
    return await db(_count_logs, user_id)


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


# ─── Stats ─────────────────────────────────────────────────────────────────────

def _get_stats(cur, user_id):
    cur.execute("""
        SELECT
            COALESCE(SUM(sent_count),0)   as total_sent,
            COALESCE(SUM(failed_count),0) as total_failed,
            COUNT(*)                       as total_jobs,
            COALESCE(MAX(group_count),0)   as max_groups
        FROM ad_jobs WHERE user_id=%s
    """, (user_id,))
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    return dict(zip(cols, row)) if row else {}

async def get_stats(user_id):
    return await db(_get_stats, user_id)


def _get_global_stats(cur):
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users WHERE is_banned=TRUE")
    banned_users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT user_id) FROM subscriptions WHERE status='approved' AND expires_at > NOW()")
    premium_users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM accounts")
    total_accounts = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM user_settings WHERE is_running=TRUE")
    running_bots = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(SUM(sent_count),0) FROM ad_jobs")
    total_sent = cur.fetchone()[0]
    return {
        "total_users": total_users,
        "banned_users": banned_users,
        "premium_users": premium_users,
        "total_accounts": total_accounts,
        "running_bots": running_bots,
        "total_sent": total_sent,
    }

async def get_global_stats():
    return await db(_get_global_stats)


def _get_recent_jobs(cur, user_id, limit=10):
    cur.execute("""
        SELECT account_phone, group_count, sent_count, failed_count, ran_at
        FROM ad_jobs WHERE user_id=%s ORDER BY ran_at DESC LIMIT %s
    """, (user_id, limit))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

async def get_recent_jobs(user_id, limit=10):
    return await db(_get_recent_jobs, user_id, limit)


# ─── Group / Channel Cache ─────────────────────────────────────────────────────

def _upsert_group_cache(cur, user_id, phone, group_id, title, is_channel=False, member_count=0):
    cur.execute("""
        INSERT INTO group_cache (user_id, account_phone, group_id, title, is_channel, member_count)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, account_phone, group_id) DO UPDATE SET
            title = EXCLUDED.title,
            is_channel = EXCLUDED.is_channel,
            member_count = EXCLUDED.member_count,
            last_synced = NOW()
    """, (user_id, phone, group_id, title, is_channel, member_count))

async def upsert_group_cache(user_id, phone, group_id, title, is_channel=False, member_count=0):
    await db(_upsert_group_cache, user_id, phone, group_id, title, is_channel, member_count)


def _get_group_cache(cur, user_id):
    cur.execute("""
        SELECT DISTINCT ON (group_id) group_id, title, is_channel, excluded, member_count
        FROM group_cache WHERE user_id=%s
        ORDER BY group_id, last_synced DESC
    """, (user_id,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

async def get_group_cache(user_id):
    return await db(_get_group_cache, user_id)


def _get_groups_only(cur, user_id):
    cur.execute("""
        SELECT DISTINCT ON (group_id) group_id, title, is_channel, excluded, member_count
        FROM group_cache WHERE user_id=%s AND is_channel=FALSE
        ORDER BY group_id, last_synced DESC
    """, (user_id,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

async def get_groups_only(user_id):
    return await db(_get_groups_only, user_id)


def _get_channels_only(cur, user_id):
    cur.execute("""
        SELECT DISTINCT ON (group_id) group_id, title, is_channel, excluded, member_count
        FROM group_cache WHERE user_id=%s AND is_channel=TRUE
        ORDER BY group_id, last_synced DESC
    """, (user_id,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

async def get_channels_only(user_id):
    return await db(_get_channels_only, user_id)


def _toggle_group_exclude(cur, user_id, group_id):
    cur.execute("""
        UPDATE group_cache SET excluded = NOT excluded
        WHERE user_id=%s AND group_id=%s
    """, (user_id, group_id))

async def toggle_group_exclude(user_id, group_id):
    await db(_toggle_group_exclude, user_id, group_id)


def _exclude_all_groups(cur, user_id):
    cur.execute("UPDATE group_cache SET excluded=TRUE WHERE user_id=%s AND is_channel=FALSE", (user_id,))

async def exclude_all_groups(user_id):
    await db(_exclude_all_groups, user_id)


def _include_all_groups(cur, user_id):
    cur.execute("UPDATE group_cache SET excluded=FALSE WHERE user_id=%s AND is_channel=FALSE", (user_id,))

async def include_all_groups(user_id):
    await db(_include_all_groups, user_id)


def _exclude_all_channels(cur, user_id):
    cur.execute("UPDATE group_cache SET excluded=TRUE WHERE user_id=%s AND is_channel=TRUE", (user_id,))

async def exclude_all_channels(user_id):
    await db(_exclude_all_channels, user_id)


def _include_all_channels(cur, user_id):
    cur.execute("UPDATE group_cache SET excluded=FALSE WHERE user_id=%s AND is_channel=TRUE", (user_id,))

async def include_all_channels(user_id):
    await db(_include_all_channels, user_id)


def _get_excluded_group_ids(cur, user_id):
    cur.execute("""
        SELECT DISTINCT group_id FROM group_cache
        WHERE user_id=%s AND excluded=TRUE
    """, (user_id,))
    return {row[0] for row in cur.fetchall()}

async def get_excluded_group_ids(user_id):
    return await db(_get_excluded_group_ids, user_id)
