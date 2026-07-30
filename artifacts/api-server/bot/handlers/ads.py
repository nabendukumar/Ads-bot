"""
Ad management: Set message, set interval, start/stop ads, run broadcast.
"""
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode

import database as db
import telethon_manager as tm
import log_sender
from config import MIN_ACCOUNTS
from keyboards import back_kb, back_and_cancel_kb, interval_kb

logger = logging.getLogger(__name__)

SET_MSG_STATE = "set_ad_msg_waiting"


# ─── Set Ad Message ───────────────────────────────────────────────────────────

async def cb_set_ad_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    settings = await db.get_settings(user.id) or {}
    current = settings.get("ad_message")
    context.user_data[SET_MSG_STATE] = True

    current_text = f"\n*Current:*\n_{current[:200]}_\n" if current else ""
    sig = settings.get("message_signature")
    sig_text = f"\n💎 *Signature:* _{sig}_\n_(auto-appended to every message)_\n" if sig else ""
    await query.edit_message_text(
        f"📝 *Set Ad Message*\n{current_text}{sig_text}\n"
        "Type your new broadcast message below:\n\n"
        "Type /cancel to go back.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_and_cancel_kb(),
    )


async def handle_ad_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get(SET_MSG_STATE):
        return False
    user = update.effective_user
    message = update.message.text.strip()
    context.user_data.pop(SET_MSG_STATE, None)

    await db.set_ad_message(user.id, message)
    await db.add_log(user.id, "ad_message_set", f"Length: {len(message)} chars")
    preview = message[:200] + ("..." if len(message) > 200 else "")
    await update.message.reply_text(
        f"✅ *Ad Message Saved!*\n\n*Preview:*\n_{preview}_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_kb("menu"),
    )
    return True


# ─── Set Time Interval ────────────────────────────────────────────────────────

async def cb_set_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    settings = await db.get_settings(user.id) or {}
    current = settings.get("interval_minutes", 60)

    await query.edit_message_text(
        f"⏰ *Set Time Interval*\n\n"
        f"*Current:* every {current} minutes\n\n"
        "Select how often to broadcast:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=interval_kb(),
    )


async def cb_interval_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    minutes = int(query.data.split("_")[1])

    await db.set_interval(user.id, minutes)
    await db.add_log(user.id, "interval_set", f"{minutes} min")
    await query.edit_message_text(
        f"✅ *Interval set to {minutes} minutes!*\n\nAds will be sent every {minutes} min.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_kb("menu"),
    )


# ─── Start Ads ────────────────────────────────────────────────────────────────

async def cb_start_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    settings = await db.get_settings(user.id) or {}

    # Validate
    accounts = await db.get_account_sessions(user.id)
    if len(accounts) < MIN_ACCOUNTS:
        await query.edit_message_text(
            f"❌ *Need at least {MIN_ACCOUNTS} account(s) to start ads!*\n\n"
            "Go to ➕ Add Account first.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_kb("menu"),
        )
        return

    if not settings.get("ad_message"):
        await query.edit_message_text(
            "❌ *No ad message set!*\n\nGo to 📝 Set Ad Message first.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_kb("menu"),
        )
        return

    if settings.get("is_running"):
        await query.edit_message_text(
            "⚠️ *Ads are already running!*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_kb("menu"),
        )
        return

    interval = settings.get("interval_minutes", 60)
    await db.set_running(user.id, True)
    await db.add_log(user.id, "ads_started", f"Interval: {interval}min, Accounts: {len(accounts)}")
    await log_sender.send_ads_started(user.id, user.username or "", len(accounts), interval)

    # Schedule periodic broadcast
    context.job_queue.run_repeating(
        _broadcast_job,
        interval=interval * 60,
        first=10,
        name=f"ads_{user.id}",
        data={"user_id": user.id},
    )

    await query.edit_message_text(
        f"🟢 *Ads Started!*\n\n"
        f"╔══════════════════════╗\n"
        f"║  🚀 Broadcasting!     ║\n"
        f"╚══════════════════════╝\n\n"
        f"📡 Sending every *{interval} minutes*\n"
        f"👥 Using *{len(accounts)} account(s)*\n\n"
        "_You'll be notified after each broadcast._",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_kb("menu"),
    )


