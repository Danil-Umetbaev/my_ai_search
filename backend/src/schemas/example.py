from pydantic import BaseModel, Field




class ExampleCreateSchema(BaseModel):
    title: str
    price: int

class ExampleUpdateSchema(ExampleCreateSchema):
    pass

class ExampleSchema(ExampleCreateSchema):
    id: int

class ExamplePatchSchema(BaseModel):
    title: str | None = Field(None)
    price: int | None = Field(None)
