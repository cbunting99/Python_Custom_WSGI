import asyncio
import ssl
from src.httptools_server import ConnectionHandler, FastWSGIServer, load_ssl_context
import pytest

class DummyWriter:
    def __init__(self):
        self.buffer = bytearray()
        self._last_status = None
        self._last_length = 0

    def get_extra_info(self, name, default=None):
        return None

    def write(self, data: bytes):
        self.buffer.extend(data)

    async def drain(self):
        await asyncio.sleep(0)

    def __getattr__(self, name):
        # Provide any last_ attributes access
        if name in ("_last_status", "_last_length"):
            return getattr(self, name, None)
        raise AttributeError

@pytest.mark.asyncio
async def test_streaming_app_chunks():
    async def dummy_reader():
        # Not used by _process_wsgi_request for our test
        pass

    # Streaming WSGI app that yields three chunks
    def streaming_app(environ, start_response):
        start_response("200 OK", [("Content-Type", "text/plain")])
        yield b"chunk1-"
        yield b"chunk2-"
        yield b"chunk3"

    handler = ConnectionHandler(streaming_app)
    writer = DummyWriter()
    request_data = {
        "method": "GET",
        "url": "/",
        "headers": {},
        "body": b"",
        "keep_alive": False,
    }

    # Run the streaming process
    await handler._process_wsgi_request(request_data, None, writer, "test-client", "req-1")

    out = bytes(writer.buffer)
    # Must contain chunked encoding terminator "0\r\n\r\n"
    assert b"0\r\n\r\n" in out
    assert b"chunk1-" in out and b"chunk2-" in out and b"chunk3" in out
