from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

import requests


@dataclass(frozen=True)
class TelegramMessage:
    chat_id: int
    chat_type: str
    user_id: int
    username: Optional[str]
    message_id: int
    text: str
    reply_to_message_from_username: Optional[str]
    is_reply_to_bot: bool


def _telegram_api_base(token: str) -> str:
    return f"https://api.telegram.org/bot{token}"


def get_bot_username(token: str, timeout_s: float = 5.0) -> Optional[str]:
    try:
        resp = requests.get(f"{_telegram_api_base(token)}/getMe", timeout=timeout_s)
        if resp.status_code != 200:
            return None
        payload = resp.json()
        if not payload.get("ok"):
            return None
        return payload.get("result", {}).get("username")
    except Exception:
        return None


def send_message(
    token: str,
    chat_id: int,
    text: str,
    reply_to_message_id: Optional[int] = None,
    timeout_s: float = 7.0,
) -> bool:
    data: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_to_message_id is not None:
        data["reply_to_message_id"] = reply_to_message_id

    try:
        resp = requests.post(
            f"{_telegram_api_base(token)}/sendMessage",
            json=data,
            timeout=timeout_s,
        )
        return resp.status_code == 200 and bool(resp.json().get("ok"))
    except Exception:
        return False


def parse_update(update: dict[str, Any], bot_username: Optional[str]) -> Optional[TelegramMessage]:
    message = update.get("message")
    if not isinstance(message, dict):
        return None
    text = message.get("text")
    if not isinstance(text, str) or not text.strip():
        return None

    chat = message.get("chat") or {}
    from_user = message.get("from") or {}

    chat_id = chat.get("id")
    chat_type = chat.get("type")
    user_id = from_user.get("id")
    message_id = message.get("message_id")
    username = from_user.get("username")

    if not isinstance(chat_id, int) or not isinstance(user_id, int) or not isinstance(message_id, int):
        return None
    if not isinstance(chat_type, str):
        return None

    reply_to = message.get("reply_to_message") or {}
    reply_from = reply_to.get("from") or {}
    reply_to_username = reply_from.get("username")
    is_reply_to_bot = bool(bot_username and reply_to_username and reply_to_username.lower() == bot_username.lower())

    return TelegramMessage(
        chat_id=chat_id,
        chat_type=chat_type,
        user_id=user_id,
        username=username if isinstance(username, str) else None,
        message_id=message_id,
        text=text,
        reply_to_message_from_username=reply_to_username if isinstance(reply_to_username, str) else None,
        is_reply_to_bot=is_reply_to_bot,
    )


def eligible_to_respond(msg: TelegramMessage, bot_username: Optional[str]) -> bool:
    if msg.chat_type in {"private"}:
        return True

    if msg.chat_type not in {"group", "supergroup"}:
        return False

    text = msg.text.strip()
    if text.startswith("/ask"):
        return True
    if msg.is_reply_to_bot:
        return True

    if bot_username:
        mention = f"@{bot_username}".lower()
        if mention in text.lower():
            return True

    return False


_ASK_PREFIX_RE = re.compile(r"^/ask(?:@\w+)?\s*", re.IGNORECASE)


def clean_user_text(text: str, bot_username: Optional[str]) -> str:
    cleaned = _ASK_PREFIX_RE.sub("", text).strip()
    if bot_username:
        cleaned = re.sub(rf"@{re.escape(bot_username)}\b", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned

