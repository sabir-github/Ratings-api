#!/usr/bin/env python3
"""
Script to list all available MCP tools
"""
import asyncio
import json
import sys
from app.mcp_server import mcp, MCP_AVAILABLE

async def list_tools():
    """List all available MCP tools"""
    if not MCP_AVAILABLE or mcp is None:
        print("ERROR: MCP server is not available. Install fastmcp to enable.")
        sys.exit(1)
    
    try:
        # Get tools from MCP server
        tools_list = await mcp.get_tools()
        
        print(f"\n{'='*60}")
        print(f"MCP Server: {mcp.name}")
        print(f"Total Tools: {len(tools_list)}")
        print(f"{'='*60}\n")
        
        # Group tools by category
        categories = {
            "Companies": [],
            "LOBs": [],
            "Products": [],
            "States": [],
            "Contexts": [],
            "Rating Tables": [],
            "Algorithms": [],
            "Rating Manuals": [],
            "Rating Plans": [],
            "Health": [],
            "Other": []
        }
        
        for tool in tools_list:
            if isinstance(tool, dict):
                tool_name = tool.get('name', '')
                tool_desc = tool.get('description', '')
                
                # Categorize tools
                if 'company' in tool_name.lower():
                    categories["Companies"].append((tool_name, tool_desc))
                elif 'lob' in tool_name.lower():
                    categories["LOBs"].append((tool_name, tool_desc))
                elif 'product' in tool_name.lower():
                    categories["Products"].append((tool_name, tool_desc))
                elif 'state' in tool_name.lower():
                    categories["States"].append((tool_name, tool_desc))
                elif 'context' in tool_name.lower():
                    categories["Contexts"].append((tool_name, tool_desc))
                elif 'ratingtable' in tool_name.lower() or 'rating_table' in tool_name.lower():
                    categories["Rating Tables"].append((tool_name, tool_desc))
                elif 'algorithm' in tool_name.lower():
                    categories["Algorithms"].append((tool_name, tool_desc))
                elif 'ratingmanual' in tool_name.lower() or 'rating_manual' in tool_name.lower():
                    categories["Rating Manuals"].append((tool_name, tool_desc))
                elif 'ratingplan' in tool_name.lower() or 'rating_plan' in tool_name.lower():
                    categories["Rating Plans"].append((tool_name, tool_desc))
                elif 'health' in tool_name.lower():
                    categories["Health"].append((tool_name, tool_desc))
                else:
                    categories["Other"].append((tool_name, tool_desc))
        
        # Print categorized tools
        for category, tools in categories.items():
            if tools:
                print(f"\n{category}:")
                print("-" * 60)
                for tool_name, tool_desc in sorted(tools):
                    print(f"  • {tool_name}")
                    if tool_desc:
                        print(f"    {tool_desc[:80]}...")
        
        # Also print as JSON
        print(f"\n{'='*60}")
        print("JSON Format:")
        print(f"{'='*60}\n")
        tools_json = [
            {
                "name": tool.get('name', '') if isinstance(tool, dict) else str(tool),
                "description": tool.get('description', '') if isinstance(tool, dict) else '',
                "inputSchema": tool.get('inputSchema', {}) if isinstance(tool, dict) else {}
            }
            for tool in tools_list
        ]
        print(json.dumps(tools_json, indent=2))
        
    except Exception as e:
        print(f"ERROR: Failed to list tools: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(list_tools())







