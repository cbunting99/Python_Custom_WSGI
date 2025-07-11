"""
HTTP/2 Integration Tests
"""
import asyncio
import ssl
import unittest
from unittest.mock import patch, MagicMock
from src.features.http2 import configure_http2, handle_http2_connection

class TestHTTP2Integration(unittest.TestCase):
    def test_ssl_configuration(self):
        ssl_ctx = configure_http2()
        self.assertEqual(ssl_ctx.minimum_version, ssl.TLSVersion.TLSv1_3)
        self.assertTrue(ssl_ctx.options & ssl.OP_NO_COMPRESSION)

    @patch('asyncio.start_server')
    async def test_connection_handling(self, mock_start_server):
        mock_start_server.return_value = asyncio.start_server
        ssl_ctx = configure_http2()
        
        server = await asyncio.start_server(
            handle_http2_connection,
            'localhost',
            8443,
            ssl=ssl_ctx
        )
        
        self.assertTrue(mock_start_server.called)
        self.assertEqual(mock_start_server.call_args[1]['ssl'], ssl_ctx)

    @patch('src.features.http2.HTTP2Connection')
    async def test_protocol_negotiation(self, mock_conn):
        reader = asyncio.StreamReader()
        writer = MagicMock(spec=asyncio.StreamWriter)
        writer.get_extra_info.return_value = ('127.0.0.1', 12345)
        
        await handle_http2_connection(reader, writer)
        
        self.assertTrue(mock_conn.called)
        mock_conn.assert_called_with(reader, writer)

if __name__ == '__main__':
    unittest.main()
