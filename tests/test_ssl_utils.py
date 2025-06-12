#!/usr/bin/env python3
"""
Test suite for SSL/TLS utilities
"""
import unittest
import ssl
from pathlib import Path
from src.core.ssl_utils import create_ssl_context, validate_cert_paths

class TestSSLUtils(unittest.TestCase):
    def setUp(self):
        """Set up test certificate paths"""
        self.cert_dir = Path(__file__).parent / 'test_certs'
        self.certfile = self.cert_dir / 'server.crt'
        self.keyfile = self.cert_dir / 'server.key'

    def test_validate_cert_paths(self):
        """Test certificate and key file path validation"""
        # Test valid paths
        cert_path, key_path = validate_cert_paths(self.certfile, self.keyfile)
        self.assertTrue(cert_path.exists())
        self.assertTrue(key_path.exists())
        
        # Test invalid certificate path
        with self.assertRaises(ValueError):
            validate_cert_paths('nonexistent.crt', self.keyfile)
            
        # Test invalid key path
        with self.assertRaises(ValueError):
            validate_cert_paths(self.certfile, 'nonexistent.key')

    def test_create_ssl_context_basic(self):
        """Test basic SSL context creation"""
        context = create_ssl_context(self.certfile, self.keyfile)
        
        # Verify it's an SSL context
        self.assertIsInstance(context, ssl.SSLContext)
        
        # Verify minimum TLS version
        self.assertEqual(
            context.minimum_version,
            ssl.TLSVersion.TLSv1_2,
            "Minimum TLS version should be 1.2"
        )

    def test_security_options(self):
        """Test security options are properly set"""
        context = create_ssl_context(self.certfile, self.keyfile)
        
        # Check TLS version restrictions
        self.assertGreaterEqual(
            context.minimum_version,
            ssl.TLSVersion.TLSv1_2,
            "TLS version should be at least 1.2"
        )
        
        # Verify verification settings
        self.assertEqual(
            context.verify_mode,
            ssl.CERT_REQUIRED,
            "Certificate verification should be required"
        )
        
        self.assertTrue(
            context.check_hostname,
            "Hostname verification should be enabled"
        )
        
        # Check cipher suite configuration
        ciphers = context.get_ciphers()
        cipher_names = [cipher['name'] for cipher in ciphers]
        
        # Verify we have secure ciphers
        self.assertTrue(
            any('ECDHE' in name for name in cipher_names),
            "Context should include ECDHE ciphers"
        )
        self.assertTrue(
            any('AES256' in name for name in cipher_names),
            "Context should include AES256 ciphers"
        )

    def test_custom_cipher_suite(self):
        """Test custom cipher suite configuration"""
        custom_ciphers = 'ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384'
        context = create_ssl_context(
            self.certfile,
            self.keyfile,
            ciphers=custom_ciphers
        )
        
        # Get the cipher list
        ciphers = context.get_ciphers()
        cipher_names = [cipher['name'] for cipher in ciphers]
        
        # Verify custom ciphers are included
        self.assertTrue(
            any('ECDHE' in name for name in cipher_names),
            "Context should include ECDHE ciphers"
        )
        self.assertTrue(
            any('AES256' in name for name in cipher_names),
            "Context should include AES256 ciphers"
        )

    def test_password_protected_key(self):
        """Test loading password-protected key"""
        # This test uses unencrypted key, so password should be ignored
        context = create_ssl_context(
            self.certfile,
            self.keyfile,
            password="unused"
        )
        self.assertIsInstance(context, ssl.SSLContext)

    def test_error_handling(self):
        """Test error handling for invalid certificates"""
        # Create invalid cert files
        bad_cert = self.cert_dir / 'invalid.crt'
        bad_key = self.cert_dir / 'invalid.key'
        
        with open(bad_cert, 'w') as f:
            f.write("INVALID CERT")
        with open(bad_key, 'w') as f:
            f.write("INVALID KEY")
        
        # Test with invalid certificate content
        with self.assertRaises(ssl.SSLError):
            create_ssl_context(bad_cert, bad_key)
            
        # Clean up invalid files
        bad_cert.unlink()
        bad_key.unlink()

if __name__ == '__main__':
    unittest.main()