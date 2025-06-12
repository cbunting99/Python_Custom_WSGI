"""
WSGI request handler implementation for processing HTTP requests.

This module provides the core request handling functionality including:
- HTTP request parsing and validation
- WSGI environment construction
- Request size and timeout limits
- Error handling and logging
"""

import asyncio
from io import BytesIO
import sys
from typing import Dict, List, Tuple, Union, Optional, Callable, Any

class WSGIHandler:
    """Handles individual HTTP requests according to WSGI specification.
    
    Constants:
        MAX_REQUEST_SIZE: Maximum allowed size for incoming requests (1MB)
        REQUEST_TIMEOUT: Timeout for receiving request data (30 seconds)
        MAX_HEADER_SIZE: Maximum size for individual headers (8KB)
    """
    MAX_REQUEST_SIZE = 1048576  # 1MB limit
    REQUEST_TIMEOUT = 30  # 30 seconds
    MAX_HEADER_SIZE = 8192  # 8KB limit per header

    def __init__(self, app):
        self.app = app
        
    async def handle_request(self,
                           reader: asyncio.StreamReader,
                           writer: asyncio.StreamWriter) -> None:
        """Process a single HTTP request.
        
        Args:
            reader: StreamReader for receiving request data
            writer: StreamWriter for sending response
            
        Raises:
            ValueError: If request is malformed or exceeds size limits
            TimeoutError: If request takes too long to receive
            Exception: For other processing errors
            
        Handles the complete request lifecycle:
        1. Reads and validates HTTP request
        2. Parses headers and body
        3. Constructs WSGI environment
        4. Calls WSGI application
        5. Sends response
        """
        try:
            # Read HTTP request with size and timeout limits
            request_data = b''
            while len(request_data) < self.MAX_REQUEST_SIZE:
                try:
                    chunk = await asyncio.wait_for(
                        reader.read(8192),
                        timeout=self.REQUEST_TIMEOUT
                    )
                    if not chunk:
                        break
                    request_data += chunk
                except asyncio.TimeoutError:
                    raise Exception("Request timeout")
                    
            if len(request_data) >= self.MAX_REQUEST_SIZE:
                raise ValueError("Request too large")
                
            if not request_data:
                return
                
            # Parse HTTP request
            request_line, headers_and_body = request_data.split(b'\r\n', 1)
            method, path, version = request_line.decode().split()
            
            # Parse headers with validation
            try:
                headers_part, body = headers_and_body.split(b'\r\n\r\n', 1)
            except ValueError:
                raise ValueError("Malformed request: missing header/body separator")
                
            headers = {}
            for line in headers_part.decode('utf-8', errors='strict').split('\r\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Validate header values
                    if '\n' in value or '\r' in value:
                        raise ValueError("Invalid header value: contains line breaks")
                    if len(value) > self.MAX_HEADER_SIZE:
                        raise ValueError(f"Header value too long: {key}")
                        
                    headers[key] = value
            
            # Build WSGI environ
            environ = self._build_environ(method, path, headers, body, writer)
            
            # Call WSGI app
            response_data = await self._call_wsgi_app(environ)
            
            # Send response
            writer.write(response_data)
            await writer.drain()
            
        except Exception as e:
            # Log the full error internally
            print(f"Error processing request: {str(e)}", file=sys.stderr)
            
            # Send generic 500 error to client
            error_response = (
                b'HTTP/1.1 500 Internal Server Error\r\n'
                b'Content-Type: text/plain\r\n'
                b'Connection: close\r\n\r\n'
                b'Internal Server Error'
            )
            try:
                writer.write(error_response)
                await writer.drain()
            except Exception as write_error:
                print(f"Error sending error response: {write_error}", file=sys.stderr)
        finally:
            writer.close()
            await writer.wait_closed()
    
    def _build_environ(self,
                      method: str,
                      path: str,
                      headers: Dict[str, str],
                      body: bytes,
                      writer: asyncio.StreamWriter) -> Dict[str, Any]:
        """Build WSGI environment dictionary from request data.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request URL path
            headers: Dictionary of HTTP headers
            body: Raw request body
            writer: StreamWriter for connection info
            
        Returns:
            Dict containing WSGI environment variables
            
        Constructs a PEP 3333 compliant WSGI environment including:
        - HTTP request information
        - Server and connection details
        - WSGI-specific variables
        - Request headers
        """
        environ = {
            'REQUEST_METHOD': method,
            'PATH_INFO': path,
            'SCRIPT_NAME': '',  # Add missing required WSGI variable
            'SERVER_NAME': writer.get_extra_info('peername')[0],
            'SERVER_PORT': str(writer.get_extra_info('peername')[1]),
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': 'http',
            'wsgi.input': BytesIO(body),  # Don't decode body
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
    
    def _sync_wsgi_call(self, environ: Dict[str, Any]) -> bytes:
        """Execute WSGI application synchronously and return response.
        
        Args:
            environ: WSGI environment dictionary
            
        Returns:
            Complete HTTP response as bytes
            
        Raises:
            ValueError: If WSGI app returns empty response
            Exception: For WSGI application errors
            
        Handles:
        1. WSGI application execution
        2. Response status and headers collection
        3. Response body aggregation
        4. HTTP response formatting
        """
        response_data: List[bytes] = []
        status: str = ''
        headers: List[Tuple[str, str]] = []
        
        def start_response(status_line: str, response_headers: List[Tuple[str, str]], exc_info=None) -> None:
            nonlocal status, headers
            if exc_info:
                try:
                    raise exc_info[0](exc_info[1]).with_traceback(exc_info[2])
                finally:
                    exc_info = None
            status = status_line
            headers = response_headers
            
        # Call the WSGI application
        try:
            result = self.app(environ, start_response)
            if not result:
                raise ValueError("WSGI app returned empty response")
        except Exception as e:
            print(f"Error in WSGI application: {e}", file=sys.stderr)
            raise
        
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