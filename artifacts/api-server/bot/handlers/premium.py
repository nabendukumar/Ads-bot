"""
Premium features — locked behind subscription:
  📊 Stats Dashboard     — detailed groups/channels/broadcast stats
  ⚡ Smart Delay         — custom per-group message delay
  📡 Broadcast Now       — one-time instant broadcast
  🚫 Remove Groups       — exclude specific groups
  🔄 Account Rotation    — distribute groups across accounts
  💎 Message Signature   — custom footer appended to every ad
  🌙 Active Hours        — only send between set hours
  📅 Scheduled Broadcast — set a daily one-time send time
  🎯 Target Filter       — groups only / channels only / all
  📈 Ad Analytics        — detailed per-account analytics
"""
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode

import database as db
import telethon_manager as tm
from keyboards import (
    back_kb, back_and_cancel_kb, premium_menu_kb,
    smart_delay_kb, active_hours_kb, lock_premium_kb,
    group_exclude_kb,
)

logger = logging.getLogger(__name__)

# State keys
SET_DELAY_STATE      = "set_smart_delay_waiting"
SET_BLACKLIST_STATE  = "set_blacklist_waiting"
SET_SIGNATURE_STATE  = "set_signature_waiting"
SET_HOURS_STATE      = "set_active_hours_waiting"
SET_SCHEDULE_STATE   = "set_scheduled_time_waiting"
SET_TARGET_STATE     = "set_target_filter_waiting"


def _require_premium_kb():
    return lock_premium_kb()


# ─── Premium Menu ─────────────────────────────────────────────────────────────

async def cb_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    settings = await db.get_settings(user.id) or {}
    is_prem = await db.is_premium(user.id)
    expiry = await db.get_premium_expiry(user.id)

    rotation  = "🟢 ON" if settings.get("rotation_mode") else "🔴 OFF"
    sig       = "🟢 Set" if settings.get("message_signature") else "🔴 Not set"
    hours     = f"{settings.get('active_hours_start',0):02d}:00–{settings.get('active_hours_end',23):02d}:59"
    scheduled = settings.get("scheduled_time") or "—"
    delay     = settings.get("smart_delay_seconds", 3)
    target    = settings.get("target_filter", "all").title()

    crown = "👑 *PREMIUM*" if is_prem else "🆓 *FREE PLAN*"
    exp_line = f"\n📅 Expires: {expiry.strftime('%d %b %Y')}" if expiry else ""

    lock = "" if is_prem else "🔒 "

    await query.edit_message_text(
        f"⭐ *Premium Features*  {crown}{exp_line}\n\n"
        f"⚡ Smart Delay: `{delay}s`\n"
        f"🔄 Account Rotation: {rotation}\n"
        f"💎 Message Signature: {sig}\n"
        f"🌙 Active Hours: `{hours} UTC`\n"
        f"📅 Scheduled: `{scheduled}`\n"
        f"🎯 Target Filter: `{target}`\n\n"
        f"{'🔓 All features unlocked!' if is_prem else f'🔒 {lock}Features need Premium subscription.'}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=premium_menu_kb(is_prem),
    )


# ─── Stats Dashboard ──────────────────────────────────────────────────────────

