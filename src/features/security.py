"""
Security features implementation including CORS, rate limiting, and IP filtering.

This module provides security-related features for the WSGI server including:
- CORS configuration and handling
- Rate limiting implementation
- IP whitelist/blacklist functionality
- Request validation and sanitization
"""

"""
Copyright 2025 Chris Bunting
File: security.py | Purpose: Security features for WSGI server
@author Chris Bunting | @version 1.0.0

CHANGELOG:
2025-07-11 - Chris Bunting: Fixed PATCH method validation, CORS headers, IP validation
2025-07-11 - Chris Bunting: Added rate limiter cleanup to prevent memory leaks
2025-07-10 - Chris Bunting: Initial implementation
"""

import time
from typing import Dict, List, Optional, Set, Union
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address, IPv4Network, IPv6Network, ip_address

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
    """Rate limiting implementation using token bucket algorithm.
    
    This class implements a token bucket rate limiting algorithm with
    automatic cleanup to prevent memory leaks from storing data for
    clients that no longer connect.
    """
    
    def __init__(self, rate: float, burst: int, cleanup_interval: int = 3600, max_entries: int = 10000):
        """Initialize rate limiter.
        
        Args:
            rate: Requests per second allowed
            burst: Maximum burst size allowed
            cleanup_interval: Seconds between cleanup of expired entries
            max_entries: Maximum number of IP addresses to track (prevents DoS)
        """
        if rate <= 0:
            raise ValueError("Rate must be positive")
        if burst <= 0:
            raise ValueError("Burst must be positive")
            
        self.rate = rate
        self.burst = burst
        self.tokens: Dict[str, float] = {}
        self.last_update: Dict[str, float] = {}
        self.cleanup_interval = cleanup_interval
        self.last_cleanup = time.time()
        self.max_entries = max_entries
    
    def is_allowed(self, ip: str) -> bool:
        """Check if request is allowed under rate limit.
        
        Args:
            ip: IP address to check
            
        Returns:
            True if request is allowed, False if rate limited
        """
        now = time.time()
        
        # Periodically clean up expired entries
        if now - self.last_cleanup > self.cleanup_interval:
            self._cleanup(now)
        
        # Prevent DoS by limiting number of tracked IPs
        if ip not in self.tokens and len(self.tokens) >= self.max_entries:
            # If we're at capacity, do emergency cleanup
            self._cleanup(now)
            # If still at capacity after cleanup, reject the request
            if len(self.tokens) >= self.max_entries:
                return False
        
        # Initialize or update tokens
        if ip not in self.tokens:
            self.tokens[ip] = self.burst
            self.last_update[ip] = now
        else:
            time_passed = now - self.last_update[ip]
            # Prevent issues with clock skew or system time changes
            if time_passed < 0:
                time_passed = 0
            elif time_passed > self.cleanup_interval:
                # If time passed is very large, cap it to avoid excessive token accumulation
                time_passed = self.cleanup_interval
                
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
        
    def _cleanup(self, now: float) -> None:
        """Remove expired entries to prevent memory leaks.
        
        Args:
            now: Current timestamp
        """
        # Calculate the expiration time (3x the time it would take to refill the bucket)
        expiration_time = 3 * self.burst / self.rate
        
        # Find expired entries
        expired_ips = [
            ip for ip, last_update in self.last_update.items()
            if now - last_update > expiration_time
        ]
        
        # Remove expired entries
        for ip in expired_ips:
            self.tokens.pop(ip, None)
            self.last_update.pop(ip, None)
            
        # If still too many entries, remove the oldest ones
        if len(self.tokens) > self.max_entries:
            # Sort by last update time
            oldest_ips = sorted(
                self.last_update.items(),
                key=lambda x: x[1]
            )[:len(self.tokens) - self.max_entries]
            
            # Remove oldest entries
            for ip, _ in oldest_ips:
                self.tokens.pop(ip, None)
                self.last_update.pop(ip, None)
            
        # Update last cleanup time
        self.last_cleanup = now

