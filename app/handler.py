from __future__ import annotations

import base64
import json
import logging
from typing import Any, Optional

from .config import ConfigError, load_config
from .inference import run_inference
from .storage import DynamoStores
from .telegram_api import (
    clean_user_text,
    eligible_to_respond,
    get_bot_username,
    parse_update,
    send_message,
)


logger = logging.getLogger()
logger.setLevel(logging.INFO)

_CACHED_BOT_USERNAME: Optional[str] = None


def _http_method(event: dict[str, Any]) -> Optional[str]:
    rc = event.get("requestContext") or {}
    http = rc.get("http") or {}
    method = http.get("method")
    if isinstance(method, str):
        return method.upper()
    return None


def _parse_body(event: dict[str, Any]) -> Optional[dict[str, Any]]:
    body = event.get("body")
    if body is None:
        return None
    if not isinstance(body, str):
        return None
    if event.get("isBase64Encoded") is True:
        try:
            body = base64.b64decode(body).decode("utf-8")
        except Exception:
            return None
    try:
        payload = json.loads(body)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    try:
        method = _http_method(event)
        if method and method != "POST":
            return {"statusCode": 200, "body": "ok"}

        update = _parse_body(event)
        if not update:
            return {"statusCode": 200, "body": "ok"}

        try:
            cfg = load_config()
        except ConfigError:
            return {"statusCode": 200, "body": "ok"}

        global _CACHED_BOT_USERNAME
        if _CACHED_BOT_USERNAME is None:
            _CACHED_BOT_USERNAME = get_bot_username(cfg.telegram_bot_token)

        msg = parse_update(update, _CACHED_BOT_USERNAME)
        if msg is None:
            return {"statusCode": 200, "body": "ok"}

        if not eligible_to_respond(msg, _CACHED_BOT_USERNAME):
            return {"statusCode": 200, "body": "ok"}

        user_text = clean_user_text(msg.text, _CACHED_BOT_USERNAME)
        if not user_text:
            return {"statusCode": 200, "body": "ok"}

        is_group = msg.chat_type in {"group", "supergroup"}

        stores = DynamoStores(cfg.dynamodb_context_table, cfg.dynamodb_log_table)

        try:
            stores.write_context(
                chat_id=msg.chat_id,
                user_id=msg.user_id,
                role="user",
                content=user_text,
                message_id=msg.message_id,
            )
            stores.trim_context(msg.chat_id, keep_last_n=cfg.context_window_size)
        except Exception:
            pass

        try:
            stores.write_training_log(
                chat_id=msg.chat_id,
                user_id=msg.user_id,
                username=msg.username,
                is_group=is_group,
                message_text=user_text,
                bot_reply=None,
                message_id=msg.message_id,
                role="user",
            )
        except Exception:
            pass

        try:
            ctx = stores.read_last_context(msg.chat_id, limit=cfg.context_window_size)
        except Exception:
            ctx = []

        try:
            inf = run_inference(
                openai_api_key=cfg.openai_api_key,
                model=cfg.openai_model,
                system_prompt=cfg.system_prompt,
                context=ctx,
                temperature=0.5,
                max_tokens=512,
                timeout_s=15.0,
            )
            reply_text = inf.reply_text
        except Exception:
            reply_text = "Inference error. Try again."

        try:
            send_message(
                cfg.telegram_bot_token,
                chat_id=msg.chat_id,
                text=reply_text,
                reply_to_message_id=msg.message_id if is_group else None,
            )
        except Exception:
            pass

        try:
            stores.write_context(
                chat_id=msg.chat_id,
                user_id=0,
                role="assistant",
                content=reply_text,
                message_id=msg.message_id + 1,
            )
            stores.trim_context(msg.chat_id, keep_last_n=cfg.context_window_size)
        except Exception:
            pass

        try:
            stores.write_training_log(
                chat_id=msg.chat_id,
                user_id=0,
                username=_CACHED_BOT_USERNAME,
                is_group=is_group,
                message_text=None,
                bot_reply=reply_text,
                message_id=msg.message_id + 1,
                role="assistant",
            )
        except Exception:
            pass

        return {"statusCode": 200, "body": "ok"}
    except Exception:
        return {"statusCode": 200, "body": "ok"}

