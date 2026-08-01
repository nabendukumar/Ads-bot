"""
Auto-reply management: toggle on/off, set custom message and inactivity time.
"""
import logging
from html import escape
from telegram import Update
from telegram.ext import (
    ContextTypes, CallbackQueryHandler, MessageHandler, CommandHandler, filters,
)
from telegram.constants import ParseMode

import database as db
import telethon_manager as tm
from keyboards import auto_reply_kb, back_kb, back_and_cancel_kb

logger = logging.getLogger(__name__)

SET_AR_STATE = "set_auto_reply_waiting"
SET_AR_TIME_STATE = "set_auto_reply_time_waiting"
DEFAULT_REPLY_MESSAGE = "Main abhi available nahi hoon. Thodi der baad message karein."
DEFAULT_INACTIVE_MINUTES = 30
MAX_INACTIVE_MINUTES = 7 * 24 * 60


def _settings_text(settings):
    enabled = settings.get("auto_reply_enabled", False)
    msg = settings.get("auto_reply_message") or DEFAULT_REPLY_MESSAGE
    inactive_minutes = int(
        settings.get("auto_reply_inactive_minutes") or DEFAULT_INACTIVE_MINUTES
    )
    return enabled, msg, inactive_minutes


async def _refresh_auto_reply_clients(user_id, bot):
    """Reload enabled auto-reply listeners after a setting/account change."""
    settings = await db.get_settings(user_id) or {}
    enabled, message, inactive_minutes = _settings_text(settings)
    await tm.teardown_all_auto_reply(user_id)
    if not enabled:
        return

    accounts = await db.get_account_sessions(user_id)
    for phone, session_string in accounts:
        await tm.setup_auto_reply(
            user_id=user_id,
            phone=phone,
            session_string=session_string,
            reply_message=message,
            inactivity_minutes=inactive_minutes,
            bot=bot,
            get_last_active_fn=db.get_user_last_active,
            get_auto_reply_settings_fn=db.get_settings,
        )


async def cb_auto_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    settings = await db.get_settings(user.id) or {}
    enabled, msg, inactive_minutes = _settings_text(settings)

    text = (
        f"💬 <b>Auto Reply Settings</b>\n\n"
        f"<b>Status:</b> {'🟢 ON' if enabled else '🔴 OFF'}\n\n"
        f"<b>Inactive Time:</b> <code>{inactive_minutes} minutes</code>\n\n"
        f"<b>Current Reply Message:</b>\n{escape(msg)}\n\n"
        f"<i>(When you haven't been active for {inactive_minutes} minutes, anyone who messages "
        "your connected accounts will receive this auto-reply)</i>"
    )
    await query.edit_message_text(
        text, parse_mode=ParseMode.HTML, reply_markup=auto_reply_kb(enabled)
    )


async def cb_toggle_auto_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    settings = await db.get_settings(user.id) or {}
    current = settings.get("auto_reply_enabled", False)
    new_state = not current

    await db.set_auto_reply(user.id, new_state)
    await db.add_log(user.id, "auto_reply_toggled", "ON" if new_state else "OFF")

    if new_state:
        accounts = await db.get_account_sessions(user.id)
        if not accounts:
            await db.set_auto_reply(user.id, False)
            await query.edit_message_text(
                "❌ <b>Connect at least one Telegram account before enabling Auto Reply.</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=auto_reply_kb(False),
            )
            return
        _, reply_msg, inactive_minutes = _settings_text(settings)
        started = 0
        failed_phones = []
        for phone, session_string in accounts:
            try:
                started_ok = await tm.setup_auto_reply(
                    user_id=user.id,
                    phone=phone,
                    session_string=session_string,
                    reply_message=reply_msg,
                    inactivity_minutes=inactive_minutes,
                    bot=context.bot,
                    get_last_active_fn=db.get_user_last_active,
                    get_auto_reply_settings_fn=db.get_settings,
                )
                if started_ok:
                    started += 1
                else:
                    failed_phones.append(phone)
            except Exception as e:
                logger.error(f"Auto reply setup error for {phone}: {e}")
                failed_phones.append(phone)

        if accounts and started == 0:
            await db.set_auto_reply(user.id, False)
            await db.add_log(user.id, "auto_reply_setup_failed", ", ".join(failed_phones))
            await query.edit_message_text(
                "❌ <b>Auto Reply could not start.</b>\n\n"
                "The connected Telegram account could not be logged in. "
                "Please reconnect the account and try again.",
                parse_mode=ParseMode.HTML,
                reply_markup=auto_reply_kb(False),
            )
            return
    else:
        await tm.teardown_all_auto_reply(user.id)

    updated = await db.get_settings(user.id) or {}
    enabled = updated.get("auto_reply_enabled", False)
    _, msg, inactive_minutes = _settings_text(updated)
    text = (
        f"💬 <b>Auto Reply Settings</b>\n\n"
        f"<b>Status:</b> {'🟢 ON' if enabled else '🔴 OFF'}\n\n"
        f"<b>Inactive Time:</b> <code>{inactive_minutes} minutes</code>\n\n"
        f"<b>Current Reply Message:</b>\n{escape(msg)}"
    )
    if new_state and accounts and failed_phones:
        text += (
            f"\n\n⚠️ Running for {started}/{len(accounts)} account(s). "
            "Some accounts could not connect."
        )
    await query.edit_message_text(
        text, parse_mode=ParseMode.HTML, reply_markup=auto_reply_kb(enabled)
    )


