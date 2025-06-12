# Changelog

All notable changes to the Python Custom WSGI Server will be documented in this file.

## [1.2.0] - 2025-06-12
### Added
- Added comprehensive type annotations to request handler
- Improved error response formatting with detailed messages
- Added proper exception handling in WSGI application calls

### Changed
- Created new `server_utils.py` module for shared functionality
- Moved socket optimization code to utility functions
- Standardized error handling across server implementations

## [1.1.2] - 2025-05-15
### Fixed
- Fixed empty except blocks in error handling
- Improved connection cleanup on errors
- Added proper error logging throughout the codebase

### Changed
- Enhanced error message formatting
- Improved socket closure handling
- Added docstrings for key functions

## [1.1.1] - 2025-04-22
### Added
- Added platform-specific socket optimizations
- Introduced TCP_NODELAY support for better performance
- Added improved error logging system

### Fixed
- Fixed connection handling in multiprocess mode
- Improved error recovery in request handler

## [1.1.0] - 2025-03-18
### Added
- Added uvloop support for better performance
- Introduced SO_REUSEPORT support for Linux systems
- Added server configuration utilities

### Changed
- Refactored server initialization code
- Improved multiprocessing support
- Enhanced socket configuration management

## [1.0.1] - 2025-02-05
### Fixed
- Fixed WSGI environment variable handling
- Improved request parsing reliability
- Added proper connection cleanup

### Added
- Added basic error logging
- Introduced platform detection for socket options
- Added initial documentation

## [1.0.0] - 2025-01-15
### Added
- Initial release of Python Custom WSGI Server
- Basic WSGI server implementation
- Multi-process worker support
- Request handler implementation
- Simple error handling