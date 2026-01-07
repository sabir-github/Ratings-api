"""
MCP Server API endpoints
Exposes MCP tools as HTTP API endpoints for easy access
Supports both REST API and MCP protocol (HTTP/SSE) for external agents
"""
from fastapi import APIRouter, HTTPException, Query, Body, status, Request
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Any, Dict, List, Optional
from app.mcp_server import mcp, MCP_AVAILABLE, call_api, TOOL_REGISTRY
import importlib
import logging
import json
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/tools")
async def list_mcp_tools():
    """List all available MCP tools"""
    if not MCP_AVAILABLE or mcp is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP server is not available. Install fastmcp to enable."
        )
    
    try:
        # Get list of tools from MCP server
        tools = []
        tool_details = []
        
        # Try multiple methods to get tools, prioritizing direct access
        # Check _tools attribute first (FastMCP stores tools here)
        if hasattr(mcp, '_tools'):
            tools_dict = mcp._tools
            if tools_dict:
                # _tools might be a dict or other collection
                if isinstance(tools_dict, dict) and len(tools_dict) > 0:
                    tools = list(tools_dict.keys())
                    # Get full tool details
                    for tool_name in tools:
                        tool_func = tools_dict.get(tool_name)
                        tool_info = {"name": tool_name}
                        # Try to get description and schema from the function
                        if tool_func and hasattr(tool_func, '__doc__'):
                            tool_info["description"] = (tool_func.__doc__ or "").strip()
                        if tool_func and hasattr(tool_func, '__annotations__'):
                            annotations = tool_func.__annotations__.copy()
                            annotations.pop('return', None)  # Remove return type
                            tool_info["inputSchema"] = {
                                "type": "object",
                                "properties": {k: {"type": "string"} for k in annotations.keys()}
                            }
                        tool_details.append(tool_info)
                elif hasattr(tools_dict, '__len__') and len(tools_dict) == 0:
                    # Empty dict, log for debugging
                    logger.debug("mcp._tools is empty")
        elif hasattr(mcp, 'get_tools'):
            # FastMCP has get_tools() method that returns tool definitions (async)
            try:
                tools_list = await mcp.get_tools()
                if isinstance(tools_list, list) and tools_list:
                    for tool in tools_list:
                        if isinstance(tool, dict):
                            tool_name = tool.get('name', '')
                            tools.append(tool_name)
                            tool_details.append({
                                "name": tool_name,
                                "description": tool.get('description', ''),
                                "inputSchema": tool.get('inputSchema', {})
                            })
                        else:
                            tools.append(str(tool))
                            tool_details.append({"name": str(tool)})
            except Exception as e:
                logger.warning(f"Error calling mcp.get_tools(): {e}")
        elif hasattr(mcp, 'list_tools'):
            # Check if list_tools is async
            if hasattr(mcp.list_tools, '__call__'):
                try:
                    import inspect
                    if inspect.iscoroutinefunction(mcp.list_tools):
                        tools = await mcp.list_tools()
                    else:
                        tools = mcp.list_tools()
                except:
                    tools = mcp.list_tools()
            else:
                tools = mcp.list_tools()
            tool_details = [{"name": tool} for tool in tools]
        elif hasattr(mcp, 'tools'):
            # Try to get tools from the internal structure
            if isinstance(mcp.tools, dict):
                tools = list(mcp.tools.keys())
                tool_details = [{"name": tool} for tool in tools]
            elif isinstance(mcp.tools, list):
                tools = mcp.tools
                tool_details = [{"name": tool} for tool in tools]
        
        # Fallback: If no tools found, return known tool names
        # FastMCP might not expose tools until server runs, so we provide a fallback list
        if not tools:
            logger.warning("No tools found via standard methods. Using fallback list of known tools.")
            # Known tools from mcp_server.py (46 tools registered)
            known_tools = [
                "get_companies", "get_company", "create_company", "update_company", "delete_company",
                "get_lobs", "get_lob", "create_lob", "update_lob", "delete_lob",
                "get_products", "get_product", "create_product", "update_product", "delete_product",
                "get_states", "get_state", "create_state", "update_state", "delete_state",
                "get_contexts", "get_context", "create_context", "update_context", "delete_context",
                "get_ratingtables", "get_ratingtable", "create_ratingtable", "update_ratingtable", "delete_ratingtable",
                "get_algorithms", "get_algorithm", "create_algorithm", "update_algorithm", "delete_algorithm",
                "get_ratingmanuals", "get_ratingmanual", "create_ratingmanual", "update_ratingmanual", "delete_ratingmanual",
                "get_ratingplans", "get_ratingplan", "create_ratingplan", "update_ratingplan", "delete_ratingplan",
                "health_check"
            ]
            tools = known_tools
            tool_details = [{"name": tool, "description": f"MCP tool: {tool}"} for tool in tools]
        
        return {
            "tools": tools,
            "tool_details": tool_details,
            "count": len(tools)
        }
    except Exception as e:
        logger.error(f"Error listing MCP tools: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tools: {str(e)}"
        )

