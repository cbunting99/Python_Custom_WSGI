"""
HTTP keep-alive connection handling for persistent connections.

This module provides functionality for handling persistent HTTP connections
with proper timeout handling and resource management.
"""

"""
Copyright 2025 Chris Bunting
File: keepalive.py | Purpose: HTTP keep-alive connection handling
@author Chris Bunting | @version 1.0.0

CHANGELOG:
2025-07-11 - Chris Bunting: Added idle timeout to prevent resource exhaustion
2025-07-10 - Chris Bunting: Initial implementation
"""

import asyncio
import sys
from ..core.server_utils import default_logger

class KeepAliveHandler:
    def __init__(self, handler, max_requests=1000, idle_timeout=60):
        """Initialize keep-alive handler.
        
        Args:
            handler: The request handler to use
            max_requests: Maximum number of requests per connection
            idle_timeout: Timeout in seconds for idle connections
        """
        self.handler = handler
        self.max_requests = max_requests
        self.idle_timeout = idle_timeout
    
    async def handle_connection(self, reader, writer):
        """Handle a persistent connection with keep-alive.
        
        Args:
            reader: StreamReader for the connection
            writer: StreamWriter for the connection
        """
        requests_handled = 0
        
        while requests_handled < self.max_requests:
            try:
                # Check if connection is still alive
                if reader.at_eof():
                    break
                
                # Wait for data with timeout
                try:
                    # Use a timeout to prevent idle connections from consuming resources
                    first_byte = await asyncio.wait_for(
                        reader.read(1), 
                        timeout=self.idle_timeout
                    )
                    
                    if not first_byte:  # Connection closed by client
                        break
                        
                    # Create a new reader with the first byte and the rest of the data
                    # This is safer than directly manipulating internal buffers
                    new_reader = asyncio.StreamReader()
                    # Feed the first byte we already read
                    new_reader.feed_data(first_byte)
                    
                    # Read any available data from the original reader without blocking
                    more_data = await reader.read(reader._buffer_size)
                    if more_data:
                        new_reader.feed_data(more_data)
                        
                    # Use the new reader for this request
                    reader = new_reader
                    
                except asyncio.TimeoutError:
                    # Connection idle for too long
                    break
                
                # Process the request
                await self.handler.handle_request(reader, writer)
                requests_handled += 1
                
                # In a full implementation, we'd check the Connection header
                # For now, we continue with keep-alive until max_requests or client closes
                
            except asyncio.IncompleteReadError:
                break
            except ConnectionResetError:
                break
            except Exception as e:
                default_logger.error(f"Keep-alive error: {e}")
                break
        
        try:
            writer.close()
            await writer.wait_closed()
        except Exception as e:
            default_logger.debug(f"Error closing connection: {e}")
            # Nothing more we can do here