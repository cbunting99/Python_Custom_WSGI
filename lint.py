#!/usr/bin/env python3
"""
Lint and format Python code in the project.

This script runs Black and Flake8 on all Python files in the project.
"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(command, description):
    """Run a command and print its output."""
    print(f"\n{description}...")
    result = subprocess.run(command, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)

    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if result.returncode != 0:
        print(f"{description} failed with exit code {result.returncode}")
    else:
        print(f"{description} completed successfully")

    return result.returncode


def main():
    """Run linting and formatting tools."""
    # Get the project root directory
    project_root = Path(__file__).parent.absolute()

    # Change to the project root directory
    os.chdir(project_root)

    # Run Black to format code
    black_result = run_command(["black", "."], "Formatting code with Black")

    # Run Flake8 to check for issues
    flake8_result = run_command(["flake8", "."], "Checking code with Flake8")

    # Install pre-commit hooks if they're not already installed
    if os.path.exists(".pre-commit-config.yaml"):
        if not os.path.exists(".git/hooks/pre-commit"):
            run_command(["pre-commit", "install"], "Installing pre-commit hooks")

    # Return non-zero exit code if any tool failed
    return black_result != 0 or flake8_result != 0


if __name__ == "__main__":
    sys.exit(main())
