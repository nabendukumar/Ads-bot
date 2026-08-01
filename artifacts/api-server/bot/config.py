import os

BOT_TOKEN = os.environ["BOT_TOKEN"]
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
DATABASE_URL = os.environ["DATABASE_URL"]
FORCE_JOIN_GROUP = int(os.environ.get("FORCE_JOIN_GROUP", "0"))
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
PORT = int(os.environ.get("PORT", "8080"))

# Log bot config
LOG_BOT_TOKEN = os.environ.get("LOG_BOT_TOKEN", "")
_log_chat_raw = os.environ.get("LOG_CHAT_ID", "")
LOG_CHAT_ID = int(_log_chat_raw) if _log_chat_raw else ADMIN_ID

# Bot username (without @)
BOT_USERNAME = os.environ.get("BOT_USERNAME", "@LuciAdsBot")
BOT_USERNAME_CLEAN = BOT_USERNAME.lstrip("@")

# Log bot username (for redirect link)
LOG_BOT_USERNAME = os.environ.get("LOG_BOT_USERNAME", "")

# Free account limit — premium needed for more
FREE_ACCOUNT_LIMIT = 2
PREMIUM_ACCOUNT_LIMIT = 10

# UPI payment ID
UPI_ID = os.environ.get("UPI_ID", "nabendu8@ptyes")

# Premium plans: (plan_id, label, days, price_inr)
PREMIUM_PLANS = [
    ("7_days",  "7 Days",  7,  10),
    ("10_days", "10 Days", 10, 20),
    ("30_days", "30 Days", 30, 50),
]

# Minimum accounts required to start ads
MIN_ACCOUNTS = 1

# Items per page for group/channel listings
PAGE_SIZE = 8

# Supported languages
LANGUAGES = {
    "en": "🇬🇧 English",
    "hi": "🇮🇳 Hindi",
    "zh": "🇨🇳 Chinese",
    "id": "🇮🇩 Indonesian",
}

# ─── Translations ──────────────────────────────────────────────────────────────

STRINGS = {
    "en": {
        "greeting": (
            "🤖 *Welcome to Luci Ads Bot!*\n\n"
            "Automatically send ads to all your Telegram groups "
            "from multiple connected accounts.\n\n"
            "✅ Connect your Telegram accounts\n"
            "📢 Set your ad message\n"
            "⏰ Set a time interval\n"
            "🚀 Start broadcasting!\n\n"
            "Choose an option from the menu below 👇"
        ),
        "ads_running": "Yes ✅",
        "ads_stopped": "No ❌",
        "auto_reply_on": "On ✅",
        "auto_reply_off": "Off ❌",
        "plan_premium": "👑 Premium",
        "plan_free": "Free",
    },
    "hi": {
        "greeting": (
            "🤖 *Luci Ads Bot में आपका स्वागत है!*\n\n"
            "अपने सभी Telegram ग्रुप में कई खातों से "
            "स्वचालित रूप से विज्ञापन भेजें।\n\n"
            "✅ अपने Telegram खाते जोड़ें\n"
            "📢 अपना विज्ञापन संदेश सेट करें\n"
            "⏰ समय अंतराल सेट करें\n"
            "🚀 ब्रॉडकास्ट शुरू करें!\n\n"
            "नीचे मेनू से विकल्प चुनें 👇"
        ),
        "ads_running": "हाँ ✅",
        "ads_stopped": "नहीं ❌",
        "auto_reply_on": "चालू ✅",
        "auto_reply_off": "बंद ❌",
        "plan_premium": "👑 प्रीमियम",
        "plan_free": "मुफ़्त",
    },
    "zh": {
        "greeting": (
            "🤖 *欢迎使用 Luci Ads Bot！*\n\n"
            "通过多个账户自动向所有 Telegram 群组发送广告。\n\n"
            "✅ 连接您的 Telegram 账户\n"
            "📢 设置您的广告消息\n"
            "⏰ 设置时间间隔\n"
            "🚀 开始广播！\n\n"
            "从下方菜单选择选项 👇"
        ),
        "ads_running": "是 ✅",
        "ads_stopped": "否 ❌",
        "auto_reply_on": "开启 ✅",
        "auto_reply_off": "关闭 ❌",
        "plan_premium": "👑 高级版",
        "plan_free": "免费",
    },
    "id": {
        "greeting": (
            "🤖 *Selamat datang di Luci Ads Bot!*\n\n"
            "Kirim iklan secara otomatis ke semua grup Telegram Anda "
            "dari beberapa akun yang terhubung.\n\n"
            "✅ Hubungkan akun Telegram Anda\n"
            "📢 Atur pesan iklan Anda\n"
            "⏰ Atur interval waktu\n"
            "🚀 Mulai siaran!\n\n"
            "Pilih opsi dari menu di bawah 👇"
        ),
        "ads_running": "Ya ✅",
        "ads_stopped": "Tidak ❌",
        "auto_reply_on": "Aktif ✅",
        "auto_reply_off": "Nonaktif ❌",
        "plan_premium": "👑 Premium",
        "plan_free": "Gratis",
    },
}

def get_string(lang: str, key: str) -> str:
    return STRINGS.get(lang, STRINGS["en"]).get(key, STRINGS["en"].get(key, ""))

GREETING = STRINGS["en"]["greeting"]
