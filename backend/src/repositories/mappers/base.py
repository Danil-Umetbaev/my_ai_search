from typing import Type

from pydantic import BaseModel
from src.database import Base


class DataMapper:
    db_model: Type[Base]
    schema: Type[BaseModel]

    @classmethod
    def map_to_domain_entity(cls, db_model):
        return cls.schema.model_validate(db_model, from_attributes=True)

    @classmethod
    def map_ro_persistance_entity(cls, schema: BaseModel):
        return cls.db_model(**schema.model_dump())
