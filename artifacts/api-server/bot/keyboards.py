from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import PREMIUM_PLANS, UPI_ID, PAGE_SIZE, LANGUAGES


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _btn(text, cbd, style=None): return InlineKeyboardButton(text, callback_data=cbd, style=style)
def _url_btn(text, url, style=None): return InlineKeyboardButton(text, url=url, style=style)

S_PRIMARY = "primary"
S_SUCCESS = "success"
S_DANGER  = "danger"


# ─── Main Menu ──────────────────────────────────────────────────────────────────

def main_menu_kb(is_premium=False):
    crown = "👑 " if is_premium else ""
    rows = [
        [
            _btn("➕ Add Account",    "add_account",  S_SUCCESS),
            _btn("👥 My Accounts",    "my_accounts",  S_PRIMARY),
        ],
        [
            _btn("📝 Set Ad Message", "set_ad_msg",   S_PRIMARY),
            _btn("⏰ Set Interval",   "set_interval", S_PRIMARY),
        ],
        [
            _btn("▶️ Start Ads",      "start_ads",    S_SUCCESS),
            _btn("⏹️ Stop Ads",       "stop_ads",     S_DANGER),
        ],
        [
            _btn("🗑️ Delete Account", "delete_account", S_DANGER),
            _btn("📋 Logs",           "logs",         S_PRIMARY),
        ],
        [
            _btn("💬 Auto Reply",     "auto_reply",   S_PRIMARY),
            _btn(f"{crown}⭐ Premium", "premium",      S_PRIMARY),
        ],
        [
            _btn("🌐 Language",       "language",     S_PRIMARY),
            _btn("🛍️ Buy Premium",    "buy_premium",  S_SUCCESS),
        ],
    ]
    return InlineKeyboardMarkup(rows)


# ─── Back buttons ───────────────────────────────────────────────────────────────

def back_kb(target="menu"):
    return InlineKeyboardMarkup([[_btn("🔙 Back", target, S_PRIMARY)]])


def back_and_cancel_kb():
    return InlineKeyboardMarkup([[_btn("❌ Cancel", "menu", S_DANGER)]])


# ─── Join group ─────────────────────────────────────────────────────────────────

def join_group_kb(group_link: str):
    return InlineKeyboardMarkup([
        [_url_btn("📢 Join Group", group_link, S_PRIMARY)],
        [_btn("✅ I've Joined", "check_join", S_SUCCESS)],
    ])


# ─── Accounts ───────────────────────────────────────────────────────────────────

def delete_accounts_kb(accounts: list):
    buttons = [
        [_btn(f"❌ {acc.get('label') or acc['phone']}", f"del_acc_{acc['id']}", S_DANGER)]
        for acc in accounts
    ]
    buttons.append([_btn("🔙 Back", "menu", S_PRIMARY)])
    return InlineKeyboardMarkup(buttons)


def accounts_list_kb():
    return InlineKeyboardMarkup([
        [_btn("➕ Add Account",    "add_account",  S_SUCCESS)],
        [_btn("🗑️ Delete Account", "delete_account", S_DANGER)],
        [_btn("🔙 Back",              "menu", S_PRIMARY)],
    ])


def otp_kb():
    return InlineKeyboardMarkup([
        [_btn("🔄 Resend OTP", "resend_otp", S_PRIMARY)],
        [_btn("❌ Cancel",     "menu",       S_DANGER)],
    ])


def upgrade_needed_kb():
    return InlineKeyboardMarkup([
        [_btn("🛍️ Buy Premium", "buy_premium", S_SUCCESS)],
        [_btn("🔙 Back",           "menu", S_PRIMARY)],
    ])


# ─── Interval ────────────────────────────────────────────────────────────────────

def interval_kb():
    return InlineKeyboardMarkup([
        [
            _btn("3 min",   "interval_3",   S_PRIMARY),
            _btn("5 min",   "interval_5",   S_PRIMARY),
            _btn("10 min",  "interval_10",  S_PRIMARY),
        ],
        [
            _btn("30 min",  "interval_30",  S_PRIMARY),
            _btn("60 min",  "interval_60",  S_PRIMARY),
            _btn("120 min", "interval_120", S_PRIMARY),
        ],
        [_btn("🔙 Back", "menu", S_PRIMARY)],
    ])


