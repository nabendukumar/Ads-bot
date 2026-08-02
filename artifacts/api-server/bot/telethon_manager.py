"""
Telethon client management for user account sessions.
"""
import asyncio
import logging
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    FloodWaitError,
    UserPrivacyRestrictedError,
)
from config import API_ID, API_HASH, BOT_USERNAME_CLEAN

logger = logging.getLogger(__name__)

# Temporary clients during login flow: user_id -> TelegramClient
_login_clients: dict = {}

# Active persistent clients for auto-reply: f"{user_id}_{phone}" -> TelegramClient
_active_clients: dict = {}
_auto_reply_tasks: dict = {}
_auto_reply_stop_events: dict = {}


def _make_client(session=None):
    return TelegramClient(
        session or StringSession(),
        API_ID,
        API_HASH,
        device_model="Samsung Galaxy S22",
        system_version="Android 13",
        app_version="10.3.1",
        lang_code="en",
        system_lang_code="en-US",
    )


# ─── Login flow ───────────────────────────────────────────────────────────────

async def create_login_client(user_id: int, phone: str) -> dict:
    try:
        if user_id in _login_clients:
            try:
                await _login_clients[user_id].disconnect()
            except Exception:
                pass
            del _login_clients[user_id]

        client = _make_client()
        await client.connect()
        await client.send_code_request(phone)
        _login_clients[user_id] = client
        return {"ok": True}
    except FloodWaitError as e:
        return {"ok": False, "error": f"Flood wait {e.seconds}s. Try later."}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def resend_otp(user_id: int, phone: str) -> dict:
    """Resend OTP by recreating the login client."""
    try:
        if user_id in _login_clients:
            try:
                await _login_clients[user_id].disconnect()
            except Exception:
                pass
            del _login_clients[user_id]
        return await create_login_client(user_id, phone)
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def submit_otp(user_id: int, otp: str) -> dict:
    client = _login_clients.get(user_id)
    if not client:
        return {"ok": False, "error": "Session expired. Please start again."}
    try:
        await client.sign_in(code=otp)
        session = client.session.save()
        await client.disconnect()
        del _login_clients[user_id]
        return {"ok": True, "session": session, "needs_2fa": False}
    except SessionPasswordNeededError:
        return {"ok": True, "session": "", "needs_2fa": True}
    except PhoneCodeExpiredError:
        return {"ok": False, "error": "OTP expired. Please request a new one."}
    except PhoneCodeInvalidError:
        return {"ok": False, "error": "Wrong OTP. Try again."}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def submit_password(user_id: int, password: str) -> dict:
    client = _login_clients.get(user_id)
    if not client:
        return {"ok": False, "error": "Session expired. Please start again."}
    try:
        await client.sign_in(password=password)
        session = client.session.save()
        await client.disconnect()
        del _login_clients[user_id]
        return {"ok": True, "session": session}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def cancel_login(user_id: int):
    if user_id in _login_clients:
        try:
            await _login_clients[user_id].disconnect()
        except Exception:
            pass
        del _login_clients[user_id]


# ─── Profile update ───────────────────────────────────────────────────────────

