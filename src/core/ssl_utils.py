"""
SSL/TLS configuration utilities for the WSGI server.

Provides functions for setting up secure SSL contexts with modern cipher suites
and proper security settings.
"""

import ssl
from typing import Optional, Union, Tuple
from pathlib import Path

def create_ssl_context(
    certfile: Union[str, Path],
    keyfile: Union[str, Path],
    password: Optional[str] = None,
    ciphers: Optional[str] = None
) -> ssl.SSLContext:
    """Create a secure SSL context with modern cipher suites.
    
    Args:
        certfile: Path to the SSL certificate file
        keyfile: Path to the private key file
        password: Optional password for encrypted private key
        ciphers: Optional custom cipher string
        
    Returns:
        Configured SSLContext with secure settings
        
    Raises:
        ssl.SSLError: If certificate/key loading fails
        ValueError: If invalid paths provided
    """
    # Create context with modern protocol
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    
    # Set security options
    # Note: On modern systems, SSLv2 and SSLv3 are often disabled at compile time
    try:
        context.options |= ssl.OP_NO_SSLv3
    except AttributeError:
        pass  # SSLv3 not available to disable
        
    # Disable old TLS versions
    context.options |= ssl.OP_NO_TLSv1
    context.options |= ssl.OP_NO_TLSv1_1
    
    # Enable forward secrecy and server cipher preferences
    context.options |= ssl.OP_SINGLE_DH_USE
    context.options |= ssl.OP_SINGLE_ECDH_USE
    context.options |= ssl.OP_CIPHER_SERVER_PREFERENCE
    
    # Set minimum TLS version (this effectively disables older protocols)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    
    # Modern cipher suites prioritizing perfect forward secrecy
    default_ciphers = (
        'ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:'
        'ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:'
        'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256'
    )
    
    # Set cipher suite
    context.set_ciphers(ciphers or default_ciphers)
    
    # Enable verification
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    
    # Load certificate and key
    context.load_cert_chain(certfile, keyfile, password)
    
    # Final verification that we have a secure configuration
    if context.minimum_version < ssl.TLSVersion.TLSv1_2:
        raise ValueError("Failed to set minimum TLS version to 1.2")
        
    return context

def validate_cert_paths(
    certfile: Union[str, Path],
    keyfile: Union[str, Path]
) -> Tuple[Path, Path]:
    """Validate certificate and key file paths.
    
    Args:
        certfile: Path to certificate file
        keyfile: Path to private key file
        
    Returns:
        Tuple of Path objects for cert and key
        
    Raises:
        ValueError: If files don't exist or are invalid
    """
    cert_path = Path(certfile)
    key_path = Path(keyfile)
    
    if not cert_path.exists():
        raise ValueError(f"Certificate file not found: {certfile}")
    if not key_path.exists():
        raise ValueError(f"Private key file not found: {keyfile}")
        
    return cert_path, key_path