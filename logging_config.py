import logging
import os
from logging.handlers import RotatingFileHandler


def get_log_dir():
    base_dir = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    log_dir = os.path.join(base_dir, "HeatExchangerCalc", "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def setup_logging(app_mode="app"):
    log_dir = get_log_dir()
    log_file = os.path.join(log_dir, "heat_exchanger_calc.log")
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    for handler in root_logger.handlers:
        if getattr(handler, "_heat_exchanger_file_handler", False):
            return log_file

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler._heat_exchanger_file_handler = True
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
    )
    root_logger.addHandler(file_handler)
    logging.getLogger(__name__).info("Logging initialized for %s: %s", app_mode, log_file)
    return log_file
