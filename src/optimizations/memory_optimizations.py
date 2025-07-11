"""
Memory optimization utilities for efficient buffer management.

This module provides memory optimization techniques including:
- Pre-allocated buffers with memoryviews for zero-copy operations
- Buffer pooling to reduce GC pressure
- Efficient I/O operations
"""

"""
Copyright 2025 Chris Bunting
File: memory_optimizations.py | Purpose: Memory optimization utilities
@author Chris Bunting | @version 1.0.0

CHANGELOG:
2025-07-11 - Chris Bunting: Fixed memory leak in buffer pool
2025-07-10 - Chris Bunting: Initial implementation
"""

import asyncio
import sys

class OptimizedBuffer:
    """Pre-allocated buffer with memoryview for zero-copy operations.
    
    This class provides a reusable buffer with memoryview to minimize
    memory allocations and reduce garbage collection pressure.
    """
    
    def __init__(self, size=8192):
        """Initialize a new buffer.
        
        Args:
            size: Size of the buffer in bytes (default: 8192)
        """
        self.buffer = bytearray(size)
        self.view = memoryview(self.buffer)
        self.size = size
    
    def read_into(self, reader, max_bytes):
        """Read directly into pre-allocated buffer.
        
        Args:
            reader: A file-like object with readinto method
            max_bytes: Maximum number of bytes to read
            
        Returns:
            Memoryview of read data, or None if no data was read
            
        Note:
            This is more efficient than read() as it avoids an extra copy
        """
        max_bytes = min(max_bytes, self.size)
        try:
            bytes_read = reader.readinto(self.view[:max_bytes])
            return self.view[:bytes_read] if bytes_read else None
        except (AttributeError, IOError) as e:
            # Handle case where reader doesn't support readinto
            print(f"Error in read_into: {e}", file=sys.stderr)
            return None
    
    async def async_read_into(self, reader, max_bytes):
        """Async version of read_into for asyncio streams.
        
        Args:
            reader: An asyncio.StreamReader
            max_bytes: Maximum number of bytes to read
            
        Returns:
            Memoryview of read data, or None if no data was read or error occurred
        """
        max_bytes = min(max_bytes, self.size)
        try:
            data = await reader.read(max_bytes)
            if data:
                data_len = len(data)
                self.buffer[:data_len] = data
                return self.view[:data_len]
            return None
        except Exception as e:
            print(f"Error in async_read_into: {e}", file=sys.stderr)
            return None

class MemoryPool:
    """Object pool for reusing buffers and reducing GC pressure.
    
    This class implements a simple object pool pattern to reuse
    OptimizedBuffer instances, reducing memory allocations and
    garbage collection overhead.
    
    Usage:
        pool = MemoryPool()
        buffer = pool.get_buffer()
        # Use buffer...
        pool.return_buffer(buffer)
    """
    def __init__(self, buffer_size=8192, pool_size=100):
        """Initialize the memory pool.
        
        Args:
            buffer_size: Size of each buffer in bytes (default: 8192)
            pool_size: Maximum number of buffers to keep in the pool (default: 100)
        """
        self.buffer_size = buffer_size
        self.pool_size = pool_size
        # Pre-allocate buffers
        self.pool = [OptimizedBuffer(buffer_size) for _ in range(pool_size)]
        self.available = list(self.pool)
    
    def get_buffer(self):
        """Get a buffer from the pool.
        
        Returns:
            An OptimizedBuffer instance
            
        Note:
            If the pool is empty, a new buffer will be created.
            This buffer should be returned to the pool when done.
        """
        if self.available:
            return self.available.pop()
        else:
            # Pool exhausted, create new buffer
            # This won't be tracked in self.pool, but can still be returned
            return OptimizedBuffer(self.buffer_size)
    
    def return_buffer(self, buffer):
        """Return a buffer to the pool for reuse.
        
        Args:
            buffer: The OptimizedBuffer to return to the pool
            
        Note:
            Only buffers of the correct size will be returned to the pool.
            If the pool is full, the buffer will be discarded.
        """
        # Only return buffers that are from our pool (same size) and not already in available list
        if not isinstance(buffer, OptimizedBuffer):
            return
            
        if (buffer.size == self.buffer_size and 
            buffer not in self.available and
            len(self.available) < len(self.pool)):
            # Clear the buffer before returning it to the pool
            buffer.buffer[:] = b'\x00' * buffer.size
            self.available.append(buffer)