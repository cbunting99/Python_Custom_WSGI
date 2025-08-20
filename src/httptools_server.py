"""
High-performance WSGI server implementation using httptools.

This module provides a high-performance WSGI server implementation that:
- Uses httptools for fast HTTP parsing
- Supports multi-processing for improved performance
- Integrates with uvloop when available
- Implements HTTP keep-alive and pipelining
- Supports streaming responses with chunked transfer encoding when Content-Length is absent
- Exposes optional Prometheus metrics and basic health/metrics endpoints
- Adds graceful shutdown handling and coordinated multiprocess shutdown
- Includes TLS helper for loading ssl.SSLContext
- Emits structured JSON access logs and per-request request IDs
"""

"""
Copyright 2025 Chris Bunting
File: httptools_server.py | Purpose: High-performance WSGI server
@author Chris Bunting | @version 1.2.0

CHANGELOG:
2025-07-11 - Chris Bunting: Fixed wsgi.errors to use sys.stderr
2025-07-10 - Chris Bunting: Initial implementation
2025-08-20 - Chris Bunting: Add streaming/chunked responses, metrics, health, graceful shutdown
2025-08-20 - Chris Bunting: Add coordinated multiprocess graceful shutdown, JSON logs, TLS helper, request IDs
"""

import asyncio
try:
    import httptools  # type: ignore
    HTTPTOOLS_AVAILABLE = True
except Exception:
    # httptools is an optional C extension; provide a graceful fallback on platforms
    # where it cannot be installed (for example, Windows + Python 3.13 where no wheel exists).
    httptools = None
    HTTPTOOLS_AVAILABLE = False

# Provide stable local aliases for symbols used across the file so code paths
# that reference them do not need to import httptools directly and static
# analysis won't complain when httptools is unavailable.
if HTTPTOOLS_AVAILABLE:
    HttpParserError = httptools.HttpParserError  # type: ignore
    HttpRequestParser = httptools.HttpRequestParser  # type: ignore
else:
    class HttpParserError(Exception):
        """Fallback exception when httptools is not installed."""
        pass

    HttpRequestParser = None  # type: ignore
import multiprocessing
import signal
import sys
import logging
import socket
import traceback
import os
import ssl
import uuid
import json
from urllib.parse import urlparse, parse_qs
from io import BytesIO
from typing import Optional, Iterable, Tuple, List

# Try to import uvloop for better performance on Linux/macOS
try:
    import uvloop  # type: ignore

    UVLOOP_AVAILABLE = True
except Exception:
    UVLOOP_AVAILABLE = False

# Optional python-json-logger for nicer JSON logs
# Import in a way that avoids the deprecation warning introduced in
# some versions (pythonjsonlogger.jsonlogger -> pythonjsonlogger.json).
try:
    # Preferred (new) location
    from pythonjsonlogger.json import JsonFormatter  # type: ignore

    JSONLOGGER_AVAILABLE = True
except Exception:
    try:
        # Fallback to older layout
        from pythonjsonlogger import jsonlogger  # type: ignore

        JsonFormatter = jsonlogger.JsonFormatter
        JSONLOGGER_AVAILABLE = True
    except Exception:
        # Provide a minimal local JsonFormatter fallback for environments where
        # python-json-logger is not installed so the editor/static-checkers
        # and runtime don't report unbound names.
        JSONLOGGER_AVAILABLE = False

        class JsonFormatter(logging.Formatter):
            """
            Minimal fallback formatter that emits a compact JSON object.
            This is intentionally simple to avoid a hard dependency on
            python-json-logger while keeping logs structured.
            """

            def format(self, record):
                base = {
                    "timestamp": self.formatTime(record, self.datefmt),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                }
                extra = getattr(record, "extra_json", None)
                if isinstance(extra, dict):
                    base.update(extra)
                return json.dumps(base, separators=(",", ":"), default=str)

# Optional prometheus_client integration
try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST  # type: ignore

    PROM_AVAILABLE = True
    REQ_TOTAL = Counter("fastwsgi_requests_total", "Total HTTP requests")
    REQ_ERRORS = Counter("fastwsgi_request_errors_total", "Total HTTP request errors")
    REQ_IN_FLIGHT = Gauge("fastwsgi_in_flight_requests", "In-flight requests")
    REQ_LATENCY = Histogram("fastwsgi_request_duration_seconds", "Request duration seconds")
