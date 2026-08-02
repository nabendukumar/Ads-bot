"""
Account management: Add, List, Delete Telegram accounts via phone login.
Features:
  - Account limit: 2 free, premium for more
  - Resend OTP button
  - Bio/name update after connect
  - Account deactivation if bot username removed from bio
"""
import asyncio
import logging
from telegram import Update
from telegram.ext import (
    ContextTypes, CallbackQueryHandler, MessageHandler, filters, CommandHandler
)
from telegram.constants import ParseMode

import database as db
import telethon_manager as tm
import log_sender
from config import BOT_USERNAME, BOT_USERNAME_CLEAN, MIN_ACCOUNTS, FREE_ACCOUNT_LIMIT, PREMIUM_ACCOUNT_LIMIT
from keyboards import accounts_list_kb, delete_accounts_kb, back_kb, otp_kb, upgrade_needed_kb

logger = logging.getLogger(__name__)

STATE = "login_state"
PHONE_KEY = "login_phone"

S_PHONE = "PHONE"
S_OTP = "OTP"
S_PASSWORD = "PASSWORD"


def _clear_state(context):
    context.user_data.pop(STATE, None)
    context.user_data.pop(PHONE_KEY, None)


# ─── My Accounts ─────────────────────────────────────────────────────────────

async def cb_my_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    accounts = await db.get_accounts(user.id)
    premium = await db.is_premium(user.id)
    limit = PREMIUM_ACCOUNT_LIMIT if premium else FREE_ACCOUNT_LIMIT

    if not accounts:
        text = (
            "👥 *My Accounts*\n\n"
            "No accounts connected yet.\n\n"
            f"📌 You can connect up to *{limit} accounts* {'(Premium)' if premium else '(Free)'}.\n\n"
            "Use ➕ *Add Account* to connect one."
        )
    else:
        lines = [f"👥 *Connected Accounts ({len(accounts)}/{limit})*\n"]
        for i, acc in enumerate(accounts, 1):
            icon = "🟢" if acc["is_active"] and acc.get("bio_ok", True) else "🔴"
            bio_note = " ⚠️ Bio removed" if not acc.get("bio_ok", True) else ""
            lines.append(f"{i}. {icon} `{acc['label'] or acc['phone']}`{bio_note}")
        text = "\n".join(lines)
        if not premium and len(accounts) >= FREE_ACCOUNT_LIMIT:
            text += f"\n\n⚠️ Free limit reached ({FREE_ACCOUNT_LIMIT} accounts). Upgrade to Premium for more!"

    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN, reply_markup=accounts_list_kb()
    )


# ─── Add Account ─────────────────────────────────────────────────────────────

async def cb_add_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    # Check account limit
    count = await db.count_accounts(user.id)
    premium = await db.is_premium(user.id)
    limit = PREMIUM_ACCOUNT_LIMIT if premium else FREE_ACCOUNT_LIMIT

    if count >= limit:
        if not premium:
            await query.edit_message_text(
                f"🔒 *Account Limit Reached!*\n\n"
                f"Free plan allows only *{FREE_ACCOUNT_LIMIT} accounts*.\n\n"
                f"💎 *Upgrade to Premium* to connect up to {PREMIUM_ACCOUNT_LIMIT} accounts!\n\n"
                f"Premium also unlocks Smart Delay, Rotation, Signature, and more!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=upgrade_needed_kb(),
            )
        else:
            await query.edit_message_text(
                f"🔒 *Account Limit Reached!*\n\n"
                f"Premium plan allows up to *{PREMIUM_ACCOUNT_LIMIT} accounts*.\n\n"
                f"You already have {count} accounts connected.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_kb("menu"),
            )
        return

    _clear_state(context)
    context.user_data[STATE] = S_PHONE

    await query.edit_message_text(
        "➕ *Add Account*\n\n"
        "Enter your phone number in international format:\n"
        "Example: `+919876543210`\n\n"
        "Type /cancel to go back.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_kb("menu"),
    )


# ─── Resend OTP ───────────────────────────────────────────────────────────────

