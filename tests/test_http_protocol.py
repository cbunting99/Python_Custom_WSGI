#!/usr/bin/env python3
"""
Test suite for HTTP protocol compliance and edge cases
"""
import unittest
import asyncio
import io
from typing import Dict, List, Any, Tuple
from src.core.request_handler import WSGIHandler, WSGIError

class MockStreamWriter:
    def __init__(self):
        self.buffer = []
        self.closed = False
        
    def write(self, data):
        self.buffer.append(data)
        
    async def drain(self):
        pass
        
    def close(self):
        self.closed = True
        
    async def wait_closed(self):
        pass
        
    def get_extra_info(self, name):
        return ('127.0.0.1', 8000) if name == 'peername' else None

class MockStreamReader:
    def __init__(self, data=b''):
        self.data = data
        self.pos = 0
        
    async def read(self, n=-1):
        if self.pos >= len(self.data):
            return b''
        if n == -1:
            chunk = self.data[self.pos:]
            self.pos = len(self.data)
        else:
            chunk = self.data[self.pos:self.pos + n]
            self.pos += n
        return chunk

class HTTPProtocolTests(unittest.TestCase):
    def setUp(self):
        self.captured_env = {}
        self.response_data = b''
        
        def test_app(environ: Dict[str, Any], start_response):
            self.captured_env = environ
            headers = [('Content-Type', 'text/plain')]
            start_response('200 OK', headers)
            return [b'Test Response']
            
        self.test_app = test_app
        self.handler = WSGIHandler(test_app)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_request_methods(self):
        """Test handling of different HTTP methods"""
        methods = ['GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'OPTIONS', 'PATCH']
        
        for method in methods:
            with self.subTest(method=method):
                request = (
                    f'{method} /test HTTP/1.1\r\n'
                    'Host: example.com\r\n'
                    '\r\n'
                ).encode()
                
                response = self._run_raw_request(request)
                self.assertEqual(self.captured_env['REQUEST_METHOD'], method)
                
                if method == 'HEAD':
                    # HEAD requests should not include body
                    self.assertNotIn(b'Test Response', response)
                    self.assertTrue(response.endswith(b'\r\n\r\n'))
                elif method != 'OPTIONS':  # OPTIONS handled separately
                    self.assertIn(b'Test Response', response)

    def test_header_handling(self):
        """Test proper handling of HTTP headers"""
        request = (
            b'GET /test HTTP/1.1\r\n'
            b'Content-Type: application/json\r\n'
            b'X-Custom-Header: test\r\n'
            b'User-Agent: Test/1.0\r\n'
            b'\r\n'
        )
        
        self._run_raw_request(request)
        
        self.assertEqual(self.captured_env['CONTENT_TYPE'], 'application/json')
        self.assertEqual(self.captured_env['HTTP_X_CUSTOM_HEADER'], 'test')
        self.assertEqual(self.captured_env['HTTP_USER_AGENT'], 'Test/1.0')

    def test_keep_alive(self):
        """Test keep-alive connection handling"""
        # Test HTTP/1.1 (keep-alive by default)
        request = (
            b'GET /test HTTP/1.1\r\n'
            b'Host: example.com\r\n'
            b'\r\n'
        )
        response = self._run_raw_request(request)
        self.assertIn(b'Connection: keep-alive\r\n', response)
        
        # Test HTTP/1.0 with keep-alive
        request = (
            b'GET /test HTTP/1.0\r\n'
            b'Connection: keep-alive\r\n'
            b'Host: example.com\r\n'
            b'\r\n'
        )
        response = self._run_raw_request(request)
        self.assertIn(b'Connection: keep-alive\r\n', response)
        
        # Test explicit close
        request = (
            b'GET /test HTTP/1.1\r\n'
            b'Connection: close\r\n'
            b'Host: example.com\r\n'
            b'\r\n'
        )
        response = self._run_raw_request(request)
        self.assertIn(b'Connection: close\r\n', response)

    def test_malformed_requests(self):
        """Test handling of malformed requests"""
        # Test invalid request line
        request = b'INVALID\r\n\r\n'
        response = self._run_raw_request(request)
        self.assertTrue(response.startswith(b'HTTP/1.1 400'))
        
        # Test missing content length
        request = (
            b'POST /test HTTP/1.1\r\n'
            b'Host: example.com\r\n'
            b'\r\n'
            b'test'
        )
        response = self._run_raw_request(request)
        self.assertTrue(response.startswith(b'HTTP/1.1 400'))
            
        # Test invalid content length
        request = (
            b'POST /test HTTP/1.1\r\n'
            b'Content-Length: invalid\r\n'
            b'Host: example.com\r\n'
            b'\r\n'
            b'test'
        )
        response = self._run_raw_request(request)
        self.assertTrue(response.startswith(b'HTTP/1.1 400'))

    def test_error_handling(self):
        """Test error response handling"""
        def error_app(environ, start_response):
            raise ValueError("Test error")

        handler = WSGIHandler(error_app)
        request = (
            b'GET /test HTTP/1.1\r\n'
            b'Host: example.com\r\n'
            b'\r\n'
        )
        response = self._run_raw_request(request, handler)
        
        self.assertTrue(response.startswith(b'HTTP/1.1 500'))
        self.assertIn(b'Internal Server Error', response)

    def _run_raw_request(self, request_data: bytes, handler=None) -> bytes:
        """Run a raw request through the handler."""
        reader = MockStreamReader(request_data)
        writer = MockStreamWriter()
        handler = handler or self.handler
        
        async def run():
            await handler.handle_request(reader, writer)
            return b''.join(writer.buffer)
            
        return self.loop.run_until_complete(run())

if __name__ == '__main__':
    unittest.main()