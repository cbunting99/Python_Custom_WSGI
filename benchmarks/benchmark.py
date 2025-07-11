#!/usr/bin/env python3
"""
Copyright 2025 Chris Bunting
File: benchmark.py | Purpose: Performance benchmarking tool for WSGI servers
@author Chris Bunting | @version 1.0.0

CHANGELOG:
2025-07-15 - Chris Bunting: Initial implementation
"""

import os
import sys
import time
import json
import argparse
import subprocess
import statistics
import platform
import multiprocessing
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Default settings
DEFAULT_DURATION = 30  # seconds
DEFAULT_CONNECTIONS = 100
DEFAULT_THREADS = 8
DEFAULT_ENDPOINT = "/"
DEFAULT_PORT_BASE = 8000
DEFAULT_PAYLOAD_SIZE = 1024  # bytes
DEFAULT_KEEP_ALIVE = True
DEFAULT_HTTP2 = False

# Server configurations
SERVERS = {
    "custom_http1": {
        "name": "Custom WSGI (HTTP/1.1)",
        "start_cmd": "python -m benchmarks.servers.custom_http1_server {port}",
        "protocol": "http",
    },
    "custom_http2": {
        "name": "Custom WSGI (HTTP/2)",
        "start_cmd": "python -m benchmarks.servers.custom_http2_server {port}",
        "protocol": "https",
    },
    "gunicorn": {
        "name": "Gunicorn",
        "start_cmd": "gunicorn -w {workers} -b 0.0.0.0:{port} benchmarks.servers.wsgi_app:app",
        "protocol": "http",
    },
    "uwsgi": {
        "name": "uWSGI",
        "start_cmd": "uwsgi --http 0.0.0.0:{port} --wsgi-file benchmarks/servers/wsgi_app.py --callable app --processes {workers} --threads 2",
        "protocol": "http",
    },
}


def create_benchmark_dirs():
    """Create necessary directories for benchmarks."""
    os.makedirs("benchmarks/servers", exist_ok=True)
    os.makedirs("benchmarks/results", exist_ok=True)
    os.makedirs("benchmarks/certs", exist_ok=True)


def generate_ssl_certs():
    """Generate self-signed SSL certificates for HTTPS testing."""
    cert_path = Path("benchmarks/certs")
    key_file = cert_path / "key.pem"
    cert_file = cert_path / "cert.pem"

    if key_file.exists() and cert_file.exists():
        print("SSL certificates already exist")
        return

    print("Generating self-signed SSL certificates...")

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


def create_server_files():
    """Create server implementation files for benchmarking."""
    # Create WSGI application file
    with open("benchmarks/servers/wsgi_app.py", "w") as f:
        f.write(
            """
import json

def app(environ, start_response):
    \"\"\"Simple WSGI application for benchmarking.\"\"\"
    status = '200 OK'
    headers = [('Content-Type', 'application/json')]

    # Get payload size from query string if provided
    try:
        payload_size = int(environ.get('QUERY_STRING', '').split('=')[1])
    except (IndexError, ValueError):
        payload_size = 1024  # Default size

    # Generate response payload
    response = {
        "message": "Hello from benchmark server!",
        "data": "X" * max(0, payload_size - 50)  # Adjust for JSON overhead
    }

    start_response(status, headers)
    return [json.dumps(response).encode()]
"""
        )

    # Create custom HTTP/1.1 server file
    with open("benchmarks/servers/custom_http1_server.py", "w") as f:
        f.write(
            """
import sys
from src.core import HighPerformanceWSGIServer
from benchmarks.servers.wsgi_app import app

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    workers = min(4, max(1, (multiprocessing.cpu_count() // 2)))

    server = HighPerformanceWSGIServer(
        app=app,
        host='0.0.0.0',
        port=port,
        workers=workers
    )
    server.run()
"""
        )

    # Create custom HTTP/2 server file
    with open("benchmarks/servers/custom_http2_server.py", "w") as f:
        f.write(
            """
import sys
import ssl
import multiprocessing
from pathlib import Path
from src.core import HighPerformanceWSGIServer
from src.features.http2 import configure_http2
from benchmarks.servers.wsgi_app import app

if __name__ == '__main__':
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
        app=app,
        host='0.0.0.0',
        port=port,
        workers=workers,
        ssl=ssl_ctx
    )
    server.run()
"""
        )

    # Create __init__.py to make the directory a package
    with open("benchmarks/servers/__init__.py", "w") as f:
        f.write("# Benchmark servers package\n")

    # Create __init__.py for benchmarks package
    with open("benchmarks/__init__.py", "w") as f:
        f.write("# Benchmarks package\n")


