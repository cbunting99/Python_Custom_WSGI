#!/usr/bin/env python3
"""
Debug test to check HTTP method handling
"""
import asyncio
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.core.request_handler import WSGIHandler

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

async def test_method(method):
    captured_env = {}
    
    def test_app(environ, start_response):
        nonlocal captured_env
        captured_env = environ.copy()
        headers = [('Content-Type', 'text/plain')]
        start_response('200 OK', headers)
        return [b'Test Response']
    
    handler = WSGIHandler(test_app)
    
    request = (
        f'{method} /test HTTP/1.1\r\n'
        'Host: example.com\r\n'
        '\r\n'
    ).encode()
    
    reader = MockStreamReader(request)
    writer = MockStreamWriter()
    
    await handler.handle_request(reader, writer)
    response = b''.join(writer.buffer)
    
    print(f"Method: {method}")
    print(f"Captured REQUEST_METHOD: {captured_env.get('REQUEST_METHOD', 'NOT_SET')}")
    print(f"Response starts with: {response[:50]}")
    print("---")
    
    return captured_env, response

async def main():
    methods = ['GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'OPTIONS', 'PATCH']
    
    for method in methods:
        await test_method(method)

if __name__ == '__main__':
    asyncio.run(main())
