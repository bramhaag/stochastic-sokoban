import argparse
import logging
import os.path
import sys
from collections import defaultdict
from decimal import Decimal

from generator.generators import JaniGenerator, PrismGenerator
from parser.parsers import SokParser

logging.basicConfig(format="%(levelname)s: %(message)s")


def exit_with_error(message: str):
    logging.error(message)
    exit(-1)


arg_parser = argparse.ArgumentParser(add_help=False)

required = arg_parser.add_argument_group("required")
optional = arg_parser.add_argument_group("optional")

optional.add_argument("-i", "--input",
                      type=str,
                      help="input file path")
optional.add_argument("-o", "--output",
                      type=str,
                      help="output file path")
optional.add_argument("-f", "--force",
                      action="store_true",
                      help="overwrite output file")
optional.add_argument("-p", "--parser",
                      type=str,
                      choices=["sok"], default="sok",
                      help="parser type (default: %(default)s)")
required.add_argument("-m", "--model",
                      type=str,
                      choices=["jani", "prism"],
                      required=True,
                      help="model type")
optional.add_argument("-x", "--probabilities",
                      type=lambda s: [item for item in s.split(",")],
                      default="u=0.25,d=0.25,l=0.25,r=0.25,b=0",
                      help="probabilities of an action happening. "
                           "Values do not need to add up to 1, they are ..??"
                           "Available actions are: (u)p, (d)own, (l)eft, (r)ight, (b)ox "
                           "(default: %(default)s)")
optional.add_argument("-h", "--help",
                      action="help",
                      help="show this help message and exit"
                      )

args = arg_parser.parse_args()

# Read input
if args.input is not None:
    try:
        with open(args.input, "r") as file:
            text = file.read()
    except FileNotFoundError:
        exit_with_error("File not found: " + args.input)
else:
    text = sys.stdin.read()

# Set parser
match args.parser:
    case "sok":
        parser = SokParser()

# Set generator
match args.model:
    case "jani":
        generator = JaniGenerator()
    case "prism":
        generator = PrismGenerator()

# Parse probabilities
probabilities = {}
for p in args.probabilities:
    parts = p.strip().split("=")
    if len(parts) > 2:
        exit_with_error(f"Invalid probability: '{p}' contains more than 1 value")

    key, value = parts
    if key not in {"u", "d", "l", "r", "b"}:
        exit_with_error(f"Invalid probability: '{p}' has an invalid key")

    if key in probabilities:
        exit_with_error(f"Probability with key '{key}' defined multiple times")

    try:
        probabilities[key] = Decimal(value)
    except ValueError:
        exit_with_error(f"Invalid probability: '{p}' has an invalid value")

# Balance probabilities
probabilities = defaultdict(lambda: 0, {k: v / sum(probabilities.values()) for k, v in probabilities.items()})

# noinspection PyUnboundLocalVariable
level = parser.parse_level(text)
# TODO handle parser errors

# noinspection PyUnboundLocalVariable
model = generator.generate_model(level, probabilities)

if args.output:
    if os.path.exists(args.output) and not args.force:
        exit_with_error("Output file already exists: " + args.output)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w+") as file:
        file.write(model)
else:
    if args.force:
        logging.warning("Argument --force ignored as no output file is specified")

    print(model)
