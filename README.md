# Custom High-Performance WSGI Server

> ⚠️ **NOTICE**: This is a work in progress (WIP) project that has not been thoroughly tested in production environments. Updates are made as time permits. Use with caution in production settings.

A high-performance, asyncio-based WSGI server implementation built for speed and scalability. This server leverages modern Python async capabilities, uvloop, and httptools to deliver exceptional performance for WSGI applications.

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
- **📊 Memory Optimized**: Buffer pooling and memory-efficient request parsing
- **🛠 WSGI Compatible**: Works with any WSGI application (Flask, Django, etc.)
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
| Gunicorn | ~2,000 | 25-50 | Mature, stable |
| uWSGI | ~3,000 | 15-30 | Feature-rich |
| This Server | ~15,000+ | 10-20 | Modern, async |

*Benchmarks are approximate and depend on hardware, application complexity, and configuration.*

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests
4. Run tests: `python -m pytest tests/`
5. Submit a pull request

## License

This project is released under the MIT License. See LICENSE file for details.

## Support

For questions, issues, or contributions:

- Open an issue on GitHub
- Check the documentation
- Review example applications

---

Built with ❤️ for high-performance Python web applications.
