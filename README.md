# 🐐 Gemini Observation and Analysis of Targets System (GOATS)

[![Run Ruff](https://github.com/gemini-hlsw/goats/actions/workflows/run_ruff.yml/badge.svg?event=push)](https://github.com/gemini-hlsw/goats/actions/workflows/run_ruff.yml)
[![Run Tests](https://github.com/gemini-hlsw/goats/actions/workflows/run_tests.yaml/badge.svg?branch=main&event=push)](https://github.com/gemini-hlsw/goats/actions/workflows/run_tests.yaml)
[![Code Coverage](https://codecov.io/github/gemini-hlsw/goats/branch/main/graph/badge.svg?token=QXC18C4T93)](https://codecov.io/github/gemini-hlsw/goats)
[![Run HTMLHint](https://github.com/gemini-hlsw/goats/actions/workflows/run_htmlhint.yaml/badge.svg?branch=main&event=push)](https://github.com/gemini-hlsw/goats/actions/workflows/run_htmlhint.yaml)
[![Run StyleLint](https://github.com/gemini-hlsw/goats/actions/workflows/run_stylelint.yaml/badge.svg?branch=main&event=push)](https://github.com/gemini-hlsw/goats/actions/workflows/run_stylelint.yaml)
[![Run JS Tests](https://github.com/gemini-hlsw/goats/actions/workflows/run_js_tests.yaml/badge.svg?branch=main&event=push)](https://github.com/gemini-hlsw/goats/actions/workflows/run_js_tests.yaml)

This is an end-to-end integrated system for time-domain and multimesseneger astronomy (TDAMM) aimed towards Gemini follow-up observations.

Its objective is to simplify the TDAMM workflow for users by serving as a one-stop shop for all the follow-up needs. To this end, it will integrate the various TDAMM services of Gemini Observatory and the larger NOIRLab organization.

<img
  src="doc/graphics/goats_with_lab.jpg"
  alt="Schematic of GOATS"
  title="Ecosystem of GOATS"
  style="display: inline-block; margin: 0 auto; max-width: 400px">

## System Requirements
- Python 3.10 or higher
- Intel Anaconda or Miniconda (works on M1 architecture) >= 4.12

### Workaround for ARM (M1/M2) Mac users:
- Ensure you have Rosetta 2 installed to run Intel-based binaries.
- Install an x86 version of Anaconda or Miniconda.
- You need to switch to an x86 terminal for installing and running Intel-only packages like DRAGONS.

## Installation
```console
git clone https://github.com/gemini-hlsw/goats.git
cd goats
conda env create -f environment.yml
conda activate goats-env
pip install .
```
This installs the `goats` CLI which can be used to install and run GOATS.
```console
goats install
goats run
```

To test:
```console
pip install '.[test]'
pytest
```


## GOATS CLI

The **Gemini Observation and Analysis of Targets System (GOATS)** CLI provides an efficient way to install and manage the GOATS project along with the antares2goats browser extension. You can get detailed help on each command using the `--help` option. Below, find the breakdown of the primary commands and options:

### `goats`
Use the following command to get an overview of available options and commands:
```console
$ goats --help

Usage: goats [OPTIONS] COMMAND [ARGS]...

  Gemini Observation and Analysis of Targets System (GOATS).

  You can run each subcommand with its own options and arguments. For
  details on a specific command, type 'goats COMMAND --help'.

Options:
  --help  Show this message and exit.

Commands:
  install  Installs GOATS and configures Redis server.
  run      Starts the webserver, Redis server, and workers for GOATS.
```

### `goats install`
```console
$ goats install --help

Usage: goats install [OPTIONS]

  Installs GOATS and configures Redis Server.

Options:
  -p, --project-name TEXT  Specify a custom project name. Default is 'GOATS'.
  -d, --directory PATH     Specify the parent directory where GOATS will be
                           installed. Default is the current directory.

  --overwrite              Overwrite the existing project, if it exists.
                           Default is False.

  -m, --media-dir PATH     Path for saving downloaded media.
  --redis-addrport TEXT    Specify the Redis server IP address and port
                           number. Examples: '6379', 'localhost:6379',
                           '192.168.1.5:6379'. Providing only a port number
                           (e.g., '6379') binds to localhost.

  --help                   Show this message and exit.
```

### `goats run`
```console
$ goats run --help

Usage: goats run [OPTIONS]

  Starts the webserver, Redis server, and workers for GOATS.

Options:
  -p, --project-name TEXT  Specify a custom project name. Default is 'GOATS'.
  -d, --directory PATH     Specify the parent directory where GOATS is
                           installed. Default is the current directory.

  -w, --workers INTEGER    Number of workers to spawn for background tasks.
  --addrport TEXT          Specify the IP address and port number to serve
                           GOATS. Examples: '8000', '0.0.0.0:8000',
                           '192.168.1.5:8000'. Providing only a port number
                           (e.g., '8000') binds to 127.0.0.1.

  --redis-addrport TEXT    Specify the Redis server IP address and port
                           number. Examples: '6379', 'localhost:6379',
                           '192.168.1.5:6379'. Providing only a port number
                           (e.g., '6379') binds to localhost.

  --help                   Show this message and exit.
```

## Troubleshooting

### Redis - Memory Overcommit Issue
On Linux platforms, if you encounter a warning regarding memory overcommitment, especially when running Redis, it may cause failures under low memory conditions. To resolve this, enable memory overcommitment.

Edit `/ect/sysctl.conf` as root:

```console
$ nano /etc/sysctl.conf
```

Add the configuration to the file:

```console
vm.overcommit_memory = 1
```

Save and exit. Then apply the configuration:

```console
$ sudo sysctl -p
```

For more information on memory overcommitment and its implications, see the [jemalloc issue tracker](https://github.com/jemalloc/jemalloc/issues/1328).

### Redis - Transparent Huge Pages (THP)
You may see a warning when starting redis about THP. THP can create latency and memory usage issues with Redis. It's recommended to disable THP on systems that run Redis.

Issue the command as root:

```console
$ echo never > /sys/kernel/mm/transparent_hugepage/enabled
```


## References and Documentation

- [GOATS Confluence](https://noirlab.atlassian.net/wiki/spaces/GOATS/overview)
- [GOATS Jira Board](https://noirlab.atlassian.net/jira/software/projects/GOATS/boards/57)