async def cb_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    stats    = await db.get_stats(user.id)
    accounts = await db.get_accounts(user.id)
    settings = await db.get_settings(user.id) or {}
    groups   = await db.get_group_cache(user.id)
    is_prem  = await db.is_premium(user.id)

    total_sent   = stats.get("total_sent", 0)
    total_failed = stats.get("total_failed", 0)
    total_jobs   = stats.get("total_jobs", 0)
    max_groups   = stats.get("max_groups", 0)
    total        = total_sent + total_failed
    rate         = round(total_sent / total * 100, 1) if total > 0 else 0.0

    bar_filled = int(rate / 10)
    bar = "🟩" * bar_filled + "⬜" * (10 - bar_filled)

    group_count   = sum(1 for g in groups if not g["is_channel"])
    channel_count = sum(1 for g in groups if g["is_channel"])
    excluded_count = sum(1 for g in groups if g.get("excluded"))
    active_count  = len(groups) - excluded_count

    account_lines = ""
    for acc in accounts:
        icon = "🟢" if acc["is_active"] and acc.get("bio_ok", True) else "🔴"
        bio_note = " ⚠️" if not acc.get("bio_ok", True) else ""
        account_lines += f"  {icon} `{acc['label'] or acc['phone']}`{bio_note}\n"

    premium_note = "\n\n_📊 Sync group list via ➕ Add Account for full details_" if not groups else ""

    text = (
        f"📊 *Your Complete Statistics*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 *Accounts:* `{len(accounts)}`\n"
        f"{account_lines}"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏘️ *Groups:* `{group_count}`\n"
        f"📢 *Channels:* `{channel_count}`\n"
        f"🚫 *Excluded:* `{excluded_count}`\n"
        f"✅ *Active targets:* `{active_count}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 *Total Broadcasts:* `{total_jobs}`\n"
        f"✅ *Messages Sent:* `{total_sent}`\n"
        f"❌ *Messages Failed:* `{total_failed}`\n"
        f"🏆 *Max Groups/Run:* `{max_groups}`\n\n"
        f"🎯 *Success Rate:* `{rate}%`\n"
        f"{bar} `{rate}%`\n\n"
        f"⏰ *Interval:* `{settings.get('interval_minutes', 60)} min`\n"
        f"🚀 *Running:* {'🟢 Yes' if settings.get('is_running') else '🔴 No'}\n"
        f"🔄 *Rotation:* {'🟢 On' if settings.get('rotation_mode') else '🔴 Off'}"
        f"{premium_note}"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 📋 Recent Jobs", callback_data="stats_jobs"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="menu")],
    ])

    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb
    )


async def cb_stats_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    jobs = await db.get_recent_jobs(user.id, limit=10)
    if not jobs:
        await query.edit_message_text(
            "📡 *Recent Broadcasts*\n\nNo broadcasts yet.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_kb("stats"),
        )
        return

    lines = ["📡 *Recent Broadcasts (Last 10)*\n"]
    for j in jobs:
        ts = j["ran_at"].strftime("%d/%m %H:%M")
        rate = round(j["sent_count"] / (j["sent_count"] + j["failed_count"]) * 100) if (j["sent_count"] + j["failed_count"]) > 0 else 0
        lines.append(
            f"`{ts}` — `{j['account_phone'][-4:]}`\n"
            f"  ✅ {j['sent_count']} / 🏘 {j['group_count']} ({rate}%)"
        )

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_kb("stats"),
    )


# ─── Smart Delay ─────────────────────────────────────────────────────────────

async def cb_smart_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if not await db.is_premium(user.id):
        await query.edit_message_text(
            "🔒 *Smart Delay is a Premium Feature*\n\nUpgrade to set custom delay between messages.",
            parse_mode=ParseMode.MARKDOWN, reply_markup=_require_premium_kb()
        )
        return

    settings = await db.get_settings(user.id) or {}
    await query.edit_message_text(
        f"⚡ *Smart Delay*\n\n"
        f"Current: `{settings.get('smart_delay_seconds', 3)}s` between each group message.\n\n"
        "Lower = faster (risk of flood ban)\nHigher = safer\n\n"
        "Select delay:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=smart_delay_kb(),
    )


async def cb_delay_preset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    seconds = int(query.data.split("_")[1])
    await db.set_smart_delay(user.id, seconds)
    await db.add_log(user.id, "smart_delay_set", f"{seconds}s")
    await query.edit_message_text(
        f"✅ *Smart Delay set to {seconds}s!*\n\nMessages will be sent with {seconds}s gap.",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("smart_delay")
    )