@router.post("/tools/{tool_name}/call")
async def call_mcp_tool(
    tool_name: str,
    parameters: Dict[str, Any] = Body(...)
):
    """Call an MCP tool by name with parameters"""
    if not MCP_AVAILABLE or mcp is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP server is not available. Install fastmcp to enable."
        )
    
    try:
        # Get the tool function
        if hasattr(mcp, '_tools') and tool_name in mcp._tools:
            tool_func = mcp._tools[tool_name]
            # Call the tool function with parameters
            if hasattr(tool_func, '__call__'):
                result = await tool_func(**parameters)
                return {"tool": tool_name, "result": result}
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Tool {tool_name} is not callable"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool {tool_name} not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calling MCP tool {tool_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to call tool: {str(e)}"
        )

@router.get("/status")
async def mcp_status():
    """Get MCP server status"""
    status_info = {
        "available": MCP_AVAILABLE,
        "initialized": mcp is not None,
        "server_name": mcp.name if (MCP_AVAILABLE and mcp is not None) else None,
        "status": "running" if (MCP_AVAILABLE and mcp is not None) else "not_available"
    }
    
    # Return appropriate HTTP status code
    if MCP_AVAILABLE and mcp is not None:
        return JSONResponse(
            content=status_info,
            status_code=status.HTTP_200_OK
        )
    else:
        return JSONResponse(
            content=status_info,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )

# Direct API endpoints that mirror MCP tools for easier HTTP access
# These endpoints call the underlying API directly

@router.get("/api/companies")
async def mcp_get_companies(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active: Optional[bool] = Query(None),
    company_name: Optional[str] = Query(None)
):
    """Get companies via MCP API"""
    params = {"skip": skip, "limit": limit}
    if active is not None:
        params["active"] = active
    if company_name:
        params["company_name"] = company_name
    return await call_api("GET", "/companies", params=params)

@router.get("/api/companies/{company_id}")
async def mcp_get_company(
    company_id: int
):
    """Get a company by ID via MCP API"""
    return await call_api("GET", f"/companies/{company_id}")

@router.post("/api/companies")
async def mcp_create_company(
    company_data: Dict[str, Any] = Body(...)
):
    """Create a company via MCP API"""
    return await call_api("POST", "/companies", json=company_data)

@router.get("/api/ratingtables")
async def mcp_get_ratingtables(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active: Optional[bool] = Query(None),
    table_name: Optional[str] = Query(None),
    company_id: Optional[int] = Query(None)
):
    """Get rating tables via MCP API"""
    params = {"skip": skip, "limit": limit}
    if active is not None:
        params["active"] = active
    if table_name:
        params["table_name"] = table_name
    if company_id is not None:
        params["company_id"] = company_id
    return await call_api("GET", "/ratingtables", params=params)

