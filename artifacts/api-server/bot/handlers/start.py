"""
/start, main menu, and forced-join verification.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.constants import ParseMode

import database as db
from config import FORCE_JOIN_GROUP, GREETING
from keyboards import main_menu_kb, join_group_kb, back_kb

logger = logging.getLogger(__name__)


async def _check_join(bot, user_id: int) -> bool:
    if not FORCE_JOIN_GROUP:
        return True
    try:
        member = await bot.get_chat_member(chat_id=FORCE_JOIN_GROUP, user_id=user_id)
        return member.status not in ("left", "kicked", "banned", "restricted")
    except Exception as e:
        logger.warning(f"Could not check group membership for {user_id}: {e}")
        return False


async def _get_invite_link(bot) -> str:
    try:
        chat = await bot.get_chat(FORCE_JOIN_GROUP)
        if chat.invite_link:
            return chat.invite_link
        link = await bot.create_chat_invite_link(FORCE_JOIN_GROUP)
        return link.invite_link
    except Exception:
        return "https://t.me/"


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    user = update.effective_user
    settings = await db.get_settings(user.id) or {}
    accounts = await db.get_accounts(user.id)
    premium = await db.is_premium(user.id)
    expiry = await db.get_premium_expiry(user.id)

    running_icon = "🟢" if settings.get("is_running") else "🔴"
    ar_icon = "🟢" if settings.get("auto_reply_enabled") else "🔴"
    crown = "👑 Premium" if premium else "Free"
    expiry_line = f"\n👑 *Premium:* Expires {expiry.strftime('%d %b %Y')}" if expiry else ""

    status_line = (
        f"📊 *Accounts:* {len(accounts)}\n"
        f"📢 *Ad Message:* {'✅' if settings.get('ad_message') else '❌ Not Set'}\n"
        f"⏰ *Interval:* {settings.get('interval_minutes', 60)} min\n"
        f"{running_icon} *Ads Running:* {'Yes ✅' if settings.get('is_running') else 'No ❌'}\n"
        f"{ar_icon} *Auto Reply:* {'On ✅' if settings.get('auto_reply_enabled') else 'Off ❌'}\n"
        f"💎 *Plan:* {crown}{expiry_line}"
    )

    text = f"{GREETING}\n\n{status_line}"

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb(premium)
        )
    else:
        msg = update.message or update.callback_query.message
        await msg.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb(premium))


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.ensure_user(user.id, user.username, user.first_name)
    await db.touch_user(user.id)

    if FORCE_JOIN_GROUP:
        joined = await _check_join(context.bot, user.id)
        if not joined:
            invite = await _get_invite_link(context.bot)
            await update.message.reply_text(
                "👋 *You need to join our group before using this bot!*\n\n"
                "Click the button below to join, then press '✅ I've Joined'.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=join_group_kb(invite),
            )
            return

    await show_main_menu(update, context)


async def cb_check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    await db.ensure_user(user.id, user.username, user.first_name)

    joined = await _check_join(context.bot, user.id)
    if not joined:
        invite = await _get_invite_link(context.bot)
        await query.edit_message_text(
            "❌ *You haven't joined the group yet!*\n\nPlease join and then check again.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=join_group_kb(invite),
        )
        return

    await db.touch_user(user.id)
    await show_main_menu(update, context, edit=True)


async def cb_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    await db.touch_user(user.id)

    if FORCE_JOIN_GROUP:
        joined = await _check_join(context.bot, user.id)
        if not joined:
            invite = await _get_invite_link(context.bot)
            await query.edit_message_text(
                "❌ You need to join the group to use this bot.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=join_group_kb(invite),
            )
            return

    await show_main_menu(update, context, edit=True)


def register(app):
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(cb_check_join, pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(cb_menu, pattern="^menu$"))
