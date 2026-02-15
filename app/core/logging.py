import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """
    Configure application logging.

    - Logs go to stdout (best for Docker/K8s/CI).
    - Uses a consistent format.
    - Aligns uvicorn log levels with app log level.
    """
    level = (level or "INFO").upper()

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Keep uvicorn loggers aligned
    logging.getLogger("uvicorn.error").setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(level)