@router.get("/api/algorithms")
async def mcp_get_algorithms(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active: Optional[bool] = Query(None),
    algorithm_name: Optional[str] = Query(None),
    company_id: Optional[int] = Query(None)
):
    """Get algorithms via MCP API"""
    params = {"skip": skip, "limit": limit}
    if active is not None:
        params["active"] = active
    if algorithm_name:
        params["algorithm_name"] = algorithm_name
    if company_id is not None:
        params["company_id"] = company_id
    return await call_api("GET", "/algorithms", params=params)

@router.get("/api/ratingmanuals")
async def mcp_get_ratingmanuals(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active: Optional[bool] = Query(None),
    manual_name: Optional[str] = Query(None),
    company_id: Optional[int] = Query(None),
    effective_date: Optional[str] = Query(None)
):
    """Get rating manuals via MCP API"""
    params = {"skip": skip, "limit": limit}
    if active is not None:
        params["active"] = active
    if manual_name:
        params["manual_name"] = manual_name
    if company_id is not None:
        params["company_id"] = company_id
    if effective_date:
        params["effective_date"] = effective_date
    return await call_api("GET", "/ratingmanuals", params=params)

@router.get("/api/ratingplans")
async def mcp_get_ratingplans(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active: Optional[bool] = Query(None),
    plan_name: Optional[str] = Query(None),
    company_id: Optional[int] = Query(None),
    effective_date: Optional[str] = Query(None)
):
    """Get rating plans via MCP API"""
    params = {"skip": skip, "limit": limit}
    if active is not None:
        params["active"] = active
    if plan_name:
        params["plan_name"] = plan_name
    if company_id is not None:
        params["company_id"] = company_id
    if effective_date:
        params["effective_date"] = effective_date
    return await call_api("GET", "/ratingplans", params=params)

@router.get("/api/health")
async def mcp_health_check():
    """Health check via MCP API"""
    return await call_api("GET", "/health")

# ============================================================================
# MCP Protocol HTTP/SSE Endpoints for External Agents (Gemini, etc.)
# ============================================================================

