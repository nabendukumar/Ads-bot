"""
Full admin dashboard — only accessible by ADMIN_ID.
Features:
  👥 View all users (paginated)
  🔍 Find specific user
  🔨 Ban / ✅ Unban users
  💎 Grant / Revoke premium
  📊 Global stats
  📢 Admin broadcast to all users
  📋 View any user's logs
"""
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode

import database as db
import log_sender
from config import ADMIN_ID
from keyboards import (
    admin_main_kb, admin_users_kb, admin_user_actions_kb, back_kb,
    admin_accounts_kb, admin_account_actions_kb, admin_account_groups_kb,
    admin_chats_kb, admin_chat_messages_kb,
)
import telethon_manager

logger = logging.getLogger(__name__)

BROADCAST_STATE  = "admin_broadcast_waiting"
BAN_STATE        = "admin_ban_input_waiting"
UNBAN_STATE      = "admin_unban_input_waiting"
FIND_STATE       = "admin_find_user_waiting"
GRANT_STATE      = "admin_grant_waiting"
REVOKE_STATE     = "admin_revoke_waiting"
BAN_REASON_STATE = "admin_ban_reason_waiting"
BAN_TARGET_STATE = "admin_ban_target_id"


def _is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def _admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not _is_admin(user.id):
            if update.callback_query:
                await update.callback_query.answer("🚫 Admin only!", show_alert=True)
            else:
                await update.message.reply_text("🚫 You are not authorized.")
            return
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper


# ─── /admin command ────────────────────────────────────────────────────────────

@_admin_only
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = await db.get_global_stats()
    text = (
        "╔══════════════════════════╗\n"
        "║  👑  *ADMIN DASHBOARD*   ║\n"
        "╚══════════════════════════╝\n\n"
        f"👥 *Total Users:* `{stats['total_users']}`\n"
        f"🚫 *Banned:* `{stats['banned_users']}`\n"
        f"💎 *Premium:* `{stats['premium_users']}`\n"
        f"🤖 *Running Bots:* `{stats['running_bots']}`\n"
        f"📱 *Total Accounts:* `{stats['total_accounts']}`\n"
        f"📡 *Total Sent:* `{stats['total_sent']:,}`\n\n"
        "Select an action 👇"
    )
    await update.message.reply_text(
        text, parse_mode=ParseMode.MARKDOWN, reply_markup=admin_main_kb()
    )


# ─── Admin panel callback ──────────────────────────────────────────────────────

@_admin_only
async def cb_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    stats = await db.get_global_stats()
    text = (
        "╔══════════════════════════╗\n"
        "║  👑  *ADMIN DASHBOARD*   ║\n"
        "╚══════════════════════════╝\n\n"
        f"👥 *Total Users:* `{stats['total_users']}`\n"
        f"🚫 *Banned:* `{stats['banned_users']}`\n"
        f"💎 *Premium:* `{stats['premium_users']}`\n"
        f"🤖 *Running Bots:* `{stats['running_bots']}`\n"
        f"📱 *Total Accounts:* `{stats['total_accounts']}`\n"
        f"📡 *Total Sent:* `{stats['total_sent']:,}`\n\n"
        "Select an action 👇"
    )
    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN, reply_markup=admin_main_kb()
    )


# ─── Stats ────────────────────────────────────────────────────────────────────

@_admin_only
async def cb_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    stats = await db.get_global_stats()
    from datetime import datetime
    ts = datetime.utcnow().strftime("%d %b %Y %H:%M UTC")
    text = (
        "📊 *Global Statistics*\n"
        f"🕐 As of `{ts}`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 *Users*\n"
        f"  • Total: `{stats['total_users']}`\n"
        f"  • Active (Premium): `{stats['premium_users']}`\n"
        f"  • Banned: `{stats['banned_users']}`\n\n"
        f"🤖 *Bot Activity*\n"
        f"  • Running ad bots: `{stats['running_bots']}`\n"
        f"  • Total accounts: `{stats['total_accounts']}`\n"
        f"  • Messages sent (all time): `{stats['total_sent']:,}`\n"
    )
    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_kb("admin_panel")
    )


