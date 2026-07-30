"""
Sends structured logs to the designated Telegram log bot/channel.
"""
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_log_bot = None
_log_chat_id = 0


def init_log_bot(token: str, chat_id: int):
    global _log_bot, _log_chat_id
    if not token or not chat_id:
        logger.warning("Log bot not configured — logs will only go to DB.")
        return
    try:
        from telegram import Bot
        _log_bot = Bot(token=token)
        _log_chat_id = chat_id
        logger.info(f"Log bot initialized ✅ → chat_id={chat_id}")
    except Exception as e:
        logger.error(f"Log bot init failed: {e}")


async def send_log(action: str, details: str = "", user_id: int = 0, username: str = "",
                   reply_markup=None):
    global _log_bot, _log_chat_id
    if not _log_bot or not _log_chat_id:
        return None
    try:
        ts = datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S UTC")
        user_part = f"👤 User: `{username or user_id}` (`{user_id}`)\n" if user_id else ""
        text = (
            f"📋 *[Luci Ads Bot Log]*\n"
            f"🕐 `{ts}`\n"
            f"{user_part}"
            f"⚡ Action: `{action}`\n"
            f"📝 Details: {details or '—'}"
        )
        msg = await _log_bot.send_message(
            chat_id=_log_chat_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )
        return msg
    except Exception as e:
        logger.warning(f"Log send failed: {e}")
        return None


async def send_account_connected(user_id: int, username: str, phone: str):
    await send_log(
        action="account_connected",
        details=f"Phone: `{phone}`",
        user_id=user_id,
        username=username,
    )


async def send_ads_started(user_id: int, username: str, account_count: int, interval: int):
    await send_log(
        action="ads_started",
        details=f"Accounts: {account_count} | Interval: {interval} min",
        user_id=user_id,
        username=username,
    )


async def send_ads_stopped(user_id: int, username: str):
    await send_log(
        action="ads_stopped",
        details="User stopped broadcast",
        user_id=user_id,
        username=username,
    )


async def send_broadcast_result(user_id: int, username: str, sent: int, failed: int, accounts: int):
    await send_log(
        action="broadcast_complete",
        details=f"Sent: {sent} | Failed: {failed} | Accounts: {accounts}",
        user_id=user_id,
        username=username,
    )


async def send_new_user(user_id: int, username: str, first_name: str):
    await send_log(
        action="new_user",
        details=f"Name: {first_name} | @{username or 'no_username'}",
        user_id=user_id,
        username=username,
    )


async def send_payment_request(user_id: int, username: str, plan_label: str,
                                price: int, plan_id: str, admin_kb):
    """Send payment notification to admin with approve/reject buttons."""
    global _log_bot, _log_chat_id
    if not _log_bot or not _log_chat_id:
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
            chat_id=_log_chat_id,
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
        details=f"Bot username removed from bio/name — account deactivated. Phone: {phone}",
        user_id=user_id,
        username=username,
    )