@router.post("/protocol")
async def mcp_protocol(request: Request):
    """
    MCP Protocol HTTP endpoint for external agents
    Handles JSON-RPC requests following MCP specification
    Compatible with Gemini and other MCP clients
    """
    if not MCP_AVAILABLE or mcp is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP server is not available. Install fastmcp to enable."
        )
    
    try:
        # Parse JSON-RPC request
        body = await request.json()
        
        # Extract JSON-RPC fields
        jsonrpc = body.get("jsonrpc", "2.0")
        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")
        
        if not method:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32600,
                        "message": "Invalid Request",
                        "data": "Missing 'method' field"
                    },
                    "id": request_id
                }
            )
        
        # Handle MCP protocol methods
        if method == "tools/list":
            # List all available tools - use same logic as /tools endpoint
            serialized_tools = []
            
            # ALWAYS use _tools dict first (most reliable, avoids Tool object serialization)
            if hasattr(mcp, '_tools') and isinstance(mcp._tools, dict):
                if len(mcp._tools) > 0:
                    # Use _tools dict directly (most reliable)
                    for tool_name, tool_func in mcp._tools.items():
                        tool_dict = {"name": tool_name}
                        if tool_func and hasattr(tool_func, '__doc__'):
                            tool_dict["description"] = (tool_func.__doc__ or "").strip()
                        if tool_func and hasattr(tool_func, '__annotations__'):
                            annotations = tool_func.__annotations__.copy()
                            annotations.pop('return', None)
                            tool_dict["inputSchema"] = {
                                "type": "object",
                                "properties": {k: {"type": "string"} for k in annotations.keys()}
                            }
                        serialized_tools.append(tool_dict)
                else:
                    # Empty dict - use fallback
                    logger.debug("mcp._tools is empty, using fallback")
            else:
                # _tools not available - use fallback immediately (don't call get_tools() to avoid Tool object issues)
                logger.debug("mcp._tools not available, using fallback")
            
            # Fallback: If no tools found, use known tool list
            if not serialized_tools:
                known_tools = [
                    "get_companies", "get_company", "create_company", "update_company", "delete_company",
                    "get_lobs", "get_lob", "create_lob", "update_lob", "delete_lob",
                    "get_products", "get_product", "create_product", "update_product", "delete_product",
                    "get_states", "get_state", "create_state", "update_state", "delete_state",
                    "get_contexts", "get_context", "create_context", "update_context", "delete_context",
                    "get_ratingtables", "get_ratingtable", "create_ratingtable", "update_ratingtable", "delete_ratingtable",
                    "get_algorithms", "get_algorithm", "create_algorithm", "update_algorithm", "delete_algorithm",
                    "get_ratingmanuals", "get_ratingmanual", "create_ratingmanual", "update_ratingmanual", "delete_ratingmanual",
                    "get_ratingplans", "get_ratingplan", "create_ratingplan", "update_ratingplan", "delete_ratingplan",
                    "health_check"
                ]
                serialized_tools = [{"name": tool, "description": f"MCP tool: {tool}"} for tool in known_tools]
            
            return JSONResponse(content={
                "jsonrpc": jsonrpc,
                "result": {
                    "tools": serialized_tools
                },
                "id": request_id
            })
        
        elif method == "tools/call":
            # Call a tool
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            if not tool_name:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "jsonrpc": jsonrpc,
                        "error": {
                            "code": -32602,
                            "message": "Invalid params",
                            "data": "Missing 'name' in params"
                        },
                        "id": request_id
                    }
                )
            
            # Get the tool function and call it
            # Try multiple methods to find and call the tool
            tool_func = None
            
            # Method 1: Check TOOL_REGISTRY (most reliable for HTTP access)
            if tool_name in TOOL_REGISTRY:
                tool_func = TOOL_REGISTRY[tool_name]
            
            # Method 2: Check _tools dict (most direct)
            if not tool_func and hasattr(mcp, '_tools') and isinstance(mcp._tools, dict):
                tool_func = mcp._tools.get(tool_name)
            
            # Method 3: Try FastMCP's internal tool registry
            if not tool_func and hasattr(mcp, 'tools') and isinstance(mcp.tools, dict):
                tool_func = mcp.tools.get(tool_name)
            
            # Method 4: Try to get from registered tools via get_tools
            if not tool_func:
                try:
                    tools_list = await mcp.get_tools()
                    if isinstance(tools_list, list):
                        for tool in tools_list:
                            tool_name_from_list = tool.get('name') if isinstance(tool, dict) else getattr(tool, 'name', None)
                            if tool_name_from_list == tool_name:
                                # Found the tool, now get the function
                                if hasattr(mcp, '_tools') and isinstance(mcp._tools, dict):
                                    tool_func = mcp._tools.get(tool_name)
                                break
                except Exception as e:
                    logger.debug(f"Could not get tools list: {e}")
            
            # Method 4: Fallback - import tool function directly from mcp_server module
            # FastMCP tools are registered as functions in the module namespace
            if not tool_func:
                try:
                    import app.mcp_server as mcp_server_module
                    # Try to get the function from the module's namespace
                    # The decorated functions are still available in the module
                    tool_func = getattr(mcp_server_module, tool_name, None)
                    # Verify it's callable and is a coroutine function
                    if tool_func:
                        import inspect
                        if not (inspect.iscoroutinefunction(tool_func) or callable(tool_func)):
                            tool_func = None
                        logger.debug(f"Found tool {tool_name} in mcp_server module: {tool_func is not None}")
                except Exception as e:
                    logger.debug(f"Could not import tool from mcp_server: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
            
            # Method 5: Fallback - try calling via FastMCP's call_tool if available
            if not tool_func and hasattr(mcp, 'call_tool'):
                try:
                    result = await mcp.call_tool(tool_name, tool_args)
                    return JSONResponse(content={
                        "jsonrpc": jsonrpc,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(result, default=str)
                                }
                            ]
                        },
                        "id": request_id
                    })
                except Exception as e:
                    logger.error(f"Error calling tool via call_tool: {e}")
            
            # If we found the tool function, call it
            if tool_func and hasattr(tool_func, '__call__'):
                try:
                    result = await tool_func(**tool_args)
                    return JSONResponse(content={
                        "jsonrpc": jsonrpc,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(result, default=str)
                                }
                            ]
                        },
                        "id": request_id
                    })
                except Exception as e:
                    logger.error(f"Error calling tool {tool_name}: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    return JSONResponse(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        content={
                            "jsonrpc": jsonrpc,
                            "error": {
                                "code": -32000,
                                "message": "Server error",
                                "data": str(e)
                            },
                            "id": request_id
                        }
                    )
            else:
                # Tool not found - log available tools for debugging
                available_tools = []
                if hasattr(mcp, '_tools') and isinstance(mcp._tools, dict):
                    available_tools = list(mcp._tools.keys())
                logger.warning(f"Tool '{tool_name}' not found. Available tools: {available_tools[:10]}")
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={
                        "jsonrpc": jsonrpc,
                        "error": {
                            "code": -32601,
                            "message": "Method not found",
                            "data": f"Tool '{tool_name}' not found. Available tools: {len(available_tools)}"
                        },
                        "id": request_id
                    }
                )
        
        elif method == "initialize":
            # Initialize MCP connection
            return JSONResponse(content={
                "jsonrpc": jsonrpc,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": mcp.name if hasattr(mcp, 'name') else "Ratings API MCP Server",
                        "version": "1.0.0"
                    }
                },
                "id": request_id
            })
        
        elif method == "ping":
            # Health check
            return JSONResponse(content={
                "jsonrpc": jsonrpc,
                "result": {},
                "id": request_id
            })
        
        else:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "jsonrpc": jsonrpc,
                    "error": {
                        "code": -32601,
                        "message": "Method not found",
                        "data": f"Unknown method: {method}"
                    },
                    "id": request_id
                }
            )
    
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "jsonrpc": "2.0",
                "error": {
                    "code": -32700,
                    "message": "Parse error"
                },
                "id": None
            }
        )
    except Exception as e:
        logger.error(f"Error in MCP protocol endpoint: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "jsonrpc": "2.0",
                "error": {
                    "code": -32000,
                    "message": "Server error",
                    "data": str(e)
                },
                "id": None
            }
        )

