"""
Entry point for Luci Ads Bot.
Runs two bots concurrently:
  - Main bot  (BOT_TOKEN)   — user-facing features
  - Log bot   (LOG_BOT_TOKEN) — personal activity logs per user
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
import warnings
import asyncio
from telegram import BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes

warnings.filterwarnings("ignore", message=".*per_message.*", category=UserWarning)

import database as db
import log_sender
import telethon_manager as tm
from config import BOT_TOKEN, LOG_BOT_TOKEN, LOG_CHAT_ID, BOT_USERNAME_CLEAN, ADMIN_ID
from handlers import start, accounts, ads, logs, auto_reply, premium, buy_premium
from handlers import admin as admin_handler
from handlers import language as lang_handler
from handlers import log_bot as log_bot_handler

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("telethon").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def _cmd_cancel(update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel any pending text-input flow and return to the main menu."""
    context.user_data.clear()
    from handlers.start import show_main_menu
    await show_main_menu(update, context)


async def post_init(application: Application):
    """Initialize DB schema, log bot, and bot commands on startup."""
    # The bot uses a manually managed Application lifecycle instead of
    # run_polling(), so python-telegram-bot does not invoke post_init for us.
    # Start the listener first so Render can detect the web service port while
    # the database performs its idempotent migrations.
    try:
        from health import start_health_server
        asyncio.create_task(start_health_server())
        logger.info("Health server started ✅")
    except Exception as e:
        logger.warning(f"Health server not started: {e}")

    try:
        await db.db(db.init_schema)
        logger.info("Database schema initialized ✅")
    except Exception as e:
        logger.exception("DB init error")
        raise RuntimeError("Database initialization failed; refusing to start") from e

    # Restore auto-reply listeners after every deploy/restart. The setting is
    # persisted in PostgreSQL, while Telethon clients live only in memory.
    try:
        sessions = await db.get_all_active_sessions()
        restored = 0
        for user_id, phone, session_string in sessions:
            settings = await db.get_settings(user_id) or {}
            if not settings.get("auto_reply_enabled"):
                continue
            try:
                await tm.setup_auto_reply(
                    user_id=user_id,
                    phone=phone,
                    session_string=session_string,
                    reply_message=settings.get("auto_reply_message") or "Main abhi available nahi hoon. Thodi der baad message karein.",
                    inactivity_minutes=int(settings.get("auto_reply_inactive_minutes") or 30),
                    bot=application.bot,
                    get_last_active_fn=db.get_user_last_active,
                    get_auto_reply_settings_fn=db.get_settings,
                )
                restored += 1
            except Exception as e:
                logger.warning(f"Auto-reply restore failed for {phone}: {e}")
        logger.info("Restored %s auto-reply account listener(s)", restored)
    except Exception:
        logger.exception("Auto-reply restore failed")

    log_sender.init_log_bot(LOG_BOT_TOKEN, LOG_CHAT_ID)

    await log_sender.send_admin_log(
        action="bot_started",
        details="Luci Ads Bot is online 🟢",
    )

    # Set bot command menu
    try:
        await application.bot.set_my_commands([
            BotCommand("start",   "🚀 Start the bot & open dashboard"),
            BotCommand("stop",    "⏹️ Stop all running ads"),
            BotCommand("admin",   "🛟 Contact admin support"),
            BotCommand("language","🌐 Change language"),
        ])
        logger.info("Bot commands menu set ✅")
    except Exception as e:
        logger.warning(f"Could not set bot commands: {e}")

    # Schedule periodic bio check (every 2 hours)
    application.job_queue.run_repeating(
        _bio_check_job,
        interval=7200,
        first=300,
        name="bio_check",
    )

async def _bio_check_job(context):
    """Check if bot username still present in all connected accounts' bio/name."""
    import telethon_manager as tm
    logger.info("Running bio check job...")
    try:
        sessions = await db.get_all_active_sessions()
        for user_id, phone, session_string in sessions:
            try:
                has_bio = await tm.check_bio_has_bot(session_string, BOT_USERNAME_CLEAN)
                account_rows = await db.get_accounts(user_id)
                acc = next((a for a in account_rows if a["phone"] == phone), None)
                if not acc:
                    continue

                if not has_bio and acc.get("bio_ok", True):
                    await db.set_account_bio_ok(user_id, phone, False)
                    await log_sender.send_bio_violation(user_id, "", phone)
                    await db.add_log(user_id, "bio_violation", f"Phone: {phone}")
                    logger.warning(f"Bio violation: user {user_id}, phone {phone}")
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=(
                                f"⚠️ *Account Deactivated!*\n\n"
                                f"📱 `{phone}`\n\n"
                                f"Bot username `@{BOT_USERNAME_CLEAN}` was removed from "
                                f"your Telegram name or bio.\n\n"
                                "❌ This account has been *deactivated* for ads.\n\n"
                                "To reactivate:\n"
                                f"1️⃣ Add `@{BOT_USERNAME_CLEAN}` back to your name or bio\n"
                                "2️⃣ Remove and re-add this account in the bot"
                            ),
                            parse_mode="Markdown",
                        )
                    except Exception:
                        pass
                elif has_bio and not acc.get("bio_ok", True):
                    await db.set_account_bio_ok(user_id, phone, True)
                    await db.add_log(user_id, "bio_restored", f"Phone: {phone}")
                    logger.info(f"Bio restored: user {user_id}, phone {phone}")
            except Exception as e:
                logger.warning(f"Bio check error for {phone}: {e}")
    except Exception as e:
        logger.error(f"Bio check job error: {e}")


