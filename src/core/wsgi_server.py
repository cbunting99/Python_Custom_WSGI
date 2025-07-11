#!/usr/bin/env python3
import asyncio
import socket
import multiprocessing
from typing import Callable

from .request_handler import WSGIHandler
from .server_utils import setup_uvloop, configure_socket_opts, handle_client_error


class HighPerformanceWSGIServer:
    def __init__(
        self,
        app: Callable,
        host: str = "127.0.0.1",
        port: int = 8000,
        workers: int = None,
        backlog: int = 2048,
    ):
        self.app = app
        self.host = host

        # Validate port number
        if not isinstance(port, int):
            raise ValueError("Port must be an integer")
        if port < 0 or port > 65535:
            raise ValueError("Port number must be between 0 and 65535")
        self.port = port

        # Validate and set worker count
        if workers is not None:
            if not isinstance(workers, int):
                raise ValueError("Workers must be an integer")
            if workers < 1:
                raise ValueError("Worker count must be at least 1")
            self.workers = workers
        else:
            self.workers = multiprocessing.cpu_count()

        # Validate backlog
        if not isinstance(backlog, int):
            raise ValueError("Backlog must be an integer")
        if backlog < 1:
            raise ValueError("Backlog must be at least 1")
        self.backlog = backlog

    def run(self):
        if self.workers == 1:
            # Single process mode
            setup_uvloop()
            asyncio.run(self._serve())
        else:
            # Multi-process mode
            self._run_multiprocess()

    def _run_multiprocess(self):
        processes = []
        for _ in range(self.workers):
            p = multiprocessing.Process(target=self._worker_process)
            p.start()
            processes.append(p)

        try:
            for p in processes:
                p.join()
        except KeyboardInterrupt:
            for p in processes:
                p.terminate()
                p.join()

    def _worker_process(self):
        setup_uvloop()
        asyncio.run(self._serve())

    async def _serve(self):
        # Create socket with optimizations
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        configure_socket_opts(sock)

        sock.bind((self.host, self.port))
        sock.listen(self.backlog)
        sock.setblocking(False)

        handler = WSGIHandler(self.app)

        print(f"Worker serving on {self.host}:{self.port}")

        while True:
            try:
                client_sock, addr = await asyncio.get_event_loop().sock_accept(sock)
                asyncio.create_task(self._handle_client(client_sock, handler))
            except Exception as e:
                print(f"Error accepting connection: {e}")

    async def _handle_client(self, client_sock, handler):
        try:
            reader, writer = await asyncio.open_connection(sock=client_sock)
            await handler.handle_request(reader, writer)
        except Exception as e:
            await handle_client_error(writer, e)
        finally:
            if not client_sock._closed:
                client_sock.close()
