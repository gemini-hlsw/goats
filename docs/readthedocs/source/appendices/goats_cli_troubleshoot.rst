.. _troubleshoot:

Troubleshooting
===============

Redis - Memory Overcommit Issue
"""""""""""""""""""""""""""""""

On Linux platforms, if you encounter a warning regarding memory overcommitment, especially when running Redis, it may cause failures under low memory conditions. To resolve this, enable memory overcommitment.

Edit ``/ect/sysctl.conf`` as root:

.. code-block:: console

    $ nano /etc/sysctl.conf

Add the configuration to the file:

.. code-block:: console

    vm.overcommit_memory = 1

Save and exit. Then apply the configuration:

.. code-block:: console

    $ sudo sysctl -p

For more information on memory overcommitment and its implications, see the `jemalloc issue tracker <https://github.com/jemalloc/jemalloc/issues/1328>`_.

Redis - Transparent Huge Pages (THP)
""""""""""""""""""""""""""""""""""""

You may see a warning when starting redis about THP. THP can create latency and memory usage issues with Redis. It is recommended to disable THP on systems that run Redis.

Issue the command as root:

.. code-block:: console

    $ echo never > /sys/kernel/mm/transparent_hugepage/enabled
