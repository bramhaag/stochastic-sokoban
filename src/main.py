import argparse
import decimal
import logging
import os.path
import sys
from collections import defaultdict

from generator.jani_generators import JaniBoxGenerator, JaniPosGenerator
from generator.prism_generators import PrismBoxGenerator, PrismPosGenerator, PrismNonDGenerator, PrismSNonDGenerator
from parser.parsers import SokParser

PARSERS = {
    "sok": SokParser
}

GENERATORS = {
    "jani-box": JaniBoxGenerator,
    "jani-pos": JaniPosGenerator,
    "prism-box": PrismBoxGenerator,
    "prism-pos": PrismPosGenerator,
    "prism-nd": PrismNonDGenerator,
    "prism-snd": PrismSNonDGenerator
}


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
                      choices=PARSERS.keys(), default="sok",
                      help="parser type (default: %(default)s)")
required.add_argument("-m", "--model",
                      type=str,
                      choices=GENERATORS.keys(),
                      required=True,
                      help="model type")
optional.add_argument("-x", "--probabilities",
                      type=lambda s: [item for item in s.split(",")],
                      default="u=0.125,U=0.125,d=0.125,D=0.125,l=0.125,L=0.125,r=0.125,R=0.125,b=0",
                      help="probabilities of an action happening. "
                           "Values do not need to add up to 1, they are ..??"
                           "Available actions are: (u)p, (d)own, (l)eft, (r)ight, (b)ox "
                           "(default: %(default)s)")
optional.add_argument("-e", "--precision",
                      type=int,
                      default=28,
                      help="precision of floating point numbers (default: %(default)s)")
optional.add_argument("--debug",
                      action="store_true",
                      help="enable debug logging")
optional.add_argument("-h", "--help",
                      action="help",
                      help="show this help message and exit"
                      )

args = arg_parser.parse_args()

if args.debug:
    logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.DEBUG)
else:
    logging.basicConfig(format="%(levelname)s: %(message)s")

# Read input
if args.input is not None:
    try:
        with open(args.input, "r") as file:
            text = file.read()
    except FileNotFoundError:
        exit_with_error("File not found: " + args.input)
else:
    text = sys.stdin.read().rstrip()

# Set parser and generator
parser = PARSERS[args.parser]()
logging.debug(f"Using parser: {type(parser)}")

generator = GENERATORS[args.model]()
logging.debug(f"Using generator: {type(generator)}")

# Parse probabilities
decimal.getcontext().prec = args.precision

probabilities = {}
for p in args.probabilities:
    parts = p.strip().split("=")
    if len(parts) > 2:
        exit_with_error(f"Invalid probability: '{p}' contains more than 1 value")

    key, value = parts
    if key.lower() not in {"u", "d", "l", "r", "b"}:
        exit_with_error(f"Invalid probability: '{p}' has an invalid key")

    if key in probabilities:
        exit_with_error(f"Probability with key '{key}' defined multiple times")

    try:
        probabilities[key] = decimal.Decimal(value)
    except ValueError:
        exit_with_error(f"Invalid probability: '{p}' has an invalid value")

# Balance probabilities
probabilities = defaultdict(lambda: 0, {k: v / sum(probabilities.values()) for k, v in probabilities.items()})
logging.debug(f"Using probabilities: {dict(probabilities)}")

levels = parser.parse_levels(text)
if len(levels) == 0:
    exit_with_error("No parseable levels found in input")

logging.debug(f"Found {len(levels)} levels")

if not args.output:
    if len(levels) > 1:
        exit_with_error("Can only write one model to stdout. Specify an output file with --output instead.")

    if args.force:
        logging.warning("Argument --force ignored as no output file is specified")

    print(generator.generate_model(levels[0], probabilities))
else:
    for i, level in enumerate(levels):
        model = generator.generate_model(level, probabilities)
        file_name, extension = os.path.splitext(args.output)

        path = f"{file_name}_{i}{extension}"
        if os.path.exists(path) and not args.force:
            logging.warning(f"File '{path}' already exists. Run with the --force flag to overwrite files.")

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w+") as file:
            file.write(model)

        logging.debug("Wrote " + path)