# ─── Auto Reply ──────────────────────────────────────────────────────────────────

def auto_reply_kb(enabled: bool):
    toggle = "❌ Turn OFF Auto Reply" if enabled else "✅ Turn ON Auto Reply"
    toggle_style = S_DANGER if enabled else S_SUCCESS
    return InlineKeyboardMarkup([
        [_btn(toggle,                        "toggle_auto_reply", toggle_style)],
        [_btn("✏️ Set Reply Message",         "set_auto_reply_msg", S_PRIMARY)],
        [_btn("⏱️ Set Inactive Time",          "set_auto_reply_time", S_PRIMARY)],
        [_btn("🔙 Back",                     "menu", S_PRIMARY)],
    ])


# ─── Premium Menu ───────────────────────────────────────────────────────────────

def premium_menu_kb(is_premium=False):
    lock = "" if is_premium else "🔒 "
    rows = [
        [
            _btn(f"{lock}⚡ Smart Delay",        "smart_delay",      S_PRIMARY),
            _btn(f"{lock}🔄 Account Rotation",   "rotation_mode",    S_PRIMARY),
        ],
        [
            _btn(f"{lock}💎 Message Signature",  "msg_signature",    S_PRIMARY),
            _btn(f"{lock}🌙 Active Hours",       "active_hours",     S_PRIMARY),
        ],
        [
            _btn(f"{lock}📅 Schedule Broadcast", "schedule_broadcast", S_PRIMARY),
            _btn(f"{lock}📡 Broadcast Now",      "broadcast_now",    S_SUCCESS),
        ],
        [
            _btn(f"{lock}🚫 Remove Groups",      "group_blacklist",  S_DANGER),
            _btn(f"{lock}📺 Remove Channels",    "channel_blacklist", S_DANGER),
        ],
        [
            _btn(f"{lock}🎯 Target Filter",      "target_filter",    S_PRIMARY),
            _btn(f"{lock}📈 Ad Analytics",       "ad_analytics",     S_PRIMARY),
        ],
        [_btn("🔙 Back", "menu", S_PRIMARY)],
    ]
    return InlineKeyboardMarkup(rows)


# ─── Smart Delay ────────────────────────────────────────────────────────────────

def smart_delay_kb():
    return InlineKeyboardMarkup([
        [
            _btn("1s",    "delay_1",  S_PRIMARY),
            _btn("3s",    "delay_3",  S_PRIMARY),
            _btn("5s",    "delay_5",  S_PRIMARY),
        ],
        [
            _btn("10s",   "delay_10", S_PRIMARY),
            _btn("15s",   "delay_15", S_PRIMARY),
            _btn("30s",   "delay_30", S_PRIMARY),
        ],
        [_btn("✏️ Custom",   "custom_delay", S_PRIMARY)],
        [_btn("🔙 Back",     "premium",      S_PRIMARY)],
    ])


# ─── Active Hours ───────────────────────────────────────────────────────────────

def active_hours_kb():
    return InlineKeyboardMarkup([
        [
            _btn("🌙 Night (22–08)", "hours_22_8", S_PRIMARY),
            _btn("☀️ Day (08–22)",   "hours_8_22", S_PRIMARY),
        ],
        [_btn("⏰ Full Day (0–23)",  "hours_0_23",   S_PRIMARY)],
        [_btn("✏️ Custom",           "custom_hours", S_PRIMARY)],
        [_btn("🔙 Back",             "premium",      S_PRIMARY)],
    ])


# ─── Group/Channel Exclusion with Pagination ────────────────────────────────────

def _paged_items_kb(items: list, page: int, page_size: int,
                     toggle_prefix: str, page_prefix: str,
                     all_on_cb: str, all_off_cb: str, back_cb: str):
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
        style = S_DANGER if excluded else S_SUCCESS
        rows.append([_btn(f"{icon} {name}", f"{toggle_prefix}{gid}", style)])

    nav = []
    if page > 0:
        nav.append(_btn("◀️ Prev", f"{page_prefix}{page - 1}", S_PRIMARY))
    nav.append(_btn(f"📄 {page + 1}/{total_pages}", "noop", S_PRIMARY))
    if page < total_pages - 1:
        nav.append(_btn("▶️ Next", f"{page_prefix}{page + 1}", S_PRIMARY))
    if nav:
        rows.append(nav)

    rows.append([
        _btn("❌ Exclude All", all_on_cb, S_DANGER),
        _btn("✅ Include All", all_off_cb, S_SUCCESS),
    ])
    rows.append([_btn("🔙 Back", back_cb, S_PRIMARY)])
    return InlineKeyboardMarkup(rows)


