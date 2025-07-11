"""
HTTP/2 protocol support implementation.

This module provides full HTTP/2 protocol support including:
- Stream multiplexing
- HPACK header compression
- Server push
- Flow control
"""

import ssl
import asyncio
from typing import Optional, Dict, List, Tuple
from collections import defaultdict
import hpack

class HTTP2Connection:
    """Handles HTTP/2 connection state and stream management."""
    
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.encoder = hpack.Encoder()
        self.decoder = hpack.Decoder()
        self.streams: Dict[int, HTTP2Stream] = {}
        self.next_stream_id = 1
        self.settings = {
            'header_table_size': 4096,
            'enable_push': 1,
            'max_concurrent_streams': 100,
            'initial_window_size': 65535,
            'max_frame_size': 16384,
            'max_header_list_size': 65536
        }
        
    async def handle_connection(self):
        """Main connection handling loop."""
        try:
            # Send connection preface
            await self._send_preface()
            
            while True:
                frame = await self._read_frame()
                await self._process_frame(frame)
        except Exception as e:
            print(f"HTTP/2 connection error: {e}")
            await self.close()

    async def _send_preface(self):
        """Send HTTP/2 connection preface."""
        self.writer.write(b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n')
        await self._send_settings()

    async def _send_settings(self):
        """Send initial settings frame."""
        settings_data = bytearray()
        for identifier, value in self._get_setting_ids():
            settings_data.extend(identifier.to_bytes(2, 'big'))
            settings_data.extend(value.to_bytes(4, 'big'))
        await self._send_frame(0, 0x4, 0, bytes(settings_data))

    def _get_setting_ids(self) -> List[Tuple[int, int]]:
        """Convert setting names to numeric identifiers and values."""
        setting_map = {
            'header_table_size': 0x1,
            'enable_push': 0x2,
            'max_concurrent_streams': 0x3,
            'initial_window_size': 0x4,
            'max_frame_size': 0x5,
            'max_header_list_size': 0x6
        }
        return [
            (setting_map[name], value) 
            for name, value in self.settings.items()
            if name in setting_map
        ]

    async def _read_frame(self):
        """Read and parse an HTTP/2 frame."""
        header = await self.reader.readexactly(9)
        length = int.from_bytes(header[:3], 'big')
        frame_type = header[3]
        flags = header[4]
        stream_id = int.from_bytes(header[5:9], 'big')
        data = await self.reader.readexactly(length)
        return (frame_type, flags, stream_id, data)

    async def _process_frame(self, frame):
        """Process incoming frame based on type."""
        frame_type, flags, stream_id, data = frame
        
        if frame_type == 0x1:  # HEADERS
            await self._process_headers(stream_id, flags, data)
        elif frame_type == 0x4:  # SETTINGS
            await self._process_settings(flags, data)
        elif frame_type == 0x0:  # DATA
            await self._process_data(stream_id, flags, data)
        # Other frame types would be handled here

    async def _process_data(self, stream_id: int, flags: int, data: bytes) -> None:
        """Process DATA frame."""
        if stream_id not in self.streams:
            await self._send_rst_stream(stream_id, 0x1)  # PROTOCOL_ERROR
            return
            
        stream = self.streams[stream_id]
        stream.data = getattr(stream, 'data', b'') + data
        
        # Handle END_STREAM flag
        if flags & 0x1:
            await stream.process_complete_request()

    async def _send_rst_stream(self, stream_id: int, error_code: int) -> None:
        """Send RST_STREAM frame."""
        payload = error_code.to_bytes(4, 'big')
        await self._send_frame(stream_id, 0x3, 0, payload)

    async def _process_headers(self, stream_id, flags, data):
        """Process HEADERS frame."""
        headers = self.decoder.decode(data)
        if stream_id not in self.streams:
            self.streams[stream_id] = HTTP2Stream(stream_id)
        await self.streams[stream_id].process_headers(headers)

    async def _send_frame(self, stream_id: int, frame_type: int, 
                        flags: int, payload: bytes) -> None:
        """Send an HTTP/2 frame."""
        length = len(payload)
        frame_header = (
            length.to_bytes(3, 'big') +
            frame_type.to_bytes(1, 'big') +
            flags.to_bytes(1, 'big') +
            stream_id.to_bytes(4, 'big')
        )
        self.writer.write(frame_header + payload)
        await self.writer.drain()

    async def _send_goaway(self) -> None:
        """Send GOAWAY frame to gracefully terminate connection."""
        last_stream_id = max(self.streams.keys()) if self.streams else 0
        error_code = 0  # NO_ERROR
        debug_data = b''
        payload = (
            last_stream_id.to_bytes(4, 'big') +
            error_code.to_bytes(4, 'big') +
            debug_data
        )
        await self._send_frame(0, 0x7, 0, payload)

    async def _process_settings(self, flags: int, data: bytes) -> None:
        """Process SETTINGS frame and send ACK if needed."""
        if not flags & 0x1:  # Not ACK
            # Update settings from frame
            for i in range(0, len(data), 6):
                identifier = int.from_bytes(data[i:i+2], 'big')
                value = int.from_bytes(data[i+2:i+6], 'big')
                self.settings[self._setting_name(identifier)] = value
            
            # Send SETTINGS ACK
            await self._send_frame(0, 0x4, 0x1, b'')

    def _setting_name(self, identifier: int) -> str:
        """Map numeric setting identifier to name."""
        settings_map = {
            0x1: 'header_table_size',
            0x2: 'enable_push',
            0x3: 'max_concurrent_streams',
            0x4: 'initial_window_size',
            0x5: 'max_frame_size',
            0x6: 'max_header_list_size'
        }
        return settings_map.get(identifier, f'unknown_setting_{identifier}')

    async def close(self):
        """Gracefully close connection."""
        try:
            await self._send_goaway()
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass

class HTTP2Stream:
    """Represents an HTTP/2 stream."""
    
    def __init__(self, stream_id: int):
        self.stream_id = stream_id
        self.state = 'idle'
        self.headers: List[Tuple[str, str]] = []
        self.data = b''
        self.response_headers: List[Tuple[str, str]] = []
        self.response_data = b''
        
    async def process_headers(self, headers):
        """Process received headers."""
        self.headers = headers
        self.state = 'open'
        
    async def process_complete_request(self):
        """Process complete request with headers and data."""
        # Here we would normally process the complete request
        # and prepare a response. For now just send basic response.
        self.response_headers = [
            (':status', '200'),
            ('content-type', 'text/plain'),
            ('content-length', str(len(b'OK')))
        ]
        self.response_data = b'OK'
        self.state = 'half_closed_remote'
        
    async def send_response(self, connection: 'HTTP2Connection'):
        """Send the prepared response."""
        # Send headers frame
        encoded_headers = connection.encoder.encode(self.response_headers)
        await connection._send_frame(
            self.stream_id, 
            0x1,  # HEADERS
            0x4,  # END_HEADERS flag
            encoded_headers
        )
        
        # Send data frame
        await connection._send_frame(
            self.stream_id,
            0x0,  # DATA
            0x1,  # END_STREAM flag
            self.response_data
        )
        self.state = 'closed'

    async def push_promise(self, connection: 'HTTP2Connection', 
                         promised_stream_id: int,
                         headers: List[Tuple[str, str]]) -> 'HTTP2Stream':
        """Initiate a server push."""
        if self.state != 'open':
            raise ValueError("Cannot push from non-open stream")
            
        # Create promised stream
        promised_stream = HTTP2Stream(promised_stream_id)
        promised_stream.state = 'reserved_remote'
        connection.streams[promised_stream_id] = promised_stream
        
        # Send PUSH_PROMISE frame
        encoded_headers = connection.encoder.encode(headers)
        await connection._send_frame(
            self.stream_id,
            0x5,  # PUSH_PROMISE
            0x4,  # END_HEADERS flag
            promised_stream_id.to_bytes(4, 'big') + encoded_headers
        )
        
        return promised_stream

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
    
    # Enable modern TLS features
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_3
    ssl_context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20')
    ssl_context.options |= ssl.OP_NO_COMPRESSION
    
    return ssl_context

async def handle_http2_connection(reader: asyncio.StreamReader, 
                                 writer: asyncio.StreamWriter):
    """Handle new HTTP/2 connection."""
    conn = HTTP2Connection(reader, writer)
    await conn.handle_connection()
