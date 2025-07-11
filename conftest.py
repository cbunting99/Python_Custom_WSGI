"""
Pytest configuration file for the Custom WSGI Server project.
This file ensures that the src package can be imported during tests.
"""

import os
import sys
from pathlib import Path

# Add the project root directory to the Python path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))