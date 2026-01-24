#!/usr/bin/env python3
"""
Example usage of the Gemini MCP Client

This script demonstrates how to use the Gemini MCP client to:
1. Connect to the MCP server
2. Enable Gemini to use MCP tools
3. Have conversations with Gemini that can interact with the Ratings API
"""

import asyncio
import os
import logging
from gemini_mcp_client import GeminiMCPClient, create_gemini_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def example_basic_usage():
    """Basic example of using the Gemini MCP client."""
    print("=" * 70)
    print("Example 1: Basic Gemini MCP Client Usage")
    print("=" * 70)
    print()
    
    # Get API key from environment or prompt user
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("⚠️  GEMINI_API_KEY not set. Please set it as an environment variable.")
        print("   You can get an API key from: https://makersuite.google.com/app/apikey")
        return
    
    # Create client using context manager
    async with GeminiMCPClient(
        mcp_base_url="http://localhost:8000/api/v1/mcp",
        gemini_api_key=gemini_api_key,
        model_name="gemini-2.0-pro"
    ) as client:
        # Get server info
        print("📡 Getting MCP server information...")
        server_info = await client.get_server_info()
        print(f"   Server: {server_info.get('serverInfo', {}).get('name')}")
        print(f"   Tools available: {server_info.get('tools', {}).get('count', 0)}")
        print()
        
        # List tools
        print("🔧 Listing available tools...")
        tools = await client.list_tools()
        print(f"   Found {len(tools)} tools")
        print(f"   Sample tools:")
        for tool in tools[:5]:
            print(f"     - {tool.get('name')}: {tool.get('description', '')[:60]}...")
        print()
        
        # Get Gemini functions
        print("🤖 Converting tools to Gemini function format...")
        functions = client.get_gemini_functions()
        print(f"   Converted {len(functions)} functions for Gemini")
        print()


async def example_chat_with_tools():
    """Example of chatting with Gemini using MCP tools."""
    print("=" * 70)
    print("Example 2: Chat with Gemini Using MCP Tools")
    print("=" * 70)
    print()
    
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("⚠️  GEMINI_API_KEY not set. Skipping chat example.")
        return
    
    async with GeminiMCPClient(
        mcp_base_url="http://localhost:8000/api/v1/mcp",
        gemini_api_key=gemini_api_key
    ) as client:
        # Example 1: Ask Gemini to fetch companies
        print("💬 Example Query 1: 'Get me all companies'")
        print("-" * 70)
        try:
            response = await client.chat_with_gemini("Get me all companies from the Ratings API")
            print(f"🤖 Gemini Response:\n{response}\n")
        except Exception as e:
            print(f"❌ Error: {e}\n")
        
        # Example 2: Ask Gemini to get a specific company
        print("💬 Example Query 2: 'Get company with ID 100000001'")
        print("-" * 70)
        try:
            response = await client.chat_with_gemini("Get the company with ID 100000001")
            print(f"🤖 Gemini Response:\n{response}\n")
        except Exception as e:
            print(f"❌ Error: {e}\n")
        
        # Example 3: Ask Gemini to create a company
        print("💬 Example Query 3: 'Create a new company called Test Company'")
        print("-" * 70)
        try:
            response = await client.chat_with_gemini(
                "Create a new company with code TC001 and name 'Test Company'"
            )
            print(f"🤖 Gemini Response:\n{response}\n")
        except Exception as e:
            print(f"❌ Error: {e}\n")


async def example_direct_tool_calls():
    """Example of directly calling MCP tools."""
    print("=" * 70)
    print("Example 3: Direct MCP Tool Calls")
    print("=" * 70)
    print()
    
    async with GeminiMCPClient() as client:
        # Directly call a tool
        print("🔧 Calling get_companies tool directly...")
        try:
            result = await client.call_mcp_tool("get_companies", {
                "skip": 0,
                "limit": 5
            })
            print(f"✅ Tool call successful!")
            if isinstance(result, dict) and "items" in result:
                companies = result["items"]
                print(f"   Found {len(companies)} companies:")
                for company in companies:
                    print(f"     - {company.get('company_name')} (ID: {company.get('id')})")
            else:
                print(f"   Result: {result}")
            print()
        except Exception as e:
            print(f"❌ Error: {e}\n")
        
        # Call health check
        print("🔧 Calling health_check tool...")
        try:
            result = await client.call_mcp_tool("health_check", {})
            print(f"✅ Health check result: {result}\n")
        except Exception as e:
            print(f"❌ Error: {e}\n")


async def example_interactive_chat():
    """Interactive chat example with Gemini."""
    print("=" * 70)
    print("Example 4: Interactive Chat with Gemini")
    print("=" * 70)
    print()
    
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("⚠️  GEMINI_API_KEY not set. Skipping interactive chat.")
        return
    
    async with GeminiMCPClient(
        mcp_base_url="http://localhost:8000/api/v1/mcp",
        gemini_api_key=gemini_api_key
    ) as client:
        print("💬 Interactive chat with Gemini (type 'exit' to quit)")
        print("-" * 70)
        print()
        
        conversation_history = []
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if user_input.lower() in ['exit', 'quit', 'q']:
                    print("\n👋 Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                print("🤖 Gemini: ", end="", flush=True)
                response = await client.chat_with_gemini(
                    user_input,
                    conversation_history=conversation_history
                )
                print(response)
                print()
                
                # Update conversation history
                conversation_history.append({
                    "role": "user",
                    "parts": [{"text": user_input}]
                })
                conversation_history.append({
                    "role": "model",
                    "parts": [{"text": response}]
                })
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")


async def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("Gemini MCP Client Examples")
    print("=" * 70)
    print()
    
    # Check if MCP server is running
    try:
        client = GeminiMCPClient()
        await client.initialize()
        await client.get_server_info()
        await client.close()
        print("✅ MCP server is accessible\n")
    except Exception as e:
        print(f"❌ Cannot connect to MCP server: {e}")
        print("   Make sure the Ratings API server is running on http://localhost:8000")
        print()
        return
    
    # Run examples
    try:
        await example_basic_usage()
        print()
        
        await example_direct_tool_calls()
        print()
        
        # Only run chat examples if API key is available
        if os.getenv("GEMINI_API_KEY"):
            await example_chat_with_tools()
            print()
            
            # Uncomment to enable interactive chat
            # await example_interactive_chat()
        else:
            print("💡 Tip: Set GEMINI_API_KEY environment variable to enable chat examples")
            print()
        
    except Exception as e:
        logger.error(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

