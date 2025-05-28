import multiprocessing
import signal
import os
import sys
from server_core import WSGIServer

# Try to import uvloop for better performance on Linux/macOS
try:
    import uvloop
    UVLOOP_AVAILABLE = True
except ImportError:
    UVLOOP_AVAILABLE = False

class MultiProcessWSGIServer:
    def __init__(self, app, workers=None, host='127.0.0.1', port=8000):
        self.app = app
        self.workers = workers or multiprocessing.cpu_count()
        self.host = host
        self.port = port
        self.worker_processes = []
        
    def start(self):
        # Set up signal handlers (Windows doesn't support SIGTERM/SIGINT the same way)
        if sys.platform != 'win32':
            signal.signal(signal.SIGTERM, self._handle_signal)
            signal.signal(signal.SIGINT, self._handle_signal)
        
        print(f"Starting {self.workers} worker processes...")
        
        for i in range(self.workers):
            process = multiprocessing.Process(
                target=self._worker_main,
                args=(i,)
            )
            process.start()
            self.worker_processes.append(process)
        
        try:
            # Wait for workers
            for process in self.worker_processes:
                process.join()
        except KeyboardInterrupt:
            print("Received interrupt, shutting down...")
            for process in self.worker_processes:
                process.terminate()
                process.join()
    
    def _worker_main(self, worker_id):
        # Each worker runs its own event loop
        import asyncio
        
        if UVLOOP_AVAILABLE and sys.platform != 'win32':
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        
        server = WSGIServer(self.app, self.host, self.port)
        asyncio.run(server.start())
    
    def _handle_signal(self, signum, frame):
        print(f"Received signal {signum}, shutting down...")
        for process in self.worker_processes:
            process.terminate()