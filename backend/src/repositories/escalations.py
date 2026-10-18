from src.repositories.base import BaseRepository
from src.repositories.mappers.mappers import EscalationDataMapper
from src.models.escalations import EscalationORM

class EscalationRepository(BaseRepository):
    mapper = EscalationDataMapper
    model = EscalationORM