async def cb_custom_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data[SET_DELAY_STATE] = True
    await query.edit_message_text(
        "✏️ *Custom Delay*\n\nEnter delay in seconds (1–120):\nType /cancel to go back.",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_and_cancel_kb()
    )


async def handle_delay_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get(SET_DELAY_STATE):
        return False
    user = update.effective_user
    text = update.message.text.strip()
    context.user_data.pop(SET_DELAY_STATE, None)
    if not text.isdigit() or not (1 <= int(text) <= 120):
        await update.message.reply_text("❌ Enter a number between 1 and 120.", reply_markup=back_kb("smart_delay"))
        return True
    seconds = int(text)
    await db.set_smart_delay(user.id, seconds)
    await update.message.reply_text(
        f"✅ *Smart Delay: {seconds}s!*", parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium")
    )
    return True


# ─── Account Rotation ────────────────────────────────────────────────────────

async def cb_rotation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if not await db.is_premium(user.id):
        await query.edit_message_text(
            "🔒 *Account Rotation is a Premium Feature*",
            parse_mode=ParseMode.MARKDOWN, reply_markup=_require_premium_kb()
        )
        return

    settings = await db.get_settings(user.id) or {}
    current = settings.get("rotation_mode", False)
    new_val = not current
    await db.set_rotation_mode(user.id, new_val)
    await db.add_log(user.id, "rotation_toggled", "ON" if new_val else "OFF")
    await query.edit_message_text(
        f"🔄 *Account Rotation: {'🟢 ON' if new_val else '🔴 OFF'}*\n\n"
        + ("Groups will be distributed evenly across all accounts.\n_Reduces flood risk!_" if new_val
           else "All accounts will send to all groups."),
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium")
    )


# ─── Message Signature ────────────────────────────────────────────────────────

async def cb_signature(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if not await db.is_premium(user.id):
        await query.edit_message_text(
            "🔒 *Message Signature is a Premium Feature*",
            parse_mode=ParseMode.MARKDOWN, reply_markup=_require_premium_kb()
        )
        return

    settings = await db.get_settings(user.id) or {}
    current = settings.get("message_signature") or "—"
    context.user_data[SET_SIGNATURE_STATE] = True
    await query.edit_message_text(
        f"💎 *Message Signature*\n\n"
        f"Current: _{current}_\n\n"
        "This text is auto-appended to every ad message.\n"
        "Send `clear` to remove. Type /cancel to go back.",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_and_cancel_kb()
    )


async def handle_signature_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get(SET_SIGNATURE_STATE):
        return False
    user = update.effective_user
    text = update.message.text.strip()
    context.user_data.pop(SET_SIGNATURE_STATE, None)
    if text.lower() == "clear":
        await db.set_message_signature(user.id, None)
        await update.message.reply_text("✅ Signature removed.", reply_markup=back_kb("premium"))
    else:
        await db.set_message_signature(user.id, text)
        await update.message.reply_text(
            f"✅ *Signature set:*\n_{text}_",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium")
        )
    return True


# ─── Active Hours ─────────────────────────────────────────────────────────────

async def cb_active_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if not await db.is_premium(user.id):
        await query.edit_message_text(
            "🔒 *Active Hours is a Premium Feature*",
            parse_mode=ParseMode.MARKDOWN, reply_markup=_require_premium_kb()
        )
        return

    settings = await db.get_settings(user.id) or {}
    sh = settings.get("active_hours_start", 0)
    eh = settings.get("active_hours_end", 23)
    now = datetime.utcnow().hour
    context.user_data[SET_HOURS_STATE] = True
    await query.edit_message_text(
        f"🌙 *Active Hours (UTC)*\n\n"
        f"Current: *{sh:02d}:00 — {eh:02d}:59 UTC*\n"
        f"Now: *{now:02d}:xx UTC*\n\n"
        "Bot only sends ads during active hours.\n\n"
        "Send: `START END`  e.g. `8 22`\n"
        "Send `0 23` for all hours. Type /cancel.",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_and_cancel_kb()
    )


async def handle_active_hours_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get(SET_HOURS_STATE):
        return False
    user = update.effective_user
    text = update.message.text.strip()
    context.user_data.pop(SET_HOURS_STATE, None)
    parts = text.split()
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        await update.message.reply_text("❌ Format: `START END` e.g. `8 22`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium"))
        return True
    s, e = int(parts[0]), int(parts[1])
    if not (0 <= s <= 23 and 0 <= e <= 23 and s <= e):
        await update.message.reply_text("❌ Both 0–23 and start ≤ end.", reply_markup=back_kb("premium"))
        return True
    await db.set_active_hours(user.id, s, e)
    await update.message.reply_text(
        f"✅ *Active Hours: {s:02d}:00 — {e:02d}:59 UTC*",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium")
    )
    return True


