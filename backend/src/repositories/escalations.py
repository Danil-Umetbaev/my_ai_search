from src.repositories.base import BaseRepository
from src.repositories.mappers.mappers import EscalationDataMapper
from src.models.escalations import EscalationORM


class EscalationRepository(BaseRepository):
    mapper = EscalationDataMapper
    model = EscalationORM

    async def get_page(self, limit=50, offset=0, **filter_by):
        return await super().get_page(
            limit,
            offset,
            order_by=(self.model.created_at.desc(), self.model.id),
            **filter_by
        )
