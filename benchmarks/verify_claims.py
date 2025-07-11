"""
Copyright 2025 Chris Bunting
File: verify_claims.py | Purpose: Verify performance claims in README
@author Chris Bunting | @version 1.0.0

CHANGELOG:
2025-07-15 - Chris Bunting: Initial implementation
"""

import os
import json
import glob
from pathlib import Path


def verify_claims():
    """Verify performance claims in README against benchmark results."""
    # Find the most recent benchmark results
    results_dir = Path("benchmarks/results")
    if not results_dir.exists():
        print("No benchmark results found. Run benchmarks first.")
        return

    # Find the most recent JSON result file
    json_files = glob.glob(str(results_dir / "benchmark-*.json"))
    if not json_files:
        print("No benchmark results found. Run benchmarks first.")
        return

    latest_file = max(json_files, key=os.path.getctime)
    print(f"Analyzing results from {latest_file}")

    # Load the results
    with open(latest_file, "r") as f:
        data = json.load(f)

    results = data["results"]

    # README claims
    claims = {
        "Gunicorn": {"req_sec": 2000, "memory": "25-50"},
        "uWSGI": {"req_sec": 3000, "memory": "15-30"},
        "Custom WSGI (HTTP/1.1)": {"req_sec": 15000, "memory": "10-20"},
        "Custom WSGI (HTTP/2)": {"req_sec": 25000, "memory": "12-22"},
    }

    # Find results for each server type
    custom_http1 = next(
        (
            r
            for r in results
            if r.get("server") == "Custom WSGI (HTTP/1.1)" and "error" not in r
        ),
        None,
    )
    custom_http2 = next(
        (
            r
            for r in results
            if r.get("server") == "Custom WSGI (HTTP/2)" and "error" not in r
        ),
        None,
    )
    gunicorn = next(
        (r for r in results if r.get("server") == "Gunicorn" and "error" not in r), None
    )
    uwsgi = next(
        (r for r in results if r.get("server") == "uWSGI" and "error" not in r), None
    )

    # Print header
    print("\n" + "=" * 80)
    print("PERFORMANCE CLAIMS VERIFICATION")
    print("=" * 80)

    # Verify claims
    if gunicorn:
        req_sec = gunicorn.get("requests_per_sec", 0)
        print(
            f"Gunicorn: {req_sec:.1f} req/sec (Claim: ~{claims['Gunicorn']['req_sec']})"
        )
        if req_sec >= claims["Gunicorn"]["req_sec"] * 0.8:  # Allow 20% margin
            print("  ✅ Claim VERIFIED")
        else:
            print(
                f"  ❌ Claim NOT VERIFIED (got {req_sec:.1f}, expected ~{claims['Gunicorn']['req_sec']})"
            )
    else:
        print("Gunicorn: No results available")

    if uwsgi:
        req_sec = uwsgi.get("requests_per_sec", 0)
        print(f"uWSGI: {req_sec:.1f} req/sec (Claim: ~{claims['uWSGI']['req_sec']})")
        if req_sec >= claims["uWSGI"]["req_sec"] * 0.8:  # Allow 20% margin
            print("  ✅ Claim VERIFIED")
        else:
            print(
                f"  ❌ Claim NOT VERIFIED (got {req_sec:.1f}, expected ~{claims['uWSGI']['req_sec']})"
            )
    else:
        print("uWSGI: No results available")

    if custom_http1:
        req_sec = custom_http1.get("requests_per_sec", 0)
        print(
            f"Custom WSGI (HTTP/1.1): {req_sec:.1f} req/sec (Claim: ~{claims['Custom WSGI (HTTP/1.1)']['req_sec']})"
        )
        if (
            req_sec >= claims["Custom WSGI (HTTP/1.1)"]["req_sec"] * 0.8
        ):  # Allow 20% margin
            print("  ✅ Claim VERIFIED")
        else:
            print(
                f"  ❌ Claim NOT VERIFIED (got {req_sec:.1f}, expected ~{claims['Custom WSGI (HTTP/1.1)']['req_sec']})"
            )
    else:
        print("Custom WSGI (HTTP/1.1): No results available")

    if custom_http2:
        req_sec = custom_http2.get("requests_per_sec", 0)
        print(
            f"Custom WSGI (HTTP/2): {req_sec:.1f} req/sec (Claim: ~{claims['Custom WSGI (HTTP/2)']['req_sec']})"
        )
        if (
            req_sec >= claims["Custom WSGI (HTTP/2)"]["req_sec"] * 0.8
        ):  # Allow 20% margin
            print("  ✅ Claim VERIFIED")
        else:
            print(
                f"  ❌ Claim NOT VERIFIED (got {req_sec:.1f}, expected ~{claims['Custom WSGI (HTTP/2)']['req_sec']})"
            )
    else:
        print("Custom WSGI (HTTP/2): No results available")

    # Verify relative performance
    print("\nRELATIVE PERFORMANCE CLAIMS")
    print("-" * 80)

    if custom_http1 and gunicorn:
        ratio = custom_http1.get("requests_per_sec", 0) / max(
            gunicorn.get("requests_per_sec", 1), 1
        )
        expected_ratio = (
            claims["Custom WSGI (HTTP/1.1)"]["req_sec"] / claims["Gunicorn"]["req_sec"]
        )
        print(
            f"Custom WSGI (HTTP/1.1) vs Gunicorn: {ratio:.1f}x faster (Expected: ~{expected_ratio:.1f}x)"
        )
        if ratio >= expected_ratio * 0.8:  # Allow 20% margin
            print("  ✅ Claim VERIFIED")
        else:
            print(
                f"  ❌ Claim NOT VERIFIED (got {ratio:.1f}x, expected ~{expected_ratio:.1f}x)"
            )

    if custom_http1 and uwsgi:
        ratio = custom_http1.get("requests_per_sec", 0) / max(
            uwsgi.get("requests_per_sec", 1), 1
        )
        expected_ratio = (
            claims["Custom WSGI (HTTP/1.1)"]["req_sec"] / claims["uWSGI"]["req_sec"]
        )
        print(
            f"Custom WSGI (HTTP/1.1) vs uWSGI: {ratio:.1f}x faster (Expected: ~{expected_ratio:.1f}x)"
        )
        if ratio >= expected_ratio * 0.8:  # Allow 20% margin
            print("  ✅ Claim VERIFIED")
        else:
            print(
                f"  ❌ Claim NOT VERIFIED (got {ratio:.1f}x, expected ~{expected_ratio:.1f}x)"
            )

    if custom_http2 and custom_http1:
        ratio = custom_http2.get("requests_per_sec", 0) / max(
            custom_http1.get("requests_per_sec", 1), 1
        )
        expected_ratio = (
            claims["Custom WSGI (HTTP/2)"]["req_sec"]
            / claims["Custom WSGI (HTTP/1.1)"]["req_sec"]
        )
        print(
            f"HTTP/2 vs HTTP/1.1: {ratio:.1f}x faster (Expected: ~{expected_ratio:.1f}x)"
        )
        if ratio >= expected_ratio * 0.8:  # Allow 20% margin
            print("  ✅ Claim VERIFIED")
        else:
            print(
                f"  ❌ Claim NOT VERIFIED (got {ratio:.1f}x, expected ~{expected_ratio:.1f}x)"
            )

    print("\nNOTE: Performance results depend on hardware, OS, and network conditions.")
    print(
        "      A claim is considered verified if the result is within 20% of the expected value."
    )
    print("=" * 80)


if __name__ == "__main__":
    verify_claims()
