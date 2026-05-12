# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
import logging
import os


def get_logger(name: str) -> logging.Logger:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    return logging.getLogger(name)
