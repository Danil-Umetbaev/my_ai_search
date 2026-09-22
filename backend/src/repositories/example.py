from src.repositories.base import BaseRepository
from backend.src.models.documents import ExampleORM
from src.repositories.mappers.mappers import ExampleDataMapper
class ExampleRepository(BaseRepository):
    mapper = ExampleDataMapper
    model = ExampleORM