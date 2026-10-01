from src.models.documents import DocumentORM
from src.repositories.mappers.mappers import DocumentDataMapper
from src.repositories.base import BaseRepository


class DocumentRepository(BaseRepository):
    mapper = DocumentDataMapper
    model = DocumentORM