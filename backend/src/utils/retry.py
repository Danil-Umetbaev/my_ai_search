import logging
import time
from collections.abc import Callable
from typing import TypeVar


logger = logging.getLogger(__name__)

T = TypeVar("T")


def load_with_retry(
    loader: Callable[[], T],
    name: str,
    attempts: int = 3,
    delay: int = 5,
) -> T:

    last_exception = None

    for attempt in range(1, attempts + 1):
        try:
            logger.info(
                "Loading %s | attempt=%s/%s",
                name,
                attempt,
                attempts,
            )

            result = loader()

            logger.info(
                "%s loaded successfully",
                name,
            )

            return result

        except Exception as ex:
            last_exception = ex

            logger.exception(
                "Failed to load %s | attempt=%s/%s",
                name,
                attempt,
                attempts,
            )

            if attempt < attempts:
                wait_time = delay * attempt

                logger.info(
                    "Retrying %s in %s seconds",
                    name,
                    wait_time,
                )

                time.sleep(wait_time)

    logger.critical(
        "Unable to load %s after %s attempts",
        name,
        attempts,
    )

    raise last_exception