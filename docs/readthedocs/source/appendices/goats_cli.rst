.. _goats_cli:

GOATS Command Line Interface
============================

The GOATS Command Line Interface (CLI) provides an efficient way to install and manage your GOATS project/interface. You can get detailed help on each command using the ``--help`` option. Below you can find the breakdown of the primary commands and options.

``goats``
"""""""""

.. code-block:: console

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

``goats install``
"""""""""""""""""

.. code-block:: console

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

``goats run``
"""""""""""""
.. code-block:: console

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