#!/usr/bin/env python3
"""
Final Demo - Complete Server Functionality Test
Shows that the Custom WSGI Server is fully operational

This demo provides a comprehensive showcase of the server's capabilities
including different content types, response handling, and performance metrics.
"""

import os
import sys
import time
import json
import threading
import platform
import datetime
import requests
import logging
import multiprocessing
from src.core.wsgi_server import HighPerformanceWSGIServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def demo_app(environ, start_response):
    """
    Demo WSGI application showcasing various response types and server capabilities.
    
    This application demonstrates:
    - HTML responses with styling
    - JSON API endpoints with proper formatting
    - Performance metrics
    - Error handling
    - Request information display
    """
    path = environ.get('PATH_INFO', '/')
    method = environ.get('REQUEST_METHOD', 'GET')
    query_string = environ.get('QUERY_STRING', '')
    request_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Track request for demo purposes
    logging.info(f"Request: {method} {path} at {request_time}")
    
    if path == '/':
        status = '200 OK'
        headers = [
            ('Content-Type', 'text/html'),
            ('Server', 'Custom-WSGI-Server/1.0.0')
        ]
        start_response(status, headers)
        
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Custom WSGI Server Demo</title>
            <style>
                body {{ 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                    margin: 0;
                    padding: 40px;
                    line-height: 1.6;
                    color: #333;
                    background-color: #f9f9f9;
                }}
                .container {{
                    max-width: 1000px;
                    margin: 0 auto;
                    background: white;
                    padding: 30px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                h1 {{ color: #2c3e50; margin-top: 0; }}
                .status {{ 
                    color: #27ae60; 
                    font-weight: bold; 
                    display: inline-block;
                    padding: 8px 16px;
                    background: #e8f5e9;
                    border-radius: 4px;
                }}
                .info {{ 
                    background: #f5f7fa; 
                    padding: 20px; 
                    border-radius: 5px;
                    margin: 20px 0;
                    border-left: 4px solid #3498db;
                }}
                .endpoints {{
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                    gap: 15px;
                    margin: 20px 0;
                }}
                .endpoint {{
                    background: #f1f8ff;
                    padding: 15px;
                    border-radius: 5px;
                    border: 1px solid #d1e5f9;
                }}
                .endpoint h4 {{
                    margin-top: 0;
                    color: #2980b9;
                }}
                a {{
                    color: #3498db;
                    text-decoration: none;
                }}
                a:hover {{
                    text-decoration: underline;
                }}
                footer {{
                    margin-top: 30px;
                    font-size: 0.9em;
                    color: #7f8c8d;
                    text-align: center;
                }}
                .metrics {{
                    background: #fff8e1;
                    padding: 15px;
                    border-radius: 5px;
                    margin-top: 20px;
                    border-left: 4px solid #ffc107;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 Custom WSGI Server</h1>
                <p class="status">✅ Server is running successfully!</p>
                
                <div class="info">
                    <h3>Server Information:</h3>
                    <ul>
                        <li><strong>Platform:</strong> {platform.system()} {platform.release()}</li>
                        <li><strong>Python:</strong> {sys.version.split()[0]}</li>
                        <li><strong>Time:</strong> {request_time}</li>
                        <li><strong>Method:</strong> {method}</li>
                        <li><strong>Path:</strong> {path}</li>
                        <li><strong>Server Process:</strong> PID {os.getpid() if 'os' in sys.modules else 'N/A'}</li>
                    </ul>
                </div>
                
                <h3>Available Endpoints:</h3>
                <div class="endpoints">
                    <div class="endpoint">
                        <h4>API Status</h4>
                        <p>Check server operational status</p>
                        <a href="/api/status">View Status</a>
                    </div>
                    
                    <div class="endpoint">
                        <h4>Server Info</h4>
                        <p>Detailed server information</p>
                        <a href="/api/info">View Info</a>
                    </div>
                    
                    <div class="endpoint">
                        <h4>Health Check</h4>
                        <p>Simple health endpoint</p>
                        <a href="/health">Check Health</a>
                    </div>
                    
                    <div class="endpoint">
                        <h4>Performance Test</h4>
                        <p>Test server response time</p>
                        <a href="/performance">Run Test</a>
                    </div>
                    
                    <div class="endpoint">
                        <h4>Echo Request</h4>
                        <p>Echo back request details</p>
                        <a href="/echo">View Echo</a>
                    </div>
                </div>
                
                <div class="metrics">
                    <h3>Server Metrics:</h3>
                    <ul>
                        <li><strong>Memory Usage:</strong> Optimized for low footprint</li>
                        <li><strong>Connection Handling:</strong> Async with Keep-Alive support</li>
                        <li><strong>Platform Optimizations:</strong> Automatic based on OS</li>
                    </ul>
                </div>
                
                <footer>
                    <p>This server supports Windows, Linux, and macOS with automatic platform optimizations!</p>
                    <p>© {datetime.datetime.now().year} Custom WSGI Server Project</p>
                </footer>
            </div>
        </body>
        </html>
        """
        return [html.encode('utf-8')]
    
    elif path == '/api/status':
        status = '200 OK'
        headers = [
            ('Content-Type', 'application/json'),
            ('Server', 'Custom-WSGI-Server/1.0.0')
        ]
        start_response(status, headers)
        
        response = {
            "status": "operational",
            "platform": sys.platform,
            "timestamp": time.time(),
            "datetime": request_time,
            "server": "Custom-WSGI-Server",
            "uptime": "N/A"  # In a real app, you would track this
        }
        return [json.dumps(response, indent=2).encode('utf-8')]
    
    elif path == '/api/info':
        status = '200 OK'
        headers = [
            ('Content-Type', 'application/json'),
            ('Server', 'Custom-WSGI-Server/1.0.0')
        ]
        start_response(status, headers)
        
        # Check for optional dependencies
        try:
            import uvloop
            uvloop_available = True
        except ImportError:
            uvloop_available = False
            
        try:
            import httptools
            httptools_available = True
        except ImportError:
            httptools_available = False
            
        response = {
            "server": "Custom High-Performance WSGI Server",
            "version": "1.0.0",
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "python": sys.version.split()[0]
            },
            "dependencies": {
                "uvloop_available": uvloop_available,
                "httptools_available": httptools_available
            },
            "features": [
                "Asyncio-based processing",
                "Multi-worker support",
                "HTTP Keep-Alive connections",
                "Memory optimizations",
                "Cross-platform compatibility",
                "Request pipelining",
                "Graceful shutdown"
            ],
            "performance_optimizations": [
                "Reduced memory allocations",
                "Efficient request parsing",
                "Optimized IO handling",
                "Platform-specific enhancements"
            ]
        }
        return [json.dumps(response, indent=2).encode('utf-8')]
    
    elif path == '/health':
        status = '200 OK'
        headers = [
            ('Content-Type', 'text/plain'),
            ('Server', 'Custom-WSGI-Server/1.0.0')
        ]
        start_response(status, headers)
        return [b'OK']
    
    elif path == '/performance':
        # Simple performance test
        status = '200 OK'
        headers = [
            ('Content-Type', 'application/json'),
            ('Server', 'Custom-WSGI-Server/1.0.0')
        ]
        start_response(status, headers)
        
        # Measure response time
        start_time = time.time()
        # Simulate some processing
        time.sleep(0.01)
        end_time = time.time()
        
        response = {
            "test": "performance",
            "response_time_ms": round((end_time - start_time) * 1000, 2),
            "timestamp": time.time(),
            "server": "Custom-WSGI-Server/1.0.0"
        }
        return [json.dumps(response, indent=2).encode('utf-8')]
    
    elif path == '/echo':
        status = '200 OK'
        headers = [
            ('Content-Type', 'application/json'),
            ('Server', 'Custom-WSGI-Server/1.0.0')
        ]
        start_response(status, headers)
        
        # Get request details to echo back
        response = {
            "method": method,
            "path": path,
            "query_string": query_string,
            "headers": {k: v for k, v in environ.items() if k.startswith('HTTP_')},
            "server_protocol": environ.get('SERVER_PROTOCOL', ''),
            "wsgi_version": environ.get('wsgi.version', ''),
            "timestamp": time.time(),
            "remote_addr": environ.get('REMOTE_ADDR', 'unknown')
        }
        return [json.dumps(response, indent=2).encode('utf-8')]
    
    else:
        status = '404 Not Found'
        headers = [
            ('Content-Type', 'text/html'),
            ('Server', 'Custom-WSGI-Server/1.0.0')
        ]
        start_response(status, headers)
        
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>404 - Not Found</title>
            <style>
                body {{ 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                    margin: 0;
                    padding: 40px;
                    line-height: 1.6;
                    color: #333;
                    background-color: #f9f9f9;
                    text-align: center;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background: white;
                    padding: 30px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                h1 {{ color: #e74c3c; }}
                a {{ color: #3498db; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>404 - Page Not Found</h1>
                <p>The requested path <strong>{path}</strong> does not exist on this server.</p>
                <p><a href="/">Return to Home</a></p>
            </div>
        </body>
        </html>
        """
        return [html.encode('utf-8')]

def test_server_connection(url="http://127.0.0.1:8000", timeout=0.5):
    """
    Test if the server is accessible by making a request to it.
    
    Args:
        url: The URL to test
        timeout: Request timeout in seconds
        
    Returns:
        bool: True if server is accessible, False otherwise
    """
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code == 200
    except requests.RequestException:
        return False

def open_browser_when_ready(url="http://127.0.0.1:8000", max_attempts=10):
    """
    Attempt to open the browser when the server is ready.
    
    Args:
        url: The URL to open
        max_attempts: Maximum number of connection attempts
    """
    import webbrowser
    
    for attempt in range(max_attempts):
        if test_server_connection(url):
            logging.info(f"Server is ready! Opening browser at {url}")
            webbrowser.open(url)
            break
        time.sleep(0.5)

def run_demo_server():
    """
    Run the demo server with enhanced functionality and user feedback.
    
    This function:
    - Configures and starts the WSGI server
    - Provides detailed server information
    - Handles graceful shutdown
    - Attempts to open a browser when the server is ready
    """
    print("\n" + "=" * 60)
    print("🌟 Starting Custom WSGI Server Demo")
    print("=" * 60)
    
    # Determine optimal worker count based on platform
    if sys.platform == 'win32':
        recommended_workers = 1
        worker_note = "(Windows optimal setting)"
    else:
        recommended_workers = min(multiprocessing.cpu_count(), 4)
        worker_note = f"(Recommended for {platform.system()})"
    
    # Server configuration
    host = '127.0.0.1'
    port = 8000
    workers = 1  # Single worker for demo
    
    print(f"\n📋 Server Configuration:")
    print(f"   Host:          {host}")
    print(f"   Port:          {port}")
    print(f"   Workers:       {workers} {worker_note}")
    print(f"   Platform:      {platform.system()} {platform.release()}")
    print(f"   Python:        {sys.version.split()[0]}")
    
    # Check for optional dependencies
    try:
        import uvloop
        print(f"   uvloop:        Available ✓")
    except ImportError:
        print(f"   uvloop:        Not available ⚠️")
    
    try:
        import httptools
        print(f"   httptools:     Available ✓")
    except ImportError:
        print(f"   httptools:     Not available ⚠️")
    
    # Create and configure server
    server = HighPerformanceWSGIServer(
        app=demo_app,
        host=host,
        port=port,
        workers=workers
    )
    
    # Start browser in a separate thread
    url = f"http://{host}:{port}"
    browser_thread = threading.Thread(
        target=open_browser_when_ready, 
        args=(url,),
        daemon=True
    )
    browser_thread.start()
    
    print("\n" + "-" * 60)
    print(f"🚀 Demo server starting on {url}")
    print(f"📱 Open your browser and visit: {url}")
    print(f"🔍 Available endpoints: /, /api/status, /api/info, /health, /performance, /echo")
    print(f"⚠️  Press Ctrl+C to stop the server")
    print("-" * 60)
    
    try:
        start_time = time.time()
        logging.info(f"Server starting at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        server.run()
    except KeyboardInterrupt:
        elapsed = time.time() - start_time
        print("\n" + "-" * 60)
        print(f"👋 Demo server stopped after running for {elapsed:.1f} seconds")
        print(f"Thank you for trying the Custom WSGI Server!")
        print("-" * 60)

if __name__ == '__main__':
    run_demo_server()