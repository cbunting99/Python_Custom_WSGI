#!/usr/bin/env python3
"""
Test runner for all WSGI server tests
"""
import unittest
import sys
import os
from pathlib import Path

def setup_test_environment():
    """Setup the test environment including Python path"""
    # Get project root directory (parent of tests directory)
    project_root = Path(__file__).parent.parent
    
    # Add project root to Python path
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

def run_all_tests():
    """Run all test suites and return overall result"""
    # Setup environment
    setup_test_environment()
    
    # Get the tests directory
    tests_dir = Path(__file__).parent
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.discover(str(tests_dir), pattern='test_*.py')
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    print("Running all WSGI server tests...\n")
    
    success = run_all_tests()
    
    # Return non-zero exit code if tests failed
    sys.exit(0 if success else 1)