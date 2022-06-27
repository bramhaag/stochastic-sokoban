import logging

BYTE_UNITS = {
    "B": 1024 ** 0,
    "KB": 1024 ** 1,
    "MB": 1024 ** 2,
    "GB": 1024 ** 3,
}


def exit_with_error(message: str):
    logging.error(message)
    exit(-1)


def convert_size(size: int, from_unit: str, to_unit: str) -> int:
    return size * BYTE_UNITS[from_unit] // BYTE_UNITS[to_unit]
