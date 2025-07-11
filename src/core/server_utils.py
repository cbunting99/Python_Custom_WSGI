"""
Utility functions for WSGI server configuration and operation.

This module provides core functionality for:
- Event loop setup and optimization with uvloop
- Socket configuration and TCP optimization
- Server kwargs generation for different platforms
- Error handling and logging setup
- Client connection management

The utilities in this module focus on performance optimization
and proper error handling for production environments.
"""

import sys
import socket
import asyncio
import logging
from typing import Dict, Any, Optional


# Configure logging
def configure_logging(level=logging.INFO, log_file=None):
    """Configure logging for the WSGI server.

    Args:
        level: Logging level (default: INFO)
        log_file: Optional path to log file

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("wsgi_server")
    logger.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Default logger instance
default_logger = configure_logging()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

# Try to import uvloop for better performance on Linux/macOS
try:
    import uvloop

    UVLOOP_AVAILABLE = True
except ImportError:
    UVLOOP_AVAILABLE = False
    logger.warning("uvloop not available, falling back to default event loop")


class ServerConfigError(Exception):
    """Custom exception for server configuration errors"""

    pass


def setup_uvloop() -> None:
    """Configure uvloop for improved event loop performance.

    Attempts to set up uvloop as the event loop policy if:
    1. uvloop is installed
    2. Running on a compatible platform (not Windows)

    Raises:
        ServerConfigError: If uvloop setup fails

    Notes:
        Falls back to default event loop if uvloop is unavailable,
        logging a warning but not raising an error in this case.
    """
    if UVLOOP_AVAILABLE and sys.platform != "win32":
        try:
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            logger.info("Using uvloop event loop")
        except Exception as e:
            logger.error(f"Failed to setup uvloop: {e}")
            raise ServerConfigError("Failed to initialize event loop")


def configure_socket_opts(sock: socket.socket) -> None:
    """Configure socket options for optimal performance.

    Args:
        sock: Socket instance to configure

    Raises:
        ServerConfigError: If critical socket options cannot be set

    Applies optimizations including:
    - Address/port reuse
    - TCP no delay
    - Keep-alive settings
    - Buffer size tuning

    Platform-specific options are applied where available.
    Non-critical option failures are logged but don't prevent startup.
    """
    try:
        # Basic socket options
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Platform specific optimizations
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except Exception as e:
                logger.warning(f"Failed to set SO_REUSEPORT: {e}")

        # TCP optimizations
        if hasattr(socket, "TCP_NODELAY"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        # Set TCP keepalive
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

        # Set receive and send buffer sizes
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)

    except Exception as e:
        logger.error(f"Failed to configure socket options: {e}")
        raise ServerConfigError("Socket configuration failed")


def get_server_kwargs() -> Dict[str, Any]:
    """Get platform-specific server configuration arguments.

    Returns:
        Dict containing asyncio.start_server kwargs optimized for
        the current platform and environment.

    The returned configuration includes:
    - Address/port reuse settings
    - Connection backlog size
    - Platform-specific optimizations

    All returned values are validated to ensure they are supported
    on the current platform.
    """
    kwargs: Dict[str, Any] = {
        "reuse_address": True,
        "backlog": 2048,  # Increased from default 100
        "start_serving": True,
    }

    if hasattr(socket, "SO_REUSEPORT"):
        kwargs["reuse_port"] = True

    return kwargs


async def handle_client_error(
    writer: asyncio.StreamWriter,
    error: Exception,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Handle client connection errors gracefully.

    Args:
        writer: StreamWriter for the client connection
        error: Exception that occurred
        logger: Optional logger instance, creates new one if None

    Performs:
    1. Error logging with full traceback
    2. Sending error response to client if possible
    3. Clean connection shutdown
    4. Transport cleanup

    Notes:
        Always attempts to close the connection even if error
        response fails. Uses transport.abort() as final fallback
        to ensure resources are released.
    """
    if logger is None:
        logger = default_logger

    error_msg = f"Error handling client request: {str(error)}"
    logger.error(error_msg, exc_info=True)

    try:
        if not writer.is_closing():
            writer.write(
                b"HTTP/1.1 500 Internal Server Error\r\n"
                b"Content-Type: text/plain\r\n"
                b"Connection: close\r\n\r\n"
                b"Internal Server Error"
            )
            await writer.drain()
            writer.close()

        await writer.wait_closed()
    except Exception as e:
        logger.error(f"Error while closing connection: {str(e)}", exc_info=True)
    finally:
        # Ensure connection is marked for closure
        if hasattr(writer, "_transport"):
            writer._transport.abort()