# ─── Users list ───────────────────────────────────────────────────────────────

@_admin_only
async def cb_admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.replace("admin_users_pg_", "")) if "pg_" in query.data else 0
    users = await db.get_all_users(limit=200)
    if not users:
        await query.edit_message_text("No users found.", reply_markup=back_kb("admin_panel"))
        return
    text = f"👥 *All Users* ({len(users)} total)\nTap a user to manage:"
    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_users_kb(users, page)
    )


# ─── View individual user ─────────────────────────────────────────────────────

@_admin_only
async def cb_admin_view_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = int(query.data.replace("admin_view_", ""))
    user = await db.get_user(uid)
    if not user:
        await query.answer("User not found.", show_alert=True)
        return

    is_prem = await db.is_premium(uid)
    expiry = await db.get_premium_expiry(uid)
    stats = await db.get_stats(uid)
    accounts = await db.get_accounts(uid)

    banned = "🚫 BANNED" if user.get("is_banned") else "✅ Active"
    plan = "💎 Premium" if is_prem else "Free"
    exp_line = f" (until {expiry.strftime('%d %b %Y')})" if expiry else ""
    ban_reason = f"\n⚠️ Reason: _{user.get('ban_reason') or 'No reason'}_" if user.get("is_banned") else ""

    text = (
        f"👤 *User Profile*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: `{uid}`\n"
        f"📛 Name: {user.get('first_name') or '—'}\n"
        f"🔗 Username: @{user.get('username') or 'none'}\n"
        f"🌐 Language: `{user.get('language', 'en')}`\n"
        f"📅 Joined: {user['joined_at'].strftime('%d %b %Y') if user.get('joined_at') else '—'}\n"
        f"🕐 Last Active: {user['last_active'].strftime('%d %b %Y %H:%M') if user.get('last_active') else '—'}\n\n"
        f"💎 Plan: {plan}{exp_line}\n"
        f"📱 Accounts: {len(accounts)}\n"
        f"📡 Msgs Sent: {stats.get('total_sent', 0):,}\n\n"
        f"Status: {banned}{ban_reason}\n"
    )
    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_user_actions_kb(uid, user.get("is_banned", False), is_prem)
    )


# ─── Ban ──────────────────────────────────────────────────────────────────────

@_admin_only
async def cb_admin_ban_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Check if direct from user view (pattern: admin_ban_USERID)
    parts = query.data.split("_")
    if len(parts) >= 3 and parts[2].lstrip("-").isdigit():
        uid = int(parts[2])
        context.user_data[BAN_TARGET_STATE] = uid
        await query.edit_message_text(
            f"🔨 *Ban User `{uid}`*\n\nSend the ban reason (or 'skip' for no reason):",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("admin_panel")
        )
        context.user_data[BAN_REASON_STATE] = True
    else:
        context.user_data[BAN_STATE] = True
        await query.edit_message_text(
            "🔨 *Ban User*\n\nSend the user ID to ban:",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("admin_panel")
        )


@_admin_only
async def cb_admin_unban_direct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    if len(parts) >= 3 and parts[2].lstrip("-").isdigit():
        uid = int(parts[2])
        await db.unban_user(uid)
        await log_sender.send_admin_action(update.effective_user.id, "unban", uid)
        await query.edit_message_text(
            f"✅ *User `{uid}` has been unbanned.*",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("admin_panel")
        )
        try:
            await context.bot.send_message(
                chat_id=uid,
                text="✅ *Your account has been unbanned.*\n\nYou can now use the bot again.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
    else:
        context.user_data[UNBAN_STATE] = True
        await query.edit_message_text(
            "✅ *Unban User*\n\nSend the user ID to unban:",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("admin_panel")
        )


# ─── Grant / Revoke Premium ───────────────────────────────────────────────────

@_admin_only
async def cb_admin_grant_direct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # pattern: admin_grant_DAYS_USERID
    parts = query.data.replace("admin_grant_", "").split("_")
    if len(parts) == 2:
        days = int(parts[0])
        uid = int(parts[1])
        await db.grant_premium(uid, days)
        await log_sender.send_admin_action(update.effective_user.id, f"grant_premium_{days}d", uid)
        await query.edit_message_text(
            f"💎 *{days}-day Premium granted to `{uid}`!*",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("admin_panel")
        )
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=(
                    f"🎉 *Congratulations!*\n\n"
                    f"👑 You have been granted *{days} days of Premium* by the admin!\n\n"
                    "Enjoy all premium features. Use /start to explore."
                ),
                parse_mode="Markdown"
            )
        except Exception:
            pass
    else:
        context.user_data[GRANT_STATE] = True
        await query.edit_message_text(
            "💎 *Grant Premium*\n\nSend: `USER_ID DAYS` (e.g., `123456789 30`)",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("admin_panel")
        )


