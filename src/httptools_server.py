"""
High-performance WSGI server implementation using httptools.

This module provides a high-performance WSGI server implementation that:
- Uses httptools for fast HTTP parsing
- Supports multi-processing for improved performance
- Integrates with uvloop when available
- Implements HTTP keep-alive and pipelining
"""

"""
Copyright 2025 Chris Bunting
File: httptools_server.py | Purpose: High-performance WSGI server
@author Chris Bunting | @version 1.0.0

CHANGELOG:
2025-07-11 - Chris Bunting: Fixed wsgi.errors to use sys.stderr
2025-07-10 - Chris Bunting: Initial implementation
"""

import asyncio
import httptools
import multiprocessing
import signal
import sys
from urllib.parse import urlparse, parse_qs
from io import BytesIO

# Try to import uvloop for better performance on Linux/macOS
try:
    import uvloop

    UVLOOP_AVAILABLE = True
except ImportError:
    UVLOOP_AVAILABLE = False


class FastWSGIServer:
    def __init__(self, app, host="127.0.0.1", port=8000, workers=None):
        self.app = app
        self.host = host
        self.port = port
        self.workers = workers or multiprocessing.cpu_count()

    def run(self):
        if self.workers == 1:
            if UVLOOP_AVAILABLE and sys.platform != "win32":
                asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            asyncio.run(self._serve())
        else:
            self._run_multiprocess()

    def _run_multiprocess(self):
        processes = []

        def signal_handler(signum, frame):
            for p in processes:
                p.terminate()

        if sys.platform != "win32":
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

        for i in range(self.workers):
            p = multiprocessing.Process(target=self._worker, args=(i,))
            p.start()
            processes.append(p)

        try:
            for p in processes:
                p.join()
        except KeyboardInterrupt:
            for p in processes:
                p.terminate()
                p.join()

    def _worker(self, worker_id):
        if UVLOOP_AVAILABLE and sys.platform != "win32":
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        asyncio.run(self._serve())

    async def _serve(self):
        server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
            reuse_address=True,
            reuse_port=True,
            backlog=2048,
        )

        print(f"Worker serving on {self.host}:{self.port}")
        async with server:
            await server.serve_forever()

    async def _handle_client(self, reader, writer):
        handler = ConnectionHandler(self.app)
        try:
            await handler.handle_connection(reader, writer)
        except Exception as e:
            print(f"Connection error: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass


class ConnectionHandler:
    def __init__(self, app):
        self.app = app

    async def handle_connection(self, reader, writer):
        """Handle keep-alive connection with multiple requests"""
        keep_alive = True
        requests_handled = 0
        max_requests = 1000  # Prevent resource exhaustion

        while keep_alive and requests_handled < max_requests:
            try:
                # Parse HTTP request
                parser = FastHTTPParser()
                request_data = await self._read_request(reader, parser)

                if not request_data:
                    break

                # Process WSGI request
                response = await self._process_wsgi_request(request_data)

                # Send response
                writer.write(response)
                await writer.drain()

                keep_alive = request_data.get("keep_alive", False)
                requests_handled += 1

            except asyncio.IncompleteReadError:
                break
            except Exception as e:
                # Send error response
                error_response = (
                    b"HTTP/1.1 500 Internal Server Error\r\n"
                    b"Content-Length: 21\r\n\r\n"
                    b"Internal Server Error"
                )
                writer.write(error_response)
                await writer.drain()
                break

    async def _read_request(self, reader, parser):
        """Read and parse HTTP request"""
        buffer = bytearray(8192)

        while not parser.complete:
            try:
                # Read data into buffer
                data = await reader.read(8192)
                if not data:
                    return None

                # Feed to parser
                parser.feed_data(data)

            except httptools.HttpParserError:
                return None

        return parser.get_request_data()

    async def _process_wsgi_request(self, request_data):
        """Process WSGI request"""
        # Build WSGI environ
        environ = self._build_environ(request_data)

        # Run WSGI app in thread pool (WSGI is synchronous)
        loop = asyncio.get_event_loop()
        response_data = await loop.run_in_executor(None, self._call_wsgi_app, environ)

        return response_data

    def _build_environ(self, request_data):
        """Build WSGI environ dict"""
        url_parts = urlparse(request_data["url"])

        environ = {
            "REQUEST_METHOD": request_data["method"],
            "PATH_INFO": url_parts.path or "/",
            "QUERY_STRING": url_parts.query or "",
            "CONTENT_TYPE": request_data["headers"].get("content-type", ""),
            "CONTENT_LENGTH": request_data["headers"].get("content-length", ""),
            "SERVER_NAME": self._get_server_name(request_data["headers"]),
            "SERVER_PORT": "8000",
            "SERVER_PROTOCOL": "HTTP/1.1",
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": "http",
            "wsgi.input": BytesIO(request_data["body"]),
            "wsgi.errors": sys.stderr,  # WSGI spec requires a file-like object
            "wsgi.multithread": False,
            "wsgi.multiprocess": True,
            "wsgi.run_once": False,
        }

        # Add HTTP headers
        for name, value in request_data["headers"].items():
            key = name.upper().replace("-", "_")
            if key not in ("CONTENT_TYPE", "CONTENT_LENGTH"):
                key = f"HTTP_{key}"
            environ[key] = value

        return environ

    def _get_server_name(self, headers):
        """Extract server name from Host header"""
        host = headers.get("host", "localhost:8000")
        return host.split(":")[0]

    def _call_wsgi_app(self, environ):
        """Call WSGI application synchronously"""
        response_data = []
        status = None
        headers = None

        def start_response(status_line, response_headers, exc_info=None):
            nonlocal status, headers
            status = status_line
            headers = response_headers

        # Call WSGI app
        try:
            result = self.app(environ, start_response)

            # Build HTTP response
            response_lines = [f"HTTP/1.1 {status}\r\n".encode()]

            for header_name, header_value in headers:
                response_lines.append(f"{header_name}: {header_value}\r\n".encode())

            response_lines.append(b"\r\n")

            # Add response body
            for data in result:
                if isinstance(data, str):
                    data = data.encode("utf-8")
                response_lines.append(data)

            return b"".join(response_lines)

        except Exception as e:
            # Return 500 error
            error_body = f"Internal Server Error: {str(e)}".encode()
            return (
                b"HTTP/1.1 500 Internal Server Error\r\n"
                b"Content-Type: text/plain\r\n"
                + f"Content-Length: {len(error_body)}\r\n\r\n".encode()
                + error_body
            )


class FastHTTPParser:
    def __init__(self):
        self.reset()

    def reset(self):
        self.headers = {}
        self.body = b""
        self.url = None
        self.method = None
        self.should_keep_alive = False
        self.complete = False
        self.parser = httptools.HttpRequestParser(self)

    def on_message_begin(self):
        pass

    def on_url(self, url: bytes):
        self.url = url.decode()

    def on_header(self, name: bytes, value: bytes):
        self.headers[name.decode().lower()] = value.decode()

    def on_headers_complete(self):
        self.method = self.parser.get_method().decode()
        self.should_keep_alive = self.parser.should_keep_alive()

    def on_body(self, body: bytes):
        self.body += body

    def on_message_complete(self):
        self.complete = True

    def feed_data(self, data: bytes):
        self.parser.feed_data(data)

    def get_request_data(self):
        return {
            "method": self.method,
            "url": self.url,
            "headers": self.headers,
            "body": self.body,
            "keep_alive": self.should_keep_alive,
        }
