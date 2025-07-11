"""
Multi-process WSGI server implementation for improved performance.

This module provides a multi-process WSGI server implementation that:
- Utilizes all available CPU cores
- Handles graceful shutdown across processes
- Integrates with uvloop when available
- Provides proper resource cleanup
"""

"""
Copyright 2025 Chris Bunting
File: multiprocess_server.py | Purpose: Multi-process WSGI server
@author Chris Bunting | @version 1.0.0

CHANGELOG:
2025-07-11 - Chris Bunting: Added proper process cleanup and graceful shutdown
2025-07-10 - Chris Bunting: Initial implementation
"""

import multiprocessing
import os
import signal
import sys
import time
from ..core.server_core import WSGIServer
from ..core.server_utils import default_logger

# Try to import uvloop for better performance on Linux/macOS
try:
    import uvloop

    UVLOOP_AVAILABLE = True
except ImportError:
    UVLOOP_AVAILABLE = False


class MultiProcessWSGIServer:
    def __init__(self, app, workers=None, host="127.0.0.1", port=8000):
        self.app = app
        self.workers = workers or multiprocessing.cpu_count()
        self.host = host
        self.port = port
        self.worker_processes = []

    def start(self):
        # Set up signal handlers (Windows doesn't support SIGTERM/SIGINT the same way)
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, self._handle_signal)
            signal.signal(signal.SIGINT, self._handle_signal)

        default_logger.info(f"Starting {self.workers} worker processes...")

        for i in range(self.workers):
            process = multiprocessing.Process(target=self._worker_main, args=(i,))
            process.start()
            self.worker_processes.append(process)

        try:
            # Wait for workers
            for process in self.worker_processes:
                process.join()
        except KeyboardInterrupt:
            default_logger.info("Received interrupt, shutting down...")
            self.shutdown()

    def _worker_main(self, worker_id):
        """Main function for worker processes.

        Args:
            worker_id: Unique ID for this worker

        This function sets up the event loop and starts the WSGI server.
        Each worker process has its own event loop and server instance.
        """
        # Set process title if available
        try:
            import setproctitle

            setproctitle.setproctitle(f"wsgi_worker_{worker_id}")
        except ImportError:
            pass

        # Configure worker-specific signal handlers
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, lambda sig, frame: sys.exit(0))
            signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))

        # Each worker runs its own event loop
        import asyncio

        try:
            # Use uvloop if available (not on Windows)
            if UVLOOP_AVAILABLE and sys.platform != "win32":
                asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

            # Create and start server
            print(
                f"Worker {worker_id} starting on {self.host}:{self.port}"
            )  # Keep print for worker process
            server = WSGIServer(self.app, self.host, self.port)
            asyncio.run(server.start())
        except KeyboardInterrupt:
            print(
                f"Worker {worker_id} received interrupt, shutting down..."
            )  # Keep print for worker process
            sys.exit(0)
        except Exception as e:
            print(
                f"Worker {worker_id} error: {e}", file=sys.stderr
            )  # Keep print for worker process
            sys.exit(1)

    def _handle_signal(self, signum, frame):
        default_logger.info(f"Received signal {signum}, shutting down...")
        self.shutdown()

    def shutdown(self):
        """Gracefully shut down all worker processes"""
        # First try to terminate gracefully
        for process in self.worker_processes:
            if process.is_alive():
                process.terminate()

        # Give processes time to terminate gracefully
        deadline = time.time() + 5  # 5 seconds timeout

        for process in self.worker_processes:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            try:
                process.join(timeout=remaining)
            except Exception:
                pass

        # Force kill any remaining processes
        for process in self.worker_processes:
            if process.is_alive():
                try:
                    if sys.platform != "win32":
                        os.kill(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                except Exception:
                    pass

        # Clear the list
        self.worker_processes.clear()
