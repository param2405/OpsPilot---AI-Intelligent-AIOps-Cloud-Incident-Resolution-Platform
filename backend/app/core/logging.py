import logging
import sys
from typing import Any


def configure_logging(level: str) -> None:
    """Configure a single, predictable stdout logger for the API process."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric_level)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_extra(**fields: Any) -> dict[str, Any]:
    """Helper for structured key/value extras without introducing a logging library."""
    return fields
