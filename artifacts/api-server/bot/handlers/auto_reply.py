"""
Auto-reply management: toggle on/off, set custom message.
"""
import logging
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


async def cb_auto_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    settings = await db.get_settings(user.id) or {}
    enabled = settings.get("auto_reply_enabled", False)
    msg = settings.get("auto_reply_message", "Main abhi available nahi hoon. Thodi der baad message karein.")

    text = (
        f"💬 *Auto Reply Settings*\n\n"
        f"*Status:* {'🟢 ON' if enabled else '🔴 OFF'}\n\n"
        f"*Current Reply Message:*\n_{msg}_\n\n"
        "_(When you haven't been active for 30+ minutes, anyone who messages "
        "your connected accounts will receive this auto-reply)_"
    )
    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN, reply_markup=auto_reply_kb(enabled)
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
        reply_msg = settings.get(
            "auto_reply_message",
            "Main abhi available nahi hoon. Thodi der baad message karein."
        )
        for phone, session_string in accounts:
            try:
                await tm.setup_auto_reply(
                    user_id=user.id,
                    phone=phone,
                    session_string=session_string,
                    reply_message=reply_msg,
                    bot=context.bot,
                    get_last_active_fn=db.get_user_last_active,
                )
            except Exception as e:
                logger.error(f"Auto reply setup error for {phone}: {e}")
    else:
        await tm.teardown_all_auto_reply(user.id)

    updated = await db.get_settings(user.id) or {}
    enabled = updated.get("auto_reply_enabled", False)
    msg = updated.get("auto_reply_message", "")
    text = (
        f"💬 *Auto Reply Settings*\n\n"
        f"*Status:* {'🟢 ON' if enabled else '🔴 OFF'}\n\n"
        f"*Current Reply Message:*\n_{msg}_"
    )
    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN, reply_markup=auto_reply_kb(enabled)
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


async def handle_auto_reply_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get(SET_AR_STATE):
        return False
    user = update.effective_user
    new_msg = update.message.text.strip()
    context.user_data.pop(SET_AR_STATE, None)

    await db.set_auto_reply(user.id, None, message=new_msg)
    await db.add_log(user.id, "auto_reply_msg_set", f"Length: {len(new_msg)}")
    await update.message.reply_text(
        f"✅ *Auto Reply Message Updated!*\n\n_{new_msg}_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_kb("auto_reply"),
    )
    return True


def register(app):
    app.add_handler(CallbackQueryHandler(cb_auto_reply, pattern="^auto_reply$"))
    app.add_handler(CallbackQueryHandler(cb_toggle_auto_reply, pattern="^toggle_auto_reply$"))
    app.add_handler(CallbackQueryHandler(cb_set_auto_reply_msg, pattern="^set_auto_reply_msg$"))
