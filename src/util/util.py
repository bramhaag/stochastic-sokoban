import logging


def exit_with_error(message: str):
    logging.error(message)
    exit(-1)


def convert_size(size, from_unit, to_unit):
    units = {
        "B": 1024 ** 0,
        "KB": 1024 ** 1,
        "MB": 1024 ** 2,
        "GB": 1024 ** 3,
    }

    return size * units[from_unit] // units[to_unit]
