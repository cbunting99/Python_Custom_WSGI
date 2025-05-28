import asyncio
import sys
import socket
from typing import Callable
from request_handler import WSGIHandler

# Try to import uvloop for better performance on Linux/macOS
try:
    import uvloop
    UVLOOP_AVAILABLE = True
except ImportError:
    UVLOOP_AVAILABLE = False

class WSGIServer:
    def __init__(self, app: Callable, host='127.0.0.1', port=8000):
        self.app = app
        self.host = host
        self.port = port
        
    async def start(self):
        # Set uvloop as the event loop if available and not on Windows
        if UVLOOP_AVAILABLE and sys.platform != 'win32':
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        
        # Configure server options based on platform
        server_kwargs = {
            'reuse_address': True
        }
        
        # Enable SO_REUSEPORT on Linux/macOS
        if hasattr(socket, 'SO_REUSEPORT'):
            server_kwargs['reuse_port'] = True
        
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
            print(f"Error handling client: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass