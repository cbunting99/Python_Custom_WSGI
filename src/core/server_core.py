import asyncio
import socket
from typing import Callable
from .request_handler import WSGIHandler
from .server_utils import setup_uvloop, get_server_kwargs, handle_client_error

class WSGIServer:
    def __init__(self, app: Callable, host='127.0.0.1', port=8000):
        self.app = app
        self.host = host
        self.port = port
        
    async def start(self):
        """Start the WSGI server"""
        setup_uvloop()
        server_kwargs = get_server_kwargs()
        
        server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port,
            **server_kwargs
        )
        
        print(f"Server started on {self.host}:{self.port}")
        async with server:
            await server.serve_forever()
    
    async def handle_client(self, reader, writer):
        """Handle incoming client connections"""
        handler = WSGIHandler(self.app)
        try:
            await handler.handle_request(reader, writer)
        except Exception as e:
            await handle_client_error(writer, e)