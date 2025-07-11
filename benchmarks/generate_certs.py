"""
Copyright 2025 Chris Bunting
File: generate_certs.py | Purpose: Generate SSL certificates for HTTP/2 testing
@author Chris Bunting | @version 1.0.0

CHANGELOG:
2025-07-15 - Chris Bunting: Initial implementation
"""

import os
import subprocess
from pathlib import Path


def generate_ssl_certs():
    """Generate self-signed SSL certificates for HTTPS testing."""
    cert_path = Path("benchmarks/certs")
    key_file = cert_path / "key.pem"
    cert_file = cert_path / "cert.pem"

    # Create directory if it doesn't exist
    os.makedirs(cert_path, exist_ok=True)

    if key_file.exists() and cert_file.exists():
        print("SSL certificates already exist")
        return

    print("Generating self-signed SSL certificates...")

    try:
        # Generate private key
        subprocess.run(["openssl", "genrsa", "-out", str(key_file), "2048"], check=True)

        # Generate self-signed certificate
        subprocess.run(
            [
                "openssl",
                "req",
                "-new",
                "-x509",
                "-key",
                str(key_file),
                "-out",
                str(cert_file),
                "-days",
                "365",
                "-subj",
                "/CN=localhost",
            ],
            check=True,
        )

        print(f"SSL certificates generated at {cert_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error generating certificates: {e}")
    except FileNotFoundError:
        print("Error: OpenSSL not found. Please install OpenSSL and try again.")


if __name__ == "__main__":
    generate_ssl_certs()
