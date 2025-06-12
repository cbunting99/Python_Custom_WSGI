#!/usr/bin/env python3
import asyncio
import socket
import multiprocessing
import sys
from typing import Callable
from .request_handler import WSGIHandler

# Try to import uvloop for better performance on Linux/macOS
try:
    import uvloop
    UVLOOP_AVAILABLE = True
except ImportError:
    UVLOOP_AVAILABLE = False

class HighPerformanceWSGIServer:
    def __init__(self, 
                 app: Callable,
                 host: str = '127.0.0.1',
                 port: int = 8000,
                 workers: int = None,
                 backlog: int = 2048):
        self.app = app
        self.host = host
        self.port = port
        self.workers = workers or multiprocessing.cpu_count()
        self.backlog = backlog
        
    def run(self):
        if self.workers == 1:
            # Single process mode
            if UVLOOP_AVAILABLE and sys.platform != 'win32':
                asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
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
        if UVLOOP_AVAILABLE and sys.platform != 'win32':
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        asyncio.run(self._serve())
    
    async def _serve(self):
        # Create socket with optimizations
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Enable SO_REUSEPORT on Linux for better load balancing
        if hasattr(socket, 'SO_REUSEPORT'):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        
        # TCP optimizations
        if hasattr(socket, 'TCP_NODELAY'):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        
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
            print(f"Error handling client: {e}")
        finally:
            try:
                client_sock.close()
            except:
                pass