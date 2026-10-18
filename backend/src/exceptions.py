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


# ==========================================
# CHAT / APPLICATION
# ==========================================

class NoConversationFoundException(AppException):
    detail = "Нет такой беседы"


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