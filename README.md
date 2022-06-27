# Stochastic Sokoban Model Generator
This repository hosts all source code related to the research done for my Bachelor's thesis in Computer Science.

The goal of the research is to create a tool that can generate probabilistic models of Sokoban levels that can be
used as part of a larger test suite to benchmark existing probabilistic model checkers.

## Scripts
### generate_model.py
The generate_model script generates probabilistic models from .sok files. 
As a .sok file can contain multiple levels, the script can output multiple files. 
Levels can also be read from `stdin` by omitting the `-i` argument, 
and can be outputted to `stdout` by omitting the `-o` argument.

Dependencies: None

Usage:
```shell
$ python src/generate_model.py --help
usage: generate_model.py [-i INPUT] [-o OUTPUT] [-f] [-p {sok}] -m {jani,jani-ns,prism,prism-b,prism-ns} [-e PRECISION] [--debug] [-h]

required:
  -m {jani,jani-ns,prism,prism-b,prism-ns}, --model {jani,jani-ns,prism,prism-b,prism-ns}
                        model type

optional:
  -i INPUT, --input INPUT
                        input file path
  -o OUTPUT, --output OUTPUT
                        output file path
  -f, --force           overwrite output file
  -p {sok}, --parser {sok}
                        parser type (default: sok)
  -e PRECISION, --precision PRECISION
                        precision of floating point numbers (default: 28)
  --debug               enable debug logging
  -h, --help            show this help message and exit
```

Example usage:
```shell
# Generate JANI models from the Microban level set
$ python src/generate_model.py -m jani -i test_sets/microban.sok -o generated_models/microban/jani/microban.jani

# Generate PRISM models from the XSokoban level set
$ python src/generate_model.py -m prism -i test_sets/xsokoban.sok -o generated_models/xsokoban/prism/xsokoban.jani
```

### generate_image.py
This script can convert .sok files into image representations of the levels. 
Supplying levels using `stdin` is also supported, as well as outputting the resulting png into `stdout`.

Dependencies: Pillow==9.1.1

Usage:
```shell
$ python src/generate_image.py --help
usage: generate_image.py [-i INPUT] [-o OUTPUT] [-ix INDICES [INDICES ...]] [-f] [-t] [-h]

optional:
  -i INPUT, --input INPUT
                        input file path
  -o OUTPUT, --output OUTPUT
                        output file path
  -ix INDICES [INDICES ...], --indices INDICES [INDICES ...]
                        space seperated list of level indices. Omit to use all levels
  -f, --force           overwrite output file
  -t, --text            display tile position indices
  -h, --help            show this help message and exit
```

### run_benchmark.py
This script automates the running of benchmarks. Most arguments (engine, property etc.) are not validated, 
so it is wise to store and check the log using the `-l` argument and verify that the model checker is producing results.

The script can be killed (`^C`) and resumed at a later time by rerunning the benchmark with the same output file.

Dependencies: None

Usage:
```shell
$ python src/run_benchmark.py --help
usage: run_benchmark.py -c {prism,storm,modest} -e ENGINE -mu MU [MU ...] -p PROPERTY [-t TIMEOUT] [-m MEMORY] [-l LOG] [--debug] [-h] input output

required:
  input                 input path. Supports glob patterns to run multiple files
  output                output result file path
  -c {prism,storm,modest}, --checker {prism,storm,modest}
                        model checker
  -e ENGINE, --engine ENGINE
                        engine to use
  -mu MU [MU ...]       values for mu. Can be a space-separated list of floating point numbers,or a string in the min:max:num steps (e.g 0:1:4 yields
                        0.00, 0.25, 0.50, 0.75, 1.00)
  -p PROPERTY, --property PROPERTY
                        property to benchmark

optional:
  -t TIMEOUT, --timeout TIMEOUT
                        timeout in seconds (default: 300)
  -m MEMORY, --memory MEMORY
                        memory limit (in MB) (default: 6144)
  -l LOG, --log LOG     output log file path
  --debug               enable debug logging
  -h, --help            show this help message and exit
```

Example usage:
```shell
# Benchmark the Microban set using Storm's hybrid engine for mu=0.3 and mu=0.9. Also store the log file.
# Be mindful to quote glob patterns
$ python src/run_benchmark.py "generated_models/microban/jani/*.jani" benchmarks/storm_hybrid.json -c storm -e hybrid -mu 0.3 0.9 -l benchmarks/storm_hybrid.txt -p goal_reached

# Benchmark the Microban set using Modest's mcsta engine for mu=0, 0.25, 0.50, 0.75, 1.
$ python src/run_benchmark.py "generated_models/microban/jani/*.jani" benchmarks/modest_mcsta.json -c modest -e mcsta -mu 0:1:4 -l benchmarks/modest_mcsta.txt -p goal_reached

# Benchmark the Microban set using PRISM's hybrid engine for mu=0.5.
# Properties are not stored in the model file, so they have to be supplied here.
$ python src/run_benchmark.py "generated_models/microban/prism/*.prism" benchmarks/prism_hybrid.json -c prism -e hybrid -mu 0.5 -l benchmarks/prism_hybrid.txt -p "Pmax=? [F \"goal_reached\"]"
```

### run_experiment.py
Run a PRISM experiment.

The script can be killed (`^C`) and resumed at a later time by rerunning the experiment with the same output file.

Usage:
```shell
$ python src/run_experiment.py --help
usage: run_experiment.py -mu MU -p PROPERTY [-t TIMEOUT] [-m MEMORY] [-l LOG] [--debug] [-h] input output

required:
  input                 input path. Supports glob patterns to run multiple files
  output                output result file path
  -mu MU                values for mu in min:step:max format
  -p PROPERTY, --property PROPERTY
                        property to use for experiment

optional:
  -t TIMEOUT, --timeout TIMEOUT
                        timeout in seconds (default: 300)
  -m MEMORY, --memory MEMORY
                        memory limit (in MB) (default: 6144)
  -l LOG, --log LOG     output log file path
  --debug               enable debug logging
  -h, --help            show this help message and exit
```

Example usage:
```shell
# Calculate Pmax=? [F goal_reached] for all levels with mu=0,0.1,0.2,..,0.9,1
python src/run_experiment.py "generated_models/microban/prism/*.prism" experiments/prism.json -mu 0:0.1:1 -p "Pmax=? [F \"goal_reached\"]" -l experiments/prism.log
```