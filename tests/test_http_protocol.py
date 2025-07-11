#!/usr/bin/env python3
"""
Test suite for HTTP protocol compliance and edge cases
"""
import unittest
import asyncio
import io
from typing import Dict, List, Any, Tuple, Optional
from src.core.request_handler import WSGIHandler, WSGIError  # type: ignore


class MockStreamWriter:
    def __init__(self):
        self.buffer: List[bytes] = []
        self.closed = False

    def write(self, data: bytes) -> None:
        if not self.closed:
            self.buffer.append(data)

    async def drain(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        pass

    def get_extra_info(self, name: str) -> Optional[Tuple[str, int]]:
        return ("127.0.0.1", 8000) if name == "peername" else None


class MockStreamReader:
    def __init__(self, data: bytes = b""):
        self.data = data
        self.pos = 0

    async def read(self, n: int = -1) -> bytes:
        if self.pos >= len(self.data):
            return b""
        if n == -1:
            chunk = self.data[self.pos :]
            self.pos = len(self.data)
        else:
            chunk = self.data[self.pos : self.pos + n]
            self.pos += n
        return chunk


class HTTPProtocolTests(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.captured_env: Dict[str, Any] = {}

        def test_app(environ: Dict[str, Any], start_response):
            self.captured_env = environ.copy()  # Capture a copy of the environment
            headers = [("Content-Type", "text/plain")]
            start_response("200 OK", headers)
            return [b"Test Response"]

        self.test_app = test_app
        self.handler = WSGIHandler(test_app)

    def tearDown(self):
        self.loop.close()

    def test_request_methods(self):
        """Test handling of different HTTP methods"""
        methods = ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH"]

        for method in methods:
            with self.subTest(method=method):
                self.captured_env = {}  # Reset for each subtest

                if method in ("POST", "PUT", "PATCH"):
                    request_body = b"key=value"
                    content_length = len(request_body)
                    request = (
                        f"{method} /test HTTP/1.1\r\n"
                        f"Host: example.com\r\n"
                        f"Content-Length: {content_length}\r\n"
                        f"Content-Type: application/x-www-form-urlencoded\r\n"
                        f"\r\n"
                    ).encode() + request_body
                else:
                    request = (
                        f"{method} /test HTTP/1.1\r\n" f"Host: example.com\r\n" f"\r\n"
                    ).encode()

                response = self._run_raw_request(request)

                if method == "OPTIONS":
                    # WSGIHandler might handle OPTIONS directly (e.g., for CORS)
                    # Check for a successful response (204 No Content or 200 OK)
                    self.assertTrue(
                        response.startswith(b"HTTP/1.1 204")
                        or response.startswith(b"HTTP/1.1 200"),
                        f"OPTIONS request failed or returned unexpected status. Response: {response[:200]}",
                    )
                    if not self.captured_env:  # App was not called
                        continue

                self.assertIn(
                    "REQUEST_METHOD",
                    self.captured_env,
                    f"REQUEST_METHOD not in captured_env for {method}",
                )
                self.assertEqual(
                    self.captured_env["REQUEST_METHOD"],
                    method,
                    f"Wrong method {self.captured_env.get('REQUEST_METHOD')} != {method}",
                )

                if method == "HEAD":
                    self.assertNotIn(
                        b"Test Response",
                        response,
                        "Body should not be in HEAD response",
                    )
                    self.assertTrue(
                        response.endswith(b"\r\n\r\n"), "HEAD response format incorrect"
                    )
                elif (
                    method != "OPTIONS"
                ):  # OPTIONS might not return 'Test Response' if not handled by app
                    self.assertIn(
                        b"Test Response", response, "Body missing from response"
                    )

    def test_header_handling(self):
        """Test proper handling of HTTP headers"""
        self.captured_env = {}  # Reset for this test method
        request = (
            b"GET /test_headers HTTP/1.1\r\n"
            b"Content-Type: application/json\r\n"
            b"X-Custom-Header: test_value\r\n"
            b"User-Agent: TestSuite/1.0\r\n"
            b"\r\n"
        )

        self._run_raw_request(request)

        self.assertEqual(self.captured_env.get("CONTENT_TYPE"), "application/json")
        self.assertEqual(self.captured_env.get("HTTP_X_CUSTOM_HEADER"), "test_value")
        self.assertEqual(self.captured_env.get("HTTP_USER_AGENT"), "TestSuite/1.0")
        self.assertEqual(self.captured_env.get("PATH_INFO"), "/test_headers")

    def test_keep_alive(self):
        """Test keep-alive connection handling"""
        # Test HTTP/1.1 (keep-alive by default)
        request_http11 = b"GET /test HTTP/1.1\r\n" b"Host: example.com\r\n" b"\r\n"
        response_http11 = self._run_raw_request(request_http11)
        response_headers = response_http11.split(b"\r\n\r\n", 1)[0].lower()
        self.assertTrue(
            b"connection: keep-alive" in response_headers
            or b"Connection: keep-alive" in response_headers,
            f"keep-alive header not found in response headers: {response_headers}",
        )

        # Test HTTP/1.0 with keep-alive
        request_http10_keepalive = (
            b"GET /test HTTP/1.0\r\n"
            b"Connection: keep-alive\r\n"
            b"Host: example.com\r\n"
            b"\r\n"
        )
        response_http10_keepalive = self._run_raw_request(request_http10_keepalive)
        response_headers = response_http10_keepalive.split(b"\r\n\r\n", 1)[0].lower()
        self.assertTrue(
            b"connection: keep-alive" in response_headers
            or b"Connection: keep-alive" in response_headers,
            f"keep-alive header not found in response headers: {response_headers}",
        )

        # Test explicit close for HTTP/1.1
        request_http11_close = (
            b"GET /test HTTP/1.1\r\n"
            b"Connection: close\r\n"
            b"Host: example.com\r\n"
            b"\r\n"
        )
        response_http11_close = self._run_raw_request(request_http11_close)
        response_headers = response_http11_close.split(b"\r\n\r\n", 1)[0].lower()
        self.assertTrue(
            b"connection: close" in response_headers
            or b"Connection: close" in response_headers,
            f"close header not found in response headers: {response_headers}",
        )

    def test_malformed_requests(self):
        """Test handling of malformed requests"""
        # Test invalid request line
        request_invalid_line = b"INVALID REQUEST\r\n\r\n"
        response_invalid_line = self._run_raw_request(request_invalid_line)
        self.assertTrue(
            response_invalid_line.startswith(b"HTTP/1.1 400"),
            "Failed: Invalid request line",
        )

        # Test missing content length for POST (if WSGIHandler enforces this before app)
        request_post_no_cl = (
            b"POST /test HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Content-Type: text/plain\r\n"
            b"\r\n"
            b"test_body"
        )
        # Handler should enforce Content-Length for requests with bodies
        response_post_no_cl = self._run_raw_request(request_post_no_cl)
        self.assertTrue(response_post_no_cl.startswith(b"HTTP/1.1 400"))

        # Test invalid content length value
        request_post_invalid_cl = (
            b"POST /test HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Content-Type: text/plain\r\n"
            b"Content-Length: invalid_value\r\n"
            b"\r\n"
            b"test_body"
        )
        response_post_invalid_cl = self._run_raw_request(request_post_invalid_cl)
        self.assertTrue(response_post_invalid_cl.startswith(b"HTTP/1.1 400"))

    def test_error_handling_in_app(self):
        """Test error response handling when WSGI app raises an exception"""

        def error_raising_app(environ: Dict[str, Any], start_response):
            # This app will raise an unhandled exception
            raise ValueError("Simulated application error")

        error_handler = WSGIHandler(error_raising_app)
        request = b"GET /error_test HTTP/1.1\r\n" b"Host: example.com\r\n" b"\r\n"
        response = self._run_raw_request(request, handler_override=error_handler)

        self.assertTrue(
            response.startswith(b"HTTP/1.1 500"),
            "Application error did not result in 500 status",
        )
        self.assertIn(
            b"Internal Server Error",
            response,
            "Application error response body incorrect",
        )

    def _run_raw_request(
        self, request_data: bytes, handler_override: Optional[WSGIHandler] = None
    ) -> bytes:
        """Run a raw request through the handler."""
        reader = MockStreamReader(request_data)
        writer = MockStreamWriter()
        current_handler = handler_override or self.handler

        async def run():
            await current_handler.handle_request(reader, writer)
            return b"".join(writer.buffer)

        return self.loop.run_until_complete(run())


if __name__ == "__main__":
    unittest.main()