# ─── Scheduled Broadcast ─────────────────────────────────────────────────────

async def cb_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if not await db.is_premium(user.id):
        await query.edit_message_text(
            "🔒 *Scheduled Broadcast is a Premium Feature*",
            parse_mode=ParseMode.MARKDOWN, reply_markup=_require_premium_kb()
        )
        return

    settings = await db.get_settings(user.id) or {}
    current = settings.get("scheduled_time") or "—"
    context.user_data[SET_SCHEDULE_STATE] = True
    await query.edit_message_text(
        f"📅 *Scheduled Broadcast*\n\nCurrent: `{current}`\n\n"
        "Send daily broadcast time as `HH:MM` (UTC).\nExample: `09:30`\n"
        "Send `off` to disable. Type /cancel.",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_and_cancel_kb()
    )


async def handle_scheduled_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get(SET_SCHEDULE_STATE):
        return False
    user = update.effective_user
    text = update.message.text.strip()
    context.user_data.pop(SET_SCHEDULE_STATE, None)
    if text.lower() == "off":
        await db.set_scheduled_time(user.id, None)
        await update.message.reply_text("✅ Scheduled broadcast disabled.", reply_markup=back_kb("premium"))
        return True
    parts = text.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts) or not (0 <= int(parts[0]) <= 23 and 0 <= int(parts[1]) <= 59):
        await update.message.reply_text("❌ Format: `HH:MM` e.g. `09:30`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium"))
        return True
    await db.set_scheduled_time(user.id, text)
    await update.message.reply_text(
        f"✅ *Scheduled Broadcast: {text} UTC daily*",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium")
    )
    return True


# ─── Broadcast Now ────────────────────────────────────────────────────────────

async def cb_broadcast_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("📡 Starting broadcast...", show_alert=False)
    user = update.effective_user

    if not await db.is_premium(user.id):
        await query.edit_message_text(
            "🔒 *Instant Broadcast is a Premium Feature*",
            parse_mode=ParseMode.MARKDOWN, reply_markup=_require_premium_kb()
        )
        return

    from handlers.ads import run_broadcast
    await run_broadcast(query, context, user)


# ─── Group Blacklist / Remove Groups ─────────────────────────────────────────

