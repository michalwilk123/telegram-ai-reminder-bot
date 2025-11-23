import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def create_logger(log_dir: Path, logger_name: str, verbose: bool) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(logger_name)
    if logger.handlers:
        return logger

    log_level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(log_level)

    handler = RotatingFileHandler(log_dir / 'application.log', maxBytes=1_000_000, backupCount=3)
    handler.setLevel(log_level)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%m/%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger


def create_log_function(logger: logging.Logger):
    def log_message(message: str, level: str):
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(message)

    return log_message
