@echo off
echo Running Windows-compatible benchmarks for Custom WSGI Server
echo.

REM Generate SSL certificates
python -m benchmarks.windows_benchmark --generate-certs

REM Run benchmarks
python -m benchmarks.windows_benchmark --duration 30 --connections 50 --http2

echo.
echo Benchmarks completed. Results are in the benchmarks/results directory.
pause