@_admin_only
async def cb_admin_revoke_direct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    if len(parts) >= 3 and parts[2].lstrip("-").isdigit():
        uid = int(parts[2])
        await db.revoke_premium(uid)
        await log_sender.send_admin_action(update.effective_user.id, "revoke_premium", uid)
        await query.edit_message_text(
            f"🚫 *Premium revoked for `{uid}`.*",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("admin_panel")
        )
        try:
            await context.bot.send_message(
                chat_id=uid,
                text="⚠️ *Your Premium subscription has been revoked by the admin.*",
                parse_mode="Markdown"
            )
        except Exception:
            pass
    else:
        context.user_data[REVOKE_STATE] = True
        await query.edit_message_text(
            "🚫 *Revoke Premium*\n\nSend the user ID:",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("admin_panel")
        )


# ─── Find user ────────────────────────────────────────────────────────────────

@_admin_only
async def cb_admin_find_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data[FIND_STATE] = True
    await query.edit_message_text(
        "🔍 *Find User*\n\nSend the user ID or username (without @):",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("admin_panel")
    )


# ─── View user logs (admin) ───────────────────────────────────────────────────

@_admin_only
async def cb_admin_view_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = int(query.data.replace("admin_logs_", ""))
    logs = await db.get_logs(uid, limit=15)
    if not logs:
        await query.edit_message_text(
            f"📋 No logs for user `{uid}`.",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("admin_panel")
        )
        return
    lines = [f"📋 *Logs for `{uid}`* (latest 15)\n"]
    for log in logs:
        ts = log["created_at"].strftime("%d/%m %H:%M")
        lines.append(f"`{ts}` — *{log['action']}*\n  _{log.get('details') or '—'}_")
    await query.edit_message_text(
        "\n".join(lines), parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_kb("admin_panel")
    )


# ─── Admin broadcast ──────────────────────────────────────────────────────────

@_admin_only
async def cb_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data[BROADCAST_STATE] = True
    await query.edit_message_text(
        "📢 *Admin Broadcast*\n\nType the message to send to ALL users.\n\n"
        "_Supports Markdown formatting._\n\nType /cancel to abort.",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("admin_panel")
    )


# ─── Text input handler ───────────────────────────────────────────────────────

