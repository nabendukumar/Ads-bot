"""
Language selection handler.
Supports: English, Hindi, Chinese, Indonesian.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.constants import ParseMode

import database as db
from config import LANGUAGES, get_string
from keyboards import language_kb, back_kb

logger = logging.getLogger(__name__)


async def cb_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    lang = await db.get_language(user.id)

    text = (
        "🌐 *Select Language / भाषा चुनें / 选择语言 / Pilih Bahasa*\n\n"
        f"Current: *{LANGUAGES.get(lang, 'English')}*\n\n"
        "Choose your preferred language:"
    )
    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=language_kb(lang)
    )


async def cb_set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    lang = query.data.replace("set_lang_", "")

    if lang not in LANGUAGES:
        await query.answer("Unknown language.", show_alert=True)
        return

    await db.set_language(user.id, lang)
    await query.answer(f"✅ Language set to {LANGUAGES[lang]}!", show_alert=False)

    lang_name = LANGUAGES[lang]
    text = (
        f"✅ *Language changed to {lang_name}!*\n\n"
        f"{get_string(lang, 'greeting')}"
    )
    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=language_kb(lang)
    )


async def cmd_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = await db.get_language(user.id)
    text = (
        "🌐 *Select Language / भाषा चुनें / 选择语言 / Pilih Bahasa*\n\n"
        f"Current: *{LANGUAGES.get(lang, 'English')}*\n\n"
        "Choose your preferred language:"
    )
    await update.message.reply_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=language_kb(lang)
    )


def register(app):
    app.add_handler(CommandHandler("language", cmd_language))
    app.add_handler(CallbackQueryHandler(cb_language,     pattern="^language$"))
    app.add_handler(CallbackQueryHandler(cb_set_language, pattern=r"^set_lang_"))
