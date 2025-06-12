"""
HTTP/2 protocol support implementation.

This module provides HTTP/2 protocol configuration and utilities for the WSGI server.
"""

import ssl
from typing import Optional

def configure_http2(ssl_context: Optional[ssl.SSLContext] = None) -> ssl.SSLContext:
    """Configure SSL context with HTTP/2 support.
    
    Args:
        ssl_context: Existing SSL context to configure, or None to create new one
        
    Returns:
        SSLContext configured for HTTP/2
    """
    if ssl_context is None:
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    
    # Set ALPN protocols with HTTP/2 support
    ssl_context.set_alpn_protocols(['h2', 'http/1.1'])
    
    # Enable TLS 1.3 which is recommended for HTTP/2
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_3
    
    return ssl_context