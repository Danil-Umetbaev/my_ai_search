import logging
import threading
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.openapi.docs import (
    get_swagger_ui_html,
)
import sys
from pathlib import Path


sys.path.append(str(Path(__file__).parent.parent))

from src.api.v1.router import router as main_router
from src.core.logging import setup_logging
from src.middleware.logging import RequestLoggingMiddleware
from src.exceptions import BaseHTTPException
from src.config import settings
from src.middleware.ai_capacity import AICapacityMiddleware
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.api.dependencies import (
        get_embedding_provider, get_llm_provider, get_reranker_provider,
    )
    app.state.models = {"status": "loading" if settings.LOAD_SEARCH_MODELS else "disabled"}
    def prepare():
        try:
            for load in (get_llm_provider, get_reranker_provider, get_embedding_provider):
                app.state.models["stage"] = load.__name__.removeprefix("get_")
                load()
            app.state.models.update(status="ready", llm=get_llm_provider(), embedding=get_embedding_provider(), reranker=get_reranker_provider())
            app.state.models.pop("stage", None)
            logger.info("Search models ready")
        except Exception:
            app.state.models["status"] = "failed"
            logger.exception("Model initialization failed; support remains available")
    if settings.LOAD_SEARCH_MODELS:
        threading.Thread(target=prepare, daemon=True, name="model-loader").start()
    yield

setup_logging()
logger = logging.getLogger(__name__)
app = FastAPI(docs_url=None, redoc_url=None, lifespan=lifespan,
              openapi_url="/openapi.json" if settings.ENABLE_DOCS else None)

app.add_middleware(CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*']
    )
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(AICapacityMiddleware)
app.include_router(main_router)

@app.middleware("http")
async def require_search_ready(request: Request, call_next):
    if request.url.path.rstrip("/") == "/api/v1/chat/messages":
        if getattr(request.app.state, "models", {}).get("status") != "ready":
            return JSONResponse(status_code=503, content={"code": "AI_SERVICE_UNAVAILABLE", "message": "Поиск подготавливается. Диагностика доступна через Техподдержку."}, headers={"Retry-After": "30"})
    return await call_next(request)

@app.exception_handler(BaseHTTPException)
async def app_http_exception_handler(
    request: Request,
    exc: BaseHTTPException
):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            'code': exc.code,
            'message': exc.detail,
        }
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception
):
    logger.exception(
        "Unhandled exception | method=%s | path=%s",
        request.method,
        request.url.path,
        exc_info=exc
    )

    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "Внутренняя ошибка сервера",
        }
    )
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css",
    )

if settings.ENABLE_DOCS:
    app.add_api_route("/docs", custom_swagger_ui_html, include_in_schema=False)


if __name__ == "__main__":
    uvicorn.run("main:app", host='0.0.0.0', reload=True)
