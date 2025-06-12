"""
Security features implementation including CORS, rate limiting, and IP filtering.

This module provides security-related features for the WSGI server including:
- CORS configuration and handling
- Rate limiting implementation
- IP whitelist/blacklist functionality
- Request validation and sanitization
"""

import time
from typing import Dict, List, Optional, Set, Union
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address, ip_address

@dataclass
class CORSConfig:
    """CORS configuration settings."""
    allowed_origins: List[str] = None
    allowed_methods: List[str] = None
    allowed_headers: List[str] = None
    allow_credentials: bool = False
    max_age: int = 86400  # 24 hours

    def __post_init__(self):
        # Set defaults if None
        self.allowed_origins = self.allowed_origins or ['*']
        self.allowed_methods = self.allowed_methods or ['GET', 'POST', 'OPTIONS']
        self.allowed_headers = self.allowed_headers or ['Content-Type']

class RateLimiter:
    """Rate limiting implementation using token bucket algorithm."""
    
    def __init__(self, rate: float, burst: int):
        """Initialize rate limiter.
        
        Args:
            rate: Requests per second allowed
            burst: Maximum burst size allowed
        """
        self.rate = rate
        self.burst = burst
        self.tokens: Dict[str, float] = {}
        self.last_update: Dict[str, float] = {}
    
    def is_allowed(self, ip: str) -> bool:
        """Check if request is allowed under rate limit.
        
        Args:
            ip: IP address to check
            
        Returns:
            True if request is allowed, False if rate limited
        """
        now = time.time()
        
        # Initialize or update tokens
        if ip not in self.tokens:
            self.tokens[ip] = self.burst
            self.last_update[ip] = now
        else:
            time_passed = now - self.last_update[ip]
            self.tokens[ip] = min(
                self.burst,
                self.tokens[ip] + time_passed * self.rate
            )
            self.last_update[ip] = now
            
        # Check if enough tokens and consume one
        if self.tokens[ip] >= 1:
            self.tokens[ip] -= 1
            return True
        return False

class IPFilter:
    """IP whitelist/blacklist implementation."""
    
    def __init__(self):
        self.whitelist: Set[Union[IPv4Address, IPv6Address]] = set()
        self.blacklist: Set[Union[IPv4Address, IPv6Address]] = set()
    
    def add_to_whitelist(self, ip: str) -> None:
        """Add IP to whitelist.
        
        Args:
            ip: IP address to whitelist
        """
        self.whitelist.add(ip_address(ip))
    
    def add_to_blacklist(self, ip: str) -> None:
        """Add IP to blacklist.
        
        Args:
            ip: IP address to blacklist
        """
        self.blacklist.add(ip_address(ip))
    
    def is_allowed(self, ip: str) -> bool:
        """Check if IP is allowed.
        
        Args:
            ip: IP address to check
            
        Returns:
            True if IP is allowed, False if blocked
        """
        ip_obj = ip_address(ip)
        
        # If whitelist exists, only allow whitelisted IPs
        if self.whitelist:
            return ip_obj in self.whitelist
            
        # Otherwise block blacklisted IPs
        return ip_obj not in self.blacklist

def validate_request(environ: Dict[str, str]) -> Optional[str]:
    """Validate and sanitize incoming request.
    
    Args:
        environ: WSGI environment dictionary
        
    Returns:
        Error message if validation fails, None if request is valid
    """
    # Validate request method
    method = environ.get('REQUEST_METHOD', '')
    if not method or method not in {'GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'HEAD'}:
        return 'Invalid request method'
    
    # Validate content length for requests with body
    if method in {'POST', 'PUT'}:
        try:
            content_length = int(environ.get('CONTENT_LENGTH', '0'))
            if content_length < 0:
                return 'Invalid content length'
        except ValueError:
            return 'Invalid content length header'
            
    # Validate content type
    content_type = environ.get('CONTENT_TYPE', '')
    if method in {'POST', 'PUT'} and not content_type:
        return 'Missing content type'
        
    # Validate path
    path = environ.get('PATH_INFO', '')
    if not path.startswith('/'):
        return 'Invalid request path'
    
    # Path traversal prevention
    if '..' in path:
        return 'Path traversal not allowed'
        
    return None

def apply_cors_headers(headers: List[tuple], cors_config: CORSConfig) -> List[tuple]:
    """Apply CORS headers to response.
    
    Args:
        headers: List of response header tuples
        cors_config: CORS configuration
        
    Returns:
        Headers with CORS headers added
    """
    cors_headers = [
        ('Access-Control-Allow-Origin', 
         ','.join(cors_config.allowed_origins)),
        ('Access-Control-Allow-Methods',
         ','.join(cors_config.allowed_methods)),
        ('Access-Control-Allow-Headers',
         ','.join(cors_config.allowed_headers)),
        ('Access-Control-Max-Age',
         str(cors_config.max_age))
    ]
    
    if cors_config.allow_credentials:
        cors_headers.append(
            ('Access-Control-Allow-Credentials', 'true')
        )
        
    return headers + cors_headers