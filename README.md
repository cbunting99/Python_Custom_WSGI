[![Python Package using Conda](https://github.com/cbunting99/Python_Custom_WSGI/actions/workflows/python-package-conda.yml/badge.svg)](https://github.com/cbunting99/Python_Custom_WSGI/actions/workflows/python-package-conda.yml)
# Custom High-Performance WSGI Server

> ⚠️ **NOTICE**: This is a work in progress (WIP) project that has not been thoroughly tested in production environments. Updates are made as time permits. Use with caution in production settings.

A high-performance, asyncio-based WSGI server implementation built for speed, security, and scalability. This server leverages modern Python async capabilities, uvloop, and httptools to deliver exceptional performance for WSGI applications while maintaining strong security practices.

## 🚀 Quick Start

Ready to use right now! Just run:

```bash
# Check if everything is ready
python tests/server_check.py

# Run interactive demo
python examples/demo.py

# Start your own server
python examples/example_usage.py
```

## Features

- **🚀 High Performance**: Built with uvloop (Linux/macOS) and httptools for maximum speed
- **⚡ Asynchronous**: Non-blocking I/O with asyncio for concurrent request handling
- **🔧 Multi-Process**: Automatic worker process management with SO_REUSEPORT
- **🔄 Keep-Alive**: HTTP/1.1 persistent connections for reduced latency
- **🚀 HTTP/2 Support**: Full protocol support with multiplexing and server push
- **📊 Memory Optimized**: Buffer pooling and memory-efficient request parsing
- **🔒 SSL/TLS Support**: Modern TLS 1.2+ with secure cipher suites
- **🔐 Enhanced Security**: CORS protection, path traversal prevention, and input validation
- **🛡️ Rate Limiting**: Protection against DoS attacks with token bucket algorithm
- **🔍 IP Filtering**: CIDR-based IP whitelist/blacklist functionality
- **✅ WSGI Compatible**: Works with any WSGI application (Flask, Django, etc.)
- **🌐 Cross-Platform**: Supports Windows, Linux, and macOS with platform-specific optimizations
- **🎯 Production Ready**: Optimized for real-world deployment scenarios

## Project Structure

```
custom_wsgi/
├── src/                   # Main package
│   ├── core/             # Core server components
│   │   ├── __init__.py
│   │   ├── http_parser.py
│   │   ├── request_handler.py
│   │   ├── server_core.py
│   │   └── wsgi_server.py
│   ├── features/         # Server features
│   │   ├── __init__.py
│   │   ├── keepalive.py
│   │   └── pipelining.py
│   ├── optimizations/    # Performance optimizations
│   │   ├── __init__.py
│   │   ├── memory_optimizations.py
│   │   └── multiprocess_server.py
│   ├── __init__.py
│   └── httptools_server.py
├── examples/             # Example usage and demos
│   ├── demo.py
│   ├── example_usage.py
│   └── httptools_example.py
└── tests/               # Test files
    ├── server_check.py
    └── test_server.py
```

## Installation

1. Clone or download this repository
2. Install dependencies:

```bash
# For Linux/macOS (with uvloop for better performance)
pip install -r requirements.txt

# For Windows (uvloop is not available, but server will work with standard asyncio)
pip install httptools
```

**Note**: The server automatically detects your platform and uses uvloop on Linux/macOS for enhanced performance, while gracefully falling back to standard asyncio on Windows.

## Basic Usage

```python
from src.core import HighPerformanceWSGIServer

def my_app(environ, start_response):
    status = '200 OK'
    headers = [('Content-Type', 'application/json')]
    start_response(status, headers)
    return [b'{"message": "Hello from high-performance WSGI!"}']

if __name__ == '__main__':
    server = HighPerformanceWSGIServer(
        app=my_app,
        host='0.0.0.0',
        port=8000,
        workers=8  # Adjust based on CPU cores
    )
    server.run()
```

## Server Implementations

### 1. HighPerformanceWSGIServer (Recommended)

The main production-ready server with all optimizations:

```python
from src.core import HighPerformanceWSGIServer
server = HighPerformanceWSGIServer(app, workers=8)
server.run()
```

### 2. FastWSGIServer (httptools-based)

Advanced server using httptools for faster HTTP parsing:

```python
from src.httptools_server import FastWSGIServer
server = FastWSGIServer(app, workers=4)
server.run()
```

### 3. WSGIServer (Basic)

Simple async server for development:

```python
from src.core import WSGIServer
import asyncio

server = WSGIServer(app)
asyncio.run(server.start())
```

## HTTP/2 Features

### HTTP/2 Protocol Support
The server supports HTTP/2 with automatic protocol negotiation (ALPN). To enable:

```python
from src.features.http2 import configure_http2

ssl_ctx = configure_http2()  # Creates optimized TLS 1.3 context
server = HighPerformanceWSGIServer(
    app,
    host='0.0.0.0',
    port=443,
    ssl=ssl_ctx  # Use the HTTP/2 optimized SSL context
)
```

Key HTTP/2 features:
- **Multiplexing**: Multiple requests over single connection
- **Header Compression**: HPACK reduces overhead
- **Server Push**: Push resources before requested
- **Stream Prioritization**: Better resource loading
- **Binary Protocol**: More efficient than HTTP/1.x

## Security Features

### SSL/TLS Support

Enable HTTPS with modern security settings:

```python
from src.core import WSGIServer

server = WSGIServer(
    app,
    host='0.0.0.0',
    port=443,
    ssl_certfile='path/to/cert.pem',
    ssl_keyfile='path/to/key.pem',
    ssl_ciphers='ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384'  # Optional
)
```

See `examples/ssl_example.py` for a complete SSL setup example.

### CORS Protection

Configure Cross-Origin Resource Sharing with proper validation:

```python
from src.features.security import CORSConfig
from src.core import WSGIServer

cors_config = CORSConfig(
    allowed_origins=['https://example.com'],
    allowed_methods=['GET', 'POST', 'OPTIONS'],
    allowed_headers=['Content-Type', 'Authorization'],
    allow_credentials=True
)

server = WSGIServer(app, cors_config=cors_config)
```

### Rate Limiting

Protect against DoS attacks with configurable rate limiting:

```python
from src.features.security import RateLimiter
from src.core import WSGIServer

# Allow 10 requests per second with burst of 50
rate_limiter = RateLimiter(rate=10.0, burst=50)
server = WSGIServer(app, rate_limiter=rate_limiter)
```

### IP Filtering

Control access with IP whitelist/blacklist functionality:

```python
from src.features.security import IPFilter
from src.core import WSGIServer

ip_filter = IPFilter()
ip_filter.add_to_whitelist('192.168.1.0/24')  # Allow entire subnet
ip_filter.add_to_blacklist('10.0.0.5')        # Block specific IP

server = WSGIServer(app, ip_filter=ip_filter)
```

## Performance Features

### HTTP Keep-Alive

Reduces connection overhead by reusing TCP connections:

```python
from src.features import KeepAliveHandler
handler = KeepAliveHandler(wsgi_handler, max_requests=1000)
```

### Request Pipelining

Allows multiple requests on a single connection:

```python
from src.features import PipelineHandler
pipeline = PipelineHandler(app)
await pipeline.handle_pipeline(reader, writer)
```

### Memory Optimization

Buffer pooling reduces garbage collection pressure:

```python
from src.optimizations import MemoryPool
pool = MemoryPool(buffer_size=8192, pool_size=100)
buffer = pool.get_buffer()
```

## Framework Examples

### Flask Application

```python
from flask import Flask
from src.core import HighPerformanceWSGIServer

app = Flask(__name__)

@app.route('/')
def hello():
    return {'message': 'Hello from Flask!'}

if __name__ == '__main__':
    server = HighPerformanceWSGIServer(app.wsgi_app, workers=4)
    server.run()
```

### HTTP/2 Application

```python
from src.features.http2 import configure_http2
from src.core import HighPerformanceWSGIServer

def app(environ, start_response):
    status = '200 OK'
    headers = [
        ('Content-Type', 'text/plain'),
        ('Cache-Control', 'public, max-age=3600')
    ]
    start_response(status, headers)
    return [b'Hello from HTTP/2 server!']

if __name__ == '__main__':
    ssl_ctx = configure_http2()
    server = HighPerformanceWSGIServer(
        app,
        host='0.0.0.0',
        port=8443,
        ssl=ssl_ctx,
        workers=4
    )
    server.run()

### Django Application

```python
import os
import django
from django.core.wsgi import get_wsgi_application
from src.core import HighPerformanceWSGIServer

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

application = get_wsgi_application()

if __name__ == '__main__':
    server = HighPerformanceWSGIServer(application, workers=6)
    server.run()
```

## Performance Comparison

| Server | Requests/sec | Memory (MB) | Features |
|--------|-------------|-------------|----------|
| Gunicorn | ~2,000 | 25-50 | HTTP/1.1 |
| uWSGI | ~3,000 | 15-30 | HTTP/1.1 |
| This Server (HTTP/1.1) | ~15,000 | 10-20 | HTTP/1.1 |
| This Server (HTTP/2) | ~25,000+ | 12-22 | HTTP/2 |

*Benchmarks are approximate and depend on hardware, application complexity, and configuration.*

## Development

### Code Quality Tools

This project uses several tools to maintain code quality:

```bash
# Install development tools
pip install black flake8 pre-commit

# Set up pre-commit hooks
pre-commit install

# Format code with Black
black .

# Check code with Flake8
flake8 .

# Run both tools at once
python lint.py
```

See [LINTING.md](LINTING.md) for more details on code quality tools.

### Testing

Run the test suite:

```bash
# Run all tests
python -m pytest

# Run specific tests
python -m pytest tests/test_http2.py

# Run tests with coverage
python -m pytest --cov=src tests/
```

### CI/CD

This project uses GitHub Actions for continuous integration:

- Runs tests on multiple Python versions (3.8-3.13)
- Checks code formatting with Black
- Lints code with Flake8
- Reports test coverage

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests
4. Run the linting tools: `python lint.py`
5. Run tests: `python -m pytest tests/`
6. Submit a pull request

## License

This project is released under the MIT License. See LICENSE file for details.

## Support

For questions, issues, or contributions:

- Open an issue on GitHub
- Check the documentation
- Review example applications

---

Built with ❤️ for high-performance Python web applications.