async def cb_resend_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🔄 Resending OTP...", show_alert=False)
    user = update.effective_user

    phone = context.user_data.get(PHONE_KEY)
    if not phone:
        await query.edit_message_text(
            "❌ Session expired. Please start account addition again.",
            reply_markup=back_kb("menu"),
        )
        return

    result = await tm.resend_otp(user.id, phone)
    if not result["ok"]:
        await query.edit_message_text(
            f"❌ *Failed to resend OTP:*\n{result['error']}\n\n"
            "Please try again or type /cancel.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=otp_kb(),
        )
        return

    context.user_data[STATE] = S_OTP
    await query.edit_message_text(
        f"✅ *OTP Resent to* `{phone}`!\n\n"
        "📱 Check your Telegram app for the new code.\n\n"
        "⚠️ *Enter code with dashes:*\n"
        "Format: `1-2-3-4-5`\n\n"
        "Type /cancel to abort.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=otp_kb(),
    )


# ─── Message handlers ─────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from handlers.ads import handle_ad_message
    from handlers.auto_reply import handle_auto_reply_message
    from handlers.premium import (
        handle_delay_input, handle_blacklist_input, handle_signature_input,
        handle_active_hours_input, handle_scheduled_time_input, handle_target_filter_input
    )

    state = context.user_data.get(STATE)
    if state == S_PHONE:
        await _handle_phone(update, context)
        return True
    elif state == S_OTP:
        await _handle_otp(update, context)
        return True
    elif state == S_PASSWORD:
        await _handle_password(update, context)
        return True

    if await handle_ad_message(update, context):
        return True
    if await handle_auto_reply_message(update, context):
        return True
    if await handle_delay_input(update, context):
        return True
    if await handle_blacklist_input(update, context):
        return True
    if await handle_signature_input(update, context):
        return True
    if await handle_active_hours_input(update, context):
        return True
    if await handle_scheduled_time_input(update, context):
        return True
    if await handle_target_filter_input(update, context):
        return True

    # Returning a boolean is important because main.py uses this function as
    # the single dispatcher for all state-based text input.  Without an
    # explicit True, the same message can be processed a second time or
    # silently fall through with no response.
    return False


