"""
/start, main menu, forced-join, ban check, animations, /stop command.
"""
import logging
import asyncio
from telegram import Update, BotCommand
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.constants import ParseMode

import database as db
import log_sender
from config import FORCE_JOIN_GROUP, STRINGS, get_string, LOG_BOT_USERNAME, ADMIN_ID
from keyboards import main_menu_kb, join_group_kb, back_kb

logger = logging.getLogger(__name__)

# ─── Luxury animation sequences ───────────────────────────────────────────────

LOADING_FRAMES = [
    "⚡ *Initializing…*\n▱▱▱▱▱▱▱▱▱▱ `0%`",
    "✨ *Loading your data…*\n▰▰▱▱▱▱▱▱▱▱ `20%`",
    "🌟 *Fetching accounts…*\n▰▰▰▰▱▱▱▱▱▱ `40%`",
    "💎 *Checking premium…*\n▰▰▰▰▰▰▱▱▱▱ `60%`",
    "🚀 *Preparing dashboard…*\n▰▰▰▰▰▰▰▰▱▱ `80%`",
    "🎯 *Almost ready…*\n▰▰▰▰▰▰▰▰▰▰ `100%`",
]

START_ANIM_FRAMES = [
    "✨",
    "✨ 🌟",
    "✨ 🌟 💎",
    "✨ 🌟 💎 👑",
    "✨ 🌟 💎 👑 🚀",
]