async def update_profile_after_login(session_string: str, bot_username: str):
    """Add bot username to the connected account's name and bio."""
    client = _make_client(StringSession(session_string))
    try:
        await client.connect()
        if not await client.is_user_authorized():
            return False
        me = await client.get_me()
        tag = f"@{bot_username.lstrip('@')}"

        first = me.first_name or ""
        last = me.last_name or ""
        bio = ""
        try:
            full = await client(
                __import__('telethon.tl.functions.users', fromlist=['GetFullUserRequest']).GetFullUserRequest(me)
            )
            bio = full.full_user.about or ""
        except Exception:
            pass

        new_first = first
        if tag not in first and tag not in last:
            new_first = f"{first} | {tag}".strip()

        new_bio = bio
        if tag not in bio:
            new_bio = f"{bio}\n{tag}".strip() if bio else tag

        from telethon.tl.functions.account import UpdateProfileRequest
        await client(UpdateProfileRequest(
            first_name=new_first[:64],
            last_name=last[:64] if last else "",
            about=new_bio[:70],
        ))
        logger.info(f"Profile updated for {me.phone}: name='{new_first}', bio='{new_bio}'")
        return True
    except Exception as e:
        logger.warning(f"update_profile_after_login error: {e}")
        return False
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def check_bio_has_bot(session_string: str, bot_username: str) -> bool:
    """Return True if bot username is still in name or bio."""
    client = _make_client(StringSession(session_string))
    try:
        await client.connect()
        if not await client.is_user_authorized():
            return False
        me = await client.get_me()
        tag = f"@{bot_username.lstrip('@')}"
        full_name = f"{me.first_name or ''} {me.last_name or ''}".lower()
        bio = ""
        try:
            from telethon.tl.functions.users import GetFullUserRequest
            full = await client(GetFullUserRequest(me))
            bio = (full.full_user.about or "").lower()
        except Exception:
            pass
        return tag.lower() in full_name or tag.lower() in bio
    except Exception as e:
        logger.warning(f"check_bio_has_bot error: {e}")
        return True  # On error assume OK to avoid false deactivation
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


# ─── Get groups/channels for an account ─────────────────────────────────────

async def get_dialogs(session_string: str):
    """Return list of groups and channels the account is in."""
    client = _make_client(StringSession(session_string))
    result = []
    try:
        await client.connect()
        if not await client.is_user_authorized():
            return result
        dialogs = await client.get_dialogs()
        for d in dialogs:
            entity = d.entity
            from telethon.tl.types import Channel, Chat
            if isinstance(entity, (Channel, Chat)):
                is_channel = isinstance(entity, Channel) and entity.broadcast
                members = getattr(entity, 'participants_count', 0) or 0
                result.append({
                    "group_id": entity.id,
                    "title": entity.title,
                    "is_channel": is_channel,
                    "member_count": members,
                })
    except Exception as e:
        logger.warning(f"get_dialogs error: {e}")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
    return result


# ─── Broadcast ────────────────────────────────────────────────────────────────

async def send_ads_to_groups(
    session_string: str,
    message: str,
    delay_seconds: int = 3,
    blacklist: list = None,
    excluded_ids: list = None,
    target_filter: str = "all",
) -> tuple:
    """Send message to all eligible groups. Returns (sent, failed, group_count)."""
    client = _make_client(StringSession(session_string))
    sent = failed = 0
    group_count = 0
    excluded_ids = excluded_ids or []
    blacklist = blacklist or []

    try:
        await client.connect()
        if not await client.is_user_authorized():
            return 0, 0, 0

        dialogs = await client.get_dialogs()
        from telethon.tl.types import Channel, Chat
        targets = []
        for d in dialogs:
            entity = d.entity
            if not isinstance(entity, (Channel, Chat)):
                continue
            is_channel = isinstance(entity, Channel) and entity.broadcast
            if target_filter == "groups" and is_channel:
                continue
            if target_filter == "channels" and not is_channel:
                continue
            name = (entity.title or "").lower()
            if any(b.strip().lstrip("@").lower() in name for b in blacklist if b.strip()):
                continue
            if entity.id in excluded_ids:
                continue
            targets.append(entity)

        group_count = len(targets)
        for entity in targets:
            try:
                await client.send_message(entity, message)
                sent += 1
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds + 5)
                try:
                    await client.send_message(entity, message)
                    sent += 1
                except Exception:
                    failed += 1
            except (UserPrivacyRestrictedError, Exception):
                failed += 1
            await asyncio.sleep(delay_seconds)
    except Exception as e:
        logger.error(f"send_ads_to_groups error: {e}")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
    return sent, failed, group_count


# ─── Auto Reply ───────────────────────────────────────────────────────────────

