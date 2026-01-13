from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

import boto3
from boto3.dynamodb.conditions import Key


def _now_sortable_ts(message_id: int) -> str:
    ms = int(time.time() * 1000)
    return f"{ms:013d}:{message_id:010d}"


@dataclass(frozen=True)
class ContextEntry:
    chat_id: int
    timestamp: str
    user_id: int
    role: str
    content: str


class DynamoStores:
    def __init__(self, context_table: str, log_table: str):
        dynamodb = boto3.resource("dynamodb")
        self.context = dynamodb.Table(context_table)
        self.log = dynamodb.Table(log_table)

    def write_context(self, chat_id: int, user_id: int, role: str, content: str, message_id: int) -> None:
        self.context.put_item(
            Item={
                "chat_id": str(chat_id),
                "timestamp": _now_sortable_ts(message_id),
                "user_id": str(user_id),
                "role": role,
                "content": content,
            }
        )

    def trim_context(self, chat_id: int, keep_last_n: int, scan_buffer: int = 40) -> None:
        if keep_last_n <= 0:
            return
        limit = keep_last_n + max(1, scan_buffer)
        resp = self.context.query(
            KeyConditionExpression=Key("chat_id").eq(str(chat_id)),
            ScanIndexForward=False,
            Limit=limit,
        )
        items = resp.get("Items") or []
        if len(items) <= keep_last_n:
            return
        to_delete = items[keep_last_n:]
        with self.context.batch_writer() as batch:
            for item in to_delete:
                batch.delete_item(Key={"chat_id": item["chat_id"], "timestamp": item["timestamp"]})

    def read_last_context(self, chat_id: int, limit: int) -> list[ContextEntry]:
        if limit <= 0:
            return []
        resp = self.context.query(
            KeyConditionExpression=Key("chat_id").eq(str(chat_id)),
            ScanIndexForward=False,
            Limit=limit,
        )
        items = resp.get("Items") or []
        items.reverse()
        out: list[ContextEntry] = []
        for item in items:
            out.append(
                ContextEntry(
                    chat_id=int(item.get("chat_id", "0")),
                    timestamp=str(item.get("timestamp", "")),
                    user_id=int(item.get("user_id", "0")),
                    role=str(item.get("role", "")),
                    content=str(item.get("content", "")),
                )
            )
        return out

    def write_training_log(
        self,
        chat_id: int,
        user_id: int,
        username: Optional[str],
        is_group: bool,
        message_text: Optional[str],
        bot_reply: Optional[str],
        message_id: int,
        role: str,
        language: Optional[str] = None,
    ) -> None:
        item: dict[str, Any] = {
            "chat_id": str(chat_id),
            "timestamp": _now_sortable_ts(message_id),
            "user_id": str(user_id),
            "username": username,
            "is_group": bool(is_group),
            "message_text": message_text,
            "bot_reply": bot_reply,
            "role": role,
        }
        if language:
            item["language"] = language
        self.log.put_item(Item=item)
