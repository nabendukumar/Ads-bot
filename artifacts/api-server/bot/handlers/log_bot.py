"""
Log Bot handlers — runs as a second bot instance.
Each user /start's the log bot (via deep link) to register their chat.
After that, all their activity logs are sent here privately.
"""
import logging
from telegram import Update, BotCommand
from telegram.ext import ContextTypes, CommandHandler, Application
from telegram.constants import ParseMode

import database as db
import log_sender

logger = logging.getLogger(__name__)

LOG_BOT_GREETING = (
    "╔═══════════════════════════╗\n"
    "║  📋  *Luci Ads Log Bot*   ║\n"
    "╚═══════════════════════════╝\n\n"
    "✨ *Welcome to your personal activity log bot!*\n\n"
    "This bot is your private dashboard for everything happening in your Luci Ads Bot account:\n\n"
    "📡 *Broadcast results* — sent, failed, success rate\n"
    "👤 *Account events* — connected, bio violations\n"
    "🚀 *Ad activity* — start/stop logs, intervals\n"
    "💎 *Subscription events* — plan activations\n"
    "⚠️ *Warnings* — rate limits, errors\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "✅ *Registration complete!*\n"
    "All future logs from your Luci Ads Bot account will appear here automatically.\n\n"
    "💡 _Tip: Pin this bot for quick access to your activity feed._"
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start [user_id] — register the user's chat for personal logs.
    Deep link format: /start logs or /start logs_USERID
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    args = context.args or []

    # Try to extract original user_id from deep link param
    target_user_id = None
    if args:
        param = args[0]
        if param.startswith("logs_"):
            try:
                target_user_id = int(param.replace("logs_", ""))
            except ValueError:
                pass
        elif param == "logs":
            target_user_id = user.id

    if not target_user_id:
        target_user_id = user.id

    # Ensure user exists in DB (create if needed)
    try:
        await db.ensure_user(user.id, user.username, user.first_name)
        await db.set_log_chat_id(target_user_id, chat_id)
        logger.info(f"Log chat registered: user_id={target_user_id} chat_id={chat_id}")
    except Exception as e:
        logger.warning(f"Could not register log chat: {e}")

    await update.message.reply_text(
        LOG_BOT_GREETING,
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Luci Ads Log Bot — Help*\n\n"
        "This bot shows your private activity logs from the main Luci Ads Bot.\n\n"
        "*Commands:*\n"
        "/start — Register & view welcome message\n"
        "/help — Show this help\n"
        "/status — Check your registration status\n\n"
        "All your logs appear here automatically. No action needed!",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = await db.get_log_chat_id(user.id)
    if chat_id:
        await update.message.reply_text(
            f"✅ *Registered!*\n\n"
            f"Your logs are being sent to this chat.\n"
            f"🆔 Your user ID: `{user.id}`",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text(
            "⚠️ *Not registered yet!*\n\nSend /start to register.",
            parse_mode=ParseMode.MARKDOWN,
        )


async def setup_log_bot_commands(bot):
    """Set the log bot's command menu."""
    try:
        await bot.set_my_commands([
            BotCommand("start",  "Register & start receiving logs"),
            BotCommand("help",   "How to use the log bot"),
            BotCommand("status", "Check your registration"),
        ])
        logger.info("Log bot commands set ✅")
    except Exception as e:
        logger.warning(f"Could not set log bot commands: {e}")


def build_log_bot_app(token: str) -> Application:
    """Build and return the log bot Application."""
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    return app
