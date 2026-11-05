from abc import ABC, abstractmethod
from uuid import UUID
from datetime import datetime
class NotificationProvider(ABC):

    @abstractmethod
    async def send_escalation(
        self,
        question: str,
        conversation_id: UUID,
        reason: str,
        created_at: datetime
    ) -> None:
        pass