async def _broadcast_job(context: ContextTypes.DEFAULT_TYPE):
    user_id = context.job.data["user_id"]
    settings = await db.get_settings(user_id) or {}

    if not settings.get("is_running"):
        context.job.schedule_removal()
        return

    # Active hours check
    now_hour = datetime.utcnow().hour
    start_h = settings.get("active_hours_start", 0)
    end_h = settings.get("active_hours_end", 23)
    if not (start_h <= now_hour <= end_h):
        logger.info(f"Outside active hours for user {user_id}, skipping.")
        return

    accounts = await db.get_account_sessions(user_id)
    if not accounts:
        return

    message = settings.get("ad_message", "")
    sig = settings.get("message_signature")
    if sig:
        message = f"{message}\n\n{sig}"

    delay = settings.get("smart_delay_seconds", 3)
    blacklist_str = settings.get("group_blacklist", "")
    blacklist = [g.strip() for g in blacklist_str.split(",") if g.strip()]
    excluded_ids = await db.get_excluded_group_ids(user_id)
    target_filter = settings.get("target_filter", "all")
    rotation = settings.get("rotation_mode", False)

    total_sent = total_failed = 0
    account_results = []

    if rotation and len(accounts) > 1:
        total_sent, total_failed, account_results = await _run_rotation(
            user_id, accounts, message, delay, blacklist, excluded_ids, target_filter
        )
    else:
        for phone, session_string in accounts:
            try:
                sent, failed, gcount = await tm.send_ads_to_groups(
                    session_string, message, delay, blacklist, excluded_ids, target_filter
                )
                total_sent += sent
                total_failed += failed
                account_results.append(f"• `{phone[-4:]}`: {sent}/{gcount} ✅")
                await db.add_job_log(user_id, phone, gcount, sent, failed)
            except Exception as e:
                logger.error(f"Broadcast error for {phone}: {e}")
                account_results.append(f"• `{phone[-4:]}`: Error ❌")

    await db.increment_ad_count(user_id)
    result_text = "\n".join(account_results) if account_results else "—"
    total = total_sent + total_failed
    rate = round(total_sent / total * 100) if total > 0 else 0

    # Notify user
    try:
        user_obj = await context.bot.get_chat(user_id)
        username = user_obj.username or ""
    except Exception:
        username = ""

    await log_sender.send_broadcast_result(user_id, username, total_sent, total_failed, len(accounts))

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"📡 *Broadcast Complete!*\n\n"
                f"✅ Sent: `{total_sent}` | ❌ Failed: `{total_failed}`\n"
                f"🎯 Rate: `{rate}%`\n\n"
                f"{result_text}"
            ),
            parse_mode="Markdown",
        )
    except Exception:
        pass


