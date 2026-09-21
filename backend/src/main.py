import logging
import uvicorn
from fastapi import FastAPI

from contextlib import asynccontextmanager

from fastapi.openapi.docs import (
    get_swagger_ui_html,
)


import sys
from pathlib import Path


sys.path.append(str(Path(__file__).parent.parent))

from database import Base, engine
from src.api.v1.router import router as main_router
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # await redis_manager.connect()
    # FastAPICache.init(RedisBackend(redis_manager.redis), prefix="fastapi-cache")
    yield
    # await redis_manager.close()


app = FastAPI(docs_url=None, redoc_url=None, lifespan=lifespan)
app.include_router(main_router)


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css",
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host='0.0.0.0', reload=True)
