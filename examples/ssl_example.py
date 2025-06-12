"""
Example demonstrating WSGI server with SSL/TLS support.

This example shows how to run a secure HTTPS server with modern cipher suites.
You'll need to generate SSL certificates before running this example.

To generate self-signed certificates for testing:
    openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
"""

from pathlib import Path
from src.core.server_core import WSGIServer

def simple_app(environ, start_response):
    """Simple WSGI application that returns a secure greeting."""
    status = '200 OK'
    headers = [('Content-type', 'text/plain')]
    start_response(status, headers)
    return [b"Hello from secure HTTPS server!"]

def main():
    # Update these paths to your SSL certificate and key files
    cert_file = Path("cert.pem")
    key_file = Path("key.pem")
    
    if not cert_file.exists() or not key_file.exists():
        print("Error: SSL certificate files not found!")
        print("Please generate SSL certificates first using the openssl command:")
        print("openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes")
        return

    # Create HTTPS server
    server = WSGIServer(
        simple_app,
        host='127.0.0.1',
        port=8443,  # Common HTTPS port
        ssl_certfile=cert_file,
        ssl_keyfile=key_file
    )
    
    print("Starting HTTPS server...")
    print("Note: Since we're using self-signed certificates, browsers will show a security warning")
    print("You can access the server at: https://127.0.0.1:8443")
    
    try:
        import asyncio
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\nServer shutdown requested...")
    except Exception as e:
        print(f"Server error: {e}")

if __name__ == "__main__":
    main()