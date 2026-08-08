"""Safe Telegram bot skeleton.

This build intentionally does not collect, retrieve, scrape, or process
government identity numbers, OTPs, credit reports, or password-protected PDFs.
It provides the safe bot shell: channel gate, inline menu, credits, and
manual payment-proof approval.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from threading import Lock
from typing import Any

import requests


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
LOGGER = logging.getLogger("safe-telegram-bot")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "8493051039"))
FORCED_CHANNEL_ID = os.getenv("FORCED_CHANNEL_ID", "-1003961304592").strip()
FORCED_CHANNEL_URL = os.getenv("FORCED_CHANNEL_URL", "").strip()
ADMIN_NAME = os.getenv("ADMIN_NAME", "Lucifer MorningStar").strip()
UPI_ID = os.getenv("UPI_ID", "nabendu8@ptyes").strip()
STATE_FILE = Path(os.getenv("STATE_FILE", "data/state.json"))
POLLING_TIMEOUT = int(os.getenv("POLLING_TIMEOUT", "25"))
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

WELCOME = "🤖 Welcome to Luci Aadhaar Pan Bot!"
JOIN_MESSAGE = (
    "👋 You need to join our group first!\n\n"
    "Click the button below to join, then press '✅ I've Joined'."
)
PLANS: dict[str, dict[str, int]] = {
    "plan_20": {"credits": 20, "price": 30},
    "plan_40": {"credits": 40, "price": 50},
    "plan_100": {"credits": 100, "price": 100},
}

STATE_LOCK = Lock()


def require_config() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    if not FORCED_CHANNEL_URL:
        raise RuntimeError(
            "FORCED_CHANNEL_URL is not configured. Set the channel username or invite link."
        )


def load_state() -> dict[str, Any]:
    with STATE_LOCK:
        if not STATE_FILE.exists():
            return {"users": {}, "payments": {}}
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            return {
                "users": state.get("users", {}),
                "payments": state.get("payments", {}),
            }
        except (OSError, json.JSONDecodeError):
            LOGGER.warning("State file is unreadable; starting with empty state")
            return {"users": {}, "payments": {}}


def save_state(state: dict[str, Any]) -> None:
    with STATE_LOCK:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = STATE_FILE.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(STATE_FILE)


def api(method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.post(
        f"{API_URL}/{method}",
        json=payload or {},
        timeout=POLLING_TIMEOUT + 10,
    )
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API {method} failed: {result}")
    return result["result"]


def send_message(chat_id: int, text: str, reply_markup: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    api("sendMessage", payload)


def answer_callback(callback_id: str, text: str | None = None) -> None:
    payload: dict[str, Any] = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
    api("answerCallbackQuery", payload)


def user_record(state: dict[str, Any], chat_id: int) -> dict[str, Any]:
    key = str(chat_id)
    if key not in state["users"]:
        state["users"][key] = {"credits": 10, "pending_payment": None}
    return state["users"][key]


def is_admin(chat_id: int) -> bool:
    return chat_id == ADMIN_CHAT_ID


def channel_keyboard() -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [{"text": "👋 Join channel", "url": FORCED_CHANNEL_URL}],
            [{"text": "✅ I've Joined", "callback_data": "check_join"}],
        ]
    }


def main_keyboard() -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "Aadhar", "callback_data": "feature_aadhar"},
                {"text": "Pan", "callback_data": "feature_pan"},
            ],
            [{"text": "Buy credits", "callback_data": "buy_credits"}],
            [{"text": "Contact Admin", "callback_data": "contact_admin"}],
        ]
    }


def credits_text(credits: int) -> str:
    return f"Your credits: {credits}\n\nChoose an option below."


def membership_exists(chat_id: int) -> bool:
    if is_admin(chat_id):
        return True
    try:
        member = api(
            "getChatMember",
            {"chat_id": FORCED_CHANNEL_ID, "user_id": chat_id},
        )
        return member.get("status") in {"creator", "administrator", "member"}
    except Exception as exc:
        LOGGER.warning("Membership check failed for %s: %s", chat_id, exc)
        return False


def require_membership(chat_id: int) -> bool:
    if membership_exists(chat_id):
        return True
    send_message(chat_id, JOIN_MESSAGE, channel_keyboard())
    return False


def send_home(chat_id: int, state: dict[str, Any]) -> None:
    record = user_record(state, chat_id)
    save_state(state)
    send_message(chat_id, f"{WELCOME}\n\n{credits_text(record['credits'])}", main_keyboard())


def send_payment_plans(chat_id: int) -> None:
    send_message(
        chat_id,
        (
            "Choose a credit pack:\n\n"
            "• ₹30 — 20 credits\n"
            "• ₹50 — 40 credits\n"
            "• ₹100 — 100 credits\n\n"
            f"UPI ID: {UPI_ID}\n\n"
            "After payment, select a pack and send the payment screenshot here. "
            "Admin will verify it manually."
        ),
        {
            "inline_keyboard": [
                [{"text": "₹30 / 20 credits", "callback_data": "plan_20"}],
                [{"text": "₹50 / 40 credits", "callback_data": "plan_40"}],
                [{"text": "₹100 / 100 credits", "callback_data": "plan_100"}],
                [{"text": "Back", "callback_data": "home"}],
            ]
        },
    )


def start_payment(chat_id: int, plan_id: str, state: dict[str, Any]) -> None:
    plan = PLANS[plan_id]
    record = user_record(state, chat_id)
    record["pending_payment"] = plan_id
    save_state(state)
    send_message(
        chat_id,
        (
            f"Selected: ₹{plan['price']} for {plan['credits']} credits.\n\n"
            f"Pay to UPI ID: {UPI_ID}\n"
            "Now send the payment screenshot in this chat. "
            "Your request will be sent to admin for approval."
        ),
    )


def payment_buttons(payment_id: str) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "Approve", "callback_data": f"approve:{payment_id}"},
                {"text": "Reject", "callback_data": f"reject:{payment_id}"},
            ]
        ]
    }


def record_payment_proof(
    chat_id: int,
    file_id: str,
    state: dict[str, Any],
    caption: str = "",
) -> None:
    record = user_record(state, chat_id)
    plan_id = record.get("pending_payment")
    if plan_id not in PLANS:
        send_message(chat_id, "Please choose a credit pack first.", main_keyboard())
        return

    payment_id = f"{chat_id}-{int(time.time())}"
    state["payments"][payment_id] = {
        "user_id": chat_id,
        "plan_id": plan_id,
        "file_id": file_id,
        "caption": caption[:500],
        "status": "pending",
    }
    record["pending_payment"] = None
    save_state(state)
    plan = PLANS[plan_id]
    send_message(chat_id, "Payment proof received. Please wait for admin verification.")
    api(
        "sendPhoto",
        {
            "chat_id": ADMIN_CHAT_ID,
            "photo": file_id,
            "caption": (
                f"Payment approval request\n"
                f"User ID: {chat_id}\n"
                f"Plan: ₹{plan['price']} / {plan['credits']} credits\n"
                f"Payment ID: {payment_id}\n"
                f"User caption: {caption[:300]}"
            ),
            "reply_markup": payment_buttons(payment_id),
        },
    )


def resolve_payment(chat_id: int, payment_id: str, approve: bool, state: dict[str, Any]) -> None:
    if not is_admin(chat_id):
        return
    payment = state["payments"].get(payment_id)
    if not payment or payment.get("status") != "pending":
        send_message(chat_id, "This payment request is missing or already resolved.")
        return

    payment["status"] = "approved" if approve else "rejected"
    target_id = int(payment["user_id"])
    if approve:
        plan = PLANS[payment["plan_id"]]
        target = user_record(state, target_id)
        target["credits"] += plan["credits"]
        send_message(
            target_id,
            f"Payment approved. {plan['credits']} credits added.\n\n"
            f"{credits_text(target['credits'])}",
            main_keyboard(),
        )
        send_message(chat_id, f"Approved payment {payment_id}.")
    else:
        send_message(target_id, "Payment proof was rejected by admin. Please contact admin.")
        send_message(chat_id, f"Rejected payment {payment_id}.")
    save_state(state)


def handle_callback(query: dict[str, Any], state: dict[str, Any]) -> None:
    callback_id = query["id"]
    chat_id = query["message"]["chat"]["id"]
    data = query.get("data", "")
    answer_callback(callback_id)

    if data.startswith(("approve:", "reject:")):
        prefix, payment_id = data.split(":", 1)
        resolve_payment(chat_id, payment_id, prefix == "approve", state)
        return
    if data == "check_join":
        if membership_exists(chat_id):
            send_home(chat_id, state)
        else:
            send_message(chat_id, JOIN_MESSAGE, channel_keyboard())
        return
    if not require_membership(chat_id):
        return
    if data in PLANS:
        start_payment(chat_id, data, state)
    elif data == "buy_credits":
        send_payment_plans(chat_id)
    elif data == "home":
        send_home(chat_id, state)
    elif data == "contact_admin":
        send_message(chat_id, f"Admin: {ADMIN_NAME}\nChat ID: {ADMIN_CHAT_ID}")
    elif data in {"feature_aadhar", "feature_pan"}:
        send_message(
            chat_id,
            "This safe build does not process Aadhaar/PAN or other identity data.",
            main_keyboard(),
        )


def handle_message(message: dict[str, Any], state: dict[str, Any]) -> None:
    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    record = user_record(state, chat_id)

    if message.get("photo"):
        photo = message["photo"][-1]
        record_payment_proof(chat_id, photo["file_id"], state, message.get("caption", ""))
        return
    if message.get("document") and message["document"].get("mime_type", "").startswith("image/"):
        record_payment_proof(
            chat_id,
            message["document"]["file_id"],
            state,
            message.get("caption", ""),
        )
        return
    if text.startswith("/start"):
        if require_membership(chat_id):
            send_home(chat_id, state)
        return
    if text.startswith("/buy"):
        if require_membership(chat_id):
            send_payment_plans(chat_id)
        return
    if not require_membership(chat_id):
        return
    send_message(chat_id, credits_text(record["credits"]), main_keyboard())


def run() -> None:
    require_config()
    LOGGER.info("Starting safe Telegram bot")
    offset = 0
    while True:
        try:
            updates = api(
                "getUpdates",
                {"offset": offset, "timeout": POLLING_TIMEOUT, "allowed_updates": ["message", "callback_query"]},
            )
            state = load_state()
            for update in updates:
                offset = update["update_id"] + 1
                if update.get("callback_query"):
                    handle_callback(update["callback_query"], state)
                elif update.get("message"):
                    handle_message(update["message"], state)
        except KeyboardInterrupt:
            LOGGER.info("Bot stopped")
            return
        except Exception:
            LOGGER.exception("Polling error; retrying in 5 seconds")
            time.sleep(5)


if __name__ == "__main__":
    run()