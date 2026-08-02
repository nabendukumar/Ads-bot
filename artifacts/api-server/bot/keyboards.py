from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import PREMIUM_PLANS, UPI_ID, PAGE_SIZE, LANGUAGES


# ─── Helper ───────────────────────────────────────────────────────────────────

def _btn(text, cbd): return InlineKeyboardButton(text, callback_data=cbd)
def _url_btn(text, url): return InlineKeyboardButton(text, url=url)


# ─── Main Menu ────────────────────────────────────────────────────────────────

def main_menu_kb(is_premium=False):
    crown = "👑 " if is_premium else ""
    rows = [
        [
            _btn("➕ Add Account",    "add_account"),
            _btn("👥 My Accounts",    "my_accounts"),
        ],
        [
            _btn("📝 Set Ad Message", "set_ad_msg"),
            _btn("⏰ Set Interval",   "set_interval"),
        ],
        [
            _btn("▶️ Start Ads",      "start_ads"),
            _btn("⏹️ Stop Ads",       "stop_ads"),
        ],
        [
            _btn("🗑️ Delete Account", "delete_account"),
            _btn("📋 Logs",           "logs"),
        ],
        [
            _btn("💬 Auto Reply",     "auto_reply"),
            _btn(f"{crown}⭐ Premium", "premium"),
        ],
        [
            _btn("🌐 Language",       "language"),
            _btn("🛍️ Buy Premium",    "buy_premium"),
        ],
    ]
    return InlineKeyboardMarkup(rows)


# ─── Back buttons ─────────────────────────────────────────────────────────────

def back_kb(target="menu"):
    return InlineKeyboardMarkup([[_btn("🔙 Back", target)]])


def back_and_cancel_kb():
    return InlineKeyboardMarkup([[_btn("❌ Cancel", "menu")]])


# ─── Join group ───────────────────────────────────────────────────────────────

def join_group_kb(group_link: str):
    return InlineKeyboardMarkup([
        [_url_btn("📢 Join Group", group_link)],
        [_btn("✅ I've Joined", "check_join")],
    ])


# ─── Accounts ────────────────────────────────────────────────────────────────

def delete_accounts_kb(accounts: list):
    buttons = [
        [_btn(f"❌ {acc.get('label') or acc['phone']}", f"del_acc_{acc['id']}")]
        for acc in accounts
    ]
    buttons.append([_btn("🔙 Back", "menu")])
    return InlineKeyboardMarkup(buttons)


def accounts_list_kb():
    return InlineKeyboardMarkup([
        [_btn("➕ Add Account",    "add_account")],
        [_btn("🗑️ Delete Account", "delete_account")],
        [_btn("🔙 Back",              "menu")],
    ])


def otp_kb():
    return InlineKeyboardMarkup([
        [_btn("🔄 Resend OTP", "resend_otp")],
        [_btn("❌ Cancel",     "menu")],
    ])


def upgrade_needed_kb():
    return InlineKeyboardMarkup([
        [_btn("🛍️ Buy Premium", "buy_premium")],
        [_btn("🔙 Back",           "menu")],
    ])


# ─── Interval ─────────────────────────────────────────────────────────────────

def interval_kb():
    return InlineKeyboardMarkup([
        [
            _btn("3 min",   "interval_3"),
            _btn("5 min",   "interval_5"),
            _btn("10 min",  "interval_10"),
        ],
        [
            _btn("30 min",  "interval_30"),
            _btn("60 min",  "interval_60"),
            _btn("120 min", "interval_120"),
        ],
        [_btn("🔙 Back", "menu")],
    ])


# ─── Auto Reply ───────────────────────────────────────────────────────────────

def auto_reply_kb(enabled: bool):
    toggle = "❌ Turn OFF Auto Reply" if enabled else "✅ Turn ON Auto Reply"
    return InlineKeyboardMarkup([
        [_btn(toggle,                        "toggle_auto_reply")],
        [_btn("✏️ Set Reply Message",         "set_auto_reply_msg")],
        [_btn("⏱️ Set Inactive Time",          "set_auto_reply_time")],
        [_btn("🔙 Back",                     "menu")],
    ])


