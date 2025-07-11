"""
Copyright 2025 Chris Bunting
File: windows_benchmark.py | Purpose: Windows-compatible benchmarking tool
@author Chris Bunting | @version 1.0.0

CHANGELOG:
2025-07-15 - Chris Bunting: Initial implementation
"""

import os
import sys
import time
import json
import asyncio
import platform
import argparse
import subprocess
import statistics
import multiprocessing
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import aiohttp
import requests
from requests.exceptions import RequestException

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Default settings
DEFAULT_DURATION = 30  # seconds
DEFAULT_CONNECTIONS = 100
DEFAULT_REQUESTS = 10000
DEFAULT_ENDPOINT = "/"
DEFAULT_PORT_BASE = 8000
DEFAULT_PAYLOAD_SIZE = 1024  # bytes

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


class HttpBenchmark:
    """HTTP benchmarking tool using Python's requests and aiohttp."""

    def __init__(
        self,
        url,
        connections=DEFAULT_CONNECTIONS,
        total_requests=DEFAULT_REQUESTS,
        duration=DEFAULT_DURATION,
        keep_alive=True,
        http2=False,
    ):
        self.url = url
        self.connections = connections
        self.total_requests = total_requests
        self.duration = duration
        self.keep_alive = keep_alive
        self.http2 = http2
        self.results = {
            "requests_completed": 0,
            "requests_per_sec": 0,
            "latency_avg": 0,
            "latency_min": 0,
            "latency_max": 0,
            "latency_stdev": 0,
            "errors": 0,
            "transfer_bytes": 0,
        }
        self.latencies = []
        self.session = None

    async def _async_worker(self, worker_id, semaphore, start_time):
        """Async worker for HTTP requests."""
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False, force_close=not self.keep_alive)
        ) as session:
            self.session = session
            request_count = 0

            while (
                time.time() - start_time < self.duration
                and request_count < self.total_requests
            ):
                async with semaphore:
                    try:
                        request_start = time.time()
                        async with session.get(self.url) as response:
                            data = await response.read()
                            request_end = time.time()

                            if response.status == 200:
                                latency = (request_end - request_start) * 1000  # ms
                                self.latencies.append(latency)
                                self.results["requests_completed"] += 1
                                self.results["transfer_bytes"] += len(data)
                            else:
                                self.results["errors"] += 1
                    except Exception as e:
                        self.results["errors"] += 1

                    request_count += 1

    async def run_async(self):
        """Run async benchmark."""
        print(f"Running async benchmark against {self.url}")
        print(f"Connections: {self.connections}, Duration: {self.duration}s")

        start_time = time.time()
        semaphore = asyncio.Semaphore(self.connections)

        # Create workers
        workers = [
            self._async_worker(i, semaphore, start_time)
            for i in range(self.connections)
        ]

        # Run workers
        await asyncio.gather(*workers)

        # Calculate results
        end_time = time.time()
        elapsed = end_time - start_time

        if self.latencies:
            self.results["latency_avg"] = statistics.mean(self.latencies)
            self.results["latency_min"] = min(self.latencies)
            self.results["latency_max"] = max(self.latencies)
            self.results["latency_stdev"] = (
                statistics.stdev(self.latencies) if len(self.latencies) > 1 else 0
            )

        self.results["requests_per_sec"] = self.results["requests_completed"] / elapsed
        self.results["transfer_per_sec"] = self.results["transfer_bytes"] / elapsed

        return self.results

    def _sync_worker(self, worker_id, start_time, results, session=None):
        """Synchronous worker for HTTP requests."""
        if session is None:
            session = requests.Session()

        request_count = 0
        local_latencies = []
        local_completed = 0
        local_errors = 0
        local_bytes = 0

        while (
            time.time() - start_time < self.duration
            and request_count < self.total_requests // self.connections
        ):
            try:
                request_start = time.time()
                response = session.get(self.url)
                request_end = time.time()

                if response.status_code == 200:
                    latency = (request_end - request_start) * 1000  # ms
                    local_latencies.append(latency)
                    local_completed += 1
                    local_bytes += len(response.content)
                else:
                    local_errors += 1
            except RequestException:
                local_errors += 1

            request_count += 1

        return {
            "latencies": local_latencies,
            "completed": local_completed,
            "errors": local_errors,
            "bytes": local_bytes,
        }

    def run_sync(self):
        """Run synchronous benchmark."""
        print(f"Running sync benchmark against {self.url}")
        print(f"Connections: {self.connections}, Duration: {self.duration}s")

        start_time = time.time()

        # Create session for keep-alive
        session = requests.Session()

        # Run workers in thread pool
        with ThreadPoolExecutor(max_workers=self.connections) as executor:
            worker_results = list(
                executor.map(
                    lambda worker_id: self._sync_worker(
                        worker_id, start_time, self.results, session
                    ),
                    range(self.connections),
                )
            )

        # Aggregate results
        all_latencies = []
        for result in worker_results:
            all_latencies.extend(result["latencies"])
            self.results["requests_completed"] += result["completed"]
            self.results["errors"] += result["errors"]
            self.results["transfer_bytes"] += result["bytes"]

        # Calculate results
        end_time = time.time()
        elapsed = end_time - start_time

        if all_latencies:
            self.results["latency_avg"] = statistics.mean(all_latencies)
            self.results["latency_min"] = min(all_latencies)
            self.results["latency_max"] = max(all_latencies)
            self.results["latency_stdev"] = (
                statistics.stdev(all_latencies) if len(all_latencies) > 1 else 0
            )

        self.results["requests_per_sec"] = self.results["requests_completed"] / elapsed
        self.results["transfer_per_sec"] = self.results["transfer_bytes"] / elapsed

        return self.results


