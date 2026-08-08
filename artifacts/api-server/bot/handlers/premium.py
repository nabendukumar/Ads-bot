"""
Premium features — locked behind subscription.
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
    group_exclude_kb, channel_exclude_kb,
)

logger = logging.getLogger(__name__)

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
        f"╔════════════════════════╗\n"
        f"║  ⭐  *PREMIUM FEATURES* ║\n"
        f"╚════════════════════════╝\n\n"
        f"{crown}{exp_line}\n\n"
        f"⚡ Smart Delay: `{delay}s`\n"
        f"🔄 Account Rotation: {rotation}\n"
        f"💎 Signature: {sig}\n"
        f"🌙 Active Hours: `{hours} UTC`\n"
        f"📅 Scheduled: `{scheduled}`\n"
        f"🎯 Target Filter: `{target}`\n\n"
        f"{'✨ All features unlocked!' if is_prem else f'🔒 Upgrade to unlock all features.'}",
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

    text = (
        f"📊 *Complete Statistics*\n"
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
        f"✅ *Sent:* `{total_sent}`\n"
        f"❌ *Failed:* `{total_failed}`\n"
        f"🏆 *Max Groups/Run:* `{max_groups}`\n\n"
        f"🎯 *Success Rate:* `{rate}%`\n"
        f"{bar} `{rate}%`\n\n"
        f"⏰ *Interval:* `{settings.get('interval_minutes', 60)} min`\n"
        f"🚀 *Running:* {'🟢 Yes' if settings.get('is_running') else '🔴 No'}"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📡 Recent Jobs", callback_data="stats_jobs", style="primary")],
        [InlineKeyboardButton("🔙 Back", callback_data="menu", style="primary")],
    ])
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


async def cb_stats_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    jobs = await db.get_recent_jobs(user.id, limit=10)
    if not jobs:
        await query.edit_message_text(
            "📡 *Recent Broadcasts*\n\nNo broadcasts yet.",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("stats"),
        )
        return

    lines = ["📡 *Recent Broadcasts (Last 10)*\n"]
    for j in jobs:
        ts = j["ran_at"].strftime("%d/%m %H:%M")
        rate = round(j["sent_count"] / (j["sent_count"] + j["failed_count"]) * 100) \
               if (j["sent_count"] + j["failed_count"]) > 0 else 0
        lines.append(
            f"`{ts}` — `...{j['account_phone'][-4:]}`\n"
            f"  ✅ {j['sent_count']} / 🏘 {j['group_count']} ({rate}%)"
        )

    await query.edit_message_text(
        "\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("stats"),
    )


# ─── Smart Delay ─────────────────────────────────────────────────────────────

async def cb_smart_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if not await db.is_premium(user.id):
        await query.edit_message_text(
            "🔒 *Smart Delay is a Premium Feature*",
            parse_mode=ParseMode.MARKDOWN, reply_markup=_require_premium_kb()
        )
        return

    settings = await db.get_settings(user.id) or {}
    delay = settings.get("smart_delay_seconds", 3)
    await query.edit_message_text(
        f"⚡ *Smart Delay*\n\nCurrent: `{delay}s`\n\n"
        "Adds a delay between each group message to avoid flood bans.\n\n"
        "Select delay duration:",
        parse_mode=ParseMode.MARKDOWN, reply_markup=smart_delay_kb()
    )


async def cb_delay_preset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    seconds = int(query.data.replace("delay_", ""))
    await db.set_smart_delay(user.id, seconds)
    await db.add_log(user.id, "smart_delay_set", f"{seconds}s")
    await query.edit_message_text(
        f"✅ *Smart Delay set to {seconds} seconds!*",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium")
    )


async def cb_custom_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data[SET_DELAY_STATE] = True
    await query.edit_message_text(
        "⚡ *Custom Delay*\n\nType the delay in seconds (1–120):",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_and_cancel_kb()
    )


async def handle_delay_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get(SET_DELAY_STATE):
        return False
    user = update.effective_user
    text = update.message.text.strip()
    context.user_data.pop(SET_DELAY_STATE, None)
    try:
        seconds = int(text)
        assert 1 <= seconds <= 120
    except Exception:
        await update.message.reply_text("❌ Enter a number between 1 and 120.",
                                        reply_markup=back_kb("premium"))
        return True
    await db.set_smart_delay(user.id, seconds)
    await db.add_log(user.id, "smart_delay_set", f"{seconds}s")
    await update.message.reply_text(
        f"✅ *Smart Delay set to {seconds} seconds!*",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium")
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
        + ("Groups distributed evenly across accounts.\n_Reduces flood risk!_" if new_val
           else "All accounts send to all groups."),
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
        f"💎 *Message Signature*\n\nCurrent: _{current}_\n\n"
        "Auto-appended to every ad. Send `clear` to remove.",
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
        await update.message.reply_text("✅ *Signature cleared!*",
                                        parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium"))
        return True

    await db.set_message_signature(user.id, text)
    await db.add_log(user.id, "signature_set", f"Length: {len(text)}")
    await update.message.reply_text(
        f"✅ *Signature saved!*\n\n_{text}_",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium")
    )
    return True


# ─── Active Hours ────────────────────────────────────────────────────────────

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
    start = settings.get("active_hours_start", 0)
    end = settings.get("active_hours_end", 23)
    await query.edit_message_text(
        f"🌙 *Active Hours*\n\nCurrent: `{start:02d}:00 – {end:02d}:59 UTC`\n\n"
        "Ads only sent during selected hours. Select a preset or type custom:",
        parse_mode=ParseMode.MARKDOWN, reply_markup=active_hours_kb()
    )


async def handle_active_hours_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get(SET_HOURS_STATE):
        return False
    user = update.effective_user
    text = update.message.text.strip()
    context.user_data.pop(SET_HOURS_STATE, None)

    try:
        parts = text.replace("–", "-").split("-")
        start, end = int(parts[0].strip()), int(parts[1].strip())
        assert 0 <= start <= 23 and 0 <= end <= 23
    except Exception:
        await update.message.reply_text(
            "❌ Format: `0-23` or `8-22`", parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_kb("premium")
        )
        return True

    await db.set_active_hours(user.id, start, end)
    await db.add_log(user.id, "active_hours_set", f"{start}-{end}")
    await update.message.reply_text(
        f"✅ *Active Hours set to {start:02d}:00–{end:02d}:59 UTC!*",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium")
    )
    return True


async def cb_hours_preset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    data = query.data.replace("hours_", "")
    try:
        start, end = map(int, data.split("_"))
    except Exception:
        return
    if end == 8:  # night: 22-08 spans midnight
        start, end = 22, 8
    await db.set_active_hours(user.id, start, end)
    await db.add_log(user.id, "active_hours_set", f"{start}-{end}")
    await query.edit_message_text(
        f"✅ *Active Hours: {start:02d}:00–{end:02d}:59 UTC*",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium")
    )


async def cb_custom_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data[SET_HOURS_STATE] = True
    await query.edit_message_text(
        "⏰ *Custom Hours*\n\nType start-end in UTC (e.g., `8-22` or `0-23`):",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_and_cancel_kb()
    )


# ─── Schedule Broadcast ───────────────────────────────────────────────────────

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
        "Type time in UTC (e.g., `08:00` for 8 AM daily). Send `clear` to disable.",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_and_cancel_kb()
    )


async def handle_scheduled_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get(SET_SCHEDULE_STATE):
        return False
    user = update.effective_user
    text = update.message.text.strip()
    context.user_data.pop(SET_SCHEDULE_STATE, None)

    if text.lower() == "clear":
        await db.set_scheduled_time(user.id, None)
        await update.message.reply_text("✅ *Scheduled broadcast disabled!*",
                                        parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium"))
        return True

    try:
        from datetime import datetime as dt
        dt.strptime(text, "%H:%M")
    except ValueError:
        await update.message.reply_text("❌ Format: `HH:MM` (e.g., `08:00`)",
                                        parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium"))
        return True

    await db.set_scheduled_time(user.id, text)
    await db.add_log(user.id, "schedule_set", text)
    await update.message.reply_text(
        f"✅ *Scheduled broadcast set for {text} UTC daily!*",
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


# ─── Remove Groups (with pagination) ─────────────────────────────────────────

async def _load_and_show_groups(query_or_msg, context, user, page=0, is_query=True):
    groups = await db.get_groups_only(user.id)

    if not groups:
        accounts = await db.get_account_sessions(user.id)
        if not accounts:
            text = "👥 *No accounts connected yet.*\nConnect an account first."
            if is_query:
                await query_or_msg.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
                                                      reply_markup=back_kb("premium"))
            else:
                await query_or_msg.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                               reply_markup=back_kb("premium"))
            return

        loading_text = "🔄 *Syncing your groups…*\n\n_Please wait a moment._"
        if is_query:
            await query_or_msg.edit_message_text(loading_text, parse_mode=ParseMode.MARKDOWN)
        else:
            await query_or_msg.reply_text(loading_text, parse_mode=ParseMode.MARKDOWN)

        for phone, session_string in accounts[:3]:
            try:
                dialogs = await tm.get_dialogs(session_string)
                for d in dialogs:
                    await db.upsert_group_cache(user.id, phone, d["group_id"], d["title"],
                                                d["is_channel"], d["member_count"])
            except Exception as e:
                logger.error(f"Group sync error for {phone}: {e}")

        groups = await db.get_groups_only(user.id)

    from config import PAGE_SIZE as PS
    total = len(groups)
    total_pages = max(1, (total + PS - 1) // PS)
    page = max(0, min(page, total_pages - 1))
    excluded_count = sum(1 for g in groups if g.get("excluded"))

    text = (
        f"🚫 *Remove Groups from Ads*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Total: `{total}` | 🚫 Excluded: `{excluded_count}`\n"
        f"📄 Page {page + 1}/{total_pages}\n\n"
        f"✅ = Included in ads\n"
        f"❌ = Excluded from ads\n\n"
        "Tap a group to toggle:"
    )

    if is_query:
        await query_or_msg.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=group_exclude_kb(groups, page)
        )
    else:
        await query_or_msg.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=group_exclude_kb(groups, page)
        )


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

    page = 0
    if "grp_page_" in query.data:
        try:
            page = int(query.data.replace("grp_page_", ""))
        except Exception:
            pass

    await _load_and_show_groups(query, context, user, page=page, is_query=True)


async def cb_group_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    if not await db.is_premium(user.id):
        await query.answer("🔒 Premium required.", show_alert=True)
        return
    page = int(query.data.replace("grp_page_", ""))
    await _load_and_show_groups(query, context, user, page=page, is_query=True)


async def cb_toggle_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    group_id = int(query.data.replace("toggle_group_", ""))
    await db.toggle_group_exclude(user.id, group_id)
    groups = await db.get_groups_only(user.id)
    excluded_count = sum(1 for g in groups if g.get("excluded"))
    from config import PAGE_SIZE as PS
    total = len(groups)
    total_pages = max(1, (total + PS - 1) // PS)
    page = context.user_data.get("grp_current_page", 0)
    page = min(page, total_pages - 1)
    text = (
        f"🚫 *Remove Groups from Ads*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Total: `{total}` | 🚫 Excluded: `{excluded_count}`\n"
        f"📄 Page {page + 1}/{total_pages}\n\n"
        "✅ = Included | ❌ = Excluded\n\nTap to toggle:"
    )
    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=group_exclude_kb(groups, page)
    )


async def cb_exclude_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    await db.exclude_all_groups(user.id)
    groups = await db.get_groups_only(user.id)
    await query.edit_message_text(
        f"🔴 *All {len(groups)} groups excluded from ads.*",
        parse_mode=ParseMode.MARKDOWN, reply_markup=group_exclude_kb(groups, 0)
    )


async def cb_include_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    await db.include_all_groups(user.id)
    groups = await db.get_groups_only(user.id)
    await query.edit_message_text(
        f"🟢 *All {len(groups)} groups included in ads.*",
        parse_mode=ParseMode.MARKDOWN, reply_markup=group_exclude_kb(groups, 0)
    )


# ─── Remove Channels (with pagination) ───────────────────────────────────────

async def _load_and_show_channels(query_or_msg, context, user, page=0, is_query=True):
    channels = await db.get_channels_only(user.id)

    if not channels:
        accounts = await db.get_account_sessions(user.id)
        if not accounts:
            text = "👥 *No accounts connected yet.*\nConnect an account first."
            if is_query:
                await query_or_msg.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
                                                      reply_markup=back_kb("premium"))
            else:
                await query_or_msg.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                               reply_markup=back_kb("premium"))
            return

        loading_text = "🔄 *Syncing your channels…*\n\n_Please wait a moment._"
        if is_query:
            await query_or_msg.edit_message_text(loading_text, parse_mode=ParseMode.MARKDOWN)
        else:
            await query_or_msg.reply_text(loading_text, parse_mode=ParseMode.MARKDOWN)

        for phone, session_string in accounts[:3]:
            try:
                dialogs = await tm.get_dialogs(session_string)
                for d in dialogs:
                    await db.upsert_group_cache(user.id, phone, d["group_id"], d["title"],
                                                d["is_channel"], d["member_count"])
            except Exception as e:
                logger.error(f"Channel sync error for {phone}: {e}")

        channels = await db.get_channels_only(user.id)

    if not channels:
        text = "📢 *No channels found.*\n\nChannels appear after your accounts sync groups."
        if is_query:
            await query_or_msg.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
                                                  reply_markup=back_kb("premium"))
        else:
            await query_or_msg.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                           reply_markup=back_kb("premium"))
        return

    from config import PAGE_SIZE as PS
    total = len(channels)
    total_pages = max(1, (total + PS - 1) // PS)
    page = max(0, min(page, total_pages - 1))
    excluded_count = sum(1 for c in channels if c.get("excluded"))

    text = (
        f"📺 *Remove Channels from Ads*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Total: `{total}` | 🚫 Excluded: `{excluded_count}`\n"
        f"📄 Page {page + 1}/{total_pages}\n\n"
        f"✅ = Included in ads\n"
        f"❌ = Excluded from ads\n\n"
        "Tap a channel to toggle:"
    )

    if is_query:
        await query_or_msg.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=channel_exclude_kb(channels, page)
        )
    else:
        await query_or_msg.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=channel_exclude_kb(channels, page)
        )


async def cb_channel_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if not await db.is_premium(user.id):
        await query.edit_message_text(
            "🔒 *Remove Channels is a Premium Feature*",
            parse_mode=ParseMode.MARKDOWN, reply_markup=_require_premium_kb()
        )
        return

    page = 0
    await _load_and_show_channels(query, context, user, page=page, is_query=True)


async def cb_channel_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    if not await db.is_premium(user.id):
        await query.answer("🔒 Premium required.", show_alert=True)
        return
    page = int(query.data.replace("ch_page_", ""))
    await _load_and_show_channels(query, context, user, page=page, is_query=True)


async def cb_toggle_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    channel_id = int(query.data.replace("toggle_channel_", ""))
    await db.toggle_group_exclude(user.id, channel_id)
    channels = await db.get_channels_only(user.id)
    excluded_count = sum(1 for c in channels if c.get("excluded"))
    from config import PAGE_SIZE as PS
    total = len(channels)
    total_pages = max(1, (total + PS - 1) // PS)
    page = context.user_data.get("ch_current_page", 0)
    page = min(page, total_pages - 1)
    text = (
        f"📺 *Remove Channels from Ads*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Total: `{total}` | 🚫 Excluded: `{excluded_count}`\n"
        f"📄 Page {page + 1}/{total_pages}\n\n"
        "✅ = Included | ❌ = Excluded\n\nTap to toggle:"
    )
    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=channel_exclude_kb(channels, page)
    )


async def cb_exclude_all_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    await db.exclude_all_channels(user.id)
    channels = await db.get_channels_only(user.id)
    await query.edit_message_text(
        f"🔴 *All {len(channels)} channels excluded from ads.*",
        parse_mode=ParseMode.MARKDOWN, reply_markup=channel_exclude_kb(channels, 0)
    )


async def cb_include_all_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    await db.include_all_channels(user.id)
    channels = await db.get_channels_only(user.id)
    await query.edit_message_text(
        f"🟢 *All {len(channels)} channels included in ads.*",
        parse_mode=ParseMode.MARKDOWN, reply_markup=channel_exclude_kb(channels, 0)
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

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{'✅' if current=='all' else '⬜'} All (Groups + Channels)", callback_data="tfilter_all", style="success" if current=='all' else "primary")],
        [InlineKeyboardButton(f"{'✅' if current=='groups' else '⬜'} Groups Only", callback_data="tfilter_groups", style="success" if current=='groups' else "primary")],
        [InlineKeyboardButton(f"{'✅' if current=='channels' else '⬜'} Channels Only", callback_data="tfilter_channels", style="success" if current=='channels' else "primary")],
        [InlineKeyboardButton("🔙 Back", callback_data="premium", style="primary")],
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
        f"✅ *Target: {target.title()}*\n\nAds will go to {target} only.",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium")
    )


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
            f"  {bar} `{rate}%`\n"
        )

    if not per_account:
        lines.append("No broadcast data yet.")

    await query.edit_message_text(
        "\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb("premium"),
    )


def register(app):
    app.add_handler(CallbackQueryHandler(cb_premium,            pattern="^premium$"))
    app.add_handler(CallbackQueryHandler(cb_stats,              pattern="^stats$"))
    app.add_handler(CallbackQueryHandler(cb_stats_jobs,         pattern="^stats_jobs$"))
    app.add_handler(CallbackQueryHandler(cb_smart_delay,        pattern="^smart_delay$"))
    app.add_handler(CallbackQueryHandler(cb_delay_preset,       pattern=r"^delay_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_custom_delay,       pattern="^custom_delay$"))
    app.add_handler(CallbackQueryHandler(cb_rotation,           pattern="^rotation_mode$"))
    app.add_handler(CallbackQueryHandler(cb_signature,          pattern="^msg_signature$"))
    app.add_handler(CallbackQueryHandler(cb_active_hours,       pattern="^active_hours$"))
    app.add_handler(CallbackQueryHandler(cb_hours_preset,       pattern=r"^hours_"))
    app.add_handler(CallbackQueryHandler(cb_custom_hours,       pattern="^custom_hours$"))
    app.add_handler(CallbackQueryHandler(cb_schedule,           pattern="^schedule_broadcast$"))
    app.add_handler(CallbackQueryHandler(cb_broadcast_now,      pattern="^broadcast_now$"))
    # Groups
    app.add_handler(CallbackQueryHandler(cb_blacklist,          pattern="^group_blacklist$"))
    app.add_handler(CallbackQueryHandler(cb_group_page,         pattern=r"^grp_page_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_toggle_group,       pattern=r"^toggle_group_-?\d+$"))
    app.add_handler(CallbackQueryHandler(cb_exclude_all,        pattern="^exclude_all_groups$"))
    app.add_handler(CallbackQueryHandler(cb_include_all,        pattern="^include_all_groups$"))
    # Channels
    app.add_handler(CallbackQueryHandler(cb_channel_blacklist,  pattern="^channel_blacklist$"))
    app.add_handler(CallbackQueryHandler(cb_channel_page,       pattern=r"^ch_page_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_toggle_channel,     pattern=r"^toggle_channel_-?\d+$"))
    app.add_handler(CallbackQueryHandler(cb_exclude_all_channels, pattern="^exclude_all_channels$"))
    app.add_handler(CallbackQueryHandler(cb_include_all_channels, pattern="^include_all_channels$"))
    # Target / Analytics
    app.add_handler(CallbackQueryHandler(cb_target_filter,      pattern="^target_filter$"))
    app.add_handler(CallbackQueryHandler(cb_target_select,      pattern=r"^tfilter_"))
    app.add_handler(CallbackQueryHandler(cb_ad_analytics,       pattern="^ad_analytics$"))
