"""Example of using the WSGI server with security features enabled.

This example demonstrates:
- HTTP/2 protocol support
- CORS configuration
- Rate limiting
- IP filtering
- Request validation
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.server_core import WSGIServer
from src.features.security import CORSConfig


def app(environ, start_response):
    """Simple WSGI application."""
    status = "200 OK"
    headers = [("Content-type", "application/json")]
    response = b'{"message": "Hello, secure world!"}'

    start_response(status, headers)
    return [response]


if __name__ == "__main__":
    # Configure CORS
    cors_config = CORSConfig(
        allowed_origins=["http://localhost:3000", "https://example.com"],
        allowed_methods=["GET", "POST", "OPTIONS"],
        allowed_headers=["Content-Type", "Authorization"],
        allow_credentials=True,
    )

    # Configure rate limiting
    rate_limit = {"rate": 10.0, "burst": 20}  # requests per second  # burst capacity

    # Configure IP filtering
    ip_whitelist = ["127.0.0.1"]  # Only allow localhost
    # ip_blacklist = ['10.0.0.1']  # Alternative: block specific IPs

    # Create and start server
    server = WSGIServer(
        app,
        host="127.0.0.1",
        port=8443,
        ssl_certfile="path/to/cert.pem",  # Replace with actual cert path
        ssl_keyfile="path/to/key.pem",  # Replace with actual key path
        enable_http2=True,
        cors_config=cors_config,
        rate_limit=rate_limit,
        ip_whitelist=ip_whitelist,
        # ip_blacklist=ip_blacklist,        # Uncomment to use blacklist instead
        max_connections=1000,
    )

    try:
        import asyncio

        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\nShutting down server...")
