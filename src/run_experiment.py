import argparse
import glob
import json
import logging
import os
import re
import subprocess
import time

from util.util import exit_with_error, convert_size

PATTERN_SCIFLOAT = r"(\d+(?:.\d+)?(?:[eE]-?\d+)?)"


def run_prism(model: str, mu: str, property: str, mem_limit: int, timeout: int) -> (bool, str):
    try:
        return True, subprocess.run(["prism", model,
                                     "-javamaxmem", str(mem_limit), "-cuddmaxmem", str(mem_limit),
                                     "-pf", property,
                                     "-const", f"mu={mu}"],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT,
                                    timeout=timeout,
                                    text=True,
                                    env=os.environ.copy(),
                                    ).stdout
    except subprocess.TimeoutExpired as e:
        return False, str(e.stdout)


def to_success(file: str, log: str) -> dict:
    mus = re.findall(rf"Model constants: mu={PATTERN_SCIFLOAT}", log)[::2]
    probabilities = re.findall(rf"Result: {PATTERN_SCIFLOAT}", log)

    return {
        "file": file,
        "solved": True,
        "result": [{"mu": mu, "result": prob} for mu, prob in zip(mus, probabilities)]
    }


def to_failure(file: str, reason: str) -> dict:
    return {
        "file": file,
        "solved": False,
        "reason": reason
    }


arg_parser = argparse.ArgumentParser(add_help=False)

required = arg_parser.add_argument_group("required")
optional = arg_parser.add_argument_group("optional")

required.add_argument("input",
                      type=str,
                      help="input path. Supports glob patterns to run multiple files")
required.add_argument("output",
                      type=str,
                      help="output result file path")
required.add_argument("-mu",
                      type=str,
                      required=True,
                      help="values for mu in min:step:max format")
required.add_argument("-p", "--property",
                      type=str,
                      required=True,
                      help="property to use for experiment")
optional.add_argument("-t", "--timeout",
                      type=int,
                      default=5 * 60,
                      help="timeout in seconds (default: %(default)s)")
optional.add_argument("-m", "--memory",
                      type=int,
                      default=6144,
                      help="memory limit (in MB) (default: %(default)s)")
optional.add_argument("-l", "--log",
                      type=str,
                      help="output log file path")
optional.add_argument("--debug",
                      action="store_true",
                      help="enable debug logging")
optional.add_argument("-h", "--help",
                      action="help",
                      help="show this help message and exit")

args = arg_parser.parse_args()

if args.debug:
    logging.basicConfig(format="[%(asctime)s] %(levelname)s: %(message)s", level=logging.DEBUG)
else:
    logging.basicConfig(format="[%(asctime)s] %(levelname)s: %(message)s", level=logging.INFO)

# Check for existing experiments
try:
    with open(args.output, 'r') as output_file:
        skipped_experiments = {b["file"] for b in json.loads(output_file.read() or "[]")}
        logging.info(f"Found {len(skipped_experiments)} existing experiments. These will not be ran again.")
except FileNotFoundError:
    skipped_experiments = {}
    logging.debug("No existing experiments found.")

# Generate experiments that still have to be run
experiments = sorted(filter(lambda f: f not in skipped_experiments, glob.glob(args.input)), key=len)

if len(experiments) == 0:
    exit_with_error("No experiments found to run")

max_memory = convert_size(args.memory, "MB", "B")
logging.debug(f"Max memory: {max_memory}")

i = 0
for file in experiments:
    i += 1
    logging.info(f"[{i}/{len(experiments)}] Running {file}"
                 + "(Time remaining: {:.0f}h {:.0f}m)".format(*divmod((len(experiments) - i) * args.timeout / 60, 60)))

    t1 = time.time()
    solved, log = run_prism(file, args.mu, args.property, max_memory, args.timeout)
    t2 = time.time()
    if solved:
        result = to_success(file, log)
        logging.info(f"Completed experiment in {t2 - t1}s")
    else:
        result = to_failure(file, "canceled")
        logging.info(f"Canceled: {result['reason']}")

    logging.debug(log)
    logging.debug(result)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    try:
        with open(args.output, "r") as output_file:
            results = json.loads(output_file.read() or "[]")
    except FileNotFoundError:
        results = []

    results.append(result)

    with open(args.output, "w") as output_file:
        json.dump(results, output_file, indent=4)

    if args.log:
        os.makedirs(os.path.dirname(args.log), exist_ok=True)
        with open(args.log, "a") as log_file:
            log_file.write(log)
            log_file.write("-- END --")
