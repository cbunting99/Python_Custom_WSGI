"""
HTTP request parser using httptools for efficient parsing.

This module provides a robust HTTP request parser with:
- Strict size limits for security
- Proper error handling and validation
- Memory efficient parsing
- Support for incremental parsing
"""

import httptools
from typing import Dict, Optional, Tuple, Any
import sys

class HTTPParserError(Exception):
    """Custom exception for HTTP parsing errors"""
    pass

class HTTPParser:
    """Parses HTTP requests using httptools with validation and safety checks.
    
    This parser implements callbacks from httptools.HttpRequestParser and manages
    the state of an HTTP request as it's being parsed.
    
    Constants:
        MAX_BODY_SIZE: Maximum allowed request body size (10MB)
        MAX_HEADER_SIZE: Maximum size per header (8KB)
        MAX_HEADERS: Maximum number of headers per request (100)
    """
    MAX_BODY_SIZE = 10485760  # 10MB limit
    MAX_HEADER_SIZE = 8192    # 8KB per header
    MAX_HEADERS = 100         # Maximum number of headers
    
    def __init__(self):
        try:
            self.parser = httptools.HttpRequestParser(self)
        except Exception as e:
            raise HTTPParserError(f"Failed to initialize parser: {e}")
            
        self.headers: Dict[str, str] = {}
        self.trailers: Dict[str, str] = {}
        self.body = b''
        self.url: Optional[bytes] = None
        self.method: Optional[bytes] = None
        self._headers_count = 0
        self._parsing_complete = False
        self._chunked = False
        self._chunk_size = 0
        self._expect_continue = False
        self._content_length = 0
        self._body_bytes_read = 0
        
    def reset(self) -> None:
        """Reset parser state to handle a new request.
        
        Clears all internal state variables including:
        - Headers dictionary
        - Trailers dictionary
        - Request body
        - URL and method information
        - Parser completion flag
        - Chunked transfer state
        """
        self.headers.clear()
        self.trailers.clear()
        self.body = b''
        self.url = None
        self.method = None
        self._headers_count = 0
        self._parsing_complete = False
        self._chunked = False
        self._chunk_size = 0
        self._expect_continue = False
        self._content_length = 0
        self._body_bytes_read = 0
        
    def on_message_begin(self) -> None:
        """Called when a new message parsing begins.
        
        Resets all parser state to prepare for a new request.
        This is a callback method for httptools.HttpRequestParser.
        """
        self.reset()
        
    def on_url(self, url: bytes) -> None:
        """Process URL data from the request.
        
        Args:
            url: Raw URL bytes from the request
            
        Raises:
            HTTPParserError: If URL exceeds length limit
            Exception: For URL parsing errors
            
        Validates URL length and stores for later use.
        """
        try:
            if len(url) > 8192:  # Reasonable URL length limit
                raise HTTPParserError("URL too long")
            self.url = url
        except Exception as e:
            print(f"Error parsing URL: {e}", file=sys.stderr)
            raise
        
    def on_header(self, name: bytes, value: bytes) -> None:
        """Process a single header from the request.
        
        Args:
            name: Header name as bytes
            value: Header value as bytes
            
        Raises:
            HTTPParserError: If header limits are exceeded or content is invalid
            UnicodeDecodeError: If header contains invalid ASCII
            
        Validates:
        - Maximum header count
        - Header name length
        - Header value size
        - No newlines in values
        - ASCII-only content
        """
        try:
            if self._headers_count >= self.MAX_HEADERS:
                raise HTTPParserError("Too many headers")
                
            name_str = name.decode('ascii')
            if len(name_str) > 256:  # Reasonable header name length
                raise HTTPParserError("Header name too long")
                
            value_str = value.decode('ascii')
            if len(value_str) > self.MAX_HEADER_SIZE:
                raise HTTPParserError("Header value too long")
                
            if '\n' in value_str or '\r' in value_str:
                raise HTTPParserError("Invalid header value")
                
            self.headers[name_str] = value_str
            self._headers_count += 1
            
        except UnicodeDecodeError as e:
            raise HTTPParserError("Invalid header encoding")
        except Exception as e:
            print(f"Error parsing header: {e}", file=sys.stderr)
            raise
        
    def on_body(self, body: bytes) -> None:
        """Process request body data incrementally.
        
        Args:
            body: Chunk of body data as bytes
            
        Raises:
            HTTPParserError: If body exceeds maximum size limit
            
        Handles both regular and chunked transfer encoding.
        """
        if self._chunked:
            self._process_chunk(body)
        else:
            if len(self.body) + len(body) > self.MAX_BODY_SIZE:
                raise HTTPParserError("Request body too large")
            self.body += body
            self._body_bytes_read += len(body)
            
    def _process_chunk(self, chunk: bytes) -> None:
        """Process chunked transfer encoding data."""
        if self._chunk_size == 0:
            # Parse chunk size line
            try:
                chunk_line = chunk.split(b'\r\n', 1)[0]
                self._chunk_size = int(chunk_line.split(b';')[0], 16)
                if self._chunk_size == 0:
                    self._parsing_complete = True
            except (ValueError, IndexError):
                raise HTTPParserError("Invalid chunk encoding")
        else:
            # Process chunk data
            if len(self.body) + len(chunk) > self.MAX_BODY_SIZE:
                raise HTTPParserError("Request body too large")
            self.body += chunk
            self._body_bytes_read += len(chunk)
            self._chunk_size -= len(chunk)
        
    def on_message_complete(self):
        """Called when parsing is complete"""
        self._parsing_complete = True

    def feed_data(self, data: bytes) -> None:
        """Feed raw request data to the parser.
        
        Args:
            data: Raw HTTP request data as bytes
            
        Raises:
            HTTPParserError: If parsing fails
            
        This method should be called with chunks of request data
        as they become available.
        """
        try:
            self.parser.feed_data(data)
        except Exception as e:
            raise HTTPParserError(f"Parser error: {e}")

    @property
    def is_complete(self) -> bool:
        """Check if parsing is complete"""
        return self._parsing_complete

    def close(self) -> None:
        """Explicitly cleanup parser resources"""
        if hasattr(self, 'parser'):
            self.parser = None
            
    def __del__(self):
        """Fallback cleanup if close() wasn't called"""
        try:
            self.close()
        except Exception:
            pass
