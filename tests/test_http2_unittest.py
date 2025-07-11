"""
HTTP/2 protocol tests using unittest.
"""

import unittest
import asyncio
import ssl
import hpack
from unittest.mock import patch, MagicMock
from src.features.http2 import HTTP2Connection, HTTP2Stream, configure_http2

class TestHTTP2Connection(unittest.TestCase):
    def setUp(self):
        self.reader = MagicMock(spec=asyncio.StreamReader)
        self.writer = MagicMock(spec=asyncio.StreamWriter)
        self.conn = HTTP2Connection(self.reader, self.writer)

    def test_connection_init(self):
        self.assertIsInstance(self.conn.encoder, type(hpack.Encoder()))
        self.assertIsInstance(self.conn.decoder, type(hpack.Decoder()))
        self.assertEqual(len(self.conn.streams), 0)

    @patch.object(HTTP2Connection, '_send_frame')
    def test_send_preface(self, mock_send_frame):
        asyncio.run(self.conn._send_preface())
        self.writer.write.assert_called_with(b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n')
        self.assertTrue(mock_send_frame.called)

class TestHTTP2Stream(unittest.TestCase):
    def setUp(self):
        self.stream = HTTP2Stream(1)

    def test_stream_init(self):
        self.assertEqual(self.stream.stream_id, 1)
        self.assertEqual(self.stream.state, 'idle')

    @patch.object(HTTP2Stream, 'process_complete_request')
    def test_process_headers(self, mock_process):
        headers = [(':method', 'GET'), (':path', '/')]
        # Run the coroutine in an event loop
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self.stream.process_headers(headers))
            self.assertEqual(self.stream.headers, headers)
            self.assertEqual(self.stream.state, 'open')
        finally:
            loop.close()

class TestConfigureHTTP2(unittest.TestCase):
    def test_configure_http2(self):
        ssl_ctx = configure_http2()
        self.assertEqual(ssl_ctx.minimum_version, ssl.TLSVersion.TLSv1_3)
        self.assertTrue(ssl_ctx.options & ssl.OP_NO_COMPRESSION)

if __name__ == '__main__':
    unittest.main()
