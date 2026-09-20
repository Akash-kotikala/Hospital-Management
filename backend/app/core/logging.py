import logging
import sys
import contextvars
from typing import Optional

# Context variable for request correlation tracking
correlation_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("correlation_id", default=None)
operation_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("operation_id", default=None)


class StructuredLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_ctx.get() or "system"
        record.operation_id = operation_id_ctx.get() or "none"
        return True


def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [corr=%(correlation_id)s] [op=%(operation_id)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    handler.addFilter(StructuredLogFilter())

    # Avoid duplicate handlers on reload
    logger.handlers.clear()
    logger.addHandler(handler)

    # Silence verbose 3rd party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


logger = logging.getLogger("healthcare_platform")
