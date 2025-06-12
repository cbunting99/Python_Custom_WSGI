"""Utility functions for WSGI server implementations"""
import sys
import socket
import asyncio

# Try to import uvloop for better performance on Linux/macOS
try:
    import uvloop
    UVLOOP_AVAILABLE = True
except ImportError:
    UVLOOP_AVAILABLE = False

def setup_uvloop():
    """Configure uvloop if available and not on Windows"""
    if UVLOOP_AVAILABLE and sys.platform != 'win32':
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

def configure_socket_opts(sock: socket.socket):
    """Apply optimal socket configurations"""
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Enable SO_REUSEPORT on Linux/macOS for better load balancing
    if hasattr(socket, 'SO_REUSEPORT'):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    
    # TCP optimizations
    if hasattr(socket, 'TCP_NODELAY'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

def get_server_kwargs():
    """Get platform-specific server keyword arguments"""
    kwargs = {'reuse_address': True}
    if hasattr(socket, 'SO_REUSEPORT'):
        kwargs['reuse_port'] = True
    return kwargs

async def handle_client_error(writer, error: Exception, logger=print):
    """Handle client errors gracefully"""
    error_msg = f"Error handling client request: {str(error)}"
    logger(error_msg)
    try:
        if not writer.is_closing():
            writer.close()
            await writer.wait_closed()
    except Exception as e:
        logger(f"Error while closing connection: {str(e)}")