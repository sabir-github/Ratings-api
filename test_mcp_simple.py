"""Simple test script for MCP external agent setup"""
import requests
import json

base_url = "http://localhost:8000/api/v1/mcp"

print("Testing MCP External Agent Setup")
print("=" * 60)

# Step 1: Get Server Info
print("\n1. Getting server info...")
try:
    r = requests.get(f"{base_url}/protocol/info", timeout=5)
    info = r.json()
    print(f"   [OK] Server: {info.get('serverInfo', {}).get('name')}")
    print(f"   [OK] Tools: {info.get('tools', {}).get('count', 0)}")
except Exception as e:
    print(f"   [ERROR] Error: {e}")
    import traceback
    traceback.print_exc()

# Step 2: Initialize
print("\n2. Initializing connection...")
try:
    r = requests.post(f"{base_url}/protocol", json={
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"}
        },
        "id": 1
    }, timeout=5)
    result = r.json()
    print(f"   [OK] Initialized: {result.get('result', {}).get('serverInfo', {}).get('name')}")
except Exception as e:
    print(f"   [ERROR] Error: {e}")
    import traceback
    traceback.print_exc()

# Step 3: List Tools
print("\n3. Listing tools...")
try:
    r = requests.post(f"{base_url}/protocol", json={
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 2
    }, timeout=10)
    result = r.json()
    if 'error' in result:
        print(f"   [ERROR] Error: {result['error']}")
    else:
        tools = result.get('result', {}).get('tools', [])
        print(f"   [OK] Found {len(tools)} tools")
        if tools:
            print(f"   [OK] First tool: {tools[0].get('name', 'unknown')}")
except Exception as e:
    print(f"   [ERROR] Error: {e}")
    import traceback
    traceback.print_exc()

# Step 4: Call Tool
print("\n4. Calling get_companies tool...")
try:
    r = requests.post(f"{base_url}/protocol", json={
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "get_companies",
            "arguments": {"skip": 0, "limit": 3}
        },
        "id": 3
    }, timeout=10)
    result = r.json()
    if 'error' in result:
        print(f"   [ERROR] Error: {result['error']}")
    else:
        print(f"   [OK] Tool called successfully")
        content = result.get('result', {}).get('content', [])
        if content:
            print(f"   [OK] Response received")
except Exception as e:
    print(f"   [ERROR] Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Test complete!")