async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not _is_admin(user.id):
        return False
    text = (update.message.text or "").strip()
    if text.lower() == "/cancel":
        for key in [BROADCAST_STATE, BAN_STATE, UNBAN_STATE, FIND_STATE, GRANT_STATE, REVOKE_STATE, BAN_REASON_STATE]:
            context.user_data.pop(key, None)
        context.user_data.pop(BAN_TARGET_STATE, None)
        await update.message.reply_text("❌ Cancelled.", reply_markup=back_kb("admin_panel"))
        return True

    # Broadcast
    if context.user_data.pop(BROADCAST_STATE, False):
        users = await db.get_all_users(limit=10000)
        sent = failed = 0
        progress_msg = await update.message.reply_text(
            f"📢 Broadcasting to {len(users)} users...\n⏳ Please wait."
        )
        for u in users:
            try:
                await context.bot.send_message(
                    chat_id=u["user_id"], text=text, parse_mode="Markdown"
                )
                sent += 1
            except Exception:
                failed += 1
        await progress_msg.edit_text(
            f"✅ *Broadcast Complete!*\n\n"
            f"✅ Sent: `{sent}` | ❌ Failed: `{failed}`",
            parse_mode="Markdown"
        )
        await log_sender.send_admin_action(user.id, "broadcast", 0, f"Sent:{sent} Failed:{failed}")
        return True

    # Ban reason
    if context.user_data.pop(BAN_REASON_STATE, False):
        uid = context.user_data.pop(BAN_TARGET_STATE, None)
        if uid:
            reason = text if text.lower() != "skip" else ""
            await db.ban_user(uid, reason)
            await log_sender.send_admin_action(user.id, "ban", uid, reason)
            await update.message.reply_text(
                f"🔨 *User `{uid}` has been banned.*",
                parse_mode="Markdown", reply_markup=back_kb("admin_panel")
            )
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"🚫 *You have been banned from this bot.*\n\nReason: _{reason or 'No reason provided'}_",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        return True

    # Ban by ID
    if context.user_data.pop(BAN_STATE, False):
        try:
            uid = int(text)
            context.user_data[BAN_TARGET_STATE] = uid
            context.user_data[BAN_REASON_STATE] = True
            await update.message.reply_text(
                f"Send ban reason for `{uid}` (or 'skip'):",
                parse_mode="Markdown", reply_markup=back_kb("admin_panel")
            )
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.", reply_markup=back_kb("admin_panel"))
        return True

    # Unban by ID
    if context.user_data.pop(UNBAN_STATE, False):
        try:
            uid = int(text)
            await db.unban_user(uid)
            await log_sender.send_admin_action(user.id, "unban", uid)
            await update.message.reply_text(
                f"✅ User `{uid}` unbanned.",
                parse_mode="Markdown", reply_markup=back_kb("admin_panel")
            )
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text="✅ *Your account has been unbanned!*",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.", reply_markup=back_kb("admin_panel"))
        return True

    # Find user
    if context.user_data.pop(FIND_STATE, False):
        try:
            uid = int(text)
        except ValueError:
            uid = None
        found = None
        if uid:
            found = await db.get_user(uid)
        if not found:
            all_users = await db.get_all_users(limit=10000)
            found = next((u for u in all_users if u.get("username", "").lower() == text.lower()), None)
        if not found:
            await update.message.reply_text("❌ User not found.", reply_markup=back_kb("admin_panel"))
        else:
            is_prem = await db.is_premium(found["user_id"])
            expiry = await db.get_premium_expiry(found["user_id"])
            exp_line = f" (until {expiry.strftime('%d %b %Y')})" if expiry else ""
            await update.message.reply_text(
                f"🔍 *Found User*\n\n"
                f"🆔 `{found['user_id']}`\n"
                f"📛 {found.get('first_name') or '—'}\n"
                f"🔗 @{found.get('username') or 'none'}\n"
                f"💎 {'Premium' + exp_line if is_prem else 'Free'}\n"
                f"🚫 {'Banned' if found.get('is_banned') else 'Active'}",
                parse_mode="Markdown",
                reply_markup=admin_user_actions_kb(
                    found["user_id"], found.get("is_banned", False), is_prem
                )
            )
        return True

    # Grant premium
    if context.user_data.pop(GRANT_STATE, False):
        try:
            parts = text.split()
            uid, days = int(parts[0]), int(parts[1])
            await db.grant_premium(uid, days)
            await log_sender.send_admin_action(user.id, f"grant_premium_{days}d", uid)
            await update.message.reply_text(
                f"💎 *{days}-day Premium granted to `{uid}`!*",
                parse_mode="Markdown", reply_markup=back_kb("admin_panel")
            )
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"🎉 *You've been granted {days} days of Premium!*\n\nEnjoy all features.",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        except Exception:
            await update.message.reply_text("❌ Format: USER_ID DAYS", reply_markup=back_kb("admin_panel"))
        return True

    # Revoke premium
    if context.user_data.pop(REVOKE_STATE, False):
        try:
            uid = int(text)
            await db.revoke_premium(uid)
            await log_sender.send_admin_action(user.id, "revoke_premium", uid)
            await update.message.reply_text(
                f"🚫 Premium revoked for `{uid}`.",
                parse_mode="Markdown", reply_markup=back_kb("admin_panel")
            )
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.", reply_markup=back_kb("admin_panel"))
        return True

    # Send message from user's account — store the message text and show groups
    send_state = context.user_data.get("admin_send")
    if send_state and "message" not in send_state:
        send_state["message"] = text
        user_id = send_state["user_id"]
        account_id = send_state["account_id"]

        account = await db.get_account_by_id(account_id)
        if not account:
            context.user_data.pop("admin_send", None)
            await update.message.reply_text(
                "❌ Account not found.",
                reply_markup=back_kb(f"admin_accounts_{user_id}"),
            )
            return True

        dialogs = await telethon_manager.admin_get_account_dialogs(account["session_string"])
        if not dialogs:
            context.user_data.pop("admin_send", None)
            await update.message.reply_text(
                "📭 No groups or channels found for this account.",
                reply_markup=back_kb(f"admin_acc_{user_id}_{account_id}"),
            )
            return True

        await update.message.reply_text(
            "📋 *Select a group to send the message to:*\n\n"
            f"Message preview:\n_{text[:200]}_",
            parse_mode=ParseMode.MARKDOWN,
        )
        await update.message.reply_text(
            f"📋 *Groups & Channels ({len(dialogs)})*\n\nTap a group to send the message.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin_account_groups_kb(user_id, account_id, dialogs),
        )
        return True

    return False