except Exception:
    # Provide safe defaults so static analysis and runtime paths that reference
    # these names do not raise UnboundName errors when prometheus_client is not installed.
    PROM_AVAILABLE = False

    def generate_latest():
        return b""

    CONTENT_TYPE_LATEST = b"text/plain; version=0.0.4; charset=utf-8"

    class _DummyMetric:
        def inc(self, *a, **k): pass
        def dec(self, *a, **k): pass
        def observe(self, *a, **k): pass

    REQ_TOTAL = _DummyMetric()
    REQ_ERRORS = _DummyMetric()
    REQ_IN_FLIGHT = _DummyMetric()
    REQ_LATENCY = _DummyMetric()

# Logger for the server (structured access log uses JSON string payloads)
logger = logging.getLogger("fastwsgi")
if not logger.handlers:
    handler = logging.StreamHandler()
    if JSONLOGGER_AVAILABLE:
        fmt = JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        handler.setFormatter(fmt)
    else:
        # Fallback to compact JSON message via custom formatter
        class _JSONFallbackFormatter(logging.Formatter):
            def format(self, record):
                base = {
                    "timestamp": self.formatTime(record, self.datefmt),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                }
                # attempt to include extra dict if provided (use getattr to avoid static type issues)
                extra = getattr(record, "extra_json", None)
                if isinstance(extra, dict):
                    base.update(extra)
                return json.dumps(base, separators=(",", ":"), default=str)

        handler.setFormatter(_JSONFallbackFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _access_log_payload(method: str, path: str, status: int, length: int, duration: float, client: str, request_id: str):
    payload = {
        "method": method,
        "path": path,
        "status": status,
        "length": length,
        "duration_s": round(duration, 6),
        "client": client,
        "request_id": request_id,
    }
    return payload


def load_ssl_context(certfile: str, keyfile: str, ca_bundle: Optional[str] = None, *, protocol=ssl.PROTOCOL_TLS_SERVER) -> ssl.SSLContext:
    """
    Helper to create an SSLContext for serving TLS.
    - certfile: path to server certificate (PEM)
    - keyfile: path to private key (PEM)
    - ca_bundle: optional CA bundle to load for client verification (if needed)
    Returns configured ssl.SSLContext
    """
    context = ssl.SSLContext(protocol)
    # Secure defaults
    context.options |= ssl.OP_NO_SSLv2 | ssl.OP_NO_SSLv3
    context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
    context.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM")
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    if ca_bundle:
        context.load_verify_locations(cafile=ca_bundle)
    # Require secure renegotiation and don't request client cert by default
    context.verify_mode = ssl.CERT_NONE
    return context


class FastWSGIServer:
    def __init__(
        self,
        app,
        host: str = "127.0.0.1",
        port: int = 8000,
        workers: Optional[int] = None,
        ssl_context: Optional[ssl.SSLContext] = None,
        read_timeout: float = 10.0,
        header_limit: int = 8192,
        body_limit: int = 10 * 1024 * 1024,
        max_requests: int = 1000,
    ):
        """
        app: WSGI application callable
        ssl_context: optional ssl.SSLContext for TLS
        read_timeout: per-read timeout in seconds
        header_limit: maximum size in bytes for headers (informational - parser may enforce)
        body_limit: maximum size in bytes for request body
        max_requests: max requests per connection (keep-alive)
        """
        self.app = app
        self.host = host
        self.port = port
        self.workers = workers or multiprocessing.cpu_count()
        self.ssl_context = ssl_context
        self.read_timeout = read_timeout
        self.header_limit = header_limit
        self.body_limit = body_limit
        self.max_requests = max_requests

        # Graceful shutdown coordination
        self._shutdown_event: Optional[asyncio.Event] = None

    def run(self):
        if self.workers == 1:
            if UVLOOP_AVAILABLE and sys.platform != "win32":
                asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            asyncio.run(self._serve())
        else:
            self._run_multiprocess()

    def _run_multiprocess(self):
        """
        Start worker processes and coordinate graceful shutdown.
        On POSIX, intercept SIGINT/SIGTERM in master and forward SIGTERM to workers
        to allow graceful draining. Wait for workers to exit cleanly, then force-terminate.
        """
        processes: List[multiprocessing.Process] = []

        def _forward_signal(signum, frame):
            logger.info("Master received signal %s, forwarding SIGTERM to workers", signum)
            for p in processes:
                try:
                    # Send SIGTERM to each worker pid (POSIX). On Windows this will raise; use terminate as fallback.
                    pid = p.pid
                    if pid is not None and hasattr(os, "kill"):
                        os.kill(pid, signal.SIGTERM)
                    else:
                        p.terminate()
                except Exception:
                    logger.exception("Failed to forward signal to worker %s", p.pid)

        if sys.platform != "win32":
            signal.signal(signal.SIGINT, _forward_signal)
            signal.signal(signal.SIGTERM, _forward_signal)

        for i in range(self.workers):
            p = multiprocessing.Process(target=self._worker, args=(i,))
            p.start()
            processes.append(p)

        # Wait for workers, but handle graceful shutdown window
        try:
            for p in processes:
                p.join()
        except KeyboardInterrupt:
            logger.info("Master interrupted; asking workers to terminate")
            for p in processes:
                try:
                    pid = p.pid
                    if pid is not None and hasattr(os, "kill"):
                        os.kill(pid, signal.SIGTERM)
                    else:
                        p.terminate()
                except Exception:
                    logger.exception("Error terminating worker %s", p.pid)

        # If any workers still alive after timeout, force terminate
        for p in processes:
            if p.is_alive():
                logger.info("Worker %s still alive; force terminating", p.pid)
                try:
                    p.terminate()
                except Exception:
                    logger.exception("Error force-terminating worker %s", p.pid)

    def _worker(self, worker_id):
        if UVLOOP_AVAILABLE and sys.platform != "win32":
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        # Worker should run server and respond to SIGTERM to perform graceful shutdown
        try:
            asyncio.run(self._serve())
        except Exception:
            logger.exception("Worker %s crashed", worker_id)

    async def _serve(self):
        # Determine reuse_port support (not available on Windows)
        reuse_port = False
        try:
            reuse_port = hasattr(socket, "SO_REUSEPORT") and sys.platform != "win32"
        except Exception:
            reuse_port = False

        self._shutdown_event = asyncio.Event()

        server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
            reuse_address=True,
            reuse_port=reuse_port,
            backlog=2048,
            ssl=self.ssl_context,
        )

        sock = server.sockets[0] if server.sockets else None
        bound = f"{self.host}:{self.port}"
        if sock:
            try:
                addr = sock.getsockname()
                bound = f"{addr[0]}:{addr[1]}"
            except Exception:
                pass

        logger.info("Worker serving on %s pid=%s", bound, os.getpid())

        # Attach signal handlers for graceful shutdown (POSIX)
        if sys.platform != "win32":
            loop = asyncio.get_event_loop()

            def _handle_sigterm():
                logger.info("SIGTERM received in worker, initiating graceful shutdown")
                loop.create_task(self._initiate_shutdown(server))

            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, _handle_sigterm)
                except Exception:
                    # Some platforms may not support add_signal_handler
                    pass

        async with server:
            await server.serve_forever()

    async def _initiate_shutdown(self, server):
        # Stop accepting new connections, allow existing to drain
        try:
            server.close()
            logger.info("Server stopped accepting new connections, waiting for close")
            await server.wait_closed()
        except Exception:
            logger.exception("Error while closing server socket")

        # Signal handlers in connection handlers can check self._shutdown_event to stop
        if self._shutdown_event and not self._shutdown_event.is_set():
            self._shutdown_event.set()

    async def _handle_client(self, reader, writer):
        # Pass server-level configuration into the connection handler
        handler = ConnectionHandler(
            self.app,
            read_timeout=self.read_timeout,
            header_limit=self.header_limit,
            body_limit=self.body_limit,
            max_requests=self.max_requests,
            shutdown_event=self._shutdown_event,
        )
        try:
            await handler.handle_connection(reader, writer)
        except Exception:
            logger.exception("Connection handler raised an unexpected exception")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                logger.debug("Error closing writer", exc_info=True)


