import logging
import sys
def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s", stream=sys.stdout)
def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)