# ─── Admin: View user connected accounts ────────────────────────────────────────

async def cb_admin_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List a user's connected accounts (admin only)."""
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != ADMIN_ID:
        return

    user_id = int(query.data.split("_")[-1])
    accounts = await db.get_accounts(user_id)

    if not accounts:
        await query.edit_message_text(
            "📱 *User Accounts*\n\nThis user has no connected accounts.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_kb(f"admin_view_{user_id}"),
        )
        return

    await query.edit_message_text(
        f"📱 *Connected Accounts ({len(accounts)})*\n\n"
        "Tap an account to view details and access it.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_accounts_kb(user_id, accounts),
    )


async def cb_admin_account_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show actions for a specific user's connected account (admin only)."""
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != ADMIN_ID:
        return

    parts = query.data.split("_")
    user_id = int(parts[-2])
    account_id = int(parts[-1])

    account = await db.get_account_by_id(account_id)
    if not account:
        await query.edit_message_text(
            "❌ Account not found.",
            reply_markup=back_kb(f"admin_accounts_{user_id}"),
        )
        return

    info = await telethon_manager.admin_get_account_info(account["session_string"])
    if info.get("ok"):
        name = f"{info.get('first_name', '')} {info.get('last_name', '')}".strip()
        text = (
            f"📱 *Account Details*\n\n"
            f"👤 *Name:* {name}\n"
            f"📛 *Username:* @{info.get('username', 'none')}\n"
            f"📞 *Phone:* `{account.get('phone', '—')}`\n"
            f"🆔 *Telegram ID:* `{info.get('id', '—')}`\n"
            f"🟢 *Status:* Active"
        )
    else:
        text = (
            f"📱 *Account Details*\n\n"
            f"📞 *Phone:* `{account.get('phone', '—')}`\n"
            f"🔴 *Status:* {info.get('error', 'Inactive')}"
        )

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_account_actions_kb(user_id, account_id, account.get("phone", "")),
    )


async def cb_admin_account_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List groups for a user's connected account (admin only)."""
    query = update.callback_query
    await query.answer("Loading groups…")
    if update.effective_user.id != ADMIN_ID:
        return

    parts = query.data.split("_")
    user_id = int(parts[-2])
    account_id = int(parts[-1])

    account = await db.get_account_by_id(account_id)
    if not account:
        await query.edit_message_text(
            "❌ Account not found.",
            reply_markup=back_kb(f"admin_accounts_{user_id}"),
        )
        return

    dialogs = await telethon_manager.admin_get_account_dialogs(account["session_string"])
    if not dialogs:
        await query.edit_message_text(
            "📭 No groups or channels found for this account.",
            reply_markup=back_kb(f"admin_acc_{user_id}_{account_id}"),
        )
        return

    await query.edit_message_text(
        f"📋 *Groups & Channels ({len(dialogs)})*\n\nTap a group to send a message to it.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_account_groups_kb(user_id, account_id, dialogs),
    )


