#!/usr/bin/env python3
"""
Simple test script for K7BAT uConsole Status API
"""

import requests
import json
import time
import sys

API_URL = "http://localhost:8080"

def test_endpoint(name, url, method='GET', data=None):
    """Test an API endpoint."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"URL: {url}")
    
    try:
        if method == 'GET':
            response = requests.get(url, timeout=5)
        elif method == 'POST':
            response = requests.post(url, json=data, timeout=5)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response:")
        print(json.dumps(response.json(), indent=2))
        return True
        
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to API server")
        print("Make sure the API is running: python3 status_api.py")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def main():
    """Run all tests."""
    print("K7BAT uConsole Status API Test Suite")
    print("="*60)
    
    # Test health check first (quick connectivity test)
    if not test_endpoint("Health Check", f"{API_URL}/api/health"):
        print("\n" + "="*60)
        print("API server is not running!")
        print("Start it with: python3 status_api.py")
        sys.exit(1)
    
    # Test version
    test_endpoint("Version Info", f"{API_URL}/api/version")
    
    # Test full status
    test_endpoint("Full Status", f"{API_URL}/api/status")
    
    # Test system endpoint
    test_endpoint("System Info", f"{API_URL}/api/status/system")
    
    # Test Wi-Fi endpoint
    test_endpoint("Wi-Fi Status", f"{API_URL}/api/status/wifi")
    
    # Test GPS endpoint
    test_endpoint("GPS Status", f"{API_URL}/api/status/gps")
    
    # Test POST command
    print(f"\n{'='*60}")
    print("Testing: POST Command (ping)")
    try:
        response = requests.post(
            f"{API_URL}/api/arduino/ping",
            json={"device": "test-arduino"},
            timeout=5
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response:")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"ERROR: {e}")
    
    # Test POST data
    print(f"\n{'='*60}")
    print("Testing: POST Data")
    try:
        test_data = {
            "gps": {
                "status": "3d_fix",
                "latitude": 47.6062,
                "longitude": -122.3321
            }
        }
        response = requests.post(
            f"{API_URL}/api/data",
            json=test_data,
            timeout=5
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response:")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"ERROR: {e}")
    
    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60)

if __name__ == "__main__":
    main()
