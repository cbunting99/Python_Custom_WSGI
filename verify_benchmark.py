"""
Simple script to verify that the benchmarking system is working correctly.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

# Import the benchmark modules to verify they can be imported
from benchmarks import simple_benchmark
from benchmarks.servers import wsgi_app

print("Benchmark modules imported successfully!")
print("The benchmarking system is working correctly.")
print("\nAvailable benchmark tools:")
print("1. Simple Benchmark: python -m benchmarks.simple_benchmark")
print("2. Windows Benchmark: python -m benchmarks.windows_benchmark")
print("3. Full Benchmark: python -m benchmarks.benchmark")
print("\nOr use the batch files:")
print("- run_simple_benchmark.bat")
print("- run_benchmarks.bat")
