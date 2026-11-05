from datetime import datetime
from uuid import UUID

from src.notifications.base import NotificationProvider


class FakeNotificationProvider(NotificationProvider):

    def __init__(self):
        self.called = False
        self.question = None
        self.conversation_id = None
        self.reason = None

    async def send_escalation(
        self,
        question: str,
        conversation_id: UUID,
        reason: str,
        created_at: datetime
    ):
        self.called = True
        self.question = question
        self.conversation_id = conversation_id
        self.reason = reason


class FailNotificationProvider(NotificationProvider):

    def __init__(self):
        self.called = False

    async def send_escalation(
        self,
        question: str,
        conversation_id: UUID,
        reason: str,
        created_at: datetime
    ):
        self.called = True

        raise Exception("Test notification error")