async def setup_auto_reply(
    user_id: int,
    phone: str,
    session_string: str,
    reply_message: str,
    bot,
    get_last_active_fn,
    inactivity_minutes: int = 30,
    get_auto_reply_settings_fn=None,
) -> bool:
    key = f"{user_id}_{phone}"
    existing_client = _active_clients.get(key)
    existing_task = _auto_reply_tasks.get(key)
    if (
        existing_client
        and existing_task
        and not existing_task.done()
        and existing_client.is_connected()
    ):
        return True
    if existing_client or existing_task:
        await teardown_auto_reply(user_id, phone)

    client = _make_client(StringSession(session_string))
    try:
        await client.connect()
        if not await client.is_user_authorized():
            return False
    except Exception as e:
        logger.error(f"Auto-reply client connect error for {phone}: {e}")
        return False

    # Register the event explicitly instead of relying on decorator state.
    # This keeps the handler attached when a persistent client reconnects.
    async def handler(event):
        try:
            import datetime
            if not event.is_private:
                return
            current_message = reply_message
            current_inactive_minutes = inactivity_minutes
            if get_auto_reply_settings_fn:
                settings = await get_auto_reply_settings_fn(user_id) or {}
                if not settings.get("auto_reply_enabled", False):
                    return
                current_message = settings.get("auto_reply_message") or reply_message
                current_inactive_minutes = int(
                    settings.get("auto_reply_inactive_minutes") or inactivity_minutes
                )
            last_active = await get_last_active_fn(user_id)
            if last_active:
                now = datetime.datetime.now(datetime.timezone.utc)
                if last_active.tzinfo is None:
                    now = now.replace(tzinfo=None)
                diff = (now - last_active).total_seconds()
                if diff < current_inactive_minutes * 60:
                    return
            await event.reply(current_message)
            logger.info(
                "Auto-reply sent for user %s via account %s",
                user_id,
                phone,
            )
        except Exception as ex:
            logger.exception("Auto-reply error for account %s: %s", phone, ex)

    client.add_event_handler(handler, events.NewMessage(incoming=True))
    _active_clients[key] = client
    stop_event = asyncio.Event()
    _auto_reply_stop_events[key] = stop_event
    _auto_reply_tasks[key] = asyncio.create_task(
        _keep_auto_reply_connected(key, client, stop_event),
        name=f"auto-reply-{user_id}-{phone}",
    )
    return True


async def _keep_auto_reply_connected(key, client, stop_event):
    """Keep an auto-reply client alive across transient Telegram disconnects."""
    while not stop_event.is_set():
        try:
            if not client.is_connected():
                await client.connect()
            if not await client.is_user_authorized():
                logger.error("Auto-reply account is no longer authorized: %s", key)
                break
            await client.run_until_disconnected()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Auto-reply connection failed for %s: %s", key, exc)

        if not stop_event.is_set():
            await asyncio.sleep(5)

    if not stop_event.is_set():
        _active_clients.pop(key, None)
        _auto_reply_tasks.pop(key, None)
        _auto_reply_stop_events.pop(key, None)


async def teardown_auto_reply(user_id: int, phone: str):
    key = f"{user_id}_{phone}"
    stop_event = _auto_reply_stop_events.pop(key, None)
    if stop_event:
        stop_event.set()
    task = _auto_reply_tasks.pop(key, None)
    if task and task is not asyncio.current_task():
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    client = _active_clients.pop(key, None)
    if client:
        try:
            await client.disconnect()
        except Exception:
            pass


async def teardown_all_auto_reply(user_id: int):
    to_remove = [k for k in _active_clients if k.startswith(f"{user_id}_")]
    to_remove.extend(
        key for key in _auto_reply_tasks
        if key.startswith(f"{user_id}_") and key not in to_remove
    )
    for key in to_remove:
        _, phone = key.split("_", 1)
        await teardown_auto_reply(user_id, phone)
