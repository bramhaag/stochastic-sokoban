import argparse
import decimal
import glob
import json
import logging
import os
import re
import subprocess
from collections import defaultdict, OrderedDict
from decimal import Decimal

from util.util import exit_with_error, convert_size


def run_process(command: [str], timeout: int) -> (bool, str):
    try:
        return True, subprocess.run(["/usr/bin/time", "-v"] + command,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT,
                                    timeout=timeout,
                                    text=True,
                                    env=os.environ.copy(),
                                    ).stdout
    except subprocess.TimeoutExpired as e:
        return False, str(e.stdout)


def run_prism(model: str, mu: str, engine: str, timeout: int, mem_limit: int, property: str) -> (dict, str):
    success, log = run_process(["prism", model,
                                f"-{engine}",
                                "-javamaxmem", str(mem_limit), "-cuddmaxmem", str(mem_limit),
                                "-pf", property,
                                "-const", f"mu={mu}"], timeout)

    if not success:
        return to_failure(model, mu, "timeout"), log

    if "Out of memory" in log:
        return to_failure(model, mu, "oom"), log

    return to_success(model, mu, log), log


def run_storm(model: str, mu: str, engine: str, timeout: int, mem_limit: int, property: str) -> (dict, str):
    success, log = run_process(["storm", "--jani", model,
                                "-e", engine,
                                "--janiproperty", property,
                                "-const", f"mu={mu}",
                                "--timemem"], timeout)

    if not success:
        return to_failure(model, mu, "timeout"), log

    return to_success(model, mu, log), log


def run_modest(model: str, mu: str, engine: str, timeout: int, mem_limit: int, property: str) -> (dict, str):
    success, log = run_process(["modest", engine, model,
                                "--props", property,
                                "-E", f"mu={mu}",
                                "-S", "Memory"], timeout)

    if not success:
        return to_failure(model, mu, "timeout"), log

    return to_success(model, mu, log), log


def to_success(file: str, mu: str, log: str) -> dict:
    timestamp = re.search(r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): (.*)", log).group(1)
    time = sum(float(p) * 60 ** i for i, p in enumerate(reversed(timestamp.split(":"))))

    memory = re.search(r"Maximum resident set size \(kbytes\): (\d+)", log).group(1)
    return {
        "file": file,
        "mu": mu,
        "solved": True,
        "time": time,
        "memory": convert_size(float(memory), "KB", "B")
    }


def to_failure(file: str, mu: str, reason: str) -> dict:
    return {
        "file": file,
        "mu": mu,
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
required.add_argument("-c", "--checker",
                      type=str,
                      required=True,
                      choices=["prism", "storm", "modest"],
                      help="model checker")
required.add_argument("-e", "--engine",
                      type=str,
                      required=True,
                      help="engine to use")
required.add_argument("-mu",
                      type=str,
                      nargs="+",
                      required=True,
                      help="values for mu. Can be a space-separated list of floating point numbers,"
                           "or a string in the min:max:num steps (e.g 0:1:4 yields 0.00, 0.25, 0.50, 0.75, 1.00)")
required.add_argument("-p", "--property",
                      type=str,
                      required=True,
                      help="property to benchmark")
optional.add_argument("-t", "--timeout",
                      type=int,
                      default=5 * 60,
                      help="timeout in seconds (default: %(default)")
optional.add_argument("-m", "--memory",
                      type=int,
                      default=6144,
                      help="memory limit (in MB) (default: %(default)")

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
    logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.DEBUG)
else:
    logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

# Parse mu parameter
mus = []
try:
    if len(args.mu) == 1 and args.mu[0].count(":") == 2:
        mi, ma, steps = args.mu[0].split(":")
        mi, ma, steps = Decimal(mi), Decimal(ma), int(steps)
        mus = [str((ma - mi) / steps * Decimal(i)) for i in range(steps + 1)]
    else:
        mus = [str(Decimal(mu)) for mu in args.mu]
except (decimal.InvalidOperation, ValueError):
    exit_with_error("Invalid pattern for mu")

logging.info(f"Benchmarking with mu values: {[str(mu) for mu in mus]}")

# Check for existing benchmark results
try:
    with open(args.output, 'r') as output_file:
        skipped_benchmarks = defaultdict(set)
        for b in json.loads(output_file.read() or "[]"):
            skipped_benchmarks[b["file"]].add(b["mu"])

        logging.info(f"Found {len(skipped_benchmarks)} existing benchmarks. These will not be ran again.")
except FileNotFoundError:
    skipped_benchmarks = {}
    logging.debug("No existing benchmarks found.")

# Generate benchmarks that still have to be run
benchmarks = OrderedDict()
for path in sorted(glob.glob(args.input), key=len):
    for mu in mus:
        if path not in skipped_benchmarks or mu not in skipped_benchmarks[path]:
            benchmarks.setdefault(path, set()).add(str(mu))

if len(benchmarks) == 0:
    exit_with_error("No files found to benchmark")

max_memory = convert_size(args.memory, "MB", "B")
logging.debug(f"Max memory: {max_memory}")

match args.checker:
    case "prism":
        runner = run_prism
    case "storm":
        runner = run_storm
    case "modest":
        runner = run_modest
    case _:
        exit_with_error("Cannot create benchmark runner")

i = 0
total_len = sum((len(v) for v in benchmarks.values()))

for benchmark_file, benchmark_mus in benchmarks.items():
    for mu in benchmark_mus:
        i += 1

        logging.info(f"[{i}/{total_len}] Running {benchmark_file} with mu={mu} "
                     + "(Time remaining: {:.0f}h {:.0f}m)".format(*divmod((total_len - i) * args.timeout / 60, 60)))

        result, log = runner(benchmark_file, mu, args.engine, args.timeout, max_memory, args.property)

        logging.debug(log)
        logging.debug(result)

        if result["solved"]:
            logging.info(f"Completed benchmark in {result['time']}s")
        else:
            logging.info(f"Canceled: {result['reason']}")

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
