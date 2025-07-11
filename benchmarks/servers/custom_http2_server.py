import sys
import ssl
import multiprocessing
from pathlib import Path
from src.core import HighPerformanceWSGIServer
from src.features.http2 import configure_http2
from benchmarks.servers.wsgi_app import app

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8443
    workers = min(4, max(1, (multiprocessing.cpu_count() // 2)))

    # Configure SSL context with HTTP/2 support
    cert_path = Path("benchmarks/certs/cert.pem")
    key_path = Path("benchmarks/certs/key.pem")

    if not cert_path.exists() or not key_path.exists():
        print("Error: SSL certificates not found. Run with --generate-certs first.")
        sys.exit(1)

    ssl_ctx = configure_http2()
    ssl_ctx.load_cert_chain(cert_path, key_path)

    server = HighPerformanceWSGIServer(
        app=app, host="0.0.0.0", port=port, workers=workers, ssl=ssl_ctx
    )
    server.run()
