#!/usr/bin/env python3
"""
Security Headers Verification Script

Verifies that all required security headers are present in API responses.
Run this script with the server running to check security posture.
"""

import sys
from typing import Dict

import httpx


def verify_security_headers(base_url: str = "http://localhost:8000") -> bool:
    """
    Verify security headers on the health endpoint.

    Args:
        base_url: Base URL of the API server

    Returns:
        True if all required headers are present, False otherwise
    """
    required_headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=(), usb=()",
    }

    # HSTS is production-only
    production_headers = {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    }

    try:
        response = httpx.get(f"{base_url}/health", timeout=5.0)
        headers = response.headers

        print(f"Testing {base_url}/health")
        print("=" * 80)

        all_present = True

        # Check required headers
        for header, expected_value in required_headers.items():
            actual_value = headers.get(header)
            if actual_value:
                if expected_value in actual_value:
                    print(f"✅ {header}: {actual_value}")
                else:
                    print(f"⚠️  {header}: Expected '{expected_value}', got '{actual_value}'")
                    all_present = False
            else:
                print(f"❌ {header}: MISSING")
                all_present = False

        # Check production headers (optional in development)
        print("\nProduction-only headers:")
        for header, expected_value in production_headers.items():
            actual_value = headers.get(header)
            if actual_value:
                print(f"✅ {header}: {actual_value}")
            else:
                print(f"ℹ️  {header}: Not present (OK in development)")

        print("=" * 80)

        if all_present:
            print("✅ All required security headers are present!")
            return True
        else:
            print("❌ Some required security headers are missing!")
            return False

    except httpx.ConnectError:
        print(f"❌ Failed to connect to {base_url}")
        print("   Make sure the server is running: uvicorn src.main:app --port 8000")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    success = verify_security_headers(base_url)
    sys.exit(0 if success else 1)
