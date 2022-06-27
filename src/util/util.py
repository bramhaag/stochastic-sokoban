import logging


def exit_with_error(message: str):
    logging.error(message)
    exit(-1)
