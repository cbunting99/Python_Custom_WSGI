"""
WSGI request handler implementation for processing HTTP requests.

This module provides the core request handling functionality including:
- HTTP request parsing and validation
- WSGI environment construction
- Request size and timeout limits
- Error handling and logging
"""

import asyncio
import sys
from io import BytesIO
from typing import Dict, List, Tuple, Optional, Any

from src.features.security import (
    CORSConfig, validate_request, apply_cors_headers
)

class WSGIError(Exception):
    """Base class for WSGI handler errors."""
    pass


class WSGIHandler:
    """Handles individual HTTP requests according to WSGI specification."""
    MAX_REQUEST_SIZE = 1048576  # 1MB limit
    REQUEST_TIMEOUT = 30  # 30 seconds
    MAX_HEADER_SIZE = 8192  # 8KB limit per header
    VALID_METHODS = {'GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'OPTIONS', 'PATCH'}

    def __init__(self, app, cors_config: Optional[CORSConfig] = None):
        self.app = app
        self.cors_config = cors_config or CORSConfig()
        self._headers: Dict[str, str] = {}

    @property
    def headers(self) -> Dict[str, str]:
        """Get the parsed headers from the last request."""
        return self._headers
        
    async def handle_request(
            self,
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter
    ) -> None:
        """Process a single HTTP request."""
        try:
            # Read request
            request_data = await self._read_request(reader)
            if not request_data:
                raise WSGIError("Empty request")

            # Parse request
            method, path, version, headers, body = await self._parse_request(request_data)
            
            # Validate method
            if method not in self.VALID_METHODS:
                raise WSGIError(f"Invalid method: {method}")

            # Handle CORS preflight
            if method == 'OPTIONS' and self.cors_config:
                await self._handle_cors_preflight(writer)
                return

            # Build environ
            environ = self._build_environ(method, path, version, headers, body, writer)
            
            # Validate request
            error = validate_request(environ)
            if error:
                await self._send_error(writer, 400, error)
                return
                
            # Call WSGI app
            response = await self._call_wsgi_app(environ)
            
            # Strip body for HEAD requests
            if method == 'HEAD':
                response = self._strip_response_body(response)
                
            writer.write(response)
            await writer.drain()
            
        except WSGIError as e:
            await self._send_error(writer, 400, str(e))
        except Exception as e:
            await self._send_error(writer, 500, "Internal Server Error")
            print(f"Error processing request: {e}", file=sys.stderr)
        finally:
            writer.close()
            await writer.wait_closed()

    async def _read_request(self, reader: asyncio.StreamReader) -> bytes:
        """Read HTTP request with size and timeout limits.

        Args:
            reader: StreamReader to read request from

        Returns:
            Complete HTTP request data

        Raises:
            WSGIError: If request is too large, malformed, or times out
        """
        request_data = b''
        headers_complete = False

        try:
            # First read headers (must end with \r\n\r\n)
            while len(request_data) < self.MAX_REQUEST_SIZE:
                chunk = await asyncio.wait_for(
                    reader.read(8192),
                    timeout=self.REQUEST_TIMEOUT
                )
                if not chunk:
                    break
                
                request_data += chunk
                
                # Check if we've received the end of headers
                if b'\r\n\r\n' in request_data:
                    headers_complete = True
                    break
            
            # Security check: Ensure we found the end of headers and didn't hit size limit
            if not headers_complete:
                if len(request_data) >= self.MAX_REQUEST_SIZE:
                    raise WSGIError("Request headers too large")
                else:
                    raise WSGIError("Incomplete request headers")
            
            # Now read the body if needed (based on Content-Length)
            headers_end = request_data.find(b'\r\n\r\n') + 4
            headers = request_data[:headers_end].decode('latin1', errors='replace')
            body_so_far = request_data[headers_end:]
            
            # Extract Content-Length if present
            content_length = 0
            for line in headers.split('\r\n'):
                if line.lower().startswith('content-length:'):
                    try:
                        content_length = int(line.split(':', 1)[1].strip())
                        break
                    except ValueError:
                        raise WSGIError("Invalid Content-Length header")
            
            # Read the rest of the body if needed
            if content_length > 0:
                remaining = content_length - len(body_so_far)
                
                # Security check: Ensure total request size doesn't exceed limit
                if headers_end + content_length > self.MAX_REQUEST_SIZE:
                    raise WSGIError("Request body too large")
                
                # Read the remaining body data
                while remaining > 0 and len(request_data) < self.MAX_REQUEST_SIZE:
                    chunk = await asyncio.wait_for(
                        reader.read(min(8192, remaining)),
                        timeout=self.REQUEST_TIMEOUT
                    )
                    if not chunk:
                        break
                        
                    request_data += chunk
                    remaining -= len(chunk)
            
            return request_data
            
        except asyncio.TimeoutError:
            raise WSGIError("Request timeout")
        except UnicodeDecodeError:
            raise WSGIError("Invalid request encoding")

    async def _parse_request(self, request_data: bytes) -> Tuple[str, str, str, Dict[str, str], bytes]:
        """Parse HTTP request line and headers."""
        try:
            # Split headers and body
            headers_part, body = request_data.split(b'\r\n\r\n', 1)
            lines = headers_part.decode('utf-8', errors='strict').split('\r\n')
            
            # Parse request line
            if not lines:
                raise WSGIError("Empty request line")
                
            request_line = lines[0].split()
            if len(request_line) != 3:
                raise WSGIError("Invalid request line")
                
            method, path, version = request_line
            
            # Parse headers
            self._headers = {}
            headers = self._headers
            for line in lines[1:]:
                if ':' not in line:
                    continue
                    
                name, value = line.split(':', 1)
                name = name.strip()
                value = ' '.join(value.strip().split())  # Normalize whitespace
                
                # Validate header value
                if '\n' in value or '\r' in value:
                    raise WSGIError("Invalid header value")
                if len(value) > self.MAX_HEADER_SIZE:
                    raise WSGIError(f"Header too long: {name}")
                    
                headers[name] = value
                
            # Validate content length for methods with body
            if method in ('POST', 'PUT', 'PATCH'):
                content_length = headers.get('Content-Length', '0')
                try:
                    length = int(content_length)
                    if length < 0:
                        raise ValueError
                except ValueError:
                    raise WSGIError("Invalid Content-Length")
                if length != len(body):
                    raise WSGIError("Content-Length mismatch")
                    
            return method, path, version, headers, body
            
        except ValueError:
            raise WSGIError("Malformed request")

    def _build_environ(self,
                      method: str,
                      path: str,
                      version: str,
                      headers: Dict[str, str],
                      body: bytes,
                      writer: asyncio.StreamWriter) -> Dict[str, Any]:
        """Build WSGI environment dictionary."""
        # Split path and query string
        path_info = path
        query_string = ''
        if '?' in path:
            path_info, query_string = path.split('?', 1)
            
        environ = {
            'REQUEST_METHOD': method,
            'SCRIPT_NAME': '',
            'PATH_INFO': path_info,
            'QUERY_STRING': query_string,
            'CONTENT_TYPE': headers.get('Content-Type', ''),
            'CONTENT_LENGTH': headers.get('Content-Length', '0'),
            'SERVER_NAME': writer.get_extra_info('peername')[0],
            'SERVER_PORT': str(writer.get_extra_info('peername')[1]),
            'SERVER_PROTOCOL': version,
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': 'http',
            'wsgi.input': BytesIO(body),
            'wsgi.errors': sys.stderr,
            'wsgi.multithread': False,
            'wsgi.multiprocess': True,
            'wsgi.run_once': False,
            'wsgi.file_wrapper': FileWrapper
        }
        
        # Add remaining headers
        for name, value in headers.items():
            if name not in ('Content-Type', 'Content-Length'):
                environ[f'HTTP_{name.upper().replace("-", "_")}'] = value
                
        return environ

    async def _call_wsgi_app(self, environ: Dict[str, Any]) -> bytes:
        """Execute WSGI application and return response."""
        response_data: List[bytes] = []
        status: str = ''
        headers: List[Tuple[str, str]] = []
        
        def start_response(status_line: str,
                         response_headers: List[Tuple[str, str]],
                         exc_info=None) -> None:
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
            if result is None:
                result = []
        except Exception as e:
            return await self._build_error_response(500, str(e))
        
        # Build HTTP response
        response_parts = [f'HTTP/1.1 {status}\r\n'.encode()]
        
        # Add headers
        headers = self._prepare_headers(headers, environ)
        
        for header_name, header_value in headers:
            response_parts.append(f'{header_name}: {header_value}\r\n'.encode())
        response_parts.append(b'\r\n')
        
        # Add body
        try:
            # Collect all data from the iterator
            for data in result:
                if data:
                    if isinstance(data, str):
                        data = data.encode()
                    response_parts.append(data)
        except TypeError:
            # Skip if result isn't iterable
            print("Warning: WSGI app returned non-iterable result", file=sys.stderr)
        except Exception as e:
            # Handle other exceptions during iteration
            print(f"Error iterating WSGI app result: {e}", file=sys.stderr)
        finally:
            # Always call close() if available (PEP 333/3333 requirement)
            if hasattr(result, 'close') and callable(result.close):
                try:
                    result.close()
                except Exception as e:
                    print(f"Error closing WSGI app result: {e}", file=sys.stderr)
            
        return b''.join(response_parts)

    def _prepare_headers(self, 
                        headers: List[Tuple[str, str]], 
                        environ: Dict[str, Any]) -> List[Tuple[str, str]]:
        """Prepare response headers."""
        final_headers = []
        has_content_type = False
        has_connection = False
        
        # Process existing headers
        for name, value in headers:
            name = name.strip()
            value = value.strip()
            final_headers.append((name, value))
            
            lower_name = name.lower()
            if lower_name == 'content-type':
                has_content_type = True
            elif lower_name == 'connection':
                has_connection = True
                
        # Add default content type if missing
        if not has_content_type:
            final_headers.append(('Content-Type', 'text/plain'))
            
        # Add connection header if missing
        if not has_connection:
            if self._should_keep_alive(environ):
                final_headers.append(('Connection', 'keep-alive'))
            else:
                final_headers.append(('Connection', 'close'))
                
        # Add CORS headers if configured
        return apply_cors_headers(final_headers, self.cors_config)

    def _should_keep_alive(self, environ: Dict[str, Any]) -> bool:
        """Determine if connection should be kept alive."""
        version = environ['SERVER_PROTOCOL']
        connection = environ.get('HTTP_CONNECTION', '').lower()
        
        if connection == 'close':
            return False
        if version == 'HTTP/1.0':
            return connection == 'keep-alive'
        return True  # Default to keep-alive for HTTP/1.1

    async def _handle_cors_preflight(self, writer: asyncio.StreamWriter) -> None:
        """Handle CORS preflight request."""
        headers = apply_cors_headers([], self.cors_config)
        response = [b'HTTP/1.1 204 No Content\r\n']
        for name, value in headers:
            response.append(f'{name}: {value}\r\n'.encode())
        response.append(b'\r\n')
        writer.write(b''.join(response))
        await writer.drain()

    def _strip_response_body(self, response: bytes) -> bytes:
        """Remove response body for HEAD requests."""
        parts = response.split(b'\r\n\r\n', 1)
        return parts[0] + b'\r\n\r\n'

    async def _build_error_response(self, code: int, message: str) -> bytes:
        """Build error response."""
        status = {
            400: 'Bad Request',
            500: 'Internal Server Error'
        }.get(code, 'Internal Server Error')
        
        return (
            f'HTTP/1.1 {code} {status}\r\n'
            f'Content-Type: text/plain\r\n'
            f'Content-Length: {len(message)}\r\n'
            f'Connection: close\r\n'
            f'\r\n'
            f'{message}'
        ).encode()

    async def _send_error(self, 
                         writer: asyncio.StreamWriter,
                         code: int,
                         message: str) -> None:
        """Send error response."""
        response = await self._build_error_response(code, message)
        writer.write(response)
        await writer.drain()

class FileWrapper:
    """WSGI file wrapper for efficient file transmission.

    This class implements the iterator protocol for WSGI applications
    to efficiently serve file-like objects.

    Args:
        filelike: A file-like object with a read method
        blksize: Block size for reading in bytes

    Raises:
        TypeError: If filelike doesn't have a read method
    """
    def __init__(self, filelike, blksize=8192):
        if not hasattr(filelike, 'read') or not callable(filelike.read):
            raise TypeError("FileWrapper requires a file-like object with a read method")
        
        self.filelike = filelike
        self.blksize = blksize
        
        # Adopt the close method if available
        if hasattr(filelike, 'close') and callable(filelike.close):
            self.close = filelike.close

    def __iter__(self):
        return self

    def __next__(self):
        try:
            data = self.filelike.read(self.blksize)
            if data:
                return data
            raise StopIteration
        except Exception as e:
            # Convert any read errors to StopIteration to maintain iterator protocol
            print(f"Error reading from file: {e}", file=sys.stderr)
            raise StopIteration
            
    def close(self):
        """Default close method if the wrapped object doesn't have one."""
        pass
 
