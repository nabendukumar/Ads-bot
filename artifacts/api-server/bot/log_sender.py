"""
Sends structured logs to each user's personal log bot chat.
Admin-level events go to the admin's LOG_CHAT_ID.
User-level events go to that user's registered log_chat_id.
"""
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_log_bot = None
_admin_chat_id = 0


def init_log_bot(token: str, chat_id: int):
    global _log_bot, _admin_chat_id
    if not token or not chat_id:
        logger.warning("Log bot not configured — logs will only go to DB.")
        return
    try:
        from telegram import Bot
        _log_bot = Bot(token=token)
        _admin_chat_id = chat_id
        logger.info(f"Log bot initialized ✅ → admin_chat_id={chat_id}")
    except Exception as e:
        logger.error(f"Log bot init failed: {e}")


def get_log_bot():
    return _log_bot


# ─── Internal helpers ─────────────────────────────────────────────────────────

async def _send_to_chat(chat_id: int, text: str, reply_markup=None):
    """Low-level: send a message to a specific chat via the log bot."""
    global _log_bot
    if not _log_bot or not chat_id:
        return None
    try:
        msg = await _log_bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )
        return msg
    except Exception as e:
        logger.warning(f"Log send failed → chat {chat_id}: {e}")
        return None


async def _get_user_chat_id(user_id: int) -> int:
    """Get the user's registered log_chat_id from DB."""
    try:
        import database as db
        chat_id = await db.get_log_chat_id(user_id)
        return chat_id or 0
    except Exception:
        return 0


# ─── Admin-level log (always goes to admin chat) ──────────────────────────────

async def send_admin_log(action: str, details: str = "", user_id: int = 0, username: str = "",
                          reply_markup=None):
    """Send a log to the admin's chat."""
    global _admin_chat_id
    if not _admin_chat_id:
        return None
    ts = datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S UTC")
    user_part = f"👤 User: `{username or user_id}` (`{user_id}`)\n" if user_id else ""
    text = (
        f"🔐 *[Admin Log — Luci Ads Bot]*\n"
        f"🕐 `{ts}`\n"
        f"{user_part}"
        f"⚡ Action: `{action}`\n"
        f"📝 Details: {details or '—'}"
    )
    return await _send_to_chat(_admin_chat_id, text, reply_markup)


# ─── User-level log (goes to that user's log bot chat) ────────────────────────

async def send_log(action: str, details: str = "", user_id: int = 0, username: str = "",
                   reply_markup=None):
    """
    Send a log for a specific user.
    - If the user has registered their log bot chat, send there.
    - Admin-only events (no user_id) go to admin chat.
    """
    ts = datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S UTC")

    if user_id:
        user_chat_id = await _get_user_chat_id(user_id)
        if user_chat_id:
            user_part = f"👤 `{username or user_id}` | `{user_id}`\n" if username else ""
            text = (
                f"╔══════════════════════╗\n"
                f"║  📋  *Activity Log*   ║\n"
                f"╚══════════════════════╝\n\n"
                f"🕐 `{ts}`\n"
                f"{user_part}"
                f"⚡ *Action:* `{action}`\n"
                f"📝 *Details:* {details or '—'}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━"
            )
            return await _send_to_chat(user_chat_id, text, reply_markup)
        # fallback: send to admin with user context
        return await send_admin_log(action, details, user_id, username, reply_markup)
    else:
        return await send_admin_log(action, details, 0, "", reply_markup)


async def send_user_log_raw(user_id: int, text: str, reply_markup=None):
    """Send arbitrary formatted text to a user's log chat."""
    chat_id = await _get_user_chat_id(user_id)
    if chat_id:
        return await _send_to_chat(chat_id, text, reply_markup)
    return await _send_to_chat(_admin_chat_id, text, reply_markup)


# ─── Specific event senders ───────────────────────────────────────────────────

async def send_account_connected(user_id: int, username: str, phone: str):
    await send_log(
        action="account_connected",
        details=f"📱 Phone: `{phone}`",
        user_id=user_id,
        username=username,
    )
    # Also notify admin
    await send_admin_log(
        action="account_connected",
        details=f"📱 Phone: `{phone}`",
        user_id=user_id,
        username=username,
    )


async def send_ads_started(user_id: int, username: str, account_count: int, interval: int):
    await send_log(
        action="ads_started",
        details=f"🤖 Accounts: {account_count} | ⏰ Interval: {interval} min",
        user_id=user_id,
        username=username,
    )


async def send_ads_stopped(user_id: int, username: str):
    await send_log(
        action="ads_stopped",
        details="🔴 User stopped broadcast",
        user_id=user_id,
        username=username,
    )


async def send_broadcast_result(user_id: int, username: str, sent: int, failed: int, accounts: int):
    """Send broadcast result ONLY to user's log bot — NOT to the main bot."""
    total = sent + failed
    rate = round(sent / total * 100, 1) if total > 0 else 0.0
    bar = "🟩" * int(rate / 10) + "⬜" * (10 - int(rate / 10))
    ts = datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S UTC")

    chat_id = await _get_user_chat_id(user_id)
    if not chat_id:
        chat_id = _admin_chat_id

    text = (
        f"📡 *Broadcast Complete!*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 `{ts}`\n"
        f"👤 `{username or user_id}` (`{user_id}`)\n\n"
        f"✅ *Sent:* `{sent}`\n"
        f"❌ *Failed:* `{failed}`\n"
        f"🎯 *Rate:* `{rate}%`\n"
        f"📊 {bar} `{rate}%`\n"
        f"🤖 *Accounts Used:* `{accounts}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )
    await _send_to_chat(chat_id, text)


async def send_new_user(user_id: int, username: str, first_name: str):
    await send_admin_log(
        action="new_user",
        details=f"👤 Name: {first_name} | @{username or 'no_username'}",
        user_id=user_id,
        username=username,
    )


async def send_payment_request(user_id: int, username: str, plan_label: str,
                                price: int, plan_id: str, admin_kb):
    """Send payment notification to admin with approve/reject buttons."""
    global _admin_chat_id
    if not _log_bot or not _admin_chat_id:
        return None
    try:
        ts = datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S UTC")
        text = (
            f"💰 *NEW PAYMENT REQUEST*\n\n"
            f"🕐 `{ts}`\n"
            f"👤 User: `@{username or user_id}` (`{user_id}`)\n"
            f"💎 Plan: *{plan_label}*\n"
            f"💵 Amount: *₹{price}*\n\n"
            f"⚡ _User has claimed payment. Please verify and approve/reject._"
        )
        msg = await _log_bot.send_message(
            chat_id=_admin_chat_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=admin_kb,
        )
        return msg
    except Exception as e:
        logger.warning(f"Payment request send failed: {e}")
        return None


async def send_bio_violation(user_id: int, username: str, phone: str):
    await send_log(
        action="bio_violation",
        details=f"⚠️ Bot username removed — account deactivated. 📱 Phone: `{phone}`",
        user_id=user_id,
        username=username,
    )
    await send_admin_log(
        action="bio_violation",
        details=f"⚠️ Phone: `{phone}`",
        user_id=user_id,
        username=username,
    )


async def send_admin_action(admin_id: int, action: str, target_user_id: int, details: str = ""):
    """Log admin actions to admin chat."""
    await send_admin_log(
        action=f"ADMIN: {action}",
        details=f"Target: `{target_user_id}` | {details}",
        user_id=admin_id,
        username="admin",
    )
