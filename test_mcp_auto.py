#!/usr/bin/env python3
"""
Automated test script for MCP server - runs without user prompts
Tests all major MCP endpoints and tools
"""
import sys
import json
try:
    import httpx
    USE_HTTPX = True
except ImportError:
    import requests
    USE_HTTPX = False
from typing import Dict, Any

# Set UTF-8 encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

API_BASE_URL = "http://localhost:8000/api/v1"
MCP_BASE_URL = f"{API_BASE_URL}/mcp"

def print_result(test_name: str, success: bool, details: str = ""):
    """Print test result"""
    import sys
    status = "PASS" if success else "FAIL"
    print(f"{status}: {test_name}", flush=True)
    if details:
        print(f"  {details}", flush=True)
    sys.stdout.flush()

def test_server_info():
    """Test MCP server info endpoint"""
    try:
        if USE_HTTPX:
            response = httpx.get(f"{MCP_BASE_URL}/protocol/info", timeout=10.0)
        else:
            response = requests.get(f"{MCP_BASE_URL}/protocol/info", timeout=10.0)
        if response.status_code == 200:
            data = response.json()
            print_result("Server Info", True, f"Protocol: {data.get('protocol_version', 'N/A')}")
            return True
        else:
            print_result("Server Info", False, f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_result("Server Info", False, str(e))
        return False

def test_list_tools():
    """Test listing MCP tools"""
    try:
        if USE_HTTPX:
            response = httpx.get(f"{MCP_BASE_URL}/tools", timeout=10.0)
        else:
            response = requests.get(f"{MCP_BASE_URL}/tools", timeout=10.0)
        if response.status_code == 200:
            data = response.json()
            tools = data.get('tools', [])
            print_result("List Tools", True, f"Found {len(tools)} tools")
            return len(tools) > 0
        else:
            print_result("List Tools", False, f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_result("List Tools", False, str(e))
        return False

def test_jsonrpc_tools_list():
    """Test JSON-RPC tools/list method"""
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1
        }
        if USE_HTTPX:
            response = httpx.post(f"{MCP_BASE_URL}/protocol", json=payload, timeout=10.0)
        else:
            response = requests.post(f"{MCP_BASE_URL}/protocol", json=payload, timeout=10.0)
        if response.status_code == 200:
            data = response.json()
            if 'result' in data and 'tools' in data['result']:
                tools = data['result']['tools']
                print_result("JSON-RPC tools/list", True, f"Found {len(tools)} tools")
                return len(tools) > 0
            else:
                print_result("JSON-RPC tools/list", False, "No tools in result")
                return False
        else:
            print_result("JSON-RPC tools/list", False, f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_result("JSON-RPC tools/list", False, str(e))
        return False

def test_tool_call(tool_name: str, tool_args: Dict[str, Any] = None):
    """Test calling an MCP tool via JSON-RPC"""
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": tool_args or {}
            },
            "id": 1
        }
        response = httpx.post(f"{MCP_BASE_URL}/protocol", json=payload, timeout=30.0)
        if response.status_code == 200:
            data = response.json()
            if 'result' in data:
                print_result(f"Call {tool_name}", True, "Tool executed successfully")
                return True
            elif 'error' in data:
                error_msg = data['error'].get('message', 'Unknown error')
                print_result(f"Call {tool_name}", False, f"Error: {error_msg}")
                return False
            else:
                print_result(f"Call {tool_name}", False, "Unexpected response format")
                return False
        else:
            print_result(f"Call {tool_name}", False, f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_result(f"Call {tool_name}", False, str(e))
        return False

def main():
    """Run all automated tests"""
    import sys
    sys.stdout.flush()
    sys.stderr.flush()
    print("=" * 60, flush=True)
    print("Automated MCP Server Test Suite", flush=True)
    print("=" * 60, flush=True)
    print(flush=True)
    
    results = []
    
    # Test 1: Server Info
    results.append(("Server Info", test_server_info()))
    print()
    
    # Test 2: List Tools (HTTP endpoint)
    results.append(("List Tools (HTTP)", test_list_tools()))
    print()
    
    # Test 3: List Tools (JSON-RPC)
    results.append(("List Tools (JSON-RPC)", test_jsonrpc_tools_list()))
    print()
    
    # Test 4: Call get_companies
    results.append(("Call get_companies", test_tool_call("get_companies", {"limit": 10})))
    print()
    
    # Test 5: Call get_states
    results.append(("Call get_states", test_tool_call("get_states", {"limit": 10})))
    print()
    
    # Test 6: Call get_ratingtables with filter
    results.append(("Call get_ratingtables", test_tool_call("get_ratingtables", {
        "table_name": "State_Relativities",
        "active": True,
        "limit": 5
    })))
    print()
    
    # Test 7: Call health_check
    results.append(("Call health_check", test_tool_call("health_check")))
    print()
    
    # Summary
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print()
    
    for test_name, result in results:
        status = "✓" if result else "✗"
        print(f"{status} {test_name}")
    
    print()
    if passed == total:
        print("All tests passed!")
        return 0
    else:
        print(f"{total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())