async def cb_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if not await db.is_premium(user.id):
        await query.edit_message_text(
            "🔒 *Remove Groups is a Premium Feature*",
            parse_mode=ParseMode.MARKDOWN, reply_markup=_require_premium_kb()
        )
        return

    groups = await db.get_group_cache(user.id)
    if not groups:
        # Try to sync from accounts
        accounts = await db.get_account_sessions(user.id)
        if not accounts:
            await query.edit_message_text(
                "👥 *No accounts connected yet.*\n\nConnect an account first.",
                parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium")
            )
            return

        await query.edit_message_text(
            "🔄 *Syncing your groups...*\n\n_Please wait a moment._",
            parse_mode=ParseMode.MARKDOWN,
        )
        import asyncio
        for phone, session_string in accounts[:2]:  # Sync first 2 accounts
            try:
                dialogs = await tm.get_dialogs(session_string)
                for d in dialogs:
                    await db.upsert_group_cache(
                        user.id, phone, d["group_id"], d["title"],
                        d["is_channel"], d["member_count"]
                    )
            except Exception as e:
                logger.error(f"Group sync error for {phone}: {e}")

        groups = await db.get_group_cache(user.id)
        if not groups:
            await context.bot.send_message(
                chat_id=user.id,
                text="❌ Could not fetch groups. Try again later.",
                reply_markup=back_kb("premium"),
            )
            return

    excluded_count = sum(1 for g in groups if g.get("excluded"))
    text = (
        f"🚫 *Remove Groups from Ads*\n\n"
        f"Total: `{len(groups)}` | Excluded: `{excluded_count}`\n\n"
        "🟢 = Will receive ads\n"
        "🔴 = Excluded from ads\n\n"
        "Tap a group to toggle:"
    )

    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=group_exclude_kb(groups[:40])  # Show max 40
    )


async def cb_toggle_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    group_id = int(query.data.replace("toggle_group_", ""))
    await db.toggle_group_exclude(user.id, group_id)

    groups = await db.get_group_cache(user.id)
    excluded_count = sum(1 for g in groups if g.get("excluded"))
    text = (
        f"🚫 *Remove Groups from Ads*\n\n"
        f"Total: `{len(groups)}` | Excluded: `{excluded_count}`\n\n"
        "🟢 = Will receive ads  |  🔴 = Excluded\n\n"
        "Tap a group to toggle:"
    )
    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=group_exclude_kb(groups[:40])
    )


async def cb_exclude_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    await db.set_all_groups_excluded(user.id, True)
    groups = await db.get_group_cache(user.id)
    await query.edit_message_text(
        f"🔴 *All {len(groups)} groups excluded from ads.*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=group_exclude_kb(groups[:40])
    )


async def cb_include_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    await db.set_all_groups_excluded(user.id, False)
    groups = await db.get_group_cache(user.id)
    await query.edit_message_text(
        f"🟢 *All {len(groups)} groups included in ads.*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=group_exclude_kb(groups[:40])
    )


# ─── Target Filter ────────────────────────────────────────────────────────────

async def cb_target_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if not await db.is_premium(user.id):
        await query.edit_message_text(
            "🔒 *Target Filter is a Premium Feature*",
            parse_mode=ParseMode.MARKDOWN, reply_markup=_require_premium_kb()
        )
        return

    settings = await db.get_settings(user.id) or {}
    current = settings.get("target_filter", "all")
    context.user_data[SET_TARGET_STATE] = True

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{'✅' if current=='all' else '🟢'} All (Groups + Channels)", callback_data="tfilter_all")],
        [InlineKeyboardButton(f"{'✅' if current=='groups' else '🟢'} Groups Only", callback_data="tfilter_groups")],
        [InlineKeyboardButton(f"{'✅' if current=='channels' else '🟢'} Channels Only", callback_data="tfilter_channels")],
        [InlineKeyboardButton("🔙 Back", callback_data="premium")],
    ])
    await query.edit_message_text(
        f"🎯 *Target Filter*\n\nCurrent: `{current}`\n\nSelect who receives your ads:",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb
    )


async def cb_target_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    target = query.data.replace("tfilter_", "")
    await db.set_target_filter(user.id, target)
    await db.add_log(user.id, "target_filter_set", target)
    await query.edit_message_text(
        f"✅ *Target Filter: {target.title()}*\n\nAds will only go to {target}.",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium")
    )


async def handle_target_filter_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return False  # Handled via callbacks


# ─── Ad Analytics ────────────────────────────────────────────────────────────

