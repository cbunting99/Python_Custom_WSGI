#!/usr/bin/env python3
"""
Test suite for security features implementation
"""
import unittest
import time
from src.features.security import (
    CORSConfig, 
    RateLimiter, 
    IPFilter, 
    validate_request, 
    apply_cors_headers
)

class TestCORSConfig(unittest.TestCase):
    def test_default_initialization(self):
        """Test CORS config initializes with default values"""
        cors_config = CORSConfig()
        self.assertEqual(cors_config.allowed_origins, ['*'])
        self.assertEqual(cors_config.allowed_methods, ['GET', 'POST', 'OPTIONS'])
        self.assertEqual(cors_config.allowed_headers, ['Content-Type'])
        self.assertEqual(cors_config.max_age, 86400)
        self.assertFalse(cors_config.allow_credentials)

    def test_custom_initialization(self):
        """Test CORS config with custom values"""
        cors_config = CORSConfig(
            allowed_origins=['https://example.com'],
            allowed_methods=['GET', 'POST'],
            allowed_headers=['X-Custom-Header'],
            allow_credentials=True,
            max_age=3600
        )
        self.assertEqual(cors_config.allowed_origins, ['https://example.com'])
        self.assertEqual(cors_config.allowed_methods, ['GET', 'POST'])
        self.assertEqual(cors_config.allowed_headers, ['X-Custom-Header'])
        self.assertTrue(cors_config.allow_credentials)
        self.assertEqual(cors_config.max_age, 3600)

class TestRateLimiter(unittest.TestCase):
    def setUp(self):
        self.rate_limiter = RateLimiter(rate=2.0, burst=3)
        
    def test_initial_request_allowed(self):
        """Test first request is always allowed"""
        self.assertTrue(self.rate_limiter.is_allowed("127.0.0.1"))
        
    def test_burst_limit(self):
        """Test burst limit enforcement"""
        ip = "127.0.0.1"
        # Use up burst allowance
        for _ in range(3):
            self.assertTrue(self.rate_limiter.is_allowed(ip))
        # Next request should be limited
        self.assertFalse(self.rate_limiter.is_allowed(ip))
        
    def test_rate_recovery(self):
        """Test token recovery over time"""
        ip = "127.0.0.1"
        # Use up tokens
        for _ in range(3):
            self.assertTrue(self.rate_limiter.is_allowed(ip))
        self.assertFalse(self.rate_limiter.is_allowed(ip))
        
        # Wait for token recovery (1 second = 2 tokens)
        time.sleep(1.0)
        self.assertTrue(self.rate_limiter.is_allowed(ip))

class TestIPFilter(unittest.TestCase):
    def setUp(self):
        self.ip_filter = IPFilter()
        
    def test_whitelist(self):
        """Test whitelist functionality"""
        self.ip_filter.add_to_whitelist("127.0.0.1")
        self.assertTrue(self.ip_filter.is_allowed("127.0.0.1"))
        self.assertFalse(self.ip_filter.is_allowed("192.168.1.1"))
        
    def test_blacklist(self):
        """Test blacklist functionality"""
        self.ip_filter.add_to_blacklist("192.168.1.1")
        self.assertFalse(self.ip_filter.is_allowed("192.168.1.1"))
        self.assertTrue(self.ip_filter.is_allowed("127.0.0.1"))
        
    def test_ipv6_support(self):
        """Test IPv6 address support"""
        self.ip_filter.add_to_whitelist("2001:db8::1")
        self.assertTrue(self.ip_filter.is_allowed("2001:db8::1"))
        self.assertFalse(self.ip_filter.is_allowed("2001:db8::2"))

class TestRequestValidation(unittest.TestCase):
    def test_valid_get_request(self):
        """Test validation of GET request"""
        environ = {
            'REQUEST_METHOD': 'GET',
            'PATH_INFO': '/test'
        }
        self.assertIsNone(validate_request(environ))
        
    def test_valid_post_request(self):
        """Test validation of POST request"""
        environ = {
            'REQUEST_METHOD': 'POST',
            'CONTENT_LENGTH': '100',
            'CONTENT_TYPE': 'application/json',
            'PATH_INFO': '/test'
        }
        self.assertIsNone(validate_request(environ))
        
    def test_invalid_method(self):
        """Test invalid request method"""
        environ = {
            'REQUEST_METHOD': 'INVALID',
            'PATH_INFO': '/test'
        }
        self.assertIsNotNone(validate_request(environ))
        
    def test_path_traversal(self):
        """Test path traversal prevention"""
        environ = {
            'REQUEST_METHOD': 'GET',
            'PATH_INFO': '/../etc/passwd'
        }
        self.assertIsNotNone(validate_request(environ))

class TestCORSHeaders(unittest.TestCase):
    def test_default_cors_headers(self):
        """Test default CORS headers application"""
        headers = [('Content-Type', 'text/plain')]
        cors_config = CORSConfig()
        new_headers = apply_cors_headers(headers, cors_config)
        
        self.assertIn(('Access-Control-Allow-Origin', '*'), new_headers)
        self.assertIn(('Access-Control-Allow-Methods', 'GET,POST,OPTIONS'), new_headers)
        
    def test_custom_cors_headers(self):
        """Test custom CORS headers application"""
        headers = [('Content-Type', 'text/plain')]
        cors_config = CORSConfig(
            allowed_origins=['https://example.com'],
            allowed_methods=['GET'],
            allow_credentials=True
        )
        new_headers = apply_cors_headers(headers, cors_config)
        
        self.assertIn(('Access-Control-Allow-Origin', 'https://example.com'), new_headers)
        self.assertIn(('Access-Control-Allow-Methods', 'GET'), new_headers)
        self.assertIn(('Access-Control-Allow-Credentials', 'true'), new_headers)

if __name__ == '__main__':
    unittest.main()