Troubleshooting
===============

Redis: Memory Overcommit
------------------------

On Linux, Redis may fail under low-memory conditions if memory overcommitment is not enabled.

To enable it:

1. Open the `sysctl` configuration file as `root`:

   .. code-block:: console

      $ sudo nano /etc/sysctl.conf

2. Add the following line:

   .. code-block:: text

      vm.overcommit_memory = 1

3. Apply the changes:

   .. code-block:: console

      $ sudo sysctl -p

For more information, see the `jemalloc issue tracker <https://github.com/jemalloc/jemalloc/issues/1328>`_.

Redis: Transparent Huge Pages (THP)
-----------------------------------

THP can cause latency and memory issues with Redis. Disable it as root:

.. code-block:: console

   $ echo never > /sys/kernel/mm/transparent_hugepage/enabled