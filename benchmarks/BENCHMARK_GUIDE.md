# Custom WSGI Server Benchmarking Guide

This guide explains the different benchmarking tools available for the Custom WSGI Server and how to use them.

## Available Benchmarking Tools

We provide several benchmarking tools to accommodate different operating systems and requirements:

1. **Simple Benchmark** (`simple_benchmark.py`)
   - Lightweight, cross-platform benchmark with minimal dependencies
   - Uses Python's `requests` library for HTTP testing
   - Works on Windows, Linux, and macOS without external tools
   - Quick to run and easy to use

2. **Windows-Compatible Benchmark** (`windows_benchmark.py`)
   - More comprehensive benchmark for Windows users
   - Uses `requests` and `aiohttp` for HTTP/1.1 and HTTP/2 testing
   - Supports concurrent connections and keep-alive testing
   - Generates detailed reports in JSON and Markdown formats

3. **Full Benchmark** (`benchmark.py`)
   - Most comprehensive benchmark using industry-standard tools
   - Requires external tools like `wrk` and `h2load`
   - Best for Linux/macOS users
   - Provides the most accurate performance measurements

## Choosing the Right Benchmark

- **For quick testing on any platform**: Use `simple_benchmark.py`
- **For Windows users who want detailed results**: Use `windows_benchmark.py`
- **For Linux/macOS users who want the most accurate results**: Use `benchmark.py`

## Running the Benchmarks

### Simple Benchmark

```bash
# Run the simple benchmark
python -m benchmarks.simple_benchmark

# Or use the batch file (Windows)
run_simple_benchmark.bat
```

### Windows-Compatible Benchmark

```bash
# Run the Windows-compatible benchmark
python -m benchmarks.windows_benchmark

# Or use the batch file (Windows)
run_benchmarks.bat
```

### Full Benchmark (Linux/macOS)

```bash
# Set up benchmark environment
python -m benchmarks.benchmark --setup-only --generate-certs

# Run all benchmarks
python -m benchmarks.benchmark

# Run HTTP/2 benchmarks
python -m benchmarks.benchmark --http2
```

## Benchmark Parameters

All benchmarks support various parameters to customize the testing:

- **Duration**: How long to run the benchmark
- **Connections**: Number of concurrent connections
- **Requests**: Total number of requests to send
- **Payload Size**: Size of the response payload
- **Keep-Alive**: Whether to use HTTP keep-alive
- **HTTP/2**: Whether to test HTTP/2 performance

## Interpreting Results

The benchmark results include:

- **Requests per second**: The number of requests the server can handle per second
- **Latency**: The time it takes for the server to respond to a request
- **Error rate**: The percentage of requests that failed
- **Throughput**: The amount of data transferred per second

These metrics can be compared against the claims in the README to verify the performance of the Custom WSGI Server.

## Verifying README Claims

The README claims the following performance characteristics:

| Server | Requests/sec | Memory (MB) | Features |
|--------|-------------|-------------|----------|
| Gunicorn | ~2,000 | 25-50 | HTTP/1.1 |
| uWSGI | ~3,000 | 15-30 | HTTP/1.1 |
| This Server (HTTP/1.1) | ~15,000 | 10-20 | HTTP/1.1 |
| This Server (HTTP/2) | ~25,000+ | 12-22 | HTTP/2 |

The benchmark tools automatically compare the results against these claims and indicate whether they are verified.

## Factors Affecting Performance

Performance results can vary based on:

- **Hardware**: CPU, memory, and disk speed
- **Operating System**: Windows, Linux, or macOS
- **Network**: Local vs. remote testing
- **Application Complexity**: Simple vs. complex WSGI applications
- **Concurrency**: Number of concurrent connections
- **Payload Size**: Size of the response payload

For the most accurate results, run benchmarks on hardware similar to your production environment.
