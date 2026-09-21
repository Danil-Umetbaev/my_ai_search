
from fastapi import APIRouter
from api.dependencies import DBDep
from exceptions import ExampleNotFoundException, TooMuchExampleFoundException, TooMuchExampleFoundHTTPException, ExampleNotFoundHTTPException
from services.example import ExampleService

from src.schemas.example import ExampleCreateSchema, ExamplePatchSchema, ExampleUpdateSchema

router = APIRouter(prefix='/examples', tags=["Примеры"])

@router.get(
    '/',
    summary='Получить все примеры',
    description="Введите параметры для фильтрации и запустите"
)
async def get_examples(
    db: DBDep,
):
    try:
        examples = await ExampleService(db).get_examples()
        return {'status': 'OK', 'data': examples}
    except ExampleNotFoundException:
        raise ExampleNotFoundHTTPException


@router.get(
    '/{id_example}',
    summary='Получить пример',
    description="Введите id примера"
)
async def get_example(
    example_id: int,
    db: DBDep,
):
    try:
        example = await ExampleService(db).get_example(example_id)
        return {'status': 'OK', 'data': example}
    except ExampleNotFoundException:
        raise ExampleNotFoundHTTPException

@router.post(
    '/',
    summary="Добавление примера",
    description="Вводим все параметры и одобавляем пример",
)
async def create_example(
    db: DBDep,
    example: ExampleCreateSchema,
):
    new_example = await ExampleService(db).add_example(example)
    return {'status': 'OK', 'data': new_example}


@router.put(
    "/{id_example}",
    summary="Обновление данных",
    description="Вводим все параметры и обновляем данные",
)
async def update_example(
    id: int,
    example_data: ExampleUpdateSchema,
    db: DBDep,
):
    try:
        await ExampleService(db).update_example(id, example_data)
    except ExampleNotFoundException:
        raise ExampleNotFoundHTTPException
    except TooMuchExampleFoundException:
        raise TooMuchExampleFoundHTTPException
    return {"status": "OK"}


@router.patch(
    "/{id_example}",
    summary="Частичное обновление данных",
    description="Вводим все параметры и обновляем данные",
)
async def partial_update_example(
    id: int,
    example_data: ExamplePatchSchema,
    db: DBDep,
):
    try:
        await ExampleService(db).partial_update_example(id, example_data)
    except ExampleNotFoundException:
        raise ExampleNotFoundHTTPException
    except TooMuchExampleFoundException:
        raise TooMuchExampleFoundHTTPException
    return {"status": "OK"}

@router.delete(
    "/{id_example}",
    summary="Удаление данных",
    description="Удаляем данные",
)
async def delete_hotel(
    id_example: int,
    db: DBDep,
):
    try:
        await ExampleService(db).delete_example(id_example)
    except ExampleNotFoundException:
        raise ExampleNotFoundHTTPException
    except TooMuchExampleFoundException:
        raise TooMuchExampleFoundHTTPException
    return {"status": "OK"}