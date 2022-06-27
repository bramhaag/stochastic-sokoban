import argparse
import logging
import os.path
import sys

from generator.jani_generators import JaniNonStochasticGenerator, JaniGenerator
from generator.prism_generators import PrismGenerator, PrismNonStochasticGenerator, PrismBGenerator
from parser.parsers import SokParser
from util.util import exit_with_error

PARSERS = {
    "sok": SokParser
}

GENERATORS = {
    "jani": JaniGenerator,
    "jani-ns": JaniNonStochasticGenerator,
    "prism": PrismGenerator,
    "prism-b": PrismBGenerator,
    "prism-ns": PrismNonStochasticGenerator
}

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

levels = parser.parse_levels(text)
if len(levels) == 0:
    exit_with_error("No parseable levels found in input")

logging.debug(f"Found {len(levels)} levels")

if not args.output:
    if len(levels) > 1:
        exit_with_error("Can only write one model to stdout. Specify an output file with --output instead.")

    if args.force:
        logging.warning("Argument --force ignored as no output file is specified")

    print(generator.generate_model(levels[0]))
else:
    for i, level in enumerate(levels):
        model = generator.generate_model(level)
        file_name, extension = os.path.splitext(args.output)

        path = f"{file_name}_{i}{extension}"
        if os.path.exists(path) and not args.force:
            logging.warning(f"File '{path}' already exists. Run with the --force flag to overwrite files.")

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w+") as file:
            file.write(model)

        logging.debug("Wrote " + path)
