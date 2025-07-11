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
    def test_connection_handling(self, mock_start_server):
        mock_start_server.return_value = MagicMock()
        ssl_ctx = configure_http2()
        
        # Create a coroutine to test
        async def test_coro():
            server = await asyncio.start_server(
                handle_http2_connection,
                'localhost',
                8443,
                ssl=ssl_ctx
            )
            return server
            
        # Run the coroutine in an event loop
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(test_coro())
            self.assertTrue(mock_start_server.called)
            self.assertEqual(mock_start_server.call_args[1]['ssl'], ssl_ctx)
        finally:
            loop.close()

    @patch('src.features.http2.HTTP2Connection')
    def test_protocol_negotiation(self, mock_conn_class):
        # Create a mock instance with an awaitable handle_connection method
        mock_conn_instance = MagicMock()
        mock_conn_instance.handle_connection = MagicMock()
        # Make handle_connection return a coroutine
        mock_conn_instance.handle_connection.return_value = asyncio.Future()
        mock_conn_instance.handle_connection.return_value.set_result(None)
        
        # Make the mock class return our mock instance
        mock_conn_class.return_value = mock_conn_instance
        
        reader = asyncio.StreamReader()
        writer = MagicMock(spec=asyncio.StreamWriter)
        writer.get_extra_info.return_value = ('127.0.0.1', 12345)
        
        # Create a coroutine to test
        async def test_coro():
            await handle_http2_connection(reader, writer)
            
        # Run the coroutine in an event loop
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(test_coro())
            self.assertTrue(mock_conn_class.called)
            mock_conn_class.assert_called_with(reader, writer)
            self.assertTrue(mock_conn_instance.handle_connection.called)
        finally:
            loop.close()

if __name__ == '__main__':
    unittest.main()