class IPFilter:
    """IP whitelist/blacklist implementation with CIDR support.
    
    This class provides IP filtering functionality with support for
    both individual IP addresses and CIDR network ranges.
    """
    
    def __init__(self):
        """Initialize IP filter with empty whitelist and blacklist."""
        self.whitelist_ips: Set[Union[IPv4Address, IPv6Address]] = set()
        self.blacklist_ips: Set[Union[IPv4Address, IPv6Address]] = set()
        self.whitelist_networks: List[Union[IPv4Network, IPv6Network]] = []
        self.blacklist_networks: List[Union[IPv4Network, IPv6Network]] = []
    
    def add_to_whitelist(self, ip_or_cidr: str) -> None:
        """Add IP or CIDR range to whitelist.
        
        Args:
            ip_or_cidr: IP address or CIDR range to whitelist
            
        Raises:
            ValueError: If the IP address or CIDR range is invalid
        """
        try:
            # Try to parse as a network (CIDR)
            if '/' in ip_or_cidr:
                network = IPv4Network(ip_or_cidr, strict=False)
                self.whitelist_networks.append(network)
            else:
                # Parse as a single IP
                self.whitelist_ips.add(ip_address(ip_or_cidr))
        except ValueError as e:
            try:
                # Try IPv6 if IPv4 fails
                if '/' in ip_or_cidr:
                    network = IPv6Network(ip_or_cidr, strict=False)
                    self.whitelist_networks.append(network)
                else:
                    raise e
            except ValueError:
                raise ValueError(f"Invalid IP address or CIDR range for whitelist: {ip_or_cidr}") from e
    
    def add_to_blacklist(self, ip_or_cidr: str) -> None:
        """Add IP or CIDR range to blacklist.
        
        Args:
            ip_or_cidr: IP address or CIDR range to blacklist
            
        Raises:
            ValueError: If the IP address or CIDR range is invalid
        """
        try:
            # Try to parse as a network (CIDR)
            if '/' in ip_or_cidr:
                network = IPv4Network(ip_or_cidr, strict=False)
                self.blacklist_networks.append(network)
            else:
                # Parse as a single IP
                self.blacklist_ips.add(ip_address(ip_or_cidr))
        except ValueError as e:
            try:
                # Try IPv6 if IPv4 fails
                if '/' in ip_or_cidr:
                    network = IPv6Network(ip_or_cidr, strict=False)
                    self.blacklist_networks.append(network)
                else:
                    raise e
            except ValueError:
                raise ValueError(f"Invalid IP address or CIDR range for blacklist: {ip_or_cidr}") from e
    
    def is_allowed(self, ip: str) -> bool:
        """Check if IP is allowed.
        
        Args:
            ip: IP address to check
            
        Returns:
            True if IP is allowed, False if blocked
            
        Note:
            Invalid IP addresses are always blocked
        """
        try:
            ip_obj = ip_address(ip)
            
            # If whitelist exists (IPs or networks), only allow whitelisted IPs
            if self.whitelist_ips or self.whitelist_networks:
                # Check if IP is in whitelist
                if ip_obj in self.whitelist_ips:
                    return True
                    
                # Check if IP is in any whitelisted network
                for network in self.whitelist_networks:
                    if ip_obj in network:
                        return True
                        
                # Not in whitelist
                return False
                
            # Otherwise check blacklist
            # Check if IP is in blacklist
            if ip_obj in self.blacklist_ips:
                return False
                
            # Check if IP is in any blacklisted network
            for network in self.blacklist_networks:
                if ip_obj in network:
                    return False
                    
            # Not in blacklist
            return True
            
        except ValueError:
            # Invalid IP addresses are always blocked
            return False

def validate_request(environ: Dict[str, str]) -> Optional[str]:
    """Validate and sanitize incoming request.
    
    Args:
        environ: WSGI environment dictionary
        
    Returns:
        Error message if validation fails, None if request is valid
    """
    # Validate request method
    method = environ.get('REQUEST_METHOD', '')
    if not method or method not in {'GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'HEAD', 'PATCH'}:
        return 'Invalid request method'
    
    # Validate content length for requests with body
    if method in {'POST', 'PUT', 'PATCH'}:
        try:
            content_length_str = environ.get('CONTENT_LENGTH', '')
            if content_length_str == '':
                if method != 'PATCH':  # PATCH can have empty body in some cases
                    return 'Missing content length'
                content_length = 0
            else:
                content_length = int(content_length_str)
                if content_length < 0:
                    return 'Invalid content length'
                elif content_length > 10 * 1024 * 1024:  # 10MB limit
                    return 'Content too large'
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
    if '..' in path or '%2e%2e' in path.lower() or '%252e%252e' in path.lower():
        return 'Path traversal not allowed'
        
    # Check for suspicious path components
    path_parts = path.split('/')
    for part in path_parts:
        # Check for null bytes and other suspicious characters
        if '\0' in part or '%00' in part.lower():
            return 'Invalid path character'
        # Check for extremely long path segments (potential DoS)
        if len(part) > 255:
            return 'Path segment too long'
            
    # Validate query string
    query_string = environ.get('QUERY_STRING', '')
    if len(query_string) > 2048:  # Reasonable limit for query string
        return 'Query string too long'
        
    return None

def apply_cors_headers(headers: List[tuple], cors_config: CORSConfig, environ: Dict[str, str] = None) -> List[tuple]:
    """Apply CORS headers to response.
    
    Args:
        headers: List of response header tuples
        cors_config: CORS configuration
        environ: WSGI environment dictionary containing request headers
        
    Returns:
        Headers with CORS headers added
    """
    # Access-Control-Allow-Origin must be a single origin or '*', not a comma-separated list
    # For multiple origins, the server should validate the Origin header and respond with the appropriate one
    origin_value = '*'
    
    # If we have specific allowed origins and the request environment
    if environ and cors_config.allowed_origins and cors_config.allowed_origins != ['*']:
        # Get the Origin header from the request
        request_origin = environ.get('HTTP_ORIGIN')
        
        # Check if the request origin is in the allowed list
        if request_origin:
            for allowed_origin in cors_config.allowed_origins:
                # Allow exact match or wildcard subdomain match (*.example.com)
                if (request_origin == allowed_origin or 
                    (allowed_origin.startswith('*.') and 
                     request_origin.endswith(allowed_origin[1:]))):
                    origin_value = request_origin
                    break
            else:
                # If no match found, don't add the header
                origin_value = 'null'
    
    cors_headers = [
        ('Access-Control-Allow-Origin', origin_value),
        ('Access-Control-Allow-Methods',
         ','.join(cors_config.allowed_methods)),
        ('Access-Control-Allow-Headers',
         ','.join(cors_config.allowed_headers)),
        ('Access-Control-Max-Age',
         str(cors_config.max_age))
    ]
    
    # Only add credentials header if allowed and not using wildcard origin
    if cors_config.allow_credentials:
        # Credentials cannot be used with wildcard origin
        if origin_value != '*':
            cors_headers.append(
                ('Access-Control-Allow-Credentials', 'true')
            )
        
    # Add Vary header when using specific origins
    if origin_value != '*':
        cors_headers.append(('Vary', 'Origin'))
        
    return headers + cors_headers