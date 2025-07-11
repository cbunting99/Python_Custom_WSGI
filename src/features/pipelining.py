"""
HTTP pipelining support for handling multiple requests in a single connection.

This module provides functionality for processing multiple HTTP requests
sent in a single connection without waiting for responses.
"""

"""
Copyright 2025 Chris Bunting
File: pipelining.py | Purpose: HTTP pipelining implementation
@author Chris Bunting | @version 1.0.0

CHANGELOG:
2025-07-11 - Chris Bunting: Fixed request body handling and added request limit
2025-07-10 - Chris Bunting: Initial implementation
"""

import asyncio

class PipelineHandler:
    def __init__(self, app, handler_class=None):
        """Initialize pipeline handler.
        
        Args:
            app: WSGI application
            handler_class: Class to handle individual requests (optional)
        """
        self.app = app
        # Create handler instance if class provided
        self.request_handler = handler_class(app) if handler_class else None
    
    async def handle_pipeline(self, reader, writer):
        while True:
            try:
                # Read multiple requests in pipeline
                requests = await self._read_pipelined_requests(reader)
                if not requests:
                    break
                
                # Process all requests
                responses = []
                for request in requests:
                    response = await self._process_request(request)
                    responses.append(response)
                
                # Send all responses in order
                for response in responses:
                    writer.write(response)
                await writer.drain()
                
            except Exception:
                break
    
    async def _read_pipelined_requests(self, reader):
        """Read multiple pipelined HTTP requests with proper body handling"""
        requests = []
        buffer = b''
        max_pipeline_requests = 20  # Limit to prevent DoS
        
        try:
            # Read initial data
            data = await reader.read(8192)
            if not data:
                return requests
            
            buffer += data
            
            # Process requests until we hit our limit
            while len(requests) < max_pipeline_requests and b'\r\n\r\n' in buffer:
                # Split headers and potential body
                headers_part, rest = buffer.split(b'\r\n\r\n', 1)
                
                # Parse headers to check for Content-Length
                headers = {}
                for line in headers_part.split(b'\r\n')[1:]:  # Skip request line
                    if b':' in line:
                        name, value = line.split(b':', 1)
                        headers[name.strip().lower()] = value.strip()
                
                # Check if we need to read a body
                content_length = 0
                if b'content-length' in headers:
                    try:
                        content_length = int(headers[b'content-length'])
                    except (ValueError, TypeError):
                        # Invalid Content-Length, treat as no body
                        content_length = 0
                
                # If we have a body, make sure we have enough data
                if content_length > 0:
                    # If we don't have the full body yet, read more data
                    while len(rest) < content_length:
                        more_data = await reader.read(8192)
                        if not more_data:  # Connection closed
                            break
                        rest += more_data
                    
                    # If we have the full body, extract it
                    if len(rest) >= content_length:
                        body = rest[:content_length]
                        # Construct the full request with headers and body
                        full_request = headers_part + b'\r\n\r\n' + body
                        requests.append(full_request)
                        # Update buffer to remove the processed request
                        buffer = rest[content_length:]
                    else:
                        # Incomplete body, can't process more requests
                        break
                else:
                    # No body, just headers
                    requests.append(headers_part + b'\r\n\r\n')
                    buffer = rest
                    
        except Exception as e:
            print(f"Error reading pipelined requests: {e}")
            
        return requests
    
    async def _process_request(self, request_data):
        """Process a single request"""
        # Use provided handler if available
        if self.request_handler:
            return await self.request_handler.handle_request(request_data)
            
        # Fallback to simple request handling
        try:
            # Parse request line and headers
            lines = request_data.decode().split('\r\n')
            request_line = lines[0]
            method, path, version = request_line.split()
            
            # Build a simple response
            response_body = b'{"message": "Pipelined response"}'
            response = (
                f'HTTP/1.1 200 OK\r\n'
                f'Content-Type: application/json\r\n'
                f'Content-Length: {len(response_body)}\r\n'
                f'Connection: keep-alive\r\n\r\n'
            ).encode() + response_body
            
            return response
            
        except Exception:
            error_body = b'Bad Request'
            return (
                b'HTTP/1.1 400 Bad Request\r\n'
                b'Content-Type: text/plain\r\n' +
                f'Content-Length: {len(error_body)}\r\n\r\n'.encode() +
                error_body
            )