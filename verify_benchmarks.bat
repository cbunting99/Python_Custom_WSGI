@echo off
echo Verifying benchmarking system...
echo.

python verify_benchmark.py

echo.
echo If the verification was successful, you can now run the benchmarks:
echo - run_simple_benchmark.bat (for a quick test)
echo - run_benchmarks.bat (for a more comprehensive test)
pause 
