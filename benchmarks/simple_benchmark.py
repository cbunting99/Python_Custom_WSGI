"""
Copyright 2025 Chris Bunting
File: simple_benchmark.py | Purpose: Simple benchmarking tool for WSGI servers
@author Chris Bunting | @version 1.0.0

CHANGELOG:
2025-07-15 - Chris Bunting: Initial implementation
"""

import os
import sys
import time
import json
import platform
import multiprocessing
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import requests
from requests.exceptions import RequestException

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def create_benchmark_dirs():
    """Create necessary directories for benchmarks."""
    os.makedirs("benchmarks/results", exist_ok=True)


def run_http_benchmark(url, num_requests=1000, concurrency=10):
    """Run a simple HTTP benchmark using requests."""
    print(f"Running benchmark against {url}")
    print(f"Requests: {num_requests}, Concurrency: {concurrency}")

    results = {
        "url": url,
        "num_requests": num_requests,
        "concurrency": concurrency,
        "successful_requests": 0,
        "failed_requests": 0,
        "total_time": 0,
        "requests_per_second": 0,
        "avg_request_time": 0,
        "min_request_time": float("inf"),
        "max_request_time": 0,
    }

    request_times = []

    def worker(worker_id):
        """Worker function to send requests."""
        session = requests.Session()
        worker_results = {"successful": 0, "failed": 0, "times": []}

        requests_per_worker = num_requests // concurrency
        for _ in range(requests_per_worker):
            try:
                start_time = time.time()
                response = session.get(url)
                end_time = time.time()

                request_time = end_time - start_time

                if response.status_code == 200:
                    worker_results["successful"] += 1
                    worker_results["times"].append(request_time)
                else:
                    worker_results["failed"] += 1
            except RequestException:
                worker_results["failed"] += 1

        return worker_results

    # Start timing
    start_time = time.time()

    # Run workers in thread pool
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        worker_results = list(executor.map(worker, range(concurrency)))

    # End timing
    end_time = time.time()

    # Aggregate results
    for result in worker_results:
        results["successful_requests"] += result["successful"]
        results["failed_requests"] += result["failed"]
        request_times.extend(result["times"])

    # Calculate statistics
    results["total_time"] = end_time - start_time

    if results["successful_requests"] > 0:
        results["requests_per_second"] = (
            results["successful_requests"] / results["total_time"]
        )
        results["avg_request_time"] = sum(request_times) / len(request_times)
        results["min_request_time"] = min(request_times)
        results["max_request_time"] = max(request_times)

    return results


def benchmark_server(server_type, port=8000, num_requests=1000, concurrency=10):
    """Benchmark a specific server type."""
    url = f"http://localhost:{port}/"

    if server_type == "custom":
        # Start the custom WSGI server
        from src.core import HighPerformanceWSGIServer

        # Simple WSGI application
        def app(environ, start_response):
            status = "200 OK"
            headers = [("Content-Type", "text/plain")]
            start_response(status, headers)
            return [b"Hello, World!"]

        # Start server in a separate process
        import subprocess

        server_process = subprocess.Popen(
            [sys.executable, "-m", "benchmarks.servers.custom_http1_server", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for server to start
        time.sleep(2)

        try:
            # Run benchmark
            results = run_http_benchmark(url, num_requests, concurrency)
            results["server"] = "Custom WSGI Server"
            return results
        finally:
            # Stop server
            server_process.terminate()
            server_process.wait()

    elif server_type == "gunicorn":
        # Start Gunicorn server
        import subprocess

        server_process = subprocess.Popen(
            [
                "gunicorn",
                "-w",
                "4",
                "-b",
                f"0.0.0.0:{port}",
                "benchmarks.servers.wsgi_app:app",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for server to start
        time.sleep(2)

        try:
            # Run benchmark
            results = run_http_benchmark(url, num_requests, concurrency)
            results["server"] = "Gunicorn"
            return results
        finally:
            # Stop server
            server_process.terminate()
            server_process.wait()

    else:
        raise ValueError(f"Unknown server type: {server_type}")


def main():
    """Run benchmarks and save results."""
    create_benchmark_dirs()

    print("Running simple benchmarks for WSGI servers...")

    # Benchmark parameters
    num_requests = 1000  # Reduced for quicker testing
    concurrency = 10  # Reduced for quicker testing

    # Run benchmarks
    results = []

    try:
        # Benchmark custom WSGI server
        print("\nBenchmarking Custom WSGI Server...")
        custom_results = benchmark_server(
            "custom", port=8000, num_requests=num_requests, concurrency=concurrency
        )
        results.append(custom_results)

        # Benchmark Gunicorn
        print("\nBenchmarking Gunicorn...")
        gunicorn_results = benchmark_server(
            "gunicorn", port=8001, num_requests=num_requests, concurrency=concurrency
        )
        results.append(gunicorn_results)
    except Exception as e:
        print(f"Error running benchmarks: {e}")

    # Print results
    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)

    for result in results:
        print(f"\nServer: {result['server']}")
        print(f"Requests per second: {result['requests_per_second']:.2f}")
        print(f"Average request time: {result['avg_request_time'] * 1000:.2f} ms")
        print(f"Min request time: {result['min_request_time'] * 1000:.2f} ms")
        print(f"Max request time: {result['max_request_time'] * 1000:.2f} ms")
        print(f"Successful requests: {result['successful_requests']}")
        print(f"Failed requests: {result['failed_requests']}")

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"benchmarks/results/simple-benchmark-{timestamp}.json"

    # Add system information
    system_info = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "cpu_count": multiprocessing.cpu_count(),
    }

    output = {
        "system_info": system_info,
        "parameters": {
            "num_requests": num_requests,
            "concurrency": concurrency,
        },
        "results": results,
    }

    with open(filename, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to {filename}")

    # Verify README claims
    if len(results) >= 2:
        custom_result = next(
            (r for r in results if r.get("server") == "Custom WSGI Server"), None
        )
        gunicorn_result = next(
            (r for r in results if r.get("server") == "Gunicorn"), None
        )

        if custom_result and gunicorn_result:
            custom_rps = custom_result["requests_per_second"]
            gunicorn_rps = gunicorn_result["requests_per_second"]

            ratio = custom_rps / max(gunicorn_rps, 1)

            print("\n" + "=" * 60)
            print("README CLAIMS VERIFICATION")
            print("=" * 60)
            print(f"\nCustom WSGI Server: {custom_rps:.2f} req/sec")
            print(f"Gunicorn: {gunicorn_rps:.2f} req/sec")
            print(f"Ratio: {ratio:.2f}x faster")

            if ratio >= 7.5:  # 15,000 / 2,000 = 7.5
                print(
                    "\n✅ README claim VERIFIED: Custom WSGI Server is significantly faster than Gunicorn"
                )
            else:
                print(
                    f"\n❌ README claim NOT VERIFIED: Custom WSGI Server is only {ratio:.2f}x faster than Gunicorn (expected 7.5x)"
                )


if __name__ == "__main__":
    main()
