# Safe Telegram Bot Skeleton

This is a standalone, privacy-conscious Telegram bot shell with:

- `/start` greeting and forced channel membership check
- Inline menu and admin contact button
- 10 free starter credits per user
- ₹30/20, ₹50/40, and ₹100/100 credit plans
- UPI payment screenshot submission
- Manual admin approve/reject workflow
- JSON state storage for a small self-hosted deployment

This build deliberately does **not** collect, retrieve, scrape, or process Aadhaar,
PAN, OTP, credit-report, or other sensitive identity/financial data.

## Run

```bash
cd safe_bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Load .env with your preferred secret manager or export its variables.
python bot.py
```

Use a real `TELEGRAM_BOT_TOKEN` only as an environment secret. Do not put it in
the repository or paste it into chat. Set `FORCED_CHANNEL_URL` to the actual
channel username or invite link; the numeric channel ID is used only for the
membership check.