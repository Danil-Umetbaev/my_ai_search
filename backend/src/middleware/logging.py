import logging
from time import perf_counter

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


logger = logging.getLogger("api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        start = perf_counter()

        try:
            response = await call_next(request)

            duration = perf_counter() - start

            logger.info(
                "%s %s | status=%s | duration=%.2fs",
                request.method,
                request.url.path,
                response.status_code,
                duration
            )

            return response

        except Exception:
            duration = perf_counter() - start

            logger.exception(
                "%s %s | failed | duration=%.2fs",
                request.method,
                request.url.path,
                duration
            )

            raise