def group_exclude_kb(groups: list, page: int = 0):
    return _paged_items_kb(
        items=groups, page=page, page_size=PAGE_SIZE,
        toggle_prefix="toggle_group_", page_prefix="grp_page_",
        all_on_cb="exclude_all_groups", all_off_cb="include_all_groups",
        back_cb="premium",
    )


def channel_exclude_kb(channels: list, page: int = 0):
    return _paged_items_kb(
        items=channels, page=page, page_size=PAGE_SIZE,
        toggle_prefix="toggle_channel_", page_prefix="ch_page_",
        all_on_cb="exclude_all_channels", all_off_cb="include_all_channels",
        back_cb="premium",
    )


def lock_premium_kb():
    return InlineKeyboardMarkup([
        [_btn("🛍️ Buy Premium to Unlock", "buy_premium", S_SUCCESS)],
        [_btn("🔙 Back", "menu", S_PRIMARY)],
    ])


# ─── Buy Premium ────────────────────────────────────────────────────────────────

def buy_premium_kb():
    rows = [
        [_btn(f"💎 {label} — ₹{price}", f"buy_plan_{plan_id}", S_SUCCESS)]
        for plan_id, label, days, price in PREMIUM_PLANS
    ]
    rows.append([_btn("🔙 Back", "menu", S_PRIMARY)])
    return InlineKeyboardMarkup(rows)


def payment_confirm_kb(plan_id: str):
    return InlineKeyboardMarkup([
        [_btn("✅ I've Paid — Verify Now", f"paid_{plan_id}", S_SUCCESS)],
        [_btn("❌ Cancel",                 "menu", S_DANGER)],
    ])


def admin_approve_kb(user_id: int, plan_id: str):
    return InlineKeyboardMarkup([
        [
            _btn("✅ APPROVE",   f"admin_approve_{user_id}_{plan_id}", S_SUCCESS),
            _btn("❌ REJECT",    f"admin_reject_{user_id}_{plan_id}", S_DANGER),
        ]
    ])


# ─── Language ────────────────────────────────────────────────────────────────────

def language_kb(current_lang: str = "en"):
    rows = []
    lang_items = list(LANGUAGES.items())
    for i in range(0, len(lang_items), 2):
        row = []
        for lang_code, lang_name in lang_items[i:i+2]:
            check = "✅ " if lang_code == current_lang else ""
            style = S_SUCCESS if lang_code == current_lang else S_PRIMARY
            row.append(_btn(f"{check}{lang_name}", f"set_lang_{lang_code}", style))
        rows.append(row)
    rows.append([_btn("🔙 Back", "menu", S_PRIMARY)])
    return InlineKeyboardMarkup(rows)


# ─── Admin Panel ─────────────────────────────────────────────────────────────────

