"""
Entry point for Luci Ads Bot.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
import warnings
import asyncio
from telegram.ext import Application

warnings.filterwarnings("ignore", message=".*per_message.*", category=UserWarning)

import database as db
import log_sender
from config import BOT_TOKEN, LOG_BOT_TOKEN, LOG_CHAT_ID, BOT_USERNAME_CLEAN
from handlers import start, accounts, ads, logs, auto_reply, premium, buy_premium

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("telethon").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def post_init(application: Application):
    """Initialize DB schema and log bot on startup."""
    try:
        await db.db(db.init_schema)
        logger.info("Database schema initialized ✅")
    except Exception as e:
        logger.error(f"DB init error: {e}")

    log_sender.init_log_bot(LOG_BOT_TOKEN, LOG_CHAT_ID)

    await log_sender.send_log(
        action="bot_started",
        details="Luci Ads Bot is online 🟢",
    )

    # Schedule periodic bio check (every 2 hours)
    application.job_queue.run_repeating(
        _bio_check_job,
        interval=7200,
        first=300,
        name="bio_check",
    )

    # Start health server for Render keep-alive
    try:
        from health import start_health_server
        asyncio.create_task(start_health_server())
        logger.info("Health server started ✅")
    except Exception as e:
        logger.warning(f"Health server not started: {e}")


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
                    # Bio removed — deactivate account
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
                    # Bio restored — reactivate
                    await db.set_account_bio_ok(user_id, phone, True)
                    await db.add_log(user_id, "bio_restored", f"Phone: {phone}")
                    logger.info(f"Bio restored: user {user_id}, phone {phone}")
            except Exception as e:
                logger.warning(f"Bio check error for {phone}: {e}")
    except Exception as e:
        logger.error(f"Bio check job error: {e}")


def main():
    logger.info("🚀 Starting Luci Ads Bot...")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    start.register(app)
    accounts.register(app)
    ads.register(app)
    logs.register(app)
    auto_reply.register(app)
    premium.register(app)
    buy_premium.register(app)

    logger.info("All handlers registered ✅")
    logger.info("Bot polling started 🤖")

    app.run_polling(drop_pending_updates=True, close_loop=False)


if __name__ == "__main__":
    main()
