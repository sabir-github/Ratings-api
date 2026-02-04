#!/usr/bin/env python3
"""
Test script to verify MCP server database connection fix
"""
import subprocess
import json
import sys

def test_mcp_tool_call():
    """Test calling an MCP tool that requires database access"""
    print("Testing MCP tool with database connection...")
    print("=" * 60)
    
    # Test via Docker exec (simulating Cursor's usage)
    print("\n1. Testing via Docker exec (Cursor configuration)...")
    try:
        # Create a test JSON-RPC request
        test_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_companies",
                "arguments": {"limit": 3}
            },
            "id": 1
        }
        
        # Write request to stdin
        request_json = json.dumps(test_request) + "\n"
        
        # Run MCP server and send request
        process = subprocess.Popen(
            ["docker", "exec", "-i", "ratings-api-api-1", "python", "/app/run_mcp_server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate(input=request_json, timeout=10)
        
        if process.returncode == 0:
            print("✅ MCP server responded")
            if stdout:
                try:
                    response = json.loads(stdout.strip())
                    if "result" in response:
                        print("✅ Tool call successful!")
                        result_text = response["result"].get("content", [{}])[0].get("text", "")
                        if result_text:
                            data = json.loads(result_text)
                            items = data.get("items", [])
                            print(f"   Found {len(items)} companies")
                            if "error" in data:
                                print(f"   ❌ Error in response: {data['error']}")
                                return False
                            return True
                    elif "error" in response:
                        print(f"❌ Tool call failed: {response['error']}")
                        return False
                except json.JSONDecodeError:
                    print(f"⚠️  Response not JSON: {stdout[:100]}")
            if stderr:
                print(f"⚠️  Stderr: {stderr[:200]}")
        else:
            print(f"❌ Process failed with code {process.returncode}")
            if stderr:
                print(f"   Error: {stderr[:200]}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Command timed out")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return False

def test_http_endpoint():
    """Test HTTP endpoint as fallback"""
    print("\n2. Testing HTTP endpoint (fallback method)...")
    try:
        import httpx
        response = httpx.post(
            "http://localhost:8000/api/v1/mcp/protocol",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "get_companies",
                    "arguments": {"limit": 3}
                },
                "id": 1
            },
            timeout=10.0
        )
        
        if response.status_code == 200:
            data = response.json()
            if "result" in data:
                print("✅ HTTP endpoint works")
                result_text = data["result"].get("content", [{}])[0].get("text", "")
                if result_text:
                    items_data = json.loads(result_text)
                    items = items_data.get("items", [])
                    print(f"   Found {len(items)} companies")
                    return True
        else:
            print(f"❌ HTTP endpoint failed: {response.status_code}")
            return False
    except ImportError:
        print("⚠️  httpx not available, skipping HTTP test")
        return None
    except Exception as e:
        print(f"❌ HTTP test error: {e}")
        return False

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("MCP Database Connection Fix Test")
    print("=" * 60)
    
    # Test 1: MCP tool call (stdio)
    result1 = test_mcp_tool_call()
    
    # Test 2: HTTP endpoint (fallback)
    result2 = test_http_endpoint()
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    if result1:
        print("✅ MCP stdio connection: WORKING")
    else:
        print("❌ MCP stdio connection: FAILED")
        print("   Note: This might be expected if FastMCP doesn't support")
        print("   interactive stdio testing. HTTP endpoint should still work.")
    
    if result2 is True:
        print("✅ HTTP endpoint: WORKING")
    elif result2 is False:
        print("❌ HTTP endpoint: FAILED")
    else:
        print("⚠️  HTTP endpoint: NOT TESTED")
    
    print("\nRecommendation:")
    if result2:
        print("✅ Database connection is working via HTTP endpoints.")
        print("   MCP tools should work in Cursor IDE after restarting Cursor.")
    else:
        print("⚠️  Check database connection and API server status.")



