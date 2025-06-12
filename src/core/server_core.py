"""
Core WSGI Server implementation providing asynchronous request handling.

This module implements a production-ready WSGI server with features including:
- Asynchronous I/O using asyncio
- Graceful shutdown handling
- Connection pooling and limiting
- Error handling and recovery
"""

import asyncio
import socket
import signal
import sys
from typing import Callable, Set, Optional, Any

from .request_handler import WSGIHandler
from .server_utils import setup_uvloop, get_server_kwargs, handle_client_error

class WSGIServer:
    """WSGI-compliant asynchronous HTTP server.
    
    Attributes:
        app: The WSGI application callable
        host: Host address to bind to
        port: Port number to listen on
        max_connections: Maximum number of simultaneous connections
    """
    def __init__(self, app: Callable, host='127.0.0.1', port=8000,
                 max_connections: int = 1000):
        self.app = app
        self.host = host
        self.port = port
        self.max_connections = max_connections
        self._connection_count = 0
        self._shutdown_event = asyncio.Event()
        self._active_connections: Set[asyncio.Task] = set()
        self._request_semaphore = asyncio.Semaphore(max_connections)
        
    async def start(self) -> None:
        """Start the WSGI server and begin accepting connections.
        
        Sets up the event loop, configures signal handlers for graceful shutdown,
        and starts listening for incoming connections.
        
        Raises:
            OSError: If server fails to bind to specified host/port
            ServerConfigError: If server configuration fails
        """
        setup_uvloop()
        server_kwargs = get_server_kwargs()
        
        # Setup signal handlers for graceful shutdown
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda s, f: asyncio.create_task(self.shutdown()))
        
        try:
            server = await asyncio.start_server(
                self.handle_client,
                self.host,
                self.port,
                **server_kwargs
            )
            
            print(f"Server started on {self.host}:{self.port}")
            async with server:
                await self._run_server(server)
        except Exception as e:
            print(f"Server error: {e}", file=sys.stderr)
            await self.shutdown()
            raise
    
    async def _run_server(self, server: asyncio.Server) -> None:
        """Run the server until shutdown is requested.
        
        Args:
            server: The asyncio Server instance to run
            
        Waits for shutdown event and ensures all connections are properly closed.
        """
        try:
            await self._shutdown_event.wait()
        finally:
            server.close()
            await server.wait_closed()
            # Wait for all active connections to complete
            if self._active_connections:
                await asyncio.wait(self._active_connections)

    async def shutdown(self) -> None:
        """Initiate graceful server shutdown.
        
        Stops accepting new connections and waits for existing connections
        to complete before shutting down the server.
        """
        print("Initiating graceful shutdown...")
        self._shutdown_event.set()

    async def handle_client(self,
                          reader: asyncio.StreamReader,
                          writer: asyncio.StreamWriter) -> None:
        """Handle incoming client connections with resource management.
        
        Args:
            reader: StreamReader for receiving client data
            writer: StreamWriter for sending responses
            
        Manages connection lifecycle including:
        - Connection limiting via semaphore
        - Request handling via WSGIHandler
        - Error handling and connection cleanup
        - Resource tracking for graceful shutdown
        """
        if self._shutdown_event.is_set():
            writer.close()
            await writer.wait_closed()
            return

        async with self._request_semaphore:
            task = asyncio.current_task()
            if task:
                self._active_connections.add(task)
            try:
                handler = WSGIHandler(self.app)
                await handler.handle_request(reader, writer)
            except Exception as e:
                await handle_client_error(writer, e)
            finally:
                if task:
                    self._active_connections.remove(task)
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception as e:
                    print(f"Error closing connection: {e}", file=sys.stderr)