async def _handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    user = update.effective_user

    if not phone.startswith("+") or not phone[1:].isdigit() or len(phone) < 8:
        await update.message.reply_text(
            "❌ *Invalid phone number!*\n"
            "Use international format. Example: `+919876543210`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    msg = await update.message.reply_text("⏳ Sending OTP...")
    result = await tm.create_login_client(user.id, phone)

    if not result["ok"]:
        _clear_state(context)
        await msg.edit_text(
            f"❌ *Error:* {result['error']}\n\nPlease try again.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_kb("menu"),
        )
        return

    context.user_data[PHONE_KEY] = phone
    context.user_data[STATE] = S_OTP

    await msg.edit_text(
        f"✅ *OTP sent to* `{phone}`!\n\n"
        "📱 Open your Telegram app — you'll see a login code.\n\n"
        "⚠️ *Enter code with dashes:*\n"
        "Format: `1-2-3-4-5`\n\n"
        "_(Dashes prevent Telegram from blocking the message)_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=otp_kb(),
    )


async def _save_account(user, phone, session_string, msg, label_suffix="", bot=None):
    await db.ensure_user(user.id, user.username, user.first_name)
    await db.add_account(user.id, phone, session_string, label=phone)
    await db.add_log(user.id, "account_added", f"Phone: {phone}{label_suffix}")

    if bot:
        settings = await db.get_settings(user.id) or {}
        if settings.get("auto_reply_enabled"):
            try:
                await tm.setup_auto_reply(
                    user_id=user.id,
                    phone=phone,
                    session_string=session_string,
                    reply_message=settings.get("auto_reply_message") or "Main abhi available nahi hoon. Thodi der baad message karein.",
                    inactivity_minutes=int(settings.get("auto_reply_inactive_minutes") or 30),
                    bot=bot,
                    get_last_active_fn=db.get_user_last_active,
                    get_auto_reply_settings_fn=db.get_settings,
                )
            except Exception as e:
                logger.warning(f"Auto-reply setup failed for new account {phone}: {e}")

    accounts = await db.get_accounts(user.id)
    premium = await db.is_premium(user.id)
    limit = PREMIUM_ACCOUNT_LIMIT if premium else FREE_ACCOUNT_LIMIT

    await msg.edit_text(
        f"✅ *Account Connected!*\n\n"
        f"╔══════════════════════╗\n"
        f"║  🎉 SUCCESS!          ║\n"
        f"╚══════════════════════╝\n\n"
        f"📱 Phone: `{phone}`\n"
        f"👥 Accounts: {len(accounts)}/{limit}\n\n"
        f"🔄 _Adding bot username to your name & bio..._\n\n"
        "🚀 Start broadcasting from the menu!",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_kb("menu"),
    )

    # Background: update bio + notify log bot
    asyncio.create_task(_post_connect_tasks(user, phone, session_string))


async def _post_connect_tasks(user, phone, session_string):
    try:
        await tm.update_profile_after_login(session_string, BOT_USERNAME)
    except Exception as e:
        logger.warning(f"Profile update failed for {phone}: {e}")
    try:
        await log_sender.send_account_connected(user.id, user.username or "", phone)
    except Exception as e:
        logger.warning(f"Log send failed: {e}")


async def _handle_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    otp = raw.replace("-", "").replace(" ", "").replace(".", "")
    user = update.effective_user

    if not otp.isdigit() or len(otp) < 4:
        await update.message.reply_text(
            "❌ Enter numbers only.\nFormat: `1-2-3-4-5`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=otp_kb(),
        )
        return

    msg = await update.message.reply_text("⏳ Verifying OTP...")
    result = await tm.submit_otp(user.id, otp)

    if not result["ok"]:
        await msg.edit_text(
            f"❌ *Error:* {result['error']}\n\n"
            "Enter the OTP again or tap 🔄 Resend OTP.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=otp_kb(),
        )
        return

    if result.get("needs_2fa"):
        context.user_data[STATE] = S_PASSWORD
        await msg.edit_text(
            "🔒 *2FA Required*\n\n"
            "Enter your *2FA password*:\n\n"
            "Type /cancel to abort.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    phone = context.user_data.get(PHONE_KEY, "unknown")
    _clear_state(context)
    await _save_account(user, phone, result["session"], msg, bot=context.bot)


async def _handle_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    user = update.effective_user

    msg = await update.message.reply_text("⏳ Verifying 2FA password...")
    result = await tm.submit_password(user.id, password)

    if not result["ok"]:
        await msg.edit_text(
            f"❌ *Error:* {result['error']}\n\nPlease try again.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    phone = context.user_data.get(PHONE_KEY, "unknown")
    _clear_state(context)
    await _save_account(user, phone, result["session"], msg, " (2FA)", context.bot)


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get(STATE):
        user = update.effective_user
        await tm.cancel_login(user.id)
        _clear_state(context)
        await update.message.reply_text(
            "❌ Cancelled. Press /start to see the menu.",
            reply_markup=back_kb("menu"),
        )
        return

    # The accounts module owns the shared /cancel handler, so also clear the
    # auto-reply input states here instead of leaving those prompts active.
    from handlers.auto_reply import SET_AR_STATE, SET_AR_TIME_STATE
    if context.user_data.pop(SET_AR_STATE, None) or context.user_data.pop(SET_AR_TIME_STATE, None):
        await update.message.reply_text(
            "❌ Cancelled.",
            reply_markup=back_kb("auto_reply"),
        )


# ─── Delete Account ───────────────────────────────────────────────────────────

async def cb_delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    accounts = await db.get_accounts(user.id)

    if not accounts:
        await query.edit_message_text(
            "🗑️ *Delete Account*\n\nNo accounts connected.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_kb("menu"),
        )
        return

    await query.edit_message_text(
        "🗑️ *Delete Account*\n\nSelect the account to remove:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=delete_accounts_kb(accounts),
    )


async def cb_del_acc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    account_id = int(query.data.split("_")[-1])

    accounts_before_delete = await db.get_accounts(user.id)
    account_to_delete = next(
        (account for account in accounts_before_delete if account["id"] == account_id),
        None,
    )
    await db.delete_account(user.id, account_id)
    if account_to_delete:
        await tm.teardown_auto_reply(user.id, account_to_delete["phone"])
        await db.add_log(user.id, "account_deleted", f"ID: {account_id}")
        await query.edit_message_text(
            "✅ *Account deleted!*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_kb("menu"),
        )
    else:
        await query.edit_message_text(
            "❌ Account not found.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_kb("menu"),
        )


def register(app):
    app.add_handler(CallbackQueryHandler(cb_my_accounts, pattern="^my_accounts$"))
    app.add_handler(CallbackQueryHandler(cb_add_account, pattern="^add_account$"))
    app.add_handler(CallbackQueryHandler(cb_resend_otp, pattern="^resend_otp$"))
    app.add_handler(CallbackQueryHandler(cb_delete_account, pattern="^delete_account$"))
    app.add_handler(CallbackQueryHandler(cb_del_acc, pattern=r"^del_acc_\d+$"))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    # NOTE: Text MessageHandler is registered centrally in main.py via _dispatch_text_handlers
