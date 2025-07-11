# WSGI Server Benchmarks

This directory contains tools for benchmarking the performance of the Custom WSGI Server against other popular WSGI servers like Gunicorn and uWSGI.

## Verifying the Benchmarking System

Before running benchmarks, you can verify that the benchmarking system is working correctly:

```bash
# Run the verification script
python verify_benchmark.py
```

This script checks that all benchmark modules can be imported correctly and provides information about the available benchmark tools.

## Windows-Compatible Benchmarks

For Windows users, we provide a simplified benchmarking tool that doesn't require external dependencies:

```bash
# Run the Windows-compatible benchmark
python -m benchmarks.windows_benchmark

# Or use the batch file
run_benchmarks.bat
```

For an even simpler benchmark with minimal dependencies:

```bash
# Run the simple benchmark
python -m benchmarks.simple_benchmark

# Or use the batch file
run_simple_benchmark.bat
```

The Windows benchmark uses Python's `requests` and `aiohttp` libraries to simulate load testing and doesn't require external tools like wrk or h2load.

### Windows Prerequisites

1. **OpenSSL** (for certificate generation)
   - Download from [OpenSSL for Windows](https://slproweb.com/products/Win32OpenSSL.html)
   - Add to PATH

2. **Python Dependencies**
   - `pip install requests aiohttp gunicorn`

## Unix/Linux Benchmarks

For Unix/Linux users, we provide a more comprehensive benchmarking tool that uses industry-standard benchmarking tools:

### Prerequisites

1. **wrk** - HTTP benchmarking tool
   - Linux: `apt-get install wrk` or build from [source](https://github.com/wg/wrk)
   - macOS: `brew install wrk`

2. **nghttp2** (for HTTP/2 benchmarks)
   - Linux: `apt-get install nghttp2-client`
   - macOS: `brew install nghttp2`

3. **OpenSSL** (for certificate generation)
   - Linux: `apt-get install openssl`
   - macOS: `brew install openssl`

4. **Server implementations to benchmark**
   - Gunicorn: `pip install gunicorn`
   - uWSGI: `pip install uwsgi`

## Running Benchmarks

### Basic Usage

```bash
# Set up benchmark files without running benchmarks
python -m benchmarks.benchmark --setup-only

# Run all benchmarks with default settings
python -m benchmarks.benchmark

# Run specific servers only
python -m benchmarks.benchmark --servers custom_http1 gunicorn

# Run HTTP/2 benchmarks
python -m benchmarks.benchmark --http2
```

### Advanced Options

```bash
# Customize benchmark parameters
python -m benchmarks.benchmark --duration 60 --connections 200 --threads 16

# Specify response payload size
python -m benchmarks.benchmark --payload-size 4096

# Disable keep-alive
python -m benchmarks.benchmark --no-keep-alive

# Only run HTTP/2 benchmarks
python -m benchmarks.benchmark --http2-only
```

## Benchmark Results

Benchmark results are saved in the `results` directory in both JSON and Markdown formats. The Markdown report includes:

- System information
- Benchmark parameters
- Performance results for each server
- Comparison with the performance claims in the main README

## Verifying README Claims

The benchmark tool automatically compares the results with the performance claims in the main README:

| Server | Requests/sec | Memory (MB) | Features |
|--------|-------------|-------------|----------|
| Gunicorn | ~2,000 | 25-50 | HTTP/1.1 |
| uWSGI | ~3,000 | 15-30 | HTTP/1.1 |
| This Server (HTTP/1.1) | ~15,000 | 10-20 | HTTP/1.1 |
| This Server (HTTP/2) | ~25,000+ | 12-22 | HTTP/2 |

The generated report will indicate whether these claims are verified by your benchmark results.

## Directory Structure

```
benchmarks/
├── benchmark.py       # Main benchmark script
├── windows_benchmark.py # Windows-compatible benchmark
├── simple_benchmark.py # Simple benchmark with minimal dependencies
├── README.md          # This file
├── BENCHMARK_GUIDE.md # Detailed guide to benchmarking
├── certs/             # SSL certificates for HTTPS/HTTP2
├── results/           # Benchmark results
└── servers/           # Server implementations for benchmarking
```

## Notes

- Performance results will vary based on hardware, operating system, and network conditions
- For the most accurate results, run benchmarks on a dedicated machine with minimal background processes
- Memory usage measurement requires additional monitoring tools