def admin_main_kb():
    return InlineKeyboardMarkup([
        [
            _btn("👥 Users",         "admin_users",    S_PRIMARY),
            _btn("📊 Stats",         "admin_stats",    S_PRIMARY),
        ],
        [
            _btn("🔍 Find User",     "admin_find_user", S_PRIMARY),
            _btn("📢 Broadcast",     "admin_broadcast", S_SUCCESS),
        ],
        [
            _btn("💎 Grant Premium", "admin_grant",    S_SUCCESS),
            _btn("🚫 Revoke Premium","admin_revoke",   S_DANGER),
        ],
        [
            _btn("🔨 Ban User",      "admin_ban",      S_DANGER),
            _btn("✅ Unban User",    "admin_unban",    S_SUCCESS),
        ],
        [_btn("🔙 Back", "menu", S_PRIMARY)],
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
        style = S_DANGER if u.get("is_banned") else S_SUCCESS
        rows.append([_btn(f"{banned_icon} {name} ({uid})", f"admin_view_{uid}", style)])

    nav = []
    if page > 0:
        nav.append(_btn("◀️ Prev", f"admin_users_pg_{page - 1}", S_PRIMARY))
    nav.append(_btn(f"📄 {page + 1}/{total_pages}", "noop", S_PRIMARY))
    if page < total_pages - 1:
        nav.append(_btn("▶️ Next", f"admin_users_pg_{page + 1}", S_PRIMARY))
    if nav:
        rows.append(nav)

    rows.append([_btn("🔙 Back", "admin_panel", S_PRIMARY)])
    return InlineKeyboardMarkup(rows)


def admin_user_actions_kb(user_id: int, is_banned: bool, is_premium: bool):
    rows = [
        [_btn(f"{'✅ Unban' if is_banned else '🔨 Ban'} User",
              f"admin_unban_{user_id}" if is_banned else f"admin_ban_{user_id}",
              S_SUCCESS if is_banned else S_DANGER)],
        [
            _btn("💎 Grant 30d Premium", f"admin_grant_30_{user_id}", S_SUCCESS),
            _btn("💎 Grant 7d Premium",  f"admin_grant_7_{user_id}",  S_SUCCESS),
        ],
    ]
    if is_premium:
        rows.append([_btn("🚫 Revoke Premium", f"admin_revoke_{user_id}", S_DANGER)])
    rows.append([_btn("📋 View Logs", f"admin_logs_{user_id}", S_PRIMARY)])
    rows.append([_btn("📱 View Accounts", f"admin_accounts_{user_id}", S_PRIMARY)])
    rows.append([_btn("🔙 Back", "admin_users", S_PRIMARY)])
    return InlineKeyboardMarkup(rows)


# ─── Admin: User Connected Accounts ──────────────────────────────────────────────

def admin_accounts_kb(user_id: int, accounts: list):
    rows = []
    for acc in accounts:
        phone = acc.get("phone", "—")
        acc_id = acc["id"]
        active = acc.get("is_active") and acc.get("bio_ok", True)
        status = "🟢" if active else "🔴"
        style = S_SUCCESS if active else S_DANGER
        rows.append([_btn(f"{status} {phone}", f"admin_acc_{user_id}_{acc_id}", style)])
    rows.append([_btn("🔙 Back", f"admin_view_{user_id}", S_PRIMARY)])
    return InlineKeyboardMarkup(rows)


def admin_account_actions_kb(user_id: int, account_id: int, phone: str):
    return InlineKeyboardMarkup([
        [_btn("📋 View Groups", f"admin_acc_groups_{user_id}_{account_id}", S_PRIMARY)],
        [_btn("📨 Send Message", f"admin_acc_send_{user_id}_{account_id}", S_SUCCESS)],
        [_btn("🔙 Back", f"admin_accounts_{user_id}", S_PRIMARY)],
    ])


def admin_account_groups_kb(user_id: int, account_id: int, groups: list, page: int = 0):
    total = len(groups)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    chunk = groups[start: start + PAGE_SIZE]

    rows = []
    for g in chunk:
        gid = g["group_id"]
        name = g.get("title") or str(gid)
        is_chan = g.get("is_channel", False)
        icon = "📺" if is_chan else "👥"
        members = g.get("member_count", 0)
        rows.append([_btn(f"{icon} {name[:30]} ({members})",
                          f"admin_grp_{user_id}_{account_id}_{gid}", S_PRIMARY)])

    nav = []
    if page > 0:
        nav.append(_btn("◀️ Prev", f"admin_acc_grp_pg_{user_id}_{account_id}_{page - 1}", S_PRIMARY))
    nav.append(_btn(f"📄 {page + 1}/{total_pages}", "noop", S_PRIMARY))
    if page < total_pages - 1:
        nav.append(_btn("▶️ Next", f"admin_acc_grp_pg_{user_id}_{account_id}_{page + 1}", S_PRIMARY))
    if nav:
        rows.append(nav)

    rows.append([_btn("🔙 Back", f"admin_acc_{user_id}_{account_id}", S_PRIMARY)])
    return InlineKeyboardMarkup(rows)
