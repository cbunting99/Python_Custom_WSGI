#!/usr/bin/env python3
"""
Unit test suite for WSGI server implementations
"""
import unittest
import asyncio
import json
import multiprocessing
from typing import Dict, Any
from src.core.wsgi_server import HighPerformanceWSGIServer
from src.httptools_server import FastWSGIServer


class TestApp:
    """Test WSGI application"""

    def __call__(self, environ: Dict[str, Any], start_response):
        """Handle WSGI request"""
        status = "200 OK"
        headers = [("Content-Type", "application/json"), ("Connection", "keep-alive")]
        start_response(status, headers)
        return [
            json.dumps(
                {"message": "Test successful!", "path": environ["PATH_INFO"]}
            ).encode()
        ]


class TestWSGIServer(unittest.TestCase):
    def setUp(self):
        """Set up test application"""
        self.app = TestApp()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        """Clean up test environment"""
        self.loop.close()

    def test_high_performance_server_init(self):
        """Test HighPerformanceWSGIServer initialization"""
        server = HighPerformanceWSGIServer(
            self.app, host="127.0.0.1", port=8000, workers=1
        )
        self.assertEqual(server.host, "127.0.0.1")
        self.assertEqual(server.port, 8000)
        self.assertEqual(server.workers, 1)
        self.assertEqual(server.backlog, 2048)  # Default value

    def test_fast_server_init(self):
        """Test FastWSGIServer initialization"""
        server = FastWSGIServer(self.app, host="127.0.0.1", port=8001, workers=1)
        self.assertEqual(server.host, "127.0.0.1")
        self.assertEqual(server.port, 8001)

    def test_server_configuration(self):
        """Test server configuration options"""
        server = HighPerformanceWSGIServer(
            self.app,
            host="0.0.0.0",  # Listen on all interfaces
            port=8080,
            workers=4,
            backlog=4096,
        )
        self.assertEqual(server.host, "0.0.0.0")
        self.assertEqual(server.port, 8080)
        self.assertEqual(server.workers, 4)
        self.assertEqual(server.backlog, 4096)

    def test_worker_count_default(self):
        """Test default worker count is CPU count"""
        server = HighPerformanceWSGIServer(self.app)
        self.assertEqual(server.workers, multiprocessing.cpu_count())

    def test_server_methods_exist(self):
        """Test that required server methods exist"""
        server = HighPerformanceWSGIServer(self.app)
        self.assertTrue(hasattr(server, "run"))
        self.assertTrue(hasattr(server, "_serve"))
        self.assertTrue(hasattr(server, "_handle_client"))
        self.assertTrue(hasattr(server, "_worker_process"))
        self.assertTrue(hasattr(server, "_run_multiprocess"))

    def test_invalid_configuration(self):
        """Test server initialization with invalid configuration"""
        # Test invalid port number (too high)
        with self.assertRaises(ValueError) as cm:
            HighPerformanceWSGIServer(self.app, port=65536)  # Port number too high
        self.assertIn("Port number must be between 0 and 65535", str(cm.exception))

        # Test invalid port number (negative)
        with self.assertRaises(ValueError) as cm:
            HighPerformanceWSGIServer(self.app, port=-1)  # Negative port number
        self.assertIn("Port number must be between 0 and 65535", str(cm.exception))

        # Test invalid port type
        with self.assertRaises(ValueError) as cm:
            HighPerformanceWSGIServer(self.app, port="8000")  # String instead of int
        self.assertIn("Port must be an integer", str(cm.exception))

        # Test invalid worker count
        with self.assertRaises(ValueError) as cm:
            HighPerformanceWSGIServer(self.app, workers=0)  # Invalid worker count
        self.assertIn("Worker count must be at least 1", str(cm.exception))

        # Test invalid worker type
        with self.assertRaises(ValueError) as cm:
            HighPerformanceWSGIServer(self.app, workers="2")  # String instead of int
        self.assertIn("Workers must be an integer", str(cm.exception))

        # Test invalid backlog
        with self.assertRaises(ValueError) as cm:
            HighPerformanceWSGIServer(self.app, backlog=0)  # Invalid backlog
        self.assertIn("Backlog must be at least 1", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
