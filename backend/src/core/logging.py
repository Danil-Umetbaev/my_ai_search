import inspect
import logging
from functools import wraps
from time import perf_counter


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        force=True
    )

    # Эти библиотеки могут писать полный URL запроса.
    # Для VK это особенно опасно из-за access_token.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Шум от transformers немного уменьшаем.
    logging.getLogger("transformers").setLevel(logging.WARNING)


def log_execution_time(name: str):
    def decorator(func):
        logger = logging.getLogger(func.__module__)

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start = perf_counter()

                try:
                    result = await func(*args, **kwargs)
                except Exception:
                    duration = perf_counter() - start

                    logger.exception(
                        "%s failed | duration=%.2fs",
                        name,
                        duration
                    )
                    raise

                duration = perf_counter() - start

                status = getattr(result, "status", None)
                confidence = getattr(result, "confidence", None)

                extra = ""

                if status is not None:
                    status_value = getattr(status, "value", status)
                    extra += f" | status={status_value}"

                if confidence is not None:
                    extra += f" | confidence={confidence:.4f}"

                logger.info(
                    "%s completed | duration=%.2fs%s",
                    name,
                    duration,
                    extra
                )

                return result

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = perf_counter()

            try:
                result = func(*args, **kwargs)
            except Exception:
                duration = perf_counter() - start

                logger.exception(
                    "%s failed | duration=%.2fs",
                    name,
                    duration
                )
                raise

            duration = perf_counter() - start

            logger.info(
                "%s completed | duration=%.2fs",
                name,
                duration
            )

            return result

        return sync_wrapper

    return decorator