async def cb_admin_account_grp_pg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pagination for admin account groups view."""
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != ADMIN_ID:
        return

    parts = query.data.split("_")
    page = int(parts[-1])
    account_id = int(parts[-2])
    user_id = int(parts[-3])

    account = await db.get_account_by_id(account_id)
    if not account:
        return

    dialogs = await telethon_manager.admin_get_account_dialogs(account["session_string"])
    await query.edit_message_text(
        f"📋 *Groups & Channels ({len(dialogs)})*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_account_groups_kb(user_id, account_id, dialogs, page),
    )


async def cb_admin_account_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt admin to enter a message to send from a user's account."""
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != ADMIN_ID:
        return

    parts = query.data.split("_")
    user_id = int(parts[-2])
    account_id = int(parts[-1])

    context.user_data["admin_send"] = {"user_id": user_id, "account_id": account_id}
    await query.edit_message_text(
        "📨 *Send Message from User's Account*\n\n"
        "Send me the message text. It will be sent to the group you select next.\n\n"
        "_Use /cancel to abort._",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_kb(f"admin_acc_{user_id}_{account_id}"),
    )


async def cb_admin_account_group_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin tapped a group — send the queued message to it from the user's account."""
    query = update.callback_query
    await query.answer("Sending message…")
    if update.effective_user.id != ADMIN_ID:
        return

    parts = query.data.split("_")
    # admin_grp_{user_id}_{account_id}_{group_id}
    group_id = int(parts[-1])
    account_id = int(parts[-2])
    user_id = int(parts[-3])

    send_state = context.user_data.pop("admin_send", None)
    if not send_state or "message" not in send_state:
        await query.edit_message_text(
            "❌ No message stored. Please start again.",
            reply_markup=back_kb(f"admin_acc_{user_id}_{account_id}"),
        )
        return

    account = await db.get_account_by_id(account_id)
    if not account:
        await query.edit_message_text(
            "❌ Account not found.",
            reply_markup=back_kb(f"admin_accounts_{user_id}"),
        )
        return

    result = await telethon_manager.admin_send_message_to_group(
        account["session_string"], group_id, send_state["message"]
    )
    if result.get("ok"):
        await log_sender.send_admin_action(
            update.effective_user.id, "send_from_account",
            send_state["user_id"], f"Account: {account.get('phone')}, Group: {group_id}"
        )
        await query.edit_message_text(
            "✅ *Message sent successfully!*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_kb(f"admin_acc_{user_id}_{account_id}"),
        )
    else:
        await query.edit_message_text(
            f"❌ *Failed to send message.*\n\nError: {result.get('error', 'Unknown error')}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_kb(f"admin_acc_{user_id}_{account_id}"),
        )


# ─── Admin: Read User Chats ───────────────────────────────────────────────────

async def cb_admin_account_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    # admin_acc_chats_{user_id}_{account_id}  OR  admin_chats_pg_{user_id}_{account_id}_{page}
    if "chats_pg" in query.data:
        user_id = int(parts[4])
        account_id = int(parts[5])
        page = int(parts[6])
    else:
        user_id = int(parts[4])
        account_id = int(parts[5])
        page = 0

    accounts = await db.get_accounts(user_id)
    account = next((a for a in accounts if a["id"] == account_id), None)
    if not account:
        await query.edit_message_text("❌ Account not found.", reply_markup=back_kb(f"admin_accounts_{user_id}"))
        return

    sessions = await db.get_account_sessions(user_id)
    session_string = None
    for phone, sess in sessions:
        if phone == account["phone"]:
            session_string = sess
            break
    if not session_string:
        await query.edit_message_text(
            "❌ No session found for this account.",
            reply_markup=back_kb(f"admin_acc_{user_id}_{account_id}"),
        )
        return

    await query.edit_message_text("🔄 *Loading chats…*", parse_mode=ParseMode.MARKDOWN)
    chats = await tm.admin_get_recent_chats(session_string, limit=30)
    if not chats:
        await query.edit_message_text(
            "💬 *No chats found.*\n\nThe account may not be authorized or has no dialogs.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_kb(f"admin_acc_{user_id}_{account_id}"),
        )
        return

    context.user_data[f"admin_chats_{user_id}_{account_id}"] = chats
    text = (
        f"💬 *User Chats*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 Account: `{account['phone']}`\n"
        f"📋 Total chats: `{len(chats)}`\n\n"
        f"Tap a chat to read messages:"
    )
    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_chats_kb(user_id, account_id, chats, page),
    )


