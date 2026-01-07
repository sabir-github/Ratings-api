#!/usr/bin/env python3
"""
Test script for external agent setup (following EXTERNAL_AGENTS_SETUP.md)
This script tests the MCP server HTTP endpoints as an external agent would
"""
import httpx
import json
import asyncio
from typing import Any, Dict, List

class MCPClient:
    """MCP Client for testing external agent functionality"""
    def __init__(self, base_url: str = "http://localhost:8000/api/v1/mcp"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        self.request_id = 0
    
    async def _request(self, method: str, params: dict = None):
        """Make a JSON-RPC request"""
        self.request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self.request_id
        }
        if params:
            payload["params"] = params
        
        response = await self.client.post(
            f"{self.base_url}/protocol",
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    async def get_server_info(self):
        """Get server information (GET endpoint)"""
        response = await self.client.get(f"{self.base_url}/protocol/info")
        response.raise_for_status()
        return response.json()
    
    async def initialize(self):
        """Initialize MCP connection"""
        return await self._request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "cursor-client",
                "version": "1.0.0"
            }
        })
    
    async def list_tools(self):
        """List all available tools"""
        result = await self._request("tools/list")
        tools = result.get("result", {}).get("tools", [])
        return tools
    
    async def call_tool(self, tool_name: str, **kwargs):
        """Call an MCP tool"""
        result = await self._request("tools/call", {
            "name": tool_name,
            "arguments": kwargs
        })
        return result.get("result", {})
    
    async def ping(self):
        """Ping the server"""
        return await self._request("ping")
    
    async def get_status(self):
        """Get server status (GET endpoint)"""
        response = await self.client.get(f"{self.base_url}/status")
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        """Close the client"""
        await self.client.aclose()

async def main():
    """Test all MCP endpoints following EXTERNAL_AGENTS_SETUP.md"""
    print("=" * 70)
    print("External Agent Setup Test (Following EXTERNAL_AGENTS_SETUP.md)")
    print("=" * 70)
    print()
    
    client = MCPClient()
    
    try:
        # Step 1: Get Server Information
        print("Step 1: Get Server Information")
        print("-" * 70)
        try:
            server_info = await client.get_server_info()
            print(f"✓ Server Info Retrieved")
            print(f"  Protocol Version: {server_info.get('protocolVersion')}")
            print(f"  Server Name: {server_info.get('serverInfo', {}).get('name')}")
            print(f"  Server Version: {server_info.get('serverInfo', {}).get('version')}")
            print(f"  Tools Count: {server_info.get('tools', {}).get('count', 0)}")
            print()
        except Exception as e:
            print(f"✗ Error getting server info: {e}")
            print()
        
        # Step 2: Initialize Connection
        print("Step 2: Initialize Connection")
        print("-" * 70)
        try:
            init_result = await client.initialize()
            print(f"✓ Connection Initialized")
            print(f"  Response: {json.dumps(init_result, indent=2)}")
            print()
        except Exception as e:
            print(f"✗ Error initializing: {e}")
            print()
        
        # Step 3: List Available Tools
        print("Step 3: List Available Tools")
        print("-" * 70)
        try:
            tools = await client.list_tools()
            print(f"✓ Tools Retrieved: {len(tools)} tools available")
            print(f"  First 5 tools:")
            for tool in tools[:5]:
                tool_name = tool.get('name', str(tool))
                tool_desc = tool.get('description', 'No description')
                print(f"    - {tool_name}: {tool_desc[:60]}...")
            print()
        except Exception as e:
            print(f"✗ Error listing tools: {e}")
            print()
        
        # Step 4: Call a Tool (get_companies)
        print("Step 4: Call a Tool (get_companies)")
        print("-" * 70)
        try:
            result = await client.call_tool("get_companies", skip=0, limit=5)
            print(f"✓ Tool Called Successfully")
            print(f"  Result type: {type(result)}")
            if isinstance(result, dict):
                content = result.get('content', [])
                if content and len(content) > 0:
                    text_content = content[0].get('text', '')
                    try:
                        data = json.loads(text_content)
                        if isinstance(data, dict) and 'items' in data:
                            companies = data['items']
                            print(f"  Companies returned: {len(companies)}")
                            for company in companies[:3]:
                                print(f"    - {company.get('company_name', 'Unknown')}")
                        else:
                            print(f"  Data: {str(data)[:100]}...")
                    except:
                        print(f"  Response: {text_content[:200]}...")
            print()
        except Exception as e:
            print(f"✗ Error calling tool: {e}")
            print()
        
        # Additional Tests
        print("Additional Tests")
        print("-" * 70)
        
        # Test Ping
        print("Testing ping...")
        try:
            ping_result = await client.ping()
            print(f"✓ Ping successful: {ping_result}")
        except Exception as e:
            print(f"✗ Ping failed: {e}")
        print()
        
        # Test Status Endpoint
        print("Testing status endpoint...")
        try:
            status = await client.get_status()
            print(f"✓ Status: {status}")
        except Exception as e:
            print(f"✗ Status check failed: {e}")
        print()
        
        print("=" * 70)
        print("Test Complete!")
        print("=" * 70)
        
    except Exception as e:
        print(f"✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())

