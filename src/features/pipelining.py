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
        """Read multiple pipelined HTTP requests"""
        requests = []
        buffer = b''
        
        try:
            data = await reader.read(8192)
            if not data:
                return requests
            
            buffer += data
            
            # Split by double CRLF to separate requests
            while b'\r\n\r\n' in buffer:
                request_data, buffer = buffer.split(b'\r\n\r\n', 1)
                if request_data:
                    requests.append(request_data + b'\r\n\r\n')
                    
        except Exception:
            pass
            
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