async def cb_admin_chat_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # admin_chat_{user_id}_{account_id}_{chat_id}
    parts = query.data.split("_")
    user_id = int(parts[3])
    account_id = int(parts[4])
    chat_id = int(parts[5])

    accounts = await db.get_accounts(user_id)
    account = next((a for a in accounts if a["id"] == account_id), None)
    if not account:
        await query.edit_message_text("❌ Account not found.", reply_markup=back_kb(f"admin_accounts_{user_id}"))
        return

    sessions = await db.get_account_sessions(user_id)
    session_string = None
    for phone, sess in sessions:
        if phone == account["phone"]:
            session_string = sess
            break
    if not session_string:
        await query.edit_message_text(
            "❌ No session found.",
            reply_markup=back_kb(f"admin_acc_{user_id}_{account_id}"),
        )
        return

    await query.edit_message_text("🔄 *Loading messages…*", parse_mode=ParseMode.MARKDOWN)
    messages = await tm.admin_get_chat_messages(session_string, chat_id, limit=20)

    chats = context.user_data.get(f"admin_chats_{user_id}_{account_id}", [])
    chat_info = next((c for c in chats if c["chat_id"] == chat_id), None)
    chat_name = chat_info["name"] if chat_info else str(chat_id)

    if not messages:
        await query.edit_message_text(
            f"💬 *{chat_name}*\n\nNo messages found.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin_chat_messages_kb(user_id, account_id, chat_id),
        )
        return

    lines = [f"💬 *{chat_name}*\n━━━━━━━━━━━━━━━━━━━━━\n"]
    for m in reversed(messages):
        time_str = m["date"].strftime("%d/%m %H:%M")
        arrow = "➡️" if m["is_outgoing"] else "⬅️"
        lines.append(f"{arrow} `{time_str}` *{m['sender'][:20]}*\n   {m['text'][:100]}\n")

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_chat_messages_kb(user_id, account_id, chat_id),
    )


def register(app):
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CallbackQueryHandler(cb_admin_panel,       pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(cb_admin_stats,       pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(cb_admin_users,       pattern=r"^admin_users(_pg_\d+)?$"))
    app.add_handler(CallbackQueryHandler(cb_admin_view_user,   pattern=r"^admin_view_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_view_logs,   pattern=r"^admin_logs_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_broadcast,   pattern="^admin_broadcast$"))
    app.add_handler(CallbackQueryHandler(cb_admin_find_user,   pattern="^admin_find_user$"))
    app.add_handler(CallbackQueryHandler(cb_admin_ban_prompt,  pattern=r"^admin_ban(_\d+)?$"))
    app.add_handler(CallbackQueryHandler(cb_admin_unban_direct,pattern=r"^admin_unban(_\d+)?$"))
    app.add_handler(CallbackQueryHandler(cb_admin_grant_direct,pattern=r"^admin_grant(_\d+_\d+)?$"))
    app.add_handler(CallbackQueryHandler(cb_admin_revoke_direct,pattern=r"^admin_revoke(_\d+)?$"))
    app.add_handler(CallbackQueryHandler(cb_admin_accounts,     pattern=r"^admin_accounts_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_account_view,  pattern=r"^admin_acc_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_account_groups, pattern=r"^admin_acc_groups_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_account_grp_pg, pattern=r"^admin_acc_grp_pg_\d+_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_account_send,   pattern=r"^admin_acc_send_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_account_group_send, pattern=r"^admin_grp_\d+_\d+_-?\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_account_chats,   pattern=r"^admin_acc_chats_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_account_chats,   pattern=r"^admin_chats_pg_\d+_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_chat_messages,   pattern=r"^admin_chat_\d+_\d+_-?\d+$"))
