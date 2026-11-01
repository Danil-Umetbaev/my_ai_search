from fastapi import HTTPException


class AppException(Exception):
    detail = "Произошла ошибка приложения"

    def __init__(self, *args, **kwargs):
        super().__init__(
            self.detail,
            *args,
            **kwargs
        )


class BaseHTTPException(HTTPException):
    status_code = 500
    code = "INTERNAL_ERROR"
    detail = "Внутренняя ошибка сервера"

    def __init__(self):
        super().__init__(
            status_code=self.status_code,
            detail=self.detail
        )


# ==========================================
# DOMAIN / REPOSITORY
# ==========================================

class NoResultFoundException(AppException):
    detail = "Объект не найден"


class TooMuchResultFoundException(AppException):
    detail = "Слишком много объектов найдено"


class ObjectAlreadyExistsException(AppException):
    detail = "Похожий объект уже существует"


class DataIntegrityException(AppException):
    detail = "Нарушена целостность данных"


class DatabaseException(AppException):
    detail = "Ошибка при работе с базой данных"


class UserAlreadyExistsException(AppException):
    detail = "Похожий пользователь уже есть"

class UserNotFoundException(AppException):
    detail = "Нет такого пользователя"

class InvalidPasswordException(AppException):
    detail = "Неверный пароль"


# ==========================================
# CHAT / APPLICATION
# ==========================================

class NoConversationFoundException(AppException):
    detail = "Нет такой беседы"

class NoEscalationFoundException(AppException):
    detail = "Нет такой эскалации"

class NoDocumentFoundException(AppException):
    detail = "Нет такого документа"

class NoUserFoundException(AppException):
    detail = "Нет такого пользователя"


class RAGProcessingException(AppException):
    detail = "Не удалось обработать запрос"


class AIServiceUnavailableException(AppException):
    detail = "AI-сервис временно недоступен"


# ==========================================
# HTTP
# ==========================================

class NoConversationFoundHTTPException(BaseHTTPException):
    status_code = 404
    code = "CONVERSATION_NOT_FOUND"
    detail = "Нет такой беседы"

class NoEscalationFoundHTTPException(BaseHTTPException):
    status_code = 404
    code = "ESCALATION_NOT_FOUND"
    detail = "Нет такой эскалации"

class NoDocumentFoundHTTPException(BaseHTTPException):
    status_code = 404
    code = "DOCUMENT_NOT_FOUND"
    detail = "Нет такого документа"

class NoUserFoundHTTPException(BaseHTTPException):
    status_code = 404
    code = "USER_NOT_FOUND"
    detail = "Нет такого пользователя"


class RAGProcessingHTTPException(BaseHTTPException):
    status_code = 500
    code = "RAG_PROCESSING_ERROR"
    detail = "Не удалось обработать запрос"


class AIServiceUnavailableHTTPException(BaseHTTPException):
    status_code = 503
    code = "AI_SERVICE_UNAVAILABLE"
    detail = "AI-сервис временно недоступен"


class DatabaseHTTPException(BaseHTTPException):
    status_code = 500
    code = "DATABASE_ERROR"
    detail = "Внутренняя ошибка сервера"



class UserEmailAlreadyExistsHTTPException(BaseHTTPException):
    detail = "Пользователь с таким email уже есть"
    code ='USER_EXISTS'
    status_code = 409

class UserNotFoundHTTPException(BaseHTTPException):
    detail = "Нет такого пользователя"
    code ='USER_NOT_FOUND'
    status_code = 404

class UserNotAuthenticatedHTTPException(BaseHTTPException):
    status_code = 401
    code ='UNAUTHORAZED'
    detail = "Вы не аутенфицированы в системе"


class InvalidPasswordHTTPException(BaseHTTPException):
    detail = "Неверный пароль"
    code ='INVALID_PASSWORD'
    status_code = 401


class PermissionHTTPError(BaseHTTPException):
    detail = 'У вас недостаточно прав для просмотра данной страницы'
    code = 'PERMISSION_ERROR'
    status_code = 403

class AdminConflictException(AppException):
    detail = "Операция конфликтует с существующими данными или связанными записями"


class AdminConflictHTTPException(BaseHTTPException):
    detail = "Операция конфликтует с существующими данными или связанными записями"
    status_code = 409
    code = "ADMIN_CONFLICT"


class AdminStorageException(AppException):
    detail = "Не удалось выполнить операцию с данными"


class AdminStorageHTTPException(BaseHTTPException):
    detail = "Не удалось выполнить операцию с данными"
    status_code = 500
    code = "ADMIN_STORAGE_ERROR"


class DocumentImportException(AppException):
    detail = "Не удалось загрузить документ из источника"


class DocumentImportHTTPException(BaseHTTPException):
    detail = "Не удалось загрузить документ из источника"
    status_code = 502
    code = "DOCUMENT_IMPORT_ERROR"


class DocumentIndexingException(AppException):
    detail = "Не удалось построить индекс документа. Изменения отменены"


class DocumentIndexingHTTPException(BaseHTTPException):
    detail = "Не удалось построить индекс документа. Изменения отменены"
    status_code = 503
    code = "DOCUMENT_INDEXING_ERROR"