async def cb_ad_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if not await db.is_premium(user.id):
        await query.edit_message_text(
            "🔒 *Ad Analytics is a Premium Feature*",
            parse_mode=ParseMode.MARKDOWN, reply_markup=_require_premium_kb()
        )
        return

    accounts = await db.get_accounts(user.id)
    jobs = await db.get_recent_jobs(user.id, limit=20)

    per_account = {}
    for j in jobs:
        phone = j["account_phone"]
        if phone not in per_account:
            per_account[phone] = {"sent": 0, "failed": 0, "jobs": 0}
        per_account[phone]["sent"] += j["sent_count"]
        per_account[phone]["failed"] += j["failed_count"]
        per_account[phone]["jobs"] += 1

    lines = ["📈 *Ad Analytics — Per Account*\n"]
    for phone, data in per_account.items():
        total = data["sent"] + data["failed"]
        rate = round(data["sent"] / total * 100) if total > 0 else 0
        bar = "🟩" * int(rate / 10) + "⬜" * (10 - int(rate / 10))
        lines.append(
            f"📱 `...{phone[-4:]}`\n"
            f"  Jobs: {data['jobs']} | ✅ {data['sent']} | ❌ {data['failed']}\n"
            f"  {bar} {rate}%\n"
        )

    if not lines[1:]:
        lines.append("No broadcast data yet.")

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_kb("premium"),
    )


# ─── Group Blacklist text input ───────────────────────────────────────────────

async def handle_blacklist_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get(SET_BLACKLIST_STATE):
        return False
    user = update.effective_user
    text = update.message.text.strip()
    context.user_data.pop(SET_BLACKLIST_STATE, None)

    if text.lower() == "clear":
        await db.set_group_blacklist(user.id, "")
        await update.message.reply_text("✅ *Blacklist cleared!*", parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium"))
        return True

    await db.set_group_blacklist(user.id, text)
    count = len([g for g in text.split(",") if g.strip()])
    await update.message.reply_text(
        f"✅ *{count} group(s) blacklisted!*", parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium")
    )
    return True


def register(app):
    app.add_handler(CallbackQueryHandler(cb_premium,       pattern="^premium$"))
    app.add_handler(CallbackQueryHandler(cb_stats,         pattern="^stats$"))
    app.add_handler(CallbackQueryHandler(cb_stats_jobs,    pattern="^stats_jobs$"))
    app.add_handler(CallbackQueryHandler(cb_smart_delay,   pattern="^smart_delay$"))
    app.add_handler(CallbackQueryHandler(cb_delay_preset,  pattern=r"^delay_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_custom_delay,  pattern="^custom_delay$"))
    app.add_handler(CallbackQueryHandler(cb_rotation,      pattern="^rotation_mode$"))
    app.add_handler(CallbackQueryHandler(cb_signature,     pattern="^msg_signature$"))
    app.add_handler(CallbackQueryHandler(cb_active_hours,  pattern="^active_hours$"))
    app.add_handler(CallbackQueryHandler(cb_schedule,      pattern="^schedule_broadcast$"))
    app.add_handler(CallbackQueryHandler(cb_broadcast_now, pattern="^broadcast_now$"))
    app.add_handler(CallbackQueryHandler(cb_blacklist,     pattern="^group_blacklist$"))
    app.add_handler(CallbackQueryHandler(cb_toggle_group,  pattern=r"^toggle_group_-?\d+$"))
    app.add_handler(CallbackQueryHandler(cb_exclude_all,   pattern="^exclude_all_groups$"))
    app.add_handler(CallbackQueryHandler(cb_include_all,   pattern="^include_all_groups$"))
    app.add_handler(CallbackQueryHandler(cb_target_filter, pattern="^target_filter$"))
    app.add_handler(CallbackQueryHandler(cb_target_select, pattern=r"^tfilter_"))
    app.add_handler(CallbackQueryHandler(cb_ad_analytics,  pattern="^ad_analytics$"))