def run_benchmark(
    server_key,
    port,
    duration,
    connections,
    requests,
    endpoint,
    payload_size,
    keep_alive,
    http2,
):
    """Run a benchmark against a specific server."""
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

    # Prepare benchmark URL
    protocol = server_config["protocol"]
    url = f"{protocol}://localhost:{port}{endpoint}?size={payload_size}"

    # Run benchmark
    try:
        if http2 and protocol == "https":
            # HTTP/2 benchmark (async)
            benchmark = HttpBenchmark(
                url=url,
                connections=connections,
                total_requests=requests,
                duration=duration,
                keep_alive=True,  # HTTP/2 always uses keep-alive
                http2=True,
            )
            results = asyncio.run(benchmark.run_async())
        else:
            # HTTP/1.1 benchmark (sync)
            benchmark = HttpBenchmark(
                url=url,
                connections=connections,
                total_requests=requests,
                duration=duration,
                keep_alive=keep_alive,
                http2=False,
            )
            results = benchmark.run_sync()

        # Format results
        formatted_results = {
            "server": server_config["name"],
            "protocol": "HTTP/2" if http2 and protocol == "https" else "HTTP/1.1",
            "requests_per_sec": results["requests_per_sec"],
            "latency_avg": f"{results['latency_avg']:.2f}ms",
            "latency_min": f"{results['latency_min']:.2f}ms",
            "latency_max": f"{results['latency_max']:.2f}ms",
            "latency_stdev": f"{results['latency_stdev']:.2f}ms",
            "transfer_per_sec": f"{results['transfer_per_sec'] / 1024:.2f}KB/s",
            "errors": results["errors"],
            "requests_completed": results["requests_completed"],
        }

        return formatted_results

    except Exception as e:
        print(f"Benchmark failed: {e}")
        return {"server": server_config["name"], "error": str(e)}
    finally:
        # Stop the server
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()


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
                requests=args.requests,
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
                requests=args.requests,
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
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
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
        f"{'Server':<25} {'Protocol':<10} {'Req/sec':<12} {'Latency Avg':<12} {'Errors':<10}"
    )
    print("-" * 80)

    for result in results:
        if "error" in result:
            print(f"{result['server']:<25} ERROR: {result['error']}")
            continue

        print(
            f"{result['server']:<25} "
            f"{result['protocol']:<10} "
            f"{result.get('requests_per_sec', 0):<12.1f} "
            f"{result.get('latency_avg', 'N/A'):<12} "
            f"{result.get('errors', 0):<10}"
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
        f.write(f"- **Requests**: {args['requests']}\n")
        f.write(f"- **Payload Size**: {args['payload_size']} bytes\n")
        f.write(
            f"- **Keep-Alive**: {'Enabled' if args['keep_alive'] else 'Disabled'}\n\n"
        )

        # Results table
        f.write("## Results\n\n")
        f.write("| Server | Protocol | Requests/sec | Latency Avg | Errors |\n")
        f.write("|--------|----------|-------------|-------------|--------|\n")

        for result in results:
            if "error" in result:
                f.write(f"| {result['server']} | ERROR | {result['error']} | - | - |\n")
                continue

            f.write(
                f"| {result['server']} | "
                f"{result['protocol']} | "
                f"{result.get('requests_per_sec', 0):.1f} | "
                f"{result.get('latency_avg', 'N/A')} | "
                f"{result.get('errors', 0)} |\n"
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

    # Check for OpenSSL (for certificate generation)
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
    parser = argparse.ArgumentParser(
        description="Benchmark WSGI servers (Windows compatible)"
    )

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
        "--requests",
        type=int,
        default=DEFAULT_REQUESTS,
        help=f"Maximum number of requests per connection (default: {DEFAULT_REQUESTS})",
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

    # Create benchmark directories
    create_benchmark_dirs()

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
