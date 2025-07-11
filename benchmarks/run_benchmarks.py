"""
Copyright 2025 Chris Bunting
File: run_benchmarks.py | Purpose: Run benchmarks and generate report
@author Chris Bunting | @version 1.0.0

CHANGELOG:
2025-07-15 - Chris Bunting: Initial implementation
"""

import os
import sys
import subprocess
from pathlib import Path


def main():
    """Run benchmarks and generate report."""
    # Ensure we're in the project root directory
    os.chdir(Path(__file__).parent.parent)

    # Check if benchmark dependencies are installed
    try:
        # Check for wrk
        subprocess.run(["wrk", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        print("Error: 'wrk' not found. Please install wrk before running benchmarks.")
        print("See benchmarks/README.md for installation instructions.")
        return 1

    # Generate SSL certificates
    print("Generating SSL certificates...")
    subprocess.run([sys.executable, "-m", "benchmarks.generate_certs"])

    # Run benchmarks
    print("\nRunning benchmarks...")
    benchmark_cmd = [
        sys.executable,
        "-m",
        "benchmarks.benchmark",
        "--duration",
        "30",
        "--connections",
        "100",
        "--threads",
        "8",
        "--http2",
    ]

    try:
        subprocess.run(benchmark_cmd, check=True)
        print("\nBenchmarks completed successfully!")
        print("See benchmarks/results directory for detailed results.")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"\nError running benchmarks: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
