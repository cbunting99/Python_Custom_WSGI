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
from pathlib import Path
from typing import Callable, Set, Optional, Any, Union, Dict, List

from .request_handler import WSGIHandler
from .server_utils import setup_uvloop, get_server_kwargs, handle_client_error
from .ssl_utils import create_ssl_context, validate_cert_paths
from src.features.security import CORSConfig, RateLimiter, IPFilter
from src.features.http2 import configure_http2

class WSGIServer:
    """WSGI-compliant asynchronous HTTP server.
    
    Attributes:
        app: The WSGI application callable
        host: Host address to bind to
        port: Port number to listen on
        max_connections: Maximum number of simultaneous connections
    """
    def __init__(self, app: Callable, host='127.0.0.1', port=8000,
                 max_connections: int = 1000, *,
                 ssl_certfile: Optional[Union[str, Path]] = None,
                 ssl_keyfile: Optional[Union[str, Path]] = None,
                 ssl_password: Optional[str] = None,
                 ssl_ciphers: Optional[str] = None,
                 enable_http2: bool = True,
                 cors_config: Optional[CORSConfig] = None,
                 rate_limit: Optional[Dict[str, Union[float, int]]] = None,
                 ip_whitelist: Optional[List[str]] = None,
                 ip_blacklist: Optional[List[str]] = None):
        """Initialize WSGI server with optional SSL support.
        
        Args:
            app: WSGI application callable
            host: Host address to bind to
            port: Port number to listen on
            max_connections: Maximum number of simultaneous connections
            ssl_certfile: Path to SSL certificate file
            ssl_keyfile: Path to SSL private key file
            ssl_password: Optional password for encrypted private key
            ssl_ciphers: Optional custom cipher string
            enable_http2: Enable HTTP/2 protocol support
            cors_config: CORS configuration settings
            rate_limit: Rate limiting config with 'rate' and 'burst' keys
            ip_whitelist: List of allowed IP addresses
            ip_blacklist: List of blocked IP addresses
        """
        self.app = app
        self.host = host
        self.port = port
        self.max_connections = max_connections
        self._connection_count = 0
        self._shutdown_event = asyncio.Event()
        self._active_connections: Set[asyncio.Task] = set()
        self._request_semaphore = asyncio.Semaphore(max_connections)
        
        # Security features
        self.cors_config = cors_config or CORSConfig()
        self.rate_limiter = None
        if rate_limit:
            self.rate_limiter = RateLimiter(
                rate=rate_limit.get('rate', 10.0),
                burst=rate_limit.get('burst', 20)
            )
        
        self.ip_filter = IPFilter()
        if ip_whitelist:
            for ip in ip_whitelist:
                self.ip_filter.add_to_whitelist(ip)
        if ip_blacklist:
            for ip in ip_blacklist:
                self.ip_filter.add_to_blacklist(ip)
        
        # SSL and HTTP/2 configuration
        self.ssl_context = None
        if ssl_certfile and ssl_keyfile:
            cert_path, key_path = validate_cert_paths(ssl_certfile, ssl_keyfile)
            self.ssl_context = create_ssl_context(
                cert_path,
                key_path,
                password=ssl_password,
                ciphers=ssl_ciphers
            )
            if enable_http2:
                self.ssl_context = configure_http2(self.ssl_context)
        
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
                ssl=self.ssl_context,
                **server_kwargs
            )
            
            protocol = "https" if self.ssl_context else "http"
            print(f"Server started on {protocol}://{self.host}:{self.port}")
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

        client_ip = writer.get_extra_info('peername')[0]
        
        # Check IP filtering
        if not self.ip_filter.is_allowed(client_ip):
            writer.write(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 9\r\n\r\nForbidden')
            await writer.drain()
            return
            
        # Check rate limiting
        if self.rate_limiter and not self.rate_limiter.is_allowed(client_ip):
            writer.write(b'HTTP/1.1 429 Too Many Requests\r\nContent-Length: 20\r\n\r\nToo many requests')
            await writer.drain()
            return
            
        async with self._request_semaphore:
            task = asyncio.current_task()
            if task:
                self._active_connections.add(task)
            try:
                handler = WSGIHandler(self.app, self.cors_config)
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