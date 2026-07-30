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

# Premium plans: (label, days, price_inr)
PREMIUM_PLANS = [
    ("7_days",  "7 Days",  7,  10),
    ("10_days", "10 Days", 10, 20),
    ("30_days", "30 Days", 30, 50),
]

# Minimum accounts required to start ads
MIN_ACCOUNTS = 1

GREETING = (
    "🤖 *Welcome to Luci Ads Bot!*\n\n"
    "Automatically send ads to all your Telegram groups "
    "from multiple connected accounts.\n\n"
    "✅ Connect your Telegram accounts\n"
    "📢 Set your ad message\n"
    "⏰ Set a time interval\n"
    "🚀 Start broadcasting!\n\n"
    "Choose an option from the menu below 👇"
)
