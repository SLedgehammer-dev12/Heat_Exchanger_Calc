import logging
import os
import tempfile
from logging.handlers import RotatingFileHandler

from config import LOG_FILE_BACKUP_COUNT, LOG_FILE_MAX_BYTES

NOISY_LOGGERS = {
    "matplotlib": logging.WARNING,
    "matplotlib.font_manager": logging.WARNING,
    "PIL": logging.WARNING,
    "PIL.PngImagePlugin": logging.WARNING,
    "urllib3": logging.WARNING,
}


def get_log_dir():
    """Return a writable log directory, or None if none is available.

    On restricted environments (e.g. macOS sandbox, read-only HOME) the
    makedirs / write may fail; this never raises, so importing the app does
    not crash. Falls back to the system temp directory.
    """
    candidates = [
        os.environ.get("LOCALAPPDATA"),
        os.path.expanduser("~"),
    ]
    for base_dir in candidates:
        if not base_dir:
            continue
        log_dir = os.path.join(base_dir, "HeatExchangerCalc", "logs")
        try:
            os.makedirs(log_dir, exist_ok=True)
            probe = os.path.join(log_dir, ".write_probe")
            with open(probe, "w", encoding="utf-8") as _f:
                _f.write("")
            os.remove(probe)
            return log_dir
        except OSError:
            continue
    try:
        log_dir = os.path.join(tempfile.gettempdir(), "HeatExchangerCalc", "logs")
        os.makedirs(log_dir, exist_ok=True)
        return log_dir
    except OSError:
        return None


def setup_logging(app_mode="app"):
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    configure_third_party_loggers()

    for handler in root_logger.handlers:
        if getattr(handler, "_heat_exchanger_file_handler", False):
            return handler.baseFilename

    log_dir = get_log_dir()
    if log_dir is not None:
        log_file = os.path.join(log_dir, "heat_exchanger_calc.log")
        try:
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=LOG_FILE_MAX_BYTES,
                backupCount=LOG_FILE_BACKUP_COUNT,
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
        except OSError:
            root_logger.handlers = [h for h in root_logger.handlers if not getattr(h, "_heat_exchanger_file_handler", False)]

    # Fallback: log to stderr only (never crash on a filesystem problem).
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    console.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
    )
    root_logger.addHandler(console)
    logging.getLogger(__name__).info("Logging to console (file log unavailable): %s", app_mode)
    return "console"


def configure_third_party_loggers():
    for logger_name, level in NOISY_LOGGERS.items():
        logging.getLogger(logger_name).setLevel(level)
