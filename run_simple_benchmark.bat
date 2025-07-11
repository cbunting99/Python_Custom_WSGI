@echo off
echo Running Simple Benchmarks for Custom WSGI Server
echo.

python -m benchmarks.simple_benchmark

echo.
echo Benchmarks completed. Results are in the benchmarks/results directory.
pause
