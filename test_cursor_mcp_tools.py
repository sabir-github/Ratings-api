#!/usr/bin/env python3
"""
Test script to verify MCP tools configured in Cursor IDE
Tests both Docker and local configurations
"""
import subprocess
import json
import sys
import os

def test_docker_config():
    """Test Docker-based MCP server configuration"""
    print("=" * 60)
    print("Testing Docker Configuration (mcp.json)")
    print("=" * 60)
    
    try:
        # Check if container is running
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=ratings-api-api-1", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if "ratings-api-api-1" not in result.stdout:
            print("❌ Docker container 'ratings-api-api-1' is not running")
            return False
        
        print("✅ Docker container is running")
        
        # Test listing tools via Docker exec
        print("\nTesting tool listing via Docker exec...")
        result = subprocess.run(
            ["docker", "exec", "-i", "ratings-api-api-1", "python", "/app/run_mcp_server.py", "--list-tools"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print("✅ Docker MCP server responds correctly")
            if "Total Tools:" in result.stdout:
                print(f"   {result.stdout.split('Total Tools:')[1].split()[0]} tools found")
            return True
        else:
            print(f"❌ Docker MCP server error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Docker command timed out")
        return False
    except FileNotFoundError:
        print("❌ Docker command not found")
        return False
    except Exception as e:
        print(f"❌ Error testing Docker config: {e}")
        return False

def test_local_config():
    """Test local Python MCP server configuration"""
    print("\n" + "=" * 60)
    print("Testing Local Configuration (mcp.json.local)")
    print("=" * 60)
    
    try:
        # Check if run_mcp_server.py exists
        if not os.path.exists("run_mcp_server.py"):
            print("❌ run_mcp_server.py not found")
            return False
        
        print("✅ run_mcp_server.py found")
        
        # Test listing tools locally
        print("\nTesting tool listing locally...")
        env = os.environ.copy()
        env.update({
            "API_URL": "http://localhost:8000",
            "MONGODB_URL": "mongodb://admin:password@localhost:37017/?authSource=admin",
            "MONGODB_DB_NAME": "ratings_db"
        })
        
        result = subprocess.run(
            [sys.executable, "run_mcp_server.py", "--list-tools"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env
        )
        
        if result.returncode == 0:
            print("✅ Local MCP server responds correctly")
            if "Total Tools:" in result.stdout:
                print(f"   {result.stdout.split('Total Tools:')[1].split()[0]} tools found")
            return True
        else:
            print(f"❌ Local MCP server error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Local command timed out")
        return False
    except Exception as e:
        print(f"❌ Error testing local config: {e}")
        return False

def test_http_endpoints():
    """Test HTTP endpoints that Cursor might use"""
    print("\n" + "=" * 60)
    print("Testing HTTP Endpoints")
    print("=" * 60)
    
    try:
        import httpx
    except ImportError:
        try:
            import requests
            USE_HTTPX = False
        except ImportError:
            print("❌ Neither httpx nor requests is installed")
            print("   Install with: pip install httpx requests")
            return False
    else:
        USE_HTTPX = True
    
    base_url = "http://localhost:8000/api/v1/mcp"
    
    # Test 1: List tools
    print("\n1. Testing GET /mcp/tools...")
    try:
        if USE_HTTPX:
            response = httpx.get(f"{base_url}/tools", timeout=5.0)
        else:
            response = requests.get(f"{base_url}/tools", timeout=5.0)
        
        if response.status_code == 200:
            data = response.json()
            tool_count = len(data.get("tools", []))
            print(f"   ✅ Found {tool_count} tools")
        else:
            print(f"   ❌ Status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Test 2: Server info
    print("\n2. Testing GET /mcp/protocol/info...")
    try:
        if USE_HTTPX:
            response = httpx.get(f"{base_url}/protocol/info", timeout=5.0)
        else:
            response = requests.get(f"{base_url}/protocol/info", timeout=5.0)
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Server: {data.get('serverInfo', {}).get('name', 'Unknown')}")
        else:
            print(f"   ❌ Status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Test 3: Call a tool via JSON-RPC
    print("\n3. Testing POST /mcp/protocol (tools/call)...")
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_companies",
                "arguments": {"limit": 2}
            },
            "id": 1
        }
        
        if USE_HTTPX:
            response = httpx.post(f"{base_url}/protocol", json=payload, timeout=10.0)
        else:
            response = requests.post(f"{base_url}/protocol", json=payload, timeout=10.0)
        
        if response.status_code == 200:
            data = response.json()
            if "result" in data:
                print("   ✅ Tool call successful")
                return True
            elif "error" in data:
                print(f"   ❌ Tool error: {data['error']}")
                return False
        else:
            print(f"   ❌ Status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("Cursor MCP Tools Test Suite")
    print("=" * 60)
    print("\nThis script tests the MCP server configurations")
    print("that would be used by Cursor IDE.\n")
    
    results = []
    
    # Test Docker config
    results.append(("Docker Configuration", test_docker_config()))
    
    # Test local config
    results.append(("Local Configuration", test_local_config()))
    
    # Test HTTP endpoints
    results.append(("HTTP Endpoints", test_http_endpoints()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ All tests passed! MCP tools are ready for Cursor IDE.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())



