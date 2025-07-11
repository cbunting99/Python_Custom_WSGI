"""
HTTP/2 protocol tests.
"""

import asyncio
import ssl
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.features.http2 import HTTP2Connection, HTTP2Stream, configure_http2, handle_http2_connection

@pytest.fixture
def mock_stream():
    reader = AsyncMock(spec=asyncio.StreamReader)
    writer = AsyncMock(spec=asyncio.StreamWriter)
    writer.get_extra_info.return_value = ('127.0.0.1', 12345)
    return reader, writer

@pytest.fixture
def http2_conn(mock_stream):
    reader, writer = mock_stream
    return HTTP2Connection(reader, writer)

@pytest.mark.asyncio
async def test_http2_connection_preface(mock_stream):
    reader, writer = mock_stream
    conn = HTTP2Connection(reader, writer)
    
    with patch.object(conn, '_send_frame') as mock_send_frame:
        await conn._send_preface()
        
        # Verify connection preface was sent
        writer.write.assert_any_call(b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n')
        # Verify settings were sent
        assert mock_send_frame.called

@pytest.mark.asyncio
async def test_http2_headers_frame(http2_conn):
    stream_id = 1
    headers = [(':method', 'GET'), (':path', '/')]
    encoded_headers = http2_conn.encoder.encode(headers)
    
    # Don't mock _process_headers so the actual implementation runs
    frame = (0x1, 0x4, stream_id, encoded_headers)  # HEADERS frame
    
    # Create a mock for process_headers to avoid actual processing
    with patch.object(HTTP2Stream, 'process_headers', new_callable=AsyncMock) as mock_process:
        await http2_conn._process_frame(frame)
        
        # Verify stream was created and added to streams dictionary
        assert stream_id in http2_conn.streams
        # Verify headers were processed
        mock_process.assert_called_once()

@pytest.mark.asyncio
async def test_http2_data_frame(http2_conn):
    stream_id = 1
    test_data = b'test data'
    http2_conn.streams[stream_id] = HTTP2Stream(stream_id)
    
    frame = (0x0, 0x1, stream_id, test_data)  # DATA frame with END_STREAM
    
    await http2_conn._process_frame(frame)
    
    # Verify data was processed
    stream = http2_conn.streams[stream_id]
    assert stream.data == test_data
    assert stream.state == 'half_closed_remote'

@pytest.mark.asyncio
async def test_http2_server_push(http2_conn):
    stream_id = 1
    promised_id = 2
    headers = [(':method', 'GET'), (':path', '/style.css')]
    
    # Create main stream
    main_stream = HTTP2Stream(stream_id)
    main_stream.state = 'open'
    http2_conn.streams[stream_id] = main_stream
    
    with patch.object(http2_conn, '_send_frame') as mock_send_frame:
        # Test push promise
        pushed_stream = await main_stream.push_promise(http2_conn, promised_id, headers)
        
        # Verify push promise
        assert pushed_stream.stream_id == promised_id
        assert pushed_stream.state == 'reserved_remote'
        assert promised_id in http2_conn.streams
        assert mock_send_frame.called

def test_configure_http2():
    # Create a mock SSL context to test
    with patch('ssl.create_default_context') as mock_create_ctx:
        # Setup the mock
        mock_ctx = MagicMock()
        mock_create_ctx.return_value = mock_ctx
        mock_ctx.set_alpn_protocols = MagicMock()
        
        # Call the function
        configure_http2()
        
        # Verify TLS settings were applied
        assert mock_ctx.minimum_version == ssl.TLSVersion.TLSv1_3
        assert mock_ctx.options & ssl.OP_NO_COMPRESSION
        
        # Verify ALPN protocols were set
        mock_ctx.set_alpn_protocols.assert_called_once_with(['h2', 'http/1.1'])

@pytest.mark.asyncio
async def test_handle_http2_connection(mock_stream):
    reader, writer = mock_stream
    
    # Configure mocks
    reader.readexactly.side_effect = asyncio.IncompleteReadError(b'', 9)
    writer.is_closing.return_value = False
    
    # Use a very short timeout for testing
    await handle_http2_connection(reader, writer, timeout=0.5)
    
    # Verify connection preface was sent
    writer.write.assert_any_call(b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n')
    
    # Verify connection was properly closed
    assert writer.close.called
    assert writer.wait_closed.called


@pytest.mark.asyncio
async def test_http2_connection_timeout(mock_stream):
    """Test that HTTP/2 connection handles timeout gracefully."""
    reader, writer = mock_stream
    
    # Configure mocks to simulate timeout
    async def hang_forever(*args, **kwargs):
        # This will be cancelled by the timeout
        await asyncio.sleep(10)
    
    reader.readexactly.side_effect = hang_forever
    writer.is_closing.return_value = False
    
    # Use a very short timeout
    await handle_http2_connection(reader, writer, timeout=0.1)
    
    # Verify connection was properly closed
    assert writer.close.called
    assert writer.wait_closed.called


@pytest.mark.asyncio
async def test_http2_connection_error_handling(mock_stream):
    """Test that HTTP/2 connection handles errors gracefully."""
    reader, writer = mock_stream
    
    # Configure mocks to raise an exception
    reader.readexactly.side_effect = ValueError("Test error")
    writer.is_closing.return_value = False
    
    # Should handle the error without raising
    await handle_http2_connection(reader, writer, timeout=0.5)
    
    # Verify connection was properly closed
    assert writer.close.called
    assert writer.wait_closed.called