def run_benchmark(
    server_key: str,
    port: int,
    duration: int,
    connections: int,
    threads: int,
    endpoint: str,
    payload_size: int,
    keep_alive: bool,
    http2: bool,
) -> Dict[str, Any]:
    """Run a benchmark against a specific server.

    Args:
        server_key: Key of the server to benchmark
        port: Port to run the server on
        duration: Duration of the benchmark in seconds
        connections: Number of concurrent connections
        threads: Number of client threads
        endpoint: Endpoint to benchmark
        payload_size: Size of the response payload in bytes
        keep_alive: Whether to use HTTP keep-alive
        http2: Whether to use HTTP/2

    Returns:
        Dictionary with benchmark results
    """
    server_config = SERVERS[server_key]
    workers = min(4, max(1, (multiprocessing.cpu_count() // 2)))

    # Format the start command
    start_cmd = server_config["start_cmd"].format(port=port, workers=workers)

    # Start the server
    print(f"Starting {server_config['name']} on port {port}...")
    server_process = subprocess.Popen(
        start_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    # Wait for server to start
    time.sleep(3)

    # Prepare benchmark command
    protocol = server_config["protocol"]
    url = f"{protocol}://localhost:{port}{endpoint}?size={payload_size}"

    wrk_cmd = [
        "wrk",
        "-d",
        str(duration),
        "-c",
        str(connections),
        "-t",
        str(threads),
    ]

    if keep_alive:
        wrk_cmd.append("-H")
        wrk_cmd.append("Connection: keep-alive")
    else:
        wrk_cmd.append("-H")
        wrk_cmd.append("Connection: close")

    if http2 and protocol == "https":
        # Use h2load for HTTP/2 benchmarks
        benchmark_cmd = [
            "h2load",
            "-n",
            str(connections * 100),  # Total number of requests
            "-c",
            str(connections),  # Concurrent clients
            "-m",
            str(threads),  # Max concurrent streams
            "-t",
            str(threads),  # Threads
            "-d",
            str(duration),  # Duration
            "--h1",  # Force HTTP/1.1
            url,
        ]
        if http2:
            benchmark_cmd.remove("--h1")  # Allow HTTP/2
    else:
        # Use wrk for HTTP/1.1 benchmarks
        benchmark_cmd = wrk_cmd + [url]

    # Run the benchmark
    print(f"Running benchmark against {url}...")
    print(f"Command: {' '.join(benchmark_cmd)}")

    try:
        benchmark_output = subprocess.check_output(
            benchmark_cmd, stderr=subprocess.STDOUT, universal_newlines=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Benchmark failed: {e.output}")
        server_process.terminate()
        return {"server": server_config["name"], "error": str(e), "output": e.output}
    finally:
        # Stop the server
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()

    # Parse benchmark results
    results = {
        "server": server_config["name"],
        "protocol": "HTTP/2" if http2 and protocol == "https" else "HTTP/1.1",
        "raw_output": benchmark_output,
    }

    # Parse wrk output
    if "wrk" in benchmark_cmd[0]:
        for line in benchmark_output.splitlines():
            if "Requests/sec:" in line:
                results["requests_per_sec"] = float(line.split(":")[1].strip())
            elif "Transfer/sec:" in line:
                results["transfer_per_sec"] = line.split(":")[1].strip()
            elif "Latency" in line and "Distribution" not in line:
                latency_parts = line.split()
                results["latency_avg"] = latency_parts[1]
                results["latency_stdev"] = latency_parts[2]
                results["latency_max"] = latency_parts[3]

    # Parse h2load output
    elif "h2load" in benchmark_cmd[0]:
        for line in benchmark_output.splitlines():
            if "requests/s:" in line:
                results["requests_per_sec"] = float(line.split(":")[1].strip())
            elif "transfer/s:" in line:
                results["transfer_per_sec"] = line.split(":")[1].strip()
            elif "time for request:" in line:
                latency_parts = line.split(":")
                if len(latency_parts) > 1:
                    latency_values = latency_parts[1].strip().split(",")
                    for value in latency_values:
                        if "mean" in value:
                            results["latency_avg"] = value.split("=")[1].strip()
                        elif "sd" in value:
                            results["latency_stdev"] = value.split("=")[1].strip()
                        elif "max" in value:
                            results["latency_max"] = value.split("=")[1].strip()

    # Add memory usage (approximate)
    results["memory_mb"] = "Not measured"  # Would require additional monitoring

    return results


def run_all_benchmarks(args):
    """Run benchmarks for all configured servers."""
    results = []
    port = args.port_base

    # Generate SSL certificates if needed
    if args.http2 or "custom_http2" in args.servers:
        generate_ssl_certs()

    for server_key in args.servers:
        if server_key not in SERVERS:
            print(f"Warning: Unknown server '{server_key}', skipping")
            continue

        # Run HTTP/1.1 benchmark
        if server_key != "custom_http2" or not args.http2_only:
            result = run_benchmark(
                server_key=server_key,
                port=port,
                duration=args.duration,
                connections=args.connections,
                threads=args.threads,
                endpoint=args.endpoint,
                payload_size=args.payload_size,
                keep_alive=args.keep_alive,
                http2=False,
            )
            results.append(result)
            port += 1

        # Run HTTP/2 benchmark if supported and requested
        if args.http2 and (
            server_key == "custom_http2" or server_key == "custom_http1"
        ):
            result = run_benchmark(
                server_key="custom_http2",  # Always use HTTP/2 server
                port=port,
                duration=args.duration,
                connections=args.connections,
                threads=args.threads,
                endpoint=args.endpoint,
                payload_size=args.payload_size,
                keep_alive=True,  # HTTP/2 always uses keep-alive
                http2=True,
            )
            results.append(result)
            port += 1

    return results


def save_results(results, args):
    """Save benchmark results to a file."""
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"benchmarks/results/benchmark-{timestamp}.json"

    # Add system information
    system_info = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "cpu_count": multiprocessing.cpu_count(),
        "benchmark_args": vars(args),
    }

    output = {"system_info": system_info, "results": results}

    with open(filename, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Results saved to {filename}")
    return filename


def print_results_table(results):
    """Print benchmark results in a formatted table."""
    print("\n" + "=" * 80)
    print(
        f"{'Server':<25} {'Protocol':<10} {'Req/sec':<12} {'Latency Avg':<12} {'Memory':<10}"
    )
    print("-" * 80)

    for result in results:
        if "error" in result:
            print(f"{result['server']:<25} ERROR: {result['error']}")
            continue

        print(
            f"{result['server']:<25} "
            f"{result['protocol']:<10} "
            f"{result.get('requests_per_sec', 'N/A'):<12.1f} "
            f"{result.get('latency_avg', 'N/A'):<12} "
            f"{result.get('memory_mb', 'N/A'):<10}"
        )

    print("=" * 80)


def generate_markdown_report(results_file):
    """Generate a Markdown report from benchmark results."""
    with open(results_file, "r") as f:
        data = json.load(f)

    system_info = data["system_info"]
    results = data["results"]

    # Create report filename
    report_file = results_file.replace(".json", ".md")

    with open(report_file, "w") as f:
        f.write("# WSGI Server Benchmark Results\n\n")

        # System information
        f.write("## System Information\n\n")
        f.write(f"- **Platform**: {system_info['platform']}\n")
        f.write(f"- **Processor**: {system_info['processor']}\n")
        f.write(f"- **CPU Count**: {system_info['cpu_count']}\n")
        f.write(f"- **Python Version**: {system_info['python_version']}\n\n")

        # Benchmark parameters
        args = system_info["benchmark_args"]
        f.write("## Benchmark Parameters\n\n")
        f.write(f"- **Duration**: {args['duration']} seconds\n")
        f.write(f"- **Connections**: {args['connections']}\n")
        f.write(f"- **Threads**: {args['threads']}\n")
        f.write(f"- **Payload Size**: {args['payload_size']} bytes\n")
        f.write(
            f"- **Keep-Alive**: {'Enabled' if args['keep_alive'] else 'Disabled'}\n\n"
        )

        # Results table
        f.write("## Results\n\n")
        f.write("| Server | Protocol | Requests/sec | Latency Avg | Memory (MB) |\n")
        f.write("|--------|----------|-------------|-------------|------------|\n")

        for result in results:
            if "error" in result:
                f.write(f"| {result['server']} | ERROR | {result['error']} | - | - |\n")
                continue

            f.write(
                f"| {result['server']} | "
                f"{result['protocol']} | "
                f"{result.get('requests_per_sec', 'N/A'):.1f} | "
                f"{result.get('latency_avg', 'N/A')} | "
                f"{result.get('memory_mb', 'N/A')} |\n"
            )

        f.write("\n")

        # Comparison with README claims
        f.write("## Comparison with README Claims\n\n")
        f.write("The README claims the following performance characteristics:\n\n")
        f.write("| Server | Requests/sec | Memory (MB) | Features |\n")
        f.write("|--------|-------------|-------------|----------|\n")
        f.write("| Gunicorn | ~2,000 | 25-50 | HTTP/1.1 |\n")
        f.write("| uWSGI | ~3,000 | 15-30 | HTTP/1.1 |\n")
        f.write("| This Server (HTTP/1.1) | ~15,000 | 10-20 | HTTP/1.1 |\n")
        f.write("| This Server (HTTP/2) | ~25,000+ | 12-22 | HTTP/2 |\n\n")

        f.write("### Verification\n\n")
        f.write(
            "Based on the benchmark results above, the README performance claims are:\n\n"
        )

        # Find results for each server type
        custom_http1 = next(
            (
                r
                for r in results
                if r.get("server") == "Custom WSGI (HTTP/1.1)" and "error" not in r
            ),
            None,
        )
        custom_http2 = next(
            (
                r
                for r in results
                if r.get("server") == "Custom WSGI (HTTP/2)" and "error" not in r
            ),
            None,
        )
        gunicorn = next(
            (r for r in results if r.get("server") == "Gunicorn" and "error" not in r),
            None,
        )
        uwsgi = next(
            (r for r in results if r.get("server") == "uWSGI" and "error" not in r),
            None,
        )

        # Verify claims
        if custom_http1 and gunicorn:
            ratio = custom_http1.get("requests_per_sec", 0) / max(
                gunicorn.get("requests_per_sec", 1), 1
            )
            f.write(
                f"- Custom WSGI (HTTP/1.1) is **{ratio:.1f}x faster** than Gunicorn "
            )
            if ratio >= 7.5:  # 15,000 / 2,000 = 7.5
                f.write("✅ (claim verified)\n")
            else:
                f.write("❌ (claim not verified)\n")

        if custom_http1 and uwsgi:
            ratio = custom_http1.get("requests_per_sec", 0) / max(
                uwsgi.get("requests_per_sec", 1), 1
            )
            f.write(f"- Custom WSGI (HTTP/1.1) is **{ratio:.1f}x faster** than uWSGI ")
            if ratio >= 5:  # 15,000 / 3,000 = 5
                f.write("✅ (claim verified)\n")
            else:
                f.write("❌ (claim not verified)\n")

        if custom_http2 and custom_http1:
            ratio = custom_http2.get("requests_per_sec", 0) / max(
                custom_http1.get("requests_per_sec", 1), 1
            )
            f.write(
                f"- Custom WSGI (HTTP/2) is **{ratio:.1f}x faster** than Custom WSGI (HTTP/1.1) "
            )
            if ratio >= 1.67:  # 25,000 / 15,000 = 1.67
                f.write("✅ (claim verified)\n")
            else:
                f.write("❌ (claim not verified)\n")

        f.write("\n")
        f.write(
            "*Note: Memory usage claims require additional monitoring tools to verify accurately.*\n"
        )

    print(f"Markdown report generated: {report_file}")
    return report_file


def check_dependencies():
    """Check if required dependencies are installed."""
    missing = []

    # Check for wrk
    try:
        subprocess.run(["wrk", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        missing.append("wrk (https://github.com/wg/wrk)")

    # Check for h2load if HTTP/2 benchmarks are needed
    try:
        subprocess.run(["h2load", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        missing.append("h2load (part of nghttp2)")

    # Check for OpenSSL
    try:
        subprocess.run(
            ["openssl", "version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except FileNotFoundError:
        missing.append("openssl")

    if missing:
        print("Missing dependencies:")
        for dep in missing:
            print(f"  - {dep}")
        print("\nPlease install these dependencies before running benchmarks.")
        return False

    return True


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Benchmark WSGI servers")

    parser.add_argument(
        "--servers",
        nargs="+",
        default=list(SERVERS.keys()),
        help="Servers to benchmark (default: all)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=DEFAULT_DURATION,
        help=f"Benchmark duration in seconds (default: {DEFAULT_DURATION})",
    )
    parser.add_argument(
        "--connections",
        type=int,
        default=DEFAULT_CONNECTIONS,
        help=f"Number of concurrent connections (default: {DEFAULT_CONNECTIONS})",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=DEFAULT_THREADS,
        help=f"Number of client threads (default: {DEFAULT_THREADS})",
    )
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help=f"Endpoint to benchmark (default: {DEFAULT_ENDPOINT})",
    )
    parser.add_argument(
        "--port-base",
        type=int,
        default=DEFAULT_PORT_BASE,
        help=f"Base port number (default: {DEFAULT_PORT_BASE})",
    )
    parser.add_argument(
        "--payload-size",
        type=int,
        default=DEFAULT_PAYLOAD_SIZE,
        help=f"Response payload size in bytes (default: {DEFAULT_PAYLOAD_SIZE})",
    )
    parser.add_argument(
        "--no-keep-alive",
        action="store_false",
        dest="keep_alive",
        help="Disable HTTP keep-alive",
    )
    parser.add_argument("--http2", action="store_true", help="Enable HTTP/2 benchmarks")
    parser.add_argument(
        "--http2-only", action="store_true", help="Only run HTTP/2 benchmarks"
    )
    parser.add_argument(
        "--generate-certs",
        action="store_true",
        help="Generate SSL certificates for HTTPS",
    )
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="Only set up benchmark files without running benchmarks",
    )

    return parser.parse_args()


def main():
    """Main function."""
    args = parse_args()

    # Create benchmark directories and files
    create_benchmark_dirs()
    create_server_files()

    # Generate SSL certificates if requested
    if args.generate_certs:
        generate_ssl_certs()

    # Exit if only setup was requested
    if args.setup_only:
        print(
            "Benchmark files created. Run without --setup-only to execute benchmarks."
        )
        return

    # Check dependencies
    if not check_dependencies():
        return

    # Run benchmarks
    results = run_all_benchmarks(args)

    # Print results
    print_results_table(results)

    # Save results
    results_file = save_results(results, args)

    # Generate report
    generate_markdown_report(results_file)


if __name__ == "__main__":
    main()
