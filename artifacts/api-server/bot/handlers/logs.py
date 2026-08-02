"""
Logs handler: redirect users to the Log Bot instead of showing logs in main bot.
"""
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode

from config import LOG_BOT_USERNAME
from keyboards import back_kb


async def cb_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if LOG_BOT_USERNAME:
        clean = LOG_BOT_USERNAME.lstrip("@")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🟢 📋 Open Log Bot", url=f"https://t.me/{clean}?start=logs")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu")],
        ])
        text = (
            "📋 *Activity Logs*\n\n"
            "╔══════════════════════╗\n"
            "║  🤖 Logs are sent to  ║\n"
            "║   your personal      ║\n"
            "║   *Log Bot* only!     ║\n"
            "╚══════════════════════╝\n\n"
            "Tap the button below to open your Log Bot 👇\n\n"
            "_(All your activity logs, broadcast results,\n"
            "and account events are there)_"
        )
    else:
        kb = back_kb("menu")
        text = (
            "📋 *Activity Logs*\n\n"
            "⚠️ Log Bot not configured.\n\n"
            "Please start the Log Bot to see your activity logs.\n\n"
            "Contact admin to set up your personal log bot."
        )

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb,
    )


def register(app):
    app.add_handler(CallbackQueryHandler(cb_logs, pattern="^logs$"))
