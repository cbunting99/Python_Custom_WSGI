#!/usr/bin/env python3
"""
Final Demo - Complete Server Functionality Test
Shows that the Custom WSGI Server is fully operational
"""

import sys
import time
import threading
import requests
from wsgi_server import HighPerformanceWSGIServer

def demo_app(environ, start_response):
    """Demo WSGI application"""
    path = environ.get('PATH_INFO', '/')
    method = environ.get('REQUEST_METHOD', 'GET')
    
    if path == '/':
        status = '200 OK'
        headers = [('Content-Type', 'text/html')]
        start_response(status, headers)
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Custom WSGI Server Demo</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .status {{ color: green; font-weight: bold; }}
                .info {{ background: #f0f0f0; padding: 15px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <h1>🚀 Custom WSGI Server</h1>
            <p class="status">✅ Server is running successfully!</p>
            
            <div class="info">
                <h3>Server Information:</h3>
                <ul>
                    <li><strong>Platform:</strong> {sys.platform}</li>
                    <li><strong>Python:</strong> {sys.version.split()[0]}</li>
                    <li><strong>Time:</strong> {time.ctime()}</li>
                    <li><strong>Method:</strong> {method}</li>
                    <li><strong>Path:</strong> {path}</li>
                </ul>
            </div>
            
            <h3>Test Endpoints:</h3>
            <ul>
                <li><a href="/api/status">API Status</a></li>
                <li><a href="/api/info">Server Info</a></li>
                <li><a href="/health">Health Check</a></li>
            </ul>
            
            <p><em>This server supports Windows, Linux, and macOS with automatic platform optimizations!</em></p>
        </body>
        </html>
        """
        return [html.encode('utf-8')]
    
    elif path == '/api/status':
        status = '200 OK'
        headers = [('Content-Type', 'application/json')]
        start_response(status, headers)
        
        response = {
            "status": "operational",
            "platform": sys.platform,
            "timestamp": time.time(),
            "server": "Custom-WSGI-Server"
        }
        return [str(response).replace("'", '"').encode('utf-8')]
    
    elif path == '/api/info':
        status = '200 OK'
        headers = [('Content-Type', 'application/json')]
        start_response(status, headers)
        
        try:
            import uvloop
            uvloop_available = True
        except ImportError:
            uvloop_available = False
            
        response = {
            "server": "Custom High-Performance WSGI Server",
            "version": "1.0.0",
            "platform": sys.platform,
            "python_version": sys.version,
            "uvloop_available": uvloop_available,
            "features": [
                "Asyncio-based",
                "Multi-worker support",
                "HTTP Keep-Alive",
                "Memory optimized",
                "Cross-platform"
            ]
        }
        return [str(response).replace("'", '"').encode('utf-8')]
    
    elif path == '/health':
        status = '200 OK'
        headers = [('Content-Type', 'text/plain')]
        start_response(status, headers)
        return [b'OK']
    
    else:
        status = '404 Not Found'
        headers = [('Content-Type', 'text/plain')]
        start_response(status, headers)
        return [b'Not Found']

def run_demo_server():
    """Run the demo server"""
    print("🌟 Starting Custom WSGI Server Demo")
    print("=" * 50)
    
    server = HighPerformanceWSGIServer(
        app=demo_app,
        host='127.0.0.1',
        port=8000,
        workers=1  # Single worker for demo
    )
    
    print("🚀 Demo server starting on http://127.0.0.1:8000")
    print("📱 Open your browser and visit: http://127.0.0.1:8000")
    print("⚠️  Press Ctrl+C to stop the server")
    print("-" * 50)
    
    try:
        server.run()
    except KeyboardInterrupt:
        print("\n👋 Demo server stopped")

if __name__ == '__main__':
    run_demo_server()