class ConnectionHandler:
    def __init__(
        self,
        app,
        read_timeout: float = 10.0,
        header_limit: int = 8192,
        body_limit: int = 10 * 1024 * 1024,
        max_requests: int = 1000,
        shutdown_event: Optional[asyncio.Event] = None,
    ):
        self.app = app
        self.read_timeout = read_timeout
        self.header_limit = header_limit
        self.body_limit = body_limit
        self.max_requests = max_requests
        self.shutdown_event = shutdown_event

    async def handle_connection(self, reader, writer):
        """Handle keep-alive connection with multiple requests"""
        keep_alive = True
        requests_handled = 0

        peer = writer.get_extra_info("peername")
        client = f"{peer[0]}:{peer[1]}" if peer else "unknown"

        while keep_alive and requests_handled < self.max_requests:
            # If server is shutting down, stop accepting new requests on this connection
            if self.shutdown_event and self.shutdown_event.is_set():
                logger.info("Shutdown in progress - closing connection to %s", client)
                break

            try:
                # Parse HTTP request
                parser = FastHTTPParser()
                request_data = await self._read_request(reader, parser)

                if not request_data:
                    break

                # Health and metrics endpoints (handled without invoking WSGI app)
                url_parts = urlparse(request_data.get("url", "/"))
                path = url_parts.path or "/"

                if path == "/health" or path == "/-/health":
                    resp = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK"
                    writer.write(resp)
                    await writer.drain()
                    requests_handled += 1
                    continue

                if PROM_AVAILABLE and path == "/metrics":
                    # Serve prometheus metrics
                    metrics_body = generate_latest()
                    headers = (
                        b"HTTP/1.1 200 OK\r\n"
                        + b"Content-Type: " + CONTENT_TYPE_LATEST + b"\r\n"
                        + b"Content-Length: " + str(len(metrics_body)).encode() + b"\r\n\r\n"
                    )
                    writer.write(headers + metrics_body)
                    await writer.drain()
                    requests_handled += 1
                    continue

                # Process WSGI request (with streaming support)
                start_time = asyncio.get_event_loop().time()
                if PROM_AVAILABLE:
                    REQ_IN_FLIGHT.inc()
                    REQ_TOTAL.inc()

                # Generate request ID and add to environ
                request_id = str(uuid.uuid4())
                request_data.setdefault("headers", {})
                request_data["headers"]["x-request-id"] = request_id

                try:
                    await self._process_wsgi_request(request_data, reader, writer, client, request_id)
                except Exception:
                    if PROM_AVAILABLE:
                        REQ_ERRORS.inc()
                    logger.exception("Error processing WSGI request")
                    # Return generic 500 without leaking internals
                    error_response = (
                        b"HTTP/1.1 500 Internal Server Error\r\n"
                        b"Content-Length: 21\r\n\r\n"
                        b"Internal Server Error"
                    )
                    writer.write(error_response)
                    await writer.drain()
                    break
                finally:
                    duration = asyncio.get_event_loop().time() - start_time
                    # Access log: method, path, status from writer attributes
                    try:
                        status = getattr(writer, "_last_status", 200)
                        length = getattr(writer, "_last_length", 0)
                        payload = _access_log_payload(request_data.get("method", "GET"), path, status, length, duration, client, request_id)
                        # Attach as extra_json so fallback formatter includes it, or log as JSON string
                        logger.info(json.dumps(payload, separators=(",", ":")), extra={"extra_json": payload})
                    except Exception:
                        logger.info("Request processed for %s %s in %fs", client, path, duration)
                    if PROM_AVAILABLE:
                        REQ_IN_FLIGHT.dec()
                        REQ_LATENCY.observe(duration)

                keep_alive = request_data.get("keep_alive", False)
                requests_handled += 1

            except asyncio.IncompleteReadError:
                break
            except Exception:
                logger.exception("Unhandled exception in connection loop")
                break

    async def _read_request(self, reader, parser):
        """Read and parse HTTP request with timeouts and limits"""
        total_read = 0
        try:
            while not parser.complete:
                try:
                    data = await asyncio.wait_for(reader.read(8192), timeout=self.read_timeout)
                except asyncio.TimeoutError:
                    logger.warning("Read timeout while receiving request")
                    return None

                if not data:
                    return None

                total_read += len(data)
                # Enforce a soft header/body size limit to avoid resource exhaustion
                if total_read > self.header_limit + self.body_limit:
                    logger.warning("Request exceeded configured max size (%d bytes)", total_read)
                    return None

                try:
                    parser.feed_data(data)
                except HttpParserError:
                    logger.warning("Malformed HTTP request received")
                    return None

            # Enforce body limit (httptools accumulates body in parser.body)
            if len(parser.body) > self.body_limit:
                logger.warning("Request body too large: %d bytes", len(parser.body))
                return None

            return parser.get_request_data()
        except Exception:
            logger.exception("Unexpected error while reading request")
            return None

    async def _process_wsgi_request(self, request_data, reader, writer, client, request_id: str):
        """Process WSGI request with streaming support using an executor and an asyncio.Queue"""
        loop = asyncio.get_event_loop()
        environ = self._build_environ(request_data)

        # If app wants to run under https, set scheme appropriately if ssl present on writer
        ssl_object = writer.get_extra_info("ssl_object")
        if ssl_object:
            environ["wsgi.url_scheme"] = "https"

        # Propagate request ID in environ
        environ["HTTP_X_REQUEST_ID"] = request_id

        # Queue to receive body chunks from worker thread
        q: asyncio.Queue = asyncio.Queue()

        def _iter_app_and_push():
            """
            Run in thread executor: call WSGI app synchronously and push chunked parts into the
            event-loop queue via loop.call_soon_threadsafe.
            """
            try:
                write_callable = None

                status = None
                headers = None
                headers_sent = False

                def write(data):
                    nonlocal write_callable
                    if isinstance(data, str):
                        chunk = data.encode("utf-8")
                    else:
                        chunk = data
                    # push chunk to loop's queue
                    loop.call_soon_threadsafe(q.put_nowait, chunk)
                    # buffer in case start_response-based write is used
                    return None

                def start_response(status_line, response_headers, exc_info=None):
                    nonlocal status, headers, headers_sent, write_callable
                    if exc_info:
                        # If headers already sent, re-raise
                        if headers_sent:
                            raise exc_info[1].with_traceback(exc_info[2])
                    status = status_line
                    headers = list(response_headers)
                    write_callable = write
                    return write

                result = self.app(environ, start_response)

                # If result is iterable, iterate and push each chunk
                for data in result:
                    if isinstance(data, str):
                        data = data.encode("utf-8")
                    loop.call_soon_threadsafe(q.put_nowait, data)

                # Close iterator if needed
                if hasattr(result, "close"):
                    try:
                        result.close()
                    except Exception:
                        logger.exception("Error closing result iterable")

                # Finally signal completion
                loop.call_soon_threadsafe(q.put_nowait, None)
            except Exception as exc:
                # Push exception marker
                logger.exception("Exception in WSGI app executor")
                loop.call_soon_threadsafe(q.put_nowait, exc)

        # Run the WSGI app in executor
        loop.run_in_executor(None, _iter_app_and_push)

        # Now, in event loop, read first item(s) to determine headers and whether we need chunked encoding.
        # Because WSGI start_response is synchronous and executed in executor, headers are not directly available here.
        # We'll buffer up first chunk(s) until headers can be inferred; to keep compatibility we will:
        # - Collect chunks until the executor signals None (done) or until we've collected enough to determine length.
        # For correctness we will stream chunks using chunked transfer encoding when Content-Length is not provided.

        # Collect initial chunks but do not buffer indefinitely
        body_parts: List[bytes] = []
        status_line = "200 OK"

        # Gather a small number of chunks to allow header detection
        while True:
            item = await q.get()
            if isinstance(item, Exception):
                # Exception occurred in app
                raise item
            if item is None:
                # No body yielded
                break
            body_parts.append(item)
            # Don't block collecting: break early if body becomes large
            if sum(len(p) for p in body_parts) > 65536:
                # Stop collecting more eagerly - start streaming
                break
            # Try to get next with a small timeout so we can continue
            if q.empty():
                # give executor a moment; if nothing new, continue to streaming
                break

        # Default to chunked transfer encoding when content-length not known
        use_chunked = True

        # Write status and minimal headers - include request-id so upstream systems can correlate
        header_lines = [f"HTTP/1.1 {status_line}\r\n".encode()]
        header_lines.append(f"X-Request-ID: {request_id}\r\n".encode())
        if use_chunked:
            header_lines.append(b"Transfer-Encoding: chunked\r\n")
        header_lines.append(b"\r\n")

        writer.write(b"".join(header_lines))
        await writer.drain()

        # If we have initial buffered parts, send them first
        for p in body_parts:
            # send chunk
            if not p:
                continue
            chunk_header = f"{len(p):X}\r\n".encode()
            writer.write(chunk_header + p + b"\r\n")
            await writer.drain()
            # track last written for access logs
            writer._last_length = getattr(writer, "_last_length", 0) + len(p)

        # Continue streaming remaining items from queue
        while True:
            item = await q.get()
            if isinstance(item, Exception):
                # error in executor => abort streaming
                logger.exception("WSGI app raised in executor while streaming")
                break
            if item is None:
                # end of stream
                break
            p = item
            if not p:
                continue
            chunk_header = f"{len(p):X}\r\n".encode()
            writer.write(chunk_header + p + b"\r\n")
            await writer.drain()
            writer._last_length = getattr(writer, "_last_length", 0) + len(p)

        # Write final zero-length chunk
        writer.write(b"0\r\n\r\n")
        await writer.drain()

        # Mark last status for access log (200 for now)
        writer._last_status = 200

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


# FastHTTPParser: prefer httptools (fast C parser). If not available, use a simple
# conservative pure-Python fallback parser that supports basic requests for testing
# and simple workloads.
if HTTPTOOLS_AVAILABLE:
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
            # Use alias that may be None when httptools is unavailable
            if HttpRequestParser is not None:
                self.parser = HttpRequestParser(self)
            else:
                self.parser = None

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
else:
    class FastHTTPParser:
        """
        Minimal pure-Python HTTP request parser fallback.
        Not a full replacement for httptools, but sufficient for tests and simple WSGI usage.
        It buffers until it sees the header/body separator (\\r\\n\\r\\n), parses request-line
        and headers, then collects the body according to Content-Length (if present).
        """
        def __init__(self):
            self.reset()

        def reset(self):
            self._buffer = b""
            self.headers = {}
            self.body = b""
            self.url = None
            self.method = None
            self.should_keep_alive = False
            self.complete = False
            self._content_length = None

        def feed_data(self, data: bytes):
            if self.complete:
                return
            self._buffer += data

            # If we haven't seen headers yet, try to parse them
            if b"\r\n\r\n" in self._buffer and not self.headers:
                head, rest = self._buffer.split(b"\r\n\r\n", 1)
                lines = head.split(b"\r\n")
                # Parse request line
                try:
                    request_line = lines[0].decode("ascii", errors="ignore")
                    parts = request_line.split()
                    if len(parts) >= 2:
                        self.method = parts[0]
                        self.url = parts[1]
                except Exception:
                    # Malformed request
                    self.complete = True
                    return

                # Parse headers
                for h in lines[1:]:
                    if not h:
                        continue
                    try:
                        name, value = h.split(b":", 1)
                        self.headers[name.decode().lower()] = value.strip().decode()
                    except Exception:
                        continue

                # Determine content length if present
                cl = self.headers.get("content-length")
                if cl:
                    try:
                        self._content_length = int(cl)
                    except Exception:
                        self._content_length = None

                # Start body with remaining bytes
                self.body = rest

                # If no content length, message is complete after headers (no body expected)
                if self._content_length is None or self._content_length == 0:
                    self.complete = True
                    self.should_keep_alive = self.headers.get("connection", "").lower() != "close"
                    return

            else:
                # If headers already parsed, append to body
                if self.headers:
                    self.body += b""

            # If we have a content length, check if we have the full body
            if self._content_length is not None:
                # If we parsed headers earlier, self.body contains remainder past headers
                if len(self.body) >= self._content_length:
                    self.complete = True
                    self.should_keep_alive = self.headers.get("connection", "").lower() != "close"

        def get_request_data(self):
            return {
                "method": self.method,
                "url": self.url if self.url is not None else "/",
                "headers": self.headers,
                "body": self.body,
                "keep_alive": self.should_keep_alive,
            }
