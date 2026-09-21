from src.models.example import ExampleORM
from src.schemas.example import ExampleSchema
from src.repositories.mappers.base import DataMapper


class ExampleDataMapper(DataMapper):
    db_model = ExampleORM
    schema = ExampleSchema