async def _run_rotation(user_id, accounts, message, delay, blacklist, excluded_ids, target_filter):
    """Distribute groups across accounts in rotation mode."""
    import asyncio
    from telethon.tl.types import Channel, Chat
    import telethon_manager as tm2
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from config import API_ID, API_HASH

    total_sent = total_failed = 0
    account_results = []

    # Collect all groups from first account
    phone, session_string = accounts[0]
    try:
        dialogs = await tm2.get_dialogs(session_string)
        all_groups = [d for d in dialogs if d["group_id"] not in excluded_ids]
    except Exception as e:
        logger.error(f"Rotation group fetch error: {e}")
        return 0, 0, []

    chunk_size = max(1, len(all_groups) // len(accounts))
    for i, (phone, session_string) in enumerate(accounts):
        items = all_groups[i * chunk_size:(i + 1) * chunk_size]
        if not items:
            continue
        sent = failed = 0
        try:
            client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
            await client.connect()
            for d in items:
                try:
                    entity = await client.get_entity(d["group_id"])
                    await client.send_message(entity, message)
                    sent += 1
                except Exception:
                    failed += 1
                import asyncio as _as
                await _as.sleep(delay)
            await client.disconnect()
        except Exception as e:
            logger.error(f"Rotation client error {phone}: {e}")
        total_sent += sent
        total_failed += failed
        account_results.append(f"• `{phone[-4:]}` (rotated): {sent}/{len(items)} ✅")
        await db.add_job_log(user_id, phone, len(items), sent, failed)

    return total_sent, total_failed, account_results


async def run_broadcast(query, context, user):
    """One-time instant broadcast (for Broadcast Now button)."""
    settings = await db.get_settings(user.id) or {}
    accounts = await db.get_account_sessions(user.id)

    if not accounts:
        await query.edit_message_text(
            "❌ No active accounts.", parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium")
        )
        return

    if not settings.get("ad_message"):
        await query.edit_message_text(
            "❌ No ad message set.", parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium")
        )
        return

    await query.edit_message_text(
        "📡 *Broadcasting now...*\n\n_This may take a few minutes._",
        parse_mode=ParseMode.MARKDOWN,
    )

    message = settings.get("ad_message", "")
    sig = settings.get("message_signature")
    if sig:
        message = f"{message}\n\n{sig}"
    delay = settings.get("smart_delay_seconds", 3)
    blacklist = [g.strip() for g in (settings.get("group_blacklist", "") or "").split(",") if g.strip()]
    excluded_ids = await db.get_excluded_group_ids(user.id)
    target_filter = settings.get("target_filter", "all")

    total_sent = total_failed = 0
    for phone, session_string in accounts:
        try:
            sent, failed, gcount = await tm.send_ads_to_groups(
                session_string, message, delay, blacklist, excluded_ids, target_filter
            )
            total_sent += sent
            total_failed += failed
            await db.add_job_log(user.id, phone, gcount, sent, failed)
        except Exception as e:
            logger.error(f"Broadcast now error {phone}: {e}")

    await db.increment_ad_count(user.id)
    total = total_sent + total_failed
    rate = round(total_sent / total * 100) if total > 0 else 0

    await context.bot.send_message(
        chat_id=user.id,
        text=(
            f"✅ *Instant Broadcast Complete!*\n\n"
            f"✅ Sent: `{total_sent}` | ❌ Failed: `{total_failed}`\n"
            f"🎯 Rate: `{rate}%`"
        ),
        parse_mode="Markdown",
        reply_markup=back_kb("premium"),
    )


# ─── Stop Ads ─────────────────────────────────────────────────────────────────

async def cb_stop_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    settings = await db.get_settings(user.id) or {}
    if not settings.get("is_running"):
        await query.edit_message_text(
            "⚠️ *Ads are not running!*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_kb("menu"),
        )
        return

    await db.set_running(user.id, False)
    await db.add_log(user.id, "ads_stopped")
    await log_sender.send_ads_stopped(user.id, user.username or "")

    for job in context.application.job_queue.get_jobs_by_name(f"ads_{user.id}"):
        job.schedule_removal()

    await query.edit_message_text(
        "🔴 *Ads Stopped.*\n\nNo more messages will be sent.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_kb("menu"),
    )


def register(app):
    app.add_handler(CallbackQueryHandler(cb_set_ad_msg, pattern="^set_ad_msg$"))
    app.add_handler(CallbackQueryHandler(cb_set_interval, pattern="^set_interval$"))
    app.add_handler(CallbackQueryHandler(cb_interval_select, pattern=r"^interval_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_start_ads, pattern="^start_ads$"))
    app.add_handler(CallbackQueryHandler(cb_stop_ads, pattern="^stop_ads$"))
