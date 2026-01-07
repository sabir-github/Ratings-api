#!/usr/bin/env python3
"""
Standalone script to run the MCP server for Ratings API
This allows the MCP server to be run separately from the FastAPI application
Compatible with Cursor IDE and other MCP clients via stdio
"""
import sys
import logging
import asyncio
from app.mcp_server import mcp, MCP_AVAILABLE

# Configure logging to stderr (stdio is used for MCP protocol)
logging.basicConfig(
    level=logging.WARNING,  # Reduce noise for MCP clients
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

async def list_tools():
    """List all available tools (for testing)"""
    if not MCP_AVAILABLE or mcp is None:
        print("ERROR: MCP server is not available.")
        return
    
    try:
        tools = await mcp.get_tools()
        print(f"\nTotal Tools: {len(tools)}\n")
        for tool in tools:
            if isinstance(tool, dict):
                print(f"  - {tool.get('name', 'Unknown')}: {tool.get('description', 'No description')}")
            else:
                print(f"  - {tool}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    if not MCP_AVAILABLE or mcp is None:
        logger.error("fastmcp is not available. Please install it with: pip install fastmcp")
        sys.exit(1)
    
    # Handle command-line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--list-tools":
            # List tools and exit (for testing)
            asyncio.run(list_tools())
            sys.exit(0)
        else:
            logger.error(f"Unknown argument: {sys.argv[1]}")
            logger.info("Usage: python run_mcp_server.py [--list-tools]")
            sys.exit(1)
    
    # Run the MCP server via stdio (for Cursor and other MCP clients)
    # FastMCP.run() handles stdio communication automatically
    # This should be called WITHOUT arguments when used with MCP clients
    try:
        mcp.run()
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"MCP server error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