async def _delete_webhook_safe(bot, label: str):
    """Delete any existing webhook / polling session before we start ours.
    This is the standard fix for the Render rolling-deploy Conflict error:
    the old instance keeps polling for a few seconds while the new one starts.
    Calling delete_webhook terminates Telegram's side of the old session instantly.
    """
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info(f"[{label}] Webhook deleted — exclusive polling claimed ✅")
    except Exception as e:
        logger.warning(f"[{label}] delete_webhook warning (non-fatal): {e}")
    # Brief pause so Telegram propagates the session termination before we poll
    await asyncio.sleep(1)


async def run_main_bot():
    """Build and run the main user-facing bot."""
    logger.info("🚀 Starting Luci Ads Bot (main)...")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Core handlers
    start.register(app)
    accounts.register(app)
    ads.register(app)
    logs.register(app)
    auto_reply.register(app)
    premium.register(app)
    buy_premium.register(app)

    # New handlers
    admin_handler.register(app)
    lang_handler.register(app)

    # /cancel is a command, so it cannot be caught by the regular text
    # dispatcher (which intentionally excludes all commands).
    app.add_handler(CommandHandler("cancel", _cmd_cancel))

    # Centralised text-input dispatcher (must be registered last)
    from telegram.ext import MessageHandler, filters
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        _dispatch_text_handlers,
    ))
    app.add_error_handler(_handle_bot_error)

    logger.info("All handlers registered ✅")

    await app.initialize()
    await post_init(app)

    # ← KEY FIX: kick out any stale polling session before starting ours
    await _delete_webhook_safe(app.bot, "main-bot")

    await app.start()
    await app.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query", "chat_member"],
    )
    logger.info("Main bot polling started 🤖")
    return app


async def run_log_bot():
    """Build and run the personal log bot."""
    if not LOG_BOT_TOKEN:
        logger.warning("LOG_BOT_TOKEN not set — log bot not started.")
        return None

    logger.info("🟢 Starting Luci Ads Log Bot...")
    log_app = log_bot_handler.build_log_bot_app(LOG_BOT_TOKEN)

    # Set log bot commands
    async def _post_init_log_bot(application):
        await log_bot_handler.setup_log_bot_commands(application.bot)

    log_app.post_init = _post_init_log_bot

    await log_app.initialize()

    # ← KEY FIX: kick out any stale polling session before starting ours
    await _delete_webhook_safe(log_app.bot, "log-bot")

    await log_app.start()
    await log_app.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"],
    )
    logger.info("Log bot polling started ✅")
    return log_app


async def _dispatch_text_handlers(update, context):
    """Route every text message to the correct state-based handler.

    Telegram callback buttons and typed messages are different update types.
    Buttons are handled by CallbackQueryHandler, while all typed text comes
    through this one handler.  Keep this dispatcher as the single entry point
    so a message is never swallowed by one of the feature modules.
    """
    try:
        if not update.message or not update.message.text:
            return

        from handlers.accounts import handle_message as handle_account_message

        # Admin input first (checks ADMIN_ID internally)
        if await admin_handler.handle_admin_input(update, context):
            return

        # Account login and all feature text flows (phone → OTP → password,
        # ad-message, auto-reply, premium inputs) are handled in one place.
        if await handle_account_message(update, context):
            return

        # There is no active text prompt. Do not silently drop the user's
        # message: explain how to continue and show the main menu again.
        logger.info(
            "Unmatched text message from user_id=%s; showing main menu",
            update.effective_user.id if update.effective_user else "unknown",
        )
        from handlers.start import show_main_menu
        await show_main_menu(update, context)
    except Exception:
        # A failed database/API call must be visible in logs and to the user;
        # otherwise the bot appears dead even though polling is still alive.
        logger.exception(
            "Text message handler failed for user_id=%s",
            update.effective_user.id if update.effective_user else "unknown",
        )
        if update.message:
            await update.message.reply_text(
                "❌ Message process nahi ho saka. Please dobara try karein ya /cancel bhejein."
            )


async def _handle_bot_error(update, context: ContextTypes.DEFAULT_TYPE):
    """Log uncaught handler errors instead of silently swallowing them."""
    logger.error(
        "Unhandled Telegram update error: %s",
        context.error,
        exc_info=(type(context.error), context.error, context.error.__traceback__)
        if context.error else None,
    )


def main():
    """Run both bots concurrently in the same event loop."""
    async def _run_all():
        main_app = await run_main_bot()
        log_app = await run_log_bot()

        try:
            # Keep running until interrupted
            await asyncio.Event().wait()
        finally:
            await main_app.updater.stop()
            await main_app.stop()
            await main_app.shutdown()
            if log_app:
                await log_app.updater.stop()
                await log_app.stop()
                await log_app.shutdown()

    asyncio.run(_run_all())


if __name__ == "__main__":
    main()