# ─── Premium Menu ─────────────────────────────────────────────────────────────

def premium_menu_kb(is_premium=False):
    lock = "" if is_premium else "🔒 "
    rows = [
        [
            _btn(f"{lock}⚡ Smart Delay",        "smart_delay"),
            _btn(f"{lock}🔄 Account Rotation",   "rotation_mode"),
        ],
        [
            _btn(f"{lock}💎 Message Signature",  "msg_signature"),
            _btn(f"{lock}🌙 Active Hours",       "active_hours"),
        ],
        [
            _btn(f"{lock}📅 Schedule Broadcast", "schedule_broadcast"),
            _btn(f"{lock}📡 Broadcast Now",      "broadcast_now"),
        ],
        [
            _btn(f"{lock}🚫 Remove Groups",      "group_blacklist"),
            _btn(f"{lock}📺 Remove Channels",    "channel_blacklist"),
        ],
        [
            _btn(f"{lock}🎯 Target Filter",      "target_filter"),
            _btn(f"{lock}📈 Ad Analytics",       "ad_analytics"),
        ],
        [_btn("🔙 Back", "menu")],
    ]
    return InlineKeyboardMarkup(rows)


# ─── Smart Delay ──────────────────────────────────────────────────────────────

def smart_delay_kb():
    return InlineKeyboardMarkup([
        [
            _btn("1s",    "delay_1"),
            _btn("3s",    "delay_3"),
            _btn("5s",    "delay_5"),
        ],
        [
            _btn("10s",   "delay_10"),
            _btn("15s",   "delay_15"),
            _btn("30s",   "delay_30"),
        ],
        [_btn("✏️ Custom",   "custom_delay")],
        [_btn("🔙 Back",     "premium")],
    ])


# ─── Active Hours ─────────────────────────────────────────────────────────────

def active_hours_kb():
    return InlineKeyboardMarkup([
        [
            _btn("🌙 Night (22–08)", "hours_22_8"),
            _btn("☀️ Day (08–22)",   "hours_8_22"),
        ],
        [_btn("⏰ Full Day (0–23)",  "hours_0_23")],
        [_btn("✏️ Custom",           "custom_hours")],
        [_btn("🔙 Back",             "premium")],
    ])


# ─── Group/Channel Exclusion with Pagination ──────────────────────────────────

def _paged_items_kb(items: list, page: int, page_size: int,
                     toggle_prefix: str, page_prefix: str,
                     all_on_cb: str, all_off_cb: str, back_cb: str):
    """Generic paginated toggle keyboard for groups or channels."""
    total = len(items)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))

    start = page * page_size
    chunk = items[start: start + page_size]

    rows = []
    for g in chunk:
        gid = g["group_id"]
        name = g["title"][:30] if g.get("title") else str(gid)
        excluded = g.get("excluded", False)
        icon = "❌" if excluded else "✅"
        rows.append([_btn(f"{icon} {name}", f"{toggle_prefix}{gid}")])

    # Pagination row
    nav = []
    if page > 0:
        nav.append(_btn("◀️ Prev", f"{page_prefix}{page - 1}"))
    nav.append(_btn(f"📄 {page + 1}/{total_pages}", "noop"))
    if page < total_pages - 1:
        nav.append(_btn("▶️ Next", f"{page_prefix}{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([
        _btn("❌ Exclude All", all_on_cb),
        _btn("✅ Include All", all_off_cb),
    ])
    rows.append([_btn("🔙 Back", back_cb)])
    return InlineKeyboardMarkup(rows)


def group_exclude_kb(groups: list, page: int = 0):
    return _paged_items_kb(
        items=groups,
        page=page,
        page_size=PAGE_SIZE,
        toggle_prefix="toggle_group_",
        page_prefix="grp_page_",
        all_on_cb="exclude_all_groups",
        all_off_cb="include_all_groups",
        back_cb="premium",
    )


def channel_exclude_kb(channels: list, page: int = 0):
    return _paged_items_kb(
        items=channels,
        page=page,
        page_size=PAGE_SIZE,
        toggle_prefix="toggle_channel_",
        page_prefix="ch_page_",
        all_on_cb="exclude_all_channels",
        all_off_cb="include_all_channels",
        back_cb="premium",
    )