async def cb_set_auto_reply_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data[SET_AR_STATE] = True
    await query.edit_message_text(
        "✏️ *Set Auto Reply Message*\n\n"
        "Type the message that will be sent automatically when you're offline:\n\n"
        "Type /cancel to go back.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_and_cancel_kb(),
    )


async def cb_set_auto_reply_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data[SET_AR_TIME_STATE] = True
    await query.edit_message_text(
        "⏱️ *Set Inactive Time*\n\n"
        "Enter how many minutes a user must be inactive before auto-reply starts.\n"
        f"Choose a whole number from 1 to {MAX_INACTIVE_MINUTES} minutes "
        "(up to 7 days).\n\n"
        "Examples: `30`, `60`, `1440`\n\n"
        "Type /cancel to go back.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_and_cancel_kb(),
    )


async def handle_auto_reply_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get(SET_AR_TIME_STATE):
        raw_value = (update.message.text or "").strip()
        try:
            minutes = int(raw_value)
        except ValueError:
            minutes = 0
        if not 1 <= minutes <= MAX_INACTIVE_MINUTES:
            await update.message.reply_text(
                f"❌ Enter a whole number from 1 to {MAX_INACTIVE_MINUTES} minutes.",
                reply_markup=back_and_cancel_kb(),
            )
            return True

        context.user_data.pop(SET_AR_TIME_STATE, None)
        user = update.effective_user
        await db.set_auto_reply_inactive_minutes(user.id, minutes)
        await db.add_log(user.id, "auto_reply_time_set", f"Minutes: {minutes}")
        await update.message.reply_text(
            f"✅ *Inactive time updated to {minutes} minutes.*\n\n"
            "The new value is used immediately for future messages.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_kb("auto_reply"),
        )
        return True

    if not context.user_data.get(SET_AR_STATE):
        return False
    user = update.effective_user
    new_msg = (update.message.text or "").strip()
    if not new_msg:
        await update.message.reply_text(
            "❌ The reply message cannot be empty. Please type a message.",
            reply_markup=back_and_cancel_kb(),
        )
        return True
    if len(new_msg) > 4000:
        await update.message.reply_text(
            "❌ Keep the reply message under 4000 characters.",
            reply_markup=back_and_cancel_kb(),
        )
        return True
    context.user_data.pop(SET_AR_STATE, None)

    await db.set_auto_reply(user.id, None, message=new_msg)
    await db.add_log(user.id, "auto_reply_msg_set", f"Length: {len(new_msg)}")
    await update.message.reply_text(
        f"✅ <b>Auto Reply Message Updated!</b>\n\n{escape(new_msg)}",
        parse_mode=ParseMode.HTML,
        reply_markup=back_kb("auto_reply"),
    )
    return True


def register(app):
    app.add_handler(CallbackQueryHandler(cb_auto_reply, pattern="^auto_reply$"))
    app.add_handler(CallbackQueryHandler(cb_toggle_auto_reply, pattern="^toggle_auto_reply$"))
    app.add_handler(CallbackQueryHandler(cb_set_auto_reply_msg, pattern="^set_auto_reply_msg$"))
    app.add_handler(CallbackQueryHandler(cb_set_auto_reply_time, pattern="^set_auto_reply_time$"))
