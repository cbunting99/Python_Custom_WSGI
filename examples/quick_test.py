#!/usr/bin/env python3
"""Quick test to verify server functionality"""

import sys
import time
import os
from pathlib import Path

# Add the project root to the Python path if needed
project_root = Path(__file__).parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.core import HighPerformanceWSGIServer

def test_app(environ, start_response):
    """Simple test WSGI application"""
    status = '200 OK'
    headers = [
        ('Content-Type', 'text/plain'),
        ('X-Server', 'Custom-WSGI-Server')
    ]
    start_response(status, headers)
    
    body = f"Server is working!\nPlatform: {sys.platform}\nTime: {time.ctime()}"
    return [body.encode('utf-8')]

if __name__ == '__main__':
    print("🚀 Testing Custom WSGI Server")
    print(f"Platform: {sys.platform}")
    
    # Test server creation
    try:
        server = HighPerformanceWSGIServer(
            app=test_app,
            host='127.0.0.1',
            port=8000,
            workers=1  # Single worker for testing
        )
        print("✓ Server instance created successfully")
        print("✓ Server is ready for use!")
        print("\nTo start the server, run:")
        print("python examples/quick_test.py")
        print("Then visit: http://127.0.0.1:8000")
        
    except Exception as e:
        print(f"❌ Error creating server: {e}")
        sys.exit(1)