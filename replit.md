# Luci Ads Bot

Telegram bot jo automatically ads send karta hai multiple connected accounts se sab groups mein.

## Run & Operate

- Bot files: `artifacts/api-server/bot/`
- `python artifacts/api-server/bot/main.py` — bot run karo
- Render deploy: `render.yaml` already configured

## Stack

- Python 3.11+, python-telegram-bot 21+, Telethon 1.37+
- PostgreSQL + psycopg2
- Render (worker service)

## Bot Features

1. **Logs** — Log Bot pe redirect hota hai, main bot mein nahi
2. **Bio Update** — Account connect hone pe bot username name/bio mein add hota hai; remove karne pe auto-deactivate
3. **Resend OTP** — OTP screen pe resend button
4. **Account Limit** — Free: 2 accounts, Premium: 10 accounts
5. **Buy Premium** — UPI payment (nabendu8@ptyes), admin approve/reject; Plans: ₹10/7d, ₹20/10d, ₹50/30d
6. **Premium Features** — Smart Delay, Rotation, Signature, Active Hours, Schedule, Broadcast Now, Remove Groups, Target Filter, Ad Analytics
7. **Remove Groups** — Group list sync + toggle exclude per group
8. **Detailed Stats** — Groups, channels, excluded count, per-account analytics
9. **Green/Red Buttons** — 🟢 active / 🔴 danger inline buttons

## Environment Variables Required (Render)

- `BOT_TOKEN` — Main bot token
- `LOG_BOT_TOKEN` — Log bot token
- `API_ID` — Telegram API ID
- `API_HASH` — Telegram API Hash
- `DATABASE_URL` — PostgreSQL connection string
- `ADMIN_ID` — Admin Telegram user ID
- `LOG_CHAT_ID` — Log chat ID (defaults to ADMIN_ID)
- `BOT_USERNAME` — e.g. `@LuciAdsBot`
- `LOG_BOT_USERNAME` — Log bot username for redirect link
- `UPI_ID` — UPI payment ID (default: nabendu8@ptyes)

## User preferences

- Hindi/Hinglish mein communicate karo
- Render pe host karna hai
- Premium animations chahiye

## Gotchas

- Bio check job har 2 ghante mein chalta hai
- Free users 2 accounts se zyada connect nahi kar sakte
- Admin ID: 8493051039
