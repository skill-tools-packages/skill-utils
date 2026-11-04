"""Config loading, logging setup, and retry logic for Claude skills."""

import json
import logging
import os
import random
import time
from functools import wraps


def load_config(path=None):
    """Load configuration from a JSON file or environment variable.

    Tries in order: explicit path > SKILL_CONFIG env var > ./skill.json.
    Returns an empty dict if no config is found anywhere.
    """
    paths = [p for p in (path, os.environ.get("SKILL_CONFIG"), "./skill.json") if p]
    for cfg_path in paths:
        try:
            with open(cfg_path) as f:
                return json.load(f)
        except (FileNotFoundError, IsADirectoryError):
            continue
    return {}


def setup_logging(name="skill_utils", level=logging.INFO):
    """Configure and return a logger for skill execution."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] %(name)s [%(levelname)s]: %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


def retry(max_attempts=3, backoff_factor=1.0, exceptions=(Exception,), logger=None, max_delay=60.0):
    """Decorator that retries a function on specified exceptions.

    Waits `backoff_factor * 2**(attempt-1)` seconds between attempts, capped at `max_delay`
    and randomly shortened by up to half so concurrent callers don't retry in lockstep.

    The `anthropic` SDK already retries rate limits, server errors, and connection failures
    itself (`max_retries`, default 2); wrapping SDK calls in this multiplies the attempts.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if logger is None:
        logger = setup_logging()

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    logger.warning("Attempt %d/%d failed (%s). Retrying...",
                                   attempt, max_attempts, type(e).__name__, exc_info=e)
                    if attempt < max_attempts:
                        delay = min(max_delay, backoff_factor * (2 ** (attempt - 1)))
                        time.sleep(delay * random.uniform(0.5, 1.0))
            raise last_exception

        return wrapper
    return decorator