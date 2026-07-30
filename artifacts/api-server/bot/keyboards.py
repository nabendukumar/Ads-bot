from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import PREMIUM_PLANS, UPI_ID


# ─── Helper ───────────────────────────────────────────────────────────────────

def _btn(text, cbd): return InlineKeyboardButton(text, callback_data=cbd)
def _url_btn(text, url): return InlineKeyboardButton(text, url=url)


# ─── Main Menu ────────────────────────────────────────────────────────────────

def main_menu_kb(is_premium=False):
    crown = "👑 " if is_premium else ""
    rows = [
        [
            _btn("➕ Add Account",   "add_account"),
            _btn("👥 My Accounts",   "my_accounts"),
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
            _btn("📊 Stats",          "stats"),
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
    """OTP screen — resend button."""
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
        [_btn("🔙 Back",                     "menu")],
    ])


# ─── Premium Menu ─────────────────────────────────────────────────────────────

def premium_menu_kb(is_premium=False):
    lock = "" if is_premium else "🔒 "
    rows = [
        [
            _btn(f"📊 Stats",                   "stats"),
            _btn(f"{lock}⚡ Smart Delay",        "smart_delay"),
        ],
        [
            _btn(f"{lock}🔄 Account Rotation",  "rotation_mode"),
            _btn(f"{lock}💎 Signature",          "msg_signature"),
        ],
        [
            _btn(f"{lock}🌙 Active Hours",       "active_hours"),
            _btn(f"{lock}📅 Schedule",           "schedule_broadcast"),
        ],
        [
            _btn(f"{lock}📡 Broadcast Now",      "broadcast_now"),
            _btn(f"{lock}🚫 Remove Groups",      "group_blacklist"),
        ],
        [
            _btn(f"{lock}🎯 Target Filter",      "target_filter"),
            _btn(f"{lock}📈 Ad Analytics",       "ad_analytics"),
        ],
        [
            _btn("🛍️ Buy Premium",              "buy_premium"),
            _btn("🔙 Back to Menu",              "menu"),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def smart_delay_kb():
    return InlineKeyboardMarkup([
        [
            _btn("1s ⚡",  "delay_1"),
            _btn("3s",     "delay_3"),
            _btn("5s",     "delay_5"),
        ],
        [
            _btn("10s",   "delay_10"),
            _btn("15s",   "delay_15"),
            _btn("30s",   "delay_30"),
        ],
        [_btn("✏️ Custom", "custom_delay")],
        [_btn("🔙 Back",   "premium")],
    ])


def active_hours_kb():
    return InlineKeyboardMarkup([[_btn("🔙 Back", "premium")]])


# ─── Buy Premium ─────────────────────────────────────────────────────────────

def buy_premium_kb():
    rows = []
    for plan_id, label, days, price in PREMIUM_PLANS:
        rows.append([_btn(f"💎 {label} — ₹{price}", f"buy_plan_{plan_id}")])
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


# ─── Stats ────────────────────────────────────────────────────────────────────

def stats_kb():
    return InlineKeyboardMarkup([
        [
            _btn("📋 Account Details", "stats_accounts"),
            _btn("📡 Broadcast Logs",  "stats_jobs"),
        ],
        [_btn("🔙 Back", "menu")],
    ])


# ─── Group Blacklist ──────────────────────────────────────────────────────────

def group_exclude_kb(groups: list):
    """Groups the user can toggle exclude/include."""
    rows = []
    for g in groups:
        gid = g["group_id"]
        name = g["title"][:28]
        excluded = g.get("excluded", False)
        icon = "❌" if excluded else "✅"
        rows.append([_btn(f"{icon} {name}", f"toggle_group_{gid}")])
    rows.append([
        _btn("❌ Exclude All",  "exclude_all_groups"),
        _btn("✅ Include All",  "include_all_groups"),
    ])
    rows.append([_btn("🔙 Back", "premium")])
    return InlineKeyboardMarkup(rows)


def lock_premium_kb():
    return InlineKeyboardMarkup([
        [_btn("🛍️ Buy Premium to Unlock", "buy_premium")],
        [_btn("🔙 Back", "menu")],
    ])
