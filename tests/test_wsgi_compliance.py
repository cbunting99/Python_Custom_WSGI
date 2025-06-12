#!/usr/bin/env python3
"""
Test suite for WSGI compliance (PEP 3333)
"""
import unittest
import io
from typing import List, Tuple, Callable, Dict, Any
from src.core.wsgi_server import HighPerformanceWSGIServer
from src.core.request_handler import WSGIHandler

class WSGIComplianceTests(unittest.TestCase):
    def setUp(self):
        self.captured_env = {}
        self.captured_status = ''
        self.captured_headers: List[Tuple[str, str]] = []
        self.captured_exc_info = None
        self.response_chunks: List[bytes] = []

    def test_environ_variables(self):
        """Test that all required WSGI environ variables are present"""
        def test_app(environ: Dict[str, Any], start_response: Callable) -> List[bytes]:
            self.captured_env = environ
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return [b'test']

        handler = WSGIHandler(test_app)
        environ = self._create_test_environ()
        
        # Run request through handler
        self._run_request(handler, environ)
        
        # Required CGI variables
        self.assertIn('REQUEST_METHOD', self.captured_env)
        self.assertIn('SCRIPT_NAME', self.captured_env)
        self.assertIn('PATH_INFO', self.captured_env)
        self.assertIn('QUERY_STRING', self.captured_env)
        self.assertIn('CONTENT_TYPE', self.captured_env)
        self.assertIn('CONTENT_LENGTH', self.captured_env)
        self.assertIn('SERVER_NAME', self.captured_env)
        self.assertIn('SERVER_PORT', self.captured_env)
        self.assertIn('SERVER_PROTOCOL', self.captured_env)
        
        # Required WSGI variables
        self.assertIn('wsgi.version', self.captured_env)
        self.assertEqual(self.captured_env['wsgi.version'], (1, 0))
        self.assertIn('wsgi.url_scheme', self.captured_env)
        self.assertIn('wsgi.input', self.captured_env)
        self.assertIn('wsgi.errors', self.captured_env)
        self.assertIn('wsgi.multithread', self.captured_env)
        self.assertIn('wsgi.multiprocess', self.captured_env)
        self.assertIn('wsgi.run_once', self.captured_env)

    def test_start_response(self):
        """Test start_response behavior including exc_info handling"""
        def test_app(environ: Dict[str, Any], start_response: Callable) -> List[bytes]:
            try:
                raise ValueError("Test error")
            except ValueError:
                import sys
                exc_info = sys.exc_info()
                start_response('500 Internal Server Error', 
                             [('Content-Type', 'text/plain')],
                             exc_info)
            return [b'Error occurred']

        handler = WSGIHandler(test_app)
        environ = self._create_test_environ()
        
        # Run request and capture response
        response = self._run_request(handler, environ)
        
        # Verify response includes error info
        self.assertIn(b'Error occurred', response)
        self.assertIn('500 Internal Server Error', self.captured_status)

    def test_response_iterator(self):
        """Test handling of response iterator including cleanup"""
        class TestIterator:
            def __init__(self):
                self.chunks = [b'chunk1', b'chunk2', b'chunk3']
                self.closed = False
                
            def __iter__(self):
                return self
                
            def __next__(self):
                if not self.chunks:
                    raise StopIteration
                return self.chunks.pop(0)
                
            def close(self):
                self.closed = True

        def test_app(environ: Dict[str, Any], start_response: Callable) -> TestIterator:
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return TestIterator()

        handler = WSGIHandler(test_app)
        environ = self._create_test_environ()
        
        # Run request
        response = self._run_request(handler, environ)
        
        # Verify all chunks were received
        self.assertIn(b'chunk1', response)
        self.assertIn(b'chunk2', response)
        self.assertIn(b'chunk3', response)

    def test_file_wrapper(self):
        """Test file wrapper support"""
        test_content = b'Test file content'
        test_file = io.BytesIO(test_content)

        def test_app(environ: Dict[str, Any], start_response: Callable) -> Any:
            start_response('200 OK', [('Content-Type', 'text/plain')])
            if 'wsgi.file_wrapper' in environ:
                return environ['wsgi.file_wrapper'](test_file)
            return iter(lambda: test_file.read(4096), b'')

        handler = WSGIHandler(test_app)
        environ = self._create_test_environ()
        
        # Run request
        response = self._run_request(handler, environ)
        
        # Verify file content was received
        self.assertEqual(response, test_content)

    def test_middleware_support(self):
        """Test middleware compatibility"""
        def middleware(app):
            def wrapped_app(environ: Dict[str, Any], start_response: Callable) -> List[bytes]:
                # Modify environ
                environ['middleware.test'] = 'modified'
                
                def wrapped_start_response(status, headers, exc_info=None):
                    # Add header
                    headers.append(('X-Middleware-Test', 'true'))
                    return start_response(status, headers, exc_info)
                
                # Call original app
                response = app(environ, wrapped_start_response)
                
                # Modify response
                return [chunk.replace(b'original', b'modified') for chunk in response]
            
            return wrapped_app

        def test_app(environ: Dict[str, Any], start_response: Callable) -> List[bytes]:
            self.captured_env = environ
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return [b'original content']

        # Apply middleware
        wrapped_app = middleware(test_app)
        handler = WSGIHandler(wrapped_app)
        environ = self._create_test_environ()
        
        # Run request
        response = self._run_request(handler, environ)
        
        # Verify middleware modifications
        self.assertEqual(self.captured_env.get('middleware.test'), 'modified')
        self.assertTrue(any(h for h in self.captured_headers 
                          if h[0] == 'X-Middleware-Test'))
        self.assertIn(b'modified content', response)

    def test_chunked_response(self):
        """Test chunked transfer encoding"""
        def test_app(environ: Dict[str, Any], start_response: Callable) -> List[bytes]:
            start_response('200 OK', [
                ('Content-Type', 'text/plain'),
                ('Transfer-Encoding', 'chunked')
            ])
            return [b'chunk1', b'chunk2', b'chunk3']

        handler = WSGIHandler(test_app)
        environ = self._create_test_environ()
        
        # Run request
        response = self._run_request(handler, environ)
        
        # Verify chunked encoding
        self.assertTrue(any(h for h in self.captured_headers 
                          if h[0].lower() == 'transfer-encoding' 
                          and h[1].lower() == 'chunked'))
        
        # Verify chunks were properly encoded
        self.assertIn(b'chunk1', response)
        self.assertIn(b'chunk2', response)
        self.assertIn(b'chunk3', response)

    def _create_test_environ(self) -> Dict[str, Any]:
        """Create a test WSGI environ dictionary"""
        return {
            'REQUEST_METHOD': 'GET',
            'SCRIPT_NAME': '',
            'PATH_INFO': '/test',
            'QUERY_STRING': '',
            'CONTENT_TYPE': '',
            'CONTENT_LENGTH': '0',
            'SERVER_NAME': 'testserver',
            'SERVER_PORT': '80',
            'SERVER_PROTOCOL': 'HTTP/1.1',
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': 'http',
            'wsgi.input': io.BytesIO(b''),
            'wsgi.errors': io.StringIO(),
            'wsgi.multithread': False,
            'wsgi.multiprocess': False,
            'wsgi.run_once': False,
        }

    def _run_request(self, handler: WSGIHandler, environ: Dict[str, Any]) -> bytes:
        """Run a test request through the handler"""
        def start_response(status: str, headers: List[Tuple[str, str]], exc_info=None):
            self.captured_status = status
            self.captured_headers = headers
            self.captured_exc_info = exc_info

        response_iter = handler.app(environ, start_response)
        response = b''
        for chunk in response_iter:
            if chunk:
                response += chunk
        
        # Call close() if available
        if hasattr(response_iter, 'close'):
            response_iter.close()
            
        return response

if __name__ == '__main__':
    unittest.main()