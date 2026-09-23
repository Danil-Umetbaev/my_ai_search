from fastapi import HTTPException, status
class BaseException(Exception):
    detail = 'Не ехала что-ли...'
    def __init__(self, *args, **kwargs):
        super().__init__(self.detail, *args, **kwargs)


class BaseHTTPException(HTTPException):
    status_code = 500
    detail = None

    def __init__(self):
        super().__init__(status_code=self.status_code, detail=self.detail)

class NoResultFoundException(BaseException):
    detail = 'Объект не найден'

class TooMuchResultFoundException(BaseException):
    detail = 'Слишком много объектов найдено'

class ObjectAlreadyExistsException(BaseException):
    detail = "Похожий объект уже существует"


#############################################################
class ExampleNotFoundException(BaseException):
    detail = "Нет такого примера"

class ExampleNotFoundHTTPException(BaseHTTPException):
    detail = "Нет такого примера"
    status_code = 404


class TooMuchExampleFoundException(BaseException):
    detail = 'Слишком много примеров найдено'

class TooMuchExampleFoundHTTPException(BaseHTTPException):
    detail = 'Слишком много примеров найдено'
    status_code = 409


class NoConversationFoundException(BaseException):
    detail = 'Нет такой беседы'

class NoConversationFoundHTTPException(BaseHTTPException):
    detail = 'Нет такой беседы'
    status_code = 404

