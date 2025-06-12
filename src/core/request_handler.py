import asyncio
from io import StringIO
import sys

class WSGIHandler:
    def __init__(self, app):
        self.app = app
        
    async def handle_request(self, reader, writer):
        try:
            # Read HTTP request
            request_data = await reader.read(8192)
            if not request_data:
                return
                
            # Parse HTTP request
            request_line, headers_and_body = request_data.split(b'\r\n', 1)
            method, path, version = request_line.decode().split()
            
            # Parse headers
            headers_part, body = headers_and_body.split(b'\r\n\r\n', 1)
            headers = {}
            for line in headers_part.decode().split('\r\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()
            
            # Build WSGI environ
            environ = self._build_environ(method, path, headers, body, writer)
            
            # Call WSGI app
            response_data = await self._call_wsgi_app(environ)
            
            # Send response
            writer.write(response_data)
            await writer.drain()
            
        except Exception as e:
            # Send 500 error
            error_response = b'HTTP/1.1 500 Internal Server Error\r\n\r\nInternal Server Error'
            writer.write(error_response)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
    
    def _build_environ(self, method, path, headers, body, writer):
        # Build WSGI environ dict
        environ = {
            'REQUEST_METHOD': method,
            'PATH_INFO': path,
            'SERVER_NAME': '127.0.0.1',
            'SERVER_PORT': '8000',
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': 'http',
            'wsgi.input': StringIO(body.decode()),
            'wsgi.errors': sys.stderr,
            'wsgi.multithread': False,
            'wsgi.multiprocess': True,
            'wsgi.run_once': False,
        }
        
        # Add headers to environ
        for key, value in headers.items():
            key = key.upper().replace('-', '_')
            if key not in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
                key = f'HTTP_{key}'
            environ[key] = value
            
        return environ
    
    async def _call_wsgi_app(self, environ):
        # WSGI apps are synchronous, so run in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_wsgi_call, environ)
    
    def _sync_wsgi_call(self, environ):
        response_data = []
        status = None
        headers = None
        
        def start_response(status_line, response_headers):
            nonlocal status, headers
            status = status_line
            headers = response_headers
            
        # Call the WSGI application
        result = self.app(environ, start_response)
        
        # Build HTTP response
        response_parts = [f'HTTP/1.1 {status}\r\n'.encode()]
        for header_name, header_value in headers:
            response_parts.append(f'{header_name}: {header_value}\r\n'.encode())
        response_parts.append(b'\r\n')
        
        # Add body
        for data in result:
            if isinstance(data, str):
                data = data.encode()
            response_parts.append(data)
            
        return b''.join(response_parts)