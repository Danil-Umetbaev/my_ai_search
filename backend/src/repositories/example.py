from src.repositories.base import BaseRepository
from src.models.example import ExampleORM
from src.repositories.mappers.mappers import ExampleDataMapper
class ExampleRepository(BaseRepository):
    mapper = ExampleDataMapper
    model = ExampleORM