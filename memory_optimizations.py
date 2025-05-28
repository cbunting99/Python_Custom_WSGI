import mmap
import asyncio

class OptimizedBuffer:
    def __init__(self, size=8192):
        self.buffer = bytearray(size)
        self.view = memoryview(self.buffer)
        self.size = size
    
    def read_into(self, reader, max_bytes):
        """Read directly into pre-allocated buffer"""
        max_bytes = min(max_bytes, self.size)
        bytes_read = reader.readinto(self.view[:max_bytes])
        return self.view[:bytes_read] if bytes_read else None
    
    async def async_read_into(self, reader, max_bytes):
        """Async version of read_into"""
        max_bytes = min(max_bytes, self.size)
        try:
            data = await reader.read(max_bytes)
            if data:
                data_len = len(data)
                self.buffer[:data_len] = data
                return self.view[:data_len]
            return None
        except Exception:
            return None

class MemoryPool:
    """Object pool for reusing buffers and reducing GC pressure"""
    def __init__(self, buffer_size=8192, pool_size=100):
        self.buffer_size = buffer_size
        self.pool = [OptimizedBuffer(buffer_size) for _ in range(pool_size)]
        self.available = list(self.pool)
    
    def get_buffer(self):
        """Get a buffer from the pool"""
        if self.available:
            return self.available.pop()
        else:
            # Pool exhausted, create new buffer
            return OptimizedBuffer(self.buffer_size)
    
    def return_buffer(self, buffer):
        """Return a buffer to the pool"""
        if len(self.available) < len(self.pool):
            self.available.append(buffer)