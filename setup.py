#!/usr/bin/env python3
"""
Setup script for Custom High-Performance WSGI Server
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="custom-wsgi-server",
    version="1.5.0",
    author="Chris Bunting",
    description="A high-performance, secure, asyncio-based WSGI server implementation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/chrisbunting/custom-wsgi-server",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Server",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Security",
        "Framework :: AsyncIO",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.23.0",
            "pytest-cov>=4.1.0",
            "aiohttp>=3.9.0",
            "black>=23.3.0",
            "flake8>=6.0.0",
            "mypy>=1.3.0",
            "isort>=5.12.0",
            "bandit>=1.7.5",  # Security linter
        ],
        "test": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.23.0",
            "pytest-cov>=4.1.0",
            "aiohttp>=3.9.0",
        ],
        "security": [
            "cryptography>=41.0.0",
            "pyopenssl>=23.2.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "custom-wsgi=src.core.wsgi_server:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
