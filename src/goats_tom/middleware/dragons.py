__all__ = ["DRAGONSMiddleware"]

from dramatiq import Broker, Worker
from dramatiq.middleware import Middleware
from gempy.eti_core.eti import ETISubprocess


class DRAGONSMiddleware(Middleware):
    """Middleware to ensure DRAGONS is properly cleaned up shut down."""

    def before_worker_shutdown(self, broker: Broker, worker: Worker) -> None:
        """Ensures `DRAGONS.ETISubprocess` is terminated when a Dramatiq worker shuts
        down.

        Parameters
        ----------
        broker : `Broker`
            The broker managing message processing.
        worker : `Worker`
            The worker instance that is shutting down.
        """
        print("DRAGONSMiddleware: Terminating DRAGONS subprocesses on worker shutdown.")

        # Only run shutdown if the ETISubprocess was started.
        if ETISubprocess.instance is not None:
            print("Found running, shutting down...")
            try:
                eti_subprocess = ETISubprocess()
                # Send quit message to loop.
                # Leaving in hoping DRAGONS merges in requested changes.
                # eti_subprocess.inQueue.put(None)
                eti_subprocess.process.join(timeout=2)

                # If still alive, force-terminate.
                if eti_subprocess.process.is_alive():
                    eti_subprocess.process.terminate()
                    eti_subprocess.process.join()

                # Free up resources.
                eti_subprocess.process.close()

                # Ensure queues are properly closed after the process is dead.
                try:
                    eti_subprocess.inQueue.close()
                    eti_subprocess.inQueue.join_thread()
                    eti_subprocess.outQueue.close()
                    eti_subprocess.outQueue.join_thread()
                except Exception:
                    pass
            except Exception as e:
                print(f"Error during DRAGONS shutdown: {e}")
