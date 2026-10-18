import logging
from uuid import UUID

from src.models.enums import Status
from src.notifications.base import NotificationProvider
from src.schemas.escalations import (
    EscalationAddSchema,
    EscalationUpdateSchema
)
from src.services.base import BaseService


logger = logging.getLogger(__name__)


class EscalationService(BaseService):

    def __init__(
        self,
        db,
        notification_provider: NotificationProvider | None
    ):
        super().__init__(db)

        self.notification_provider = notification_provider

    @property
    def enabled(self) -> bool:
        return self.notification_provider is not None

    async def escalate(
        self,
        conversation_id: UUID,
        question: str,
        reason: str
    ):
        escalation = await self.db.escalations.add(
            EscalationAddSchema(
                conversation_id=conversation_id,
                question=question,
                reason=reason,
                status=Status.pending
            )
        )

        await self.db.commit()

        logger.info(
            "Escalation created | escalation_id=%s | conversation_id=%s",
            escalation.id,
            conversation_id
        )

        try:
            await self.notification_provider.send_escalation(
                question=question,
                conversation_id=conversation_id,
                reason=reason,
                created_at=escalation.created_at
            )

            await self.db.escalations.edit(
                EscalationUpdateSchema(
                    status=Status.sent
                ),
                id=escalation.id
            )

            await self.db.commit()

            logger.info(
                "Escalation sent | escalation_id=%s",
                escalation.id
            )

        except Exception:
            logger.exception(
                "Escalation notification failed | escalation_id=%s",
                escalation.id
            )

            await self.db.escalations.edit(
                EscalationUpdateSchema(
                    status=Status.failed
                ),
                id=escalation.id
            )

            await self.db.commit()

        return await self.db.escalations.get_one(
            id=escalation.id
        )
