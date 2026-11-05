import logging
import secrets
from datetime import datetime
from uuid import UUID

import httpx

from src.notifications.base import NotificationProvider


logger = logging.getLogger(__name__)


class VKNotificationProvider(NotificationProvider):

    def __init__(
        self,
        token: str,
        peer_id: int,
        group_id: int,
        api_version: str
    ):
        self.token = token
        self.peer_id = peer_id
        self.group_id = group_id
        self.api_version = api_version

    async def send_escalation(
        self,
        question: str,
        conversation_id: UUID,
        reason: str,
        created_at: datetime
    ):
        message = (
            "⚠ Новый нерешённый вопрос\n"
            f"Вопрос: {question}\n"
            f"Дата: {created_at}\n"
            f"Conversation: {conversation_id}\n"
            f"Причина: {reason}"
        )

        data = {
            "access_token": self.token,
            "peer_id": self.peer_id,
            "group_id": self.group_id,
            "message": message,
            "random_id": secrets.randbelow(2_147_483_647) + 1,
            "v": self.api_version
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.vk.com/method/messages.send",
                data=data
            )

            response.raise_for_status()

            result = response.json()

            if "error" in result:
                error = result["error"]

                error_code = error.get("error_code")
                error_msg = error.get("error_msg")

                raise RuntimeError(
                    f"VK API error {error_code}: {error_msg}"
                )

        logger.info(
            "VK notification sent | conversation_id=%s",
            conversation_id
        )