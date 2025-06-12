#!/usr/bin/env python3
"""
Test script for the WSGI server implementations
"""
import asyncio
import aiohttp
import time
import sys
import multiprocessing
from src.core.wsgi_server import HighPerformanceWSGIServer
from src.httptools_server import FastWSGIServer  # This will need to be moved later


def test_app(environ, start_response):
    """Simple test WSGI application"""
    status = '200 OK'
    headers = [
        ('Content-Type', 'application/json'),
        ('Connection', 'keep-alive')
    ]
    start_response(status, headers)
    return [b'{"message": "Test successful!", "path": "' + environ['PATH_INFO'].encode() + b'"}']


async def test_server_response(url="http://localhost:8000", num_requests=10):
    """Test server by making HTTP requests"""
    print(f"Testing server at {url} with {num_requests} requests...")
    
    async with aiohttp.ClientSession() as session:
        start_time = time.time()
        
        for i in range(num_requests):
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"Request {i+1}: {data}")
                    else:
                        print(f"Request {i+1}: HTTP {response.status}")
            except Exception as e:
                print(f"Request {i+1}: Error - {e}")
        
        end_time = time.time()
        print(f"Completed {num_requests} requests in {end_time - start_time:.2f} seconds")


def run_server_test(server_class, server_name, port=8000):
    """Run a server for testing"""
    print(f"\nStarting {server_name} on port {port}")
    try:
        server = server_class(test_app, host='127.0.0.1', port=port, workers=1)
        server.run()
    except KeyboardInterrupt:
        print(f"\n{server_name} stopped")
    except Exception as e:
        print(f"Error starting {server_name}: {e}")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'test-client':
            # Run client test
            asyncio.run(test_server_response())
        elif sys.argv[1] == 'high-perf':
            # Run high performance server
            run_server_test(HighPerformanceWSGIServer, "HighPerformanceWSGIServer", 8000)
        elif sys.argv[1] == 'fast':
            # Run fast server
            run_server_test(FastWSGIServer, "FastWSGIServer", 8001)
        else:
            print("Usage: python test_server.py [test-client|high-perf|fast]")
    else:
        print("WSGI Server Test Script")
        print("Usage:")
        print("  python test_server.py high-perf    # Run HighPerformanceWSGIServer")
        print("  python test_server.py fast         # Run FastWSGIServer") 
        print("  python test_server.py test-client  # Test server with HTTP requests")
        print("\nExample workflow:")
        print("  1. python test_server.py high-perf  # In one terminal")
        print("  2. python test_server.py test-client # In another terminal")