def lock_premium_kb():
    return InlineKeyboardMarkup([
        [_btn("🛍️ Buy Premium to Unlock", "buy_premium")],
        [_btn("🔙 Back", "menu")],
    ])


# ─── Buy Premium ─────────────────────────────────────────────────────────────

def buy_premium_kb():
    rows = [
        [_btn(f"💎 {label} — ₹{price}", f"buy_plan_{plan_id}")]
        for plan_id, label, days, price in PREMIUM_PLANS
    ]
    rows.append([_btn("🔙 Back", "menu")])
    return InlineKeyboardMarkup(rows)


def payment_confirm_kb(plan_id: str):
    return InlineKeyboardMarkup([
        [_btn("✅ I've Paid — Verify Now", f"paid_{plan_id}")],
        [_btn("❌ Cancel",                 "menu")],
    ])


def admin_approve_kb(user_id: int, plan_id: str):
    return InlineKeyboardMarkup([
        [
            _btn("✅ APPROVE",   f"admin_approve_{user_id}_{plan_id}"),
            _btn("❌ REJECT",    f"admin_reject_{user_id}_{plan_id}"),
        ]
    ])


# ─── Language ──────────────────────────────────────────────────────────────────

def language_kb(current_lang: str = "en"):
    rows = []
    lang_items = list(LANGUAGES.items())
    for i in range(0, len(lang_items), 2):
        row = []
        for lang_code, lang_name in lang_items[i:i+2]:
            check = "✅ " if lang_code == current_lang else ""
            row.append(_btn(f"{check}{lang_name}", f"set_lang_{lang_code}"))
        rows.append(row)
    rows.append([_btn("🔙 Back", "menu")])
    return InlineKeyboardMarkup(rows)


# ─── Admin Panel ──────────────────────────────────────────────────────────────

def admin_main_kb():
    return InlineKeyboardMarkup([
        [
            _btn("👥 Users",         "admin_users"),
            _btn("📊 Stats",         "admin_stats"),
        ],
        [
            _btn("🔍 Find User",     "admin_find_user"),
            _btn("📢 Broadcast",     "admin_broadcast"),
        ],
        [
            _btn("💎 Grant Premium", "admin_grant"),
            _btn("🚫 Revoke Premium","admin_revoke"),
        ],
        [
            _btn("🔨 Ban User",      "admin_ban"),
            _btn("✅ Unban User",    "admin_unban"),
        ],
        [_btn("🔙 Back", "menu")],
    ])


def admin_users_kb(users: list, page: int = 0):
    total = len(users)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    chunk = users[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

    rows = []
    for u in chunk:
        uid = u["user_id"]
        name = (u.get("first_name") or u.get("username") or str(uid))[:20]
        banned_icon = "🚫" if u.get("is_banned") else "✅"
        rows.append([_btn(f"{banned_icon} {name} ({uid})", f"admin_view_{uid}")])

    nav = []
    if page > 0:
        nav.append(_btn("◀️ Prev", f"admin_users_pg_{page - 1}"))
    nav.append(_btn(f"📄 {page + 1}/{total_pages}", "noop"))
    if page < total_pages - 1:
        nav.append(_btn("▶️ Next", f"admin_users_pg_{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([_btn("🔙 Back", "admin_panel")])
    return InlineKeyboardMarkup(rows)


def admin_user_actions_kb(user_id: int, is_banned: bool, is_premium: bool):
    rows = [
        [_btn(f"{'✅ Unban' if is_banned else '🔨 Ban'} User",
              f"admin_unban_{user_id}" if is_banned else f"admin_ban_{user_id}")],
        [
            _btn("💎 Grant 30d Premium", f"admin_grant_30_{user_id}"),
            _btn("💎 Grant 7d Premium",  f"admin_grant_7_{user_id}"),
        ],
    ]
    if is_premium:
        rows.append([_btn("🚫 Revoke Premium", f"admin_revoke_{user_id}")])
    rows.append([_btn("📋 View Logs", f"admin_logs_{user_id}")])
    rows.append([_btn("🔙 Back", "admin_users")])
    return InlineKeyboardMarkup(rows)
