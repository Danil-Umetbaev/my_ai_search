from fastapi import APIRouter, Response
from src.api.dependencies import UserDataDep
from src.schemas.users import UserRequestAdd, UserAdd, UserLogin
from src.services.auth import AuthService
from src.api.dependencies import DBDep
from src.exceptions import UserEmailAlreadyExistsHTTPException, UserAlreadyExistsException, UserNotFoundException, \
    UserNotFoundHTTPException, InvalidPasswordException, InvalidPasswordHTTPException

auth_router = APIRouter(prefix="/auth", tags=["Авторизация и аутенфикация"])


@auth_router.post("/register")
async def register_user(data: UserRequestAdd, db: DBDep):
    try:
        await AuthService(db).register_user(data)
    except UserAlreadyExistsException:
        raise UserEmailAlreadyExistsHTTPException
    return {"status": "OK"}


@auth_router.post("/login")
async def login_user(data: UserLogin, response: Response, db: DBDep):
    try:
        await AuthService(db).login_user(data, response)
    except UserNotFoundException:
        raise UserNotFoundHTTPException
    except InvalidPasswordException:
        raise InvalidPasswordHTTPException
    return {"status": 'OK'}


@auth_router.get("/me")
async def get_me(user_data: UserDataDep, db: DBDep, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return await AuthService(db).get_me(user_data.id)


@auth_router.delete("/logout")
async def logout_user(response: Response):
    await AuthService().logout_user(response)
    return {"status": "OK"}