@router.get("/protocol/sse")
async def mcp_protocol_sse(request: Request):
    """
    MCP Protocol Server-Sent Events (SSE) endpoint
    Provides streaming MCP protocol support for real-time communication
    Compatible with MCP clients that support SSE transport
    """
    if not MCP_AVAILABLE or mcp is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP server is not available. Install fastmcp to enable."
        )
    
    async def event_generator():
        """Generate SSE events for MCP protocol"""
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connection', 'status': 'connected'})}\n\n"
            
            # Keep connection alive and handle incoming requests
            # Note: In a real implementation, you'd parse incoming SSE messages
            # For now, this provides the SSE endpoint structure
            while True:
                await asyncio.sleep(30)  # Keep-alive ping
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"
        
        except asyncio.CancelledError:
            logger.info("SSE connection closed")
        except Exception as e:
            logger.error(f"Error in SSE stream: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.get("/protocol/info")
async def mcp_protocol_info():
    """
    Get MCP server information and capabilities
    Useful for external agents to discover server capabilities
    """
    if not MCP_AVAILABLE or mcp is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP server is not available. Install fastmcp to enable."
        )
    
    try:
        # Get tools using the exact same pattern as /tools endpoint
        tools = []
        tool_details = []
        
        if hasattr(mcp, 'get_tools'):
            # FastMCP has get_tools() method that returns tool definitions (async)
            tools_list = await mcp.get_tools()
            if isinstance(tools_list, list):
                for tool in tools_list:
                    if isinstance(tool, dict):
                        tool_name = tool.get('name', '')
                        tools.append(tool_name)
                        tool_details.append({
                            "name": tool_name,
                            "description": tool.get('description', ''),
                            "inputSchema": tool.get('inputSchema', {})
                        })
                    else:
                        tools.append(str(tool))
                        tool_details.append({"name": str(tool)})
        elif hasattr(mcp, 'list_tools'):
            # Check if list_tools is async
            if hasattr(mcp.list_tools, '__call__'):
                try:
                    import inspect
                    if inspect.iscoroutinefunction(mcp.list_tools):
                        tools = await mcp.list_tools()
                    else:
                        tools = mcp.list_tools()
                except:
                    tools = mcp.list_tools()
            else:
                tools = mcp.list_tools()
            tool_details = [{"name": tool} for tool in tools]
        elif hasattr(mcp, '_tools'):
            tools_dict = mcp._tools
            if tools_dict and isinstance(tools_dict, dict) and len(tools_dict) > 0:
                tools = list(tools_dict.keys())
                for tool_name in tools:
                    tool_func = tools_dict.get(tool_name)
                    tool_info = {
                        "name": tool_name,
                        "description": (tool_func.__doc__ if tool_func and hasattr(tool_func, '__doc__') else "").strip()
                    }
                    if tool_func and hasattr(tool_func, '__annotations__'):
                        annotations = tool_func.__annotations__.copy()
                        annotations.pop('return', None)
                        tool_info["inputSchema"] = {
                            "type": "object",
                            "properties": {k: {"type": "string"} for k in annotations.keys()}
                        }
                    tool_details.append(tool_info)
        elif hasattr(mcp, 'tools'):
            # Try to get tools from the internal structure
            if isinstance(mcp.tools, dict):
                tools = list(mcp.tools.keys())
                tool_details = [{"name": tool} for tool in tools]
            elif isinstance(mcp.tools, list):
                tools = mcp.tools
                tool_details = [{"name": tool} for tool in tools]
        
        # Fallback: If no tools found, use known tool names (same as /tools endpoint)
        if not tools:
            logger.warning("No tools found via standard methods. Using fallback list of known tools.")
            known_tools = [
                "get_companies", "get_company", "create_company", "update_company", "delete_company",
                "get_lobs", "get_lob", "create_lob", "update_lob", "delete_lob",
                "get_products", "get_product", "create_product", "update_product", "delete_product",
                "get_states", "get_state", "create_state", "update_state", "delete_state",
                "get_contexts", "get_context", "create_context", "update_context", "delete_context",
                "get_ratingtables", "get_ratingtable", "create_ratingtable", "update_ratingtable", "delete_ratingtable",
                "get_algorithms", "get_algorithm", "create_algorithm", "update_algorithm", "delete_algorithm",
                "get_ratingmanuals", "get_ratingmanual", "create_ratingmanual", "update_ratingmanual", "delete_ratingmanual",
                "get_ratingplans", "get_ratingplan", "create_ratingplan", "update_ratingplan", "delete_ratingplan",
                "health_check"
            ]
            tools = known_tools
            tool_details = [{"name": tool, "description": f"MCP tool: {tool}"} for tool in tools]
        
        # Get server name (same pattern as /status endpoint)
        server_name = mcp.name if (MCP_AVAILABLE and mcp is not None) else "Ratings API MCP Server"
        
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {
                    "listChanged": True
                }
            },
            "serverInfo": {
                "name": server_name,
                "version": "1.0.0"
            },
            "tools": {
                "count": len(tool_details) if tool_details else len(tools),
                "list": tool_details if tool_details else tools
            },
            "endpoints": {
                "http": "/api/v1/mcp/protocol",
                "sse": "/api/v1/mcp/protocol/sse",
                "info": "/api/v1/mcp/protocol/info",
                "tools": "/api/v1/mcp/tools",
                "status": "/api/v1/mcp/status"
            }
        }
    except Exception as e:
        logger.error(f"Error getting MCP protocol info: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get protocol info: {str(e)}"
        )