async def _animate_loading(msg, frames: list, delay: float = 0.3):
    """Animate through frames by editing the message."""
    for frame in frames:
        try:
            await msg.edit_text(frame, parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(delay)
        except Exception:
            break


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
    lang = await db.get_language(user.id)
    settings = await db.get_settings(user.id) or {}
    accounts = await db.get_accounts(user.id)
    premium = await db.is_premium(user.id)
    expiry = await db.get_premium_expiry(user.id)

    running_icon = "🟢" if settings.get("is_running") else "🔴"
    ar_icon = "🟢" if settings.get("auto_reply_enabled") else "🔴"
    crown = get_string(lang, "plan_premium") if premium else get_string(lang, "plan_free")
    expiry_line = f"\n👑 *Premium:* Expires {expiry.strftime('%d %b %Y')}" if expiry else ""

    status_line = (
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Accounts:* `{len(accounts)}`\n"
        f"📢 *Ad Message:* {'✅' if settings.get('ad_message') else '❌ Not Set'}\n"
        f"⏰ *Interval:* `{settings.get('interval_minutes', 60)} min`\n"
        f"{running_icon} *Ads Running:* {get_string(lang, 'ads_running') if settings.get('is_running') else get_string(lang, 'ads_stopped')}\n"
        f"{ar_icon} *Auto Reply:* {get_string(lang, 'auto_reply_on') if settings.get('auto_reply_enabled') else get_string(lang, 'auto_reply_off')}\n"
        f"💎 *Plan:* {crown}{expiry_line}\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )

    greeting = get_string(lang, "greeting")
    text = f"{greeting}\n\n{status_line}"

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb(premium)
        )
    else:
        msg = update.message or (update.callback_query.message if update.callback_query else None)
        if msg:
            await msg.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb(premium))


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Ensure user exists
    await db.ensure_user(user.id, user.username, user.first_name)
    await db.touch_user(user.id)

    # Ban check
    if await db.is_banned(user.id):
        user_data = await db.get_user(user.id)
        reason = (user_data or {}).get("ban_reason") or "No reason provided"
        await update.message.reply_text(
            f"🚫 *You have been banned from this bot.*\n\n"
            f"Reason: _{reason}_\n\n"
            f"If you believe this is a mistake, please contact the admin.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Force join check
    if FORCE_JOIN_GROUP:
        joined = await _check_join(context.bot, user.id)
        if not joined:
            invite = await _get_invite_link(context.bot)
            await update.message.reply_text(
                "👋 *You need to join our group first!*\n\n"
                "Click the button below to join, then press '✅ I've Joined'.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=join_group_kb(invite),
            )
            return

    # Luxury loading animation
    anim_msg = await update.message.reply_text(
        START_ANIM_FRAMES[0], parse_mode=ParseMode.MARKDOWN
    )
    for frame in START_ANIM_FRAMES[1:]:
        await asyncio.sleep(0.25)
        try:
            await anim_msg.edit_text(frame, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass
    await asyncio.sleep(0.25)

    # Delete animation, show loading progress
    try:
        await anim_msg.edit_text(LOADING_FRAMES[0], parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.2)
        await anim_msg.edit_text(LOADING_FRAMES[1], parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.2)
        await anim_msg.edit_text(LOADING_FRAMES[2], parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.2)
        await anim_msg.edit_text(LOADING_FRAMES[3], parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.2)
        await anim_msg.edit_text(LOADING_FRAMES[4], parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.2)
        await anim_msg.edit_text(LOADING_FRAMES[5], parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.3)
    except Exception:
        pass

    # Check if new user for welcome log
    try:
        logs_count = await db.count_logs(user.id)
        if logs_count == 0:
            await log_sender.send_new_user(user.id, user.username or "", user.first_name or "")
    except Exception:
        pass

    # Delete animation message and show main menu
    try:
        await anim_msg.delete()
    except Exception:
        pass

    await show_main_menu(update, context)


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick /stop to stop ads without going through menu."""
    user = update.effective_user
    settings = await db.get_settings(user.id) or {}

    if not settings.get("is_running"):
        await update.message.reply_text(
            "⚠️ *Ads are already stopped.*",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("menu")
        )
        return

    await db.set_running(user.id, False)
    await db.add_log(user.id, "ads_stopped", "/stop command")
    await log_sender.send_ads_stopped(user.id, user.username or "")

    for job in context.application.job_queue.get_jobs_by_name(f"ads_{user.id}"):
        job.schedule_removal()

    await update.message.reply_text(
        "🔴 *Ads Stopped.*\n\n"
        "No more messages will be sent.\n"
        "Use /start to go back to the menu.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_admin_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Connect user to admin support."""
    user = update.effective_user
    await db.add_log(user.id, "admin_support_request", "User requested admin support")
    await update.message.reply_text(
        "🛟 *Admin Support*\n\n"
        "Your support request has been noted.\n\n"
        "📩 To contact the admin directly, please use the Telegram username set by the bot owner.\n\n"
        "_Response may take a few hours._",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_kb("menu"),
    )
    # Notify admin
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🛟 *Support Request*\n\n"
                f"👤 User: `{user.first_name}` (@{user.username or 'none'})\n"
                f"🆔 ID: `{user.id}`"
            ),
            parse_mode="Markdown",
        )
    except Exception:
        pass


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

    # Ban check on menu nav too
    if await db.is_banned(user.id):
        await query.edit_message_text(
            "🚫 *You have been banned from this bot.*",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

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


async def cb_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """No-op callback for pagination page labels."""
    await update.callback_query.answer()


async def setup_bot_commands(bot):
    """Set the bot's command menu (appears in Telegram's ☰ menu)."""
    try:
        commands = [
            BotCommand("start",   "🚀 Start the bot & open dashboard"),
            BotCommand("stop",    "⏹️ Stop all running ads"),
            BotCommand("admin",   "🛟 Contact admin support"),
            BotCommand("language","🌐 Change language"),
        ]
        await bot.set_my_commands(commands)
        logger.info("Bot commands set ✅")
    except Exception as e:
        logger.warning(f"Could not set bot commands: {e}")


def register(app):
    from telegram.ext import filters as tg_filters
    # /admin for non-admin users → support request; admin /admin → admin panel (registered in admin.py)
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("stop",   cmd_stop))
    app.add_handler(CommandHandler("admin",  cmd_admin_support,
                                   filters=tg_filters.TEXT & ~tg_filters.User(user_id=ADMIN_ID)))
    app.add_handler(CallbackQueryHandler(cb_check_join, pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(cb_menu,       pattern="^menu$"))
    app.add_handler(CallbackQueryHandler(cb_noop,       pattern="^noop$"))
