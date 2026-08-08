"""
Buy Premium flow:
  - Show price list with UPI payment
  - User claims payment
  - Admin gets notification with Approve/Reject buttons
  - On approve: user gets premium, notification sent
  - On reject: user gets rejection message
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode

import database as db
import log_sender
from config import PREMIUM_PLANS, UPI_ID, ADMIN_ID
from keyboards import buy_premium_kb, payment_confirm_kb, admin_approve_kb, back_kb

logger = logging.getLogger(__name__)

PLAN_MAP = {p[0]: p for p in PREMIUM_PLANS}  # plan_id -> (plan_id, label, days, price)


# ─── Buy Premium Menu ─────────────────────────────────────────────────────────

async def cb_buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    premium = await db.is_premium(user.id)
    expiry = await db.get_premium_expiry(user.id)

    if premium and expiry:
        status_line = f"\n\n👑 *Your premium expires:* {expiry.strftime('%d %b %Y')}"
    else:
        status_line = "\n\n❌ *You are on Free plan*"

    plan_lines = "\n".join([
        f"  💎 *{label}* — ₹{price}"
        for _, label, days, price in PREMIUM_PLANS
    ])

    text = (
        "🛍️ *Buy Premium*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"{plan_lines}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"{status_line}\n\n"
        "✨ *Premium Features:*\n"
        "  🔓 Up to 10 accounts\n"
        "  ⚡ Smart Delay control\n"
        "  🔄 Account Rotation\n"
        "  💎 Message Signature\n"
        "  🌙 Active Hours setting\n"
        "  📅 Scheduled Broadcast\n"
        "  📡 Instant Broadcast\n"
        "  🚫 Remove specific groups\n"
        "  🎯 Group/Channel filter\n"
        "  📈 Detailed Ad Analytics\n\n"
        "Select a plan to proceed 👇"
    )

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=buy_premium_kb(),
    )


# ─── Plan selected → show payment instructions ────────────────────────────────

async def cb_buy_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    plan_id = query.data.replace("buy_plan_", "")
    plan = PLAN_MAP.get(plan_id)
    if not plan:
        await query.answer("❌ Plan not found.", show_alert=True)
        return

    _, label, days, price = plan

    text = (
        f"💳 *Payment Instructions*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💎 *Plan:* {label}\n"
        f"💵 *Amount:* ₹{price}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📲 *Pay via UPI:*\n"
        f"`{UPI_ID}`\n\n"
        f"_(Tap the UPI ID to copy it)_\n\n"
        f"⚠️ *Steps:*\n"
        f"1️⃣ Open any UPI app (GPay, PhonePe, Paytm)\n"
        f"2️⃣ Send ₹{price} to `{UPI_ID}`\n"
        f"3️⃣ Come back here and tap ✅ *I've Paid*\n"
        f"4️⃣ Admin will verify and activate your plan\n\n"
        f"⏳ _Activation may take a few minutes_"
    )

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=payment_confirm_kb(plan_id),
    )


# ─── User claims payment ─────────────────────────────────────────────────────

async def cb_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ Sending verification request...", show_alert=False)
    user = update.effective_user

    plan_id = query.data.replace("paid_", "")
    plan = PLAN_MAP.get(plan_id)
    if not plan:
        await query.answer("❌ Plan not found.", show_alert=True)
        return

    _, label, days, price = plan

    # Save pending subscription
    await db.create_subscription_request(user.id, plan_id, days, price)
    await db.add_log(user.id, "payment_claimed", f"Plan: {label} ₹{price}")

    # Notify admin
    admin_kb = admin_approve_kb(user.id, plan_id)
    await log_sender.send_payment_request(
        user_id=user.id,
        username=user.username or "",
        plan_label=label,
        price=price,
        plan_id=plan_id,
        admin_kb=admin_kb,
    )

    # Also notify admin directly if not same as log chat
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"💰 *PAYMENT REQUEST*\n\n"
                f"👤 User: @{user.username or user.id} (`{user.id}`)\n"
                f"💎 Plan: *{label}*\n"
                f"💵 Amount: *₹{price}*\n\n"
                f"Please verify and approve/reject below."
            ),
            parse_mode="Markdown",
            reply_markup=admin_kb,
        )
    except Exception as e:
        logger.warning(f"Admin direct notify failed: {e}")

    await query.edit_message_text(
        "⏳ *Verification Pending*\n\n"
        "╔══════════════════════╗\n"
        "║  💰 Payment request   ║\n"
        "║   sent to admin!     ║\n"
        "╚══════════════════════╝\n\n"
        "🔄 Please wait while admin verifies your payment.\n\n"
        "⏱️ _You will receive a notification once approved._\n\n"
        "Thank you for your patience! 🙏",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_kb("menu"),
    )


# ─── Admin: Approve ───────────────────────────────────────────────────────────

async def cb_admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    admin = update.effective_user

    if admin.id != ADMIN_ID:
        await query.answer("❌ Not authorized.", show_alert=True)
        return

    parts = query.data.replace("admin_approve_", "").split("_", 1)
    if len(parts) != 2:
        await query.answer("Invalid data.", show_alert=True)
        return

    user_id = int(parts[0])
    plan_id = parts[1]
    plan = PLAN_MAP.get(plan_id)
    if not plan:
        await query.answer("Plan not found.", show_alert=True)
        return

    _, label, days, price = plan
    success = await db.approve_subscription(user_id, plan_id)

    if success:
        await query.edit_message_text(
            f"✅ *APPROVED*\n\n"
            f"👤 User `{user_id}` — {label} premium activated!",
            parse_mode=ParseMode.MARKDOWN,
        )
        # Notify user
        try:
            expiry = await db.get_premium_expiry(user_id)
            exp_str = expiry.strftime('%d %b %Y') if expiry else "—"
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "🎉 *Premium Activated!*\n\n"
                    "╔══════════════════════╗\n"
                    "║  👑 PREMIUM MEMBER!   ║\n"
                    "╚══════════════════════╝\n\n"
                    f"💎 Plan: *{label}*\n"
                    f"📅 Expires: *{exp_str}*\n\n"
                    "✨ All premium features are now unlocked!\n\n"
                    "Tap /start to enjoy your premium features 🚀"
                ),
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.warning(f"User notify failed: {e}")
        await db.add_log(user_id, "premium_approved", f"Plan: {label}")
    else:
        await query.answer("No pending request found.", show_alert=True)


# ─── Admin: Reject ────────────────────────────────────────────────────────────

async def cb_admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    admin = update.effective_user

    if admin.id != ADMIN_ID:
        await query.answer("❌ Not authorized.", show_alert=True)
        return

    parts = query.data.replace("admin_reject_", "").split("_", 1)
    if len(parts) != 2:
        await query.answer("Invalid data.", show_alert=True)
        return

    user_id = int(parts[0])
    plan_id = parts[1]
    plan = PLAN_MAP.get(plan_id)

    label = plan[1] if plan else plan_id
    success = await db.reject_subscription(user_id, plan_id)

    if success:
        await query.edit_message_text(
            f"🔴 *REJECTED*\n\nUser `{user_id}` subscription rejected.",
            parse_mode=ParseMode.MARKDOWN,
        )
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "❌ *Payment Not Verified*\n\n"
                    f"Your premium request for *{label}* was not approved.\n\n"
                    "If you believe this is a mistake, please contact admin.\n\n"
                    "You can try again with /start → 🛍️ Buy Premium."
                ),
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.warning(f"User reject notify failed: {e}")
        await db.add_log(user_id, "premium_rejected", f"Plan: {label}")
    else:
        await query.answer("No pending request found.", show_alert=True)


def register(app):
    app.add_handler(CallbackQueryHandler(cb_buy_premium, pattern="^buy_premium$"))
    app.add_handler(CallbackQueryHandler(cb_buy_plan, pattern=r"^buy_plan_"))
    app.add_handler(CallbackQueryHandler(cb_paid, pattern=r"^paid_"))
    app.add_handler(CallbackQueryHandler(cb_admin_approve, pattern=r"^admin_approve_"))
    app.add_handler(CallbackQueryHandler(cb_admin_reject, pattern=r"^admin_reject_"))
