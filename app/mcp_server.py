"""
MCP Server implementation for Ratings API
Exposes all existing API endpoints as MCP tools for AI model interaction
"""
import httpx
from typing import Any, Dict, List, Optional, Union
import logging
import os
from app.core.config import settings

logger = logging.getLogger(__name__)

# Try to import fastmcp
try:
    from fastmcp import FastMCP
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("fastmcp not available. MCP server functionality will be disabled.")

# Create HTTP client for internal API calls with performance optimizations
# Use API_URL environment variable if set (for Docker), otherwise use localhost
api_url = os.getenv("API_URL", "http://localhost:8000")
base_url = f"{api_url}{settings.API_V1_STR}"

# Optimized HTTP client configuration for better performance
# - Reduced timeout for faster failure detection
# - Connection pooling with limits for better resource management
# - Keep-alive connections to reduce overhead
client = httpx.AsyncClient(
    base_url=base_url,
    timeout=httpx.Timeout(10.0, connect=5.0),  # 10s total, 5s connect timeout
    follow_redirects=True,
    limits=httpx.Limits(
        max_keepalive_connections=20,  # Keep connections alive for reuse
        max_connections=100,  # Max concurrent connections
        keepalive_expiry=30.0  # Keep connections alive for 30 seconds
    )
    # Note: HTTP/2 support can be enabled by installing httpx[http2] and setting http2=True
)

# Initialize FastMCP server if available
mcp = None
if MCP_AVAILABLE:
    mcp = FastMCP("Ratings API MCP Server")

# Helper function to normalize boolean values
def normalize_bool(value: Any) -> Optional[bool]:
    """Convert string or other types to boolean, or return None"""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lower_val = value.lower().strip()
        if lower_val in ('true', '1', 'yes', 'on'):
            return True
        if lower_val in ('false', '0', 'no', 'off', ''):
            return False
    # Try to convert to bool for other types
    try:
        return bool(value)
    except (ValueError, TypeError):
        return None

# Helper function to make API calls with performance optimizations
async def call_api(method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
    """Make an API call and return the response with optimized error handling"""
    try:
        # Use stream=False for small responses, but allow streaming for large ones
        response = await client.request(method, endpoint, **kwargs)
        response.raise_for_status()
        
        # Parse JSON efficiently
        data = response.json()
        
        # FastMCP requires dict responses, not lists
        # Wrap list responses in a dict (optimized for large lists)
        if isinstance(data, list):
            return {"items": data, "count": len(data)}
        
        # If it's already a dict, return as is
        if isinstance(data, dict):
            return data
        
        # For any other type, wrap it
        return {"data": data}
    except httpx.TimeoutException as e:
        logger.warning(f"API call timeout: {endpoint} - {e}")
        return {"error": f"Request timeout: {str(e)}", "status_code": 408}
    except httpx.HTTPStatusError as e:
        logger.warning(f"API call failed with status {e.response.status_code}: {endpoint}")
        return {"error": str(e), "status_code": e.response.status_code}
    except httpx.HTTPError as e:
        logger.error(f"API call failed: {endpoint} - {e}")
        return {"error": str(e), "status_code": None}
    except Exception as e:
        logger.error(f"Unexpected error in API call {endpoint}: {e}")
        return {"error": str(e)}


# Tool registry for HTTP access (maps tool names to functions)
# This allows tools to be called via HTTP endpoints even if _tools is not populated
TOOL_REGISTRY = {}

# Only register tools if MCP is available
if MCP_AVAILABLE and mcp is not None:
    # Companies endpoints
    @mcp.tool()
    async def get_companies(
        skip: int = 0,
        limit: int = 100,
        active: Union[bool, str, None] = None,
        company_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get a list of companies with optional filtering and pagination. Use limit to control response size for better performance."""
        # Cap limit to prevent excessive data transfer
        limit = min(limit, 1000)
        params = {"skip": skip, "limit": limit}
        active_bool = normalize_bool(active)
        if active_bool is not None:
            params["active"] = active_bool
        if company_name:
            params["company_name"] = company_name
        return await call_api("GET", "/companies", params=params)

    @mcp.tool()
    async def get_company(company_id: int) -> Dict[str, Any]:
        """Get a specific company by ID"""
        return await call_api("GET", f"/companies/{company_id}")

    @mcp.tool()
    async def create_company(company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new company"""
        return await call_api("POST", "/companies", json=company_data)


    @mcp.tool()
    async def update_company(company_id: int, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing company"""
        return await call_api("PUT", f"/companies/{company_id}", json=company_data)


    @mcp.tool()
    async def delete_company(company_id: int) -> Dict[str, Any]:
        """Delete a company by ID"""
        return await call_api("DELETE", f"/companies/{company_id}")


    # LOBs endpoints
    @mcp.tool()
    async def get_lobs(
        skip: int = 0,
        limit: int = 100,
        active: Union[bool, str, None] = None,
        lob_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get a list of lines of business with optional filtering and pagination"""
        params = {"skip": skip, "limit": limit}
        active_bool = normalize_bool(active)
        if active_bool is not None:
            params["active"] = active_bool
        if lob_name:
            params["lob_name"] = lob_name
        return await call_api("GET", "/lobs", params=params)


    @mcp.tool()
    async def get_lob(lob_id: int) -> Dict[str, Any]:
        """Get a specific line of business by ID"""
        return await call_api("GET", f"/lobs/{lob_id}")


    @mcp.tool()
    async def create_lob(lob_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new line of business"""
        return await call_api("POST", "/lobs", json=lob_data)


    @mcp.tool()
    async def update_lob(lob_id: int, lob_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing line of business"""
        return await call_api("PUT", f"/lobs/{lob_id}", json=lob_data)


    @mcp.tool()
    async def delete_lob(lob_id: int) -> Dict[str, Any]:
        """Delete a line of business by ID"""
        return await call_api("DELETE", f"/lobs/{lob_id}")


    # Products endpoints
    @mcp.tool()
    async def get_products(
        skip: int = 0,
        limit: int = 100,
        active: Union[bool, str, None] = None,
        product_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get a list of products with optional filtering and pagination"""
        params = {"skip": skip, "limit": limit}
        active_bool = normalize_bool(active)
        if active_bool is not None:
            params["active"] = active_bool
        if product_name:
            params["product_name"] = product_name
        return await call_api("GET", "/products", params=params)


    @mcp.tool()
    async def get_product(product_id: int) -> Dict[str, Any]:
        """Get a specific product by ID"""
        return await call_api("GET", f"/products/{product_id}")


    @mcp.tool()
    async def create_product(product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new product"""
        return await call_api("POST", "/products", json=product_data)


    @mcp.tool()
    async def update_product(product_id: int, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing product"""
        return await call_api("PUT", f"/products/{product_id}", json=product_data)


    @mcp.tool()
    async def delete_product(product_id: int) -> Dict[str, Any]:
        """Delete a product by ID"""
        return await call_api("DELETE", f"/products/{product_id}")


    # States endpoints
    @mcp.tool()
    async def get_states(
        skip: int = 0,
        limit: int = 100,
        active: Union[bool, str, None] = None,
        state_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get a list of states with optional filtering and pagination"""
        params = {"skip": skip, "limit": limit}
        active_bool = normalize_bool(active)
        if active_bool is not None:
            params["active"] = active_bool
        if state_name:
            params["state_name"] = state_name
        return await call_api("GET", "/states", params=params)


    @mcp.tool()
    async def get_state(state_id: int) -> Dict[str, Any]:
        """Get a specific state by ID"""
        return await call_api("GET", f"/states/{state_id}")


    @mcp.tool()
    async def create_state(state_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new state"""
        return await call_api("POST", "/states", json=state_data)


    @mcp.tool()
    async def update_state(state_id: int, state_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing state"""
        return await call_api("PUT", f"/states/{state_id}", json=state_data)


    @mcp.tool()
    async def delete_state(state_id: int) -> Dict[str, Any]:
        """Delete a state by ID"""
        return await call_api("DELETE", f"/states/{state_id}")


    # Contexts endpoints
    @mcp.tool()
    async def get_contexts(
        skip: int = 0,
        limit: int = 100,
        active: Union[bool, str, None] = None,
        context_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get a list of contexts with optional filtering and pagination"""
        params = {"skip": skip, "limit": limit}
        active_bool = normalize_bool(active)
        if active_bool is not None:
            params["active"] = active_bool
        if context_name:
            params["context_name"] = context_name
        return await call_api("GET", "/contexts", params=params)


    @mcp.tool()
    async def get_context(context_id: int) -> Dict[str, Any]:
        """Get a specific context by ID"""
        return await call_api("GET", f"/contexts/{context_id}")


    @mcp.tool()
    async def create_context(context_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new context"""
        return await call_api("POST", "/contexts", json=context_data)


    @mcp.tool()
    async def update_context(context_id: int, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing context"""
        return await call_api("PUT", f"/contexts/{context_id}", json=context_data)


    @mcp.tool()
    async def delete_context(context_id: int) -> Dict[str, Any]:
        """Delete a context by ID"""
        return await call_api("DELETE", f"/contexts/{context_id}")


    # Rating Tables endpoints
    @mcp.tool()
    async def get_ratingtables(
        skip: int = 0,
        limit: int = 100,
        active: Union[bool, str, None] = None,
        table_name: Optional[str] = None,
        table_type: Optional[str] = None,
        company_id: Optional[int] = None,
        lob_id: Optional[int] = None,
        state_id: Optional[int] = None,
        product_id: Optional[int] = None,
        context_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get a list of rating tables with optional filtering and pagination. Use limit to control response size for better performance."""
        # Cap limit to prevent excessive data transfer (rating tables can be large)
        limit = min(limit, 500)
        params = {"skip": skip, "limit": limit}
        active_bool = normalize_bool(active)
        if active_bool is not None:
            params["active"] = active_bool
        if table_name:
            params["table_name"] = table_name
        if table_type:
            params["table_type"] = table_type
        if company_id is not None:
            params["company_id"] = company_id
        if lob_id is not None:
            params["lob_id"] = lob_id
        if state_id is not None:
            params["state_id"] = state_id
        if product_id is not None:
            params["product_id"] = product_id
        if context_id is not None:
            params["context_id"] = context_id
        return await call_api("GET", "/ratingtables", params=params)


    @mcp.tool()
    async def get_ratingtable(ratingtable_id: int) -> Dict[str, Any]:
        """Get a specific rating table by ID"""
        return await call_api("GET", f"/ratingtables/{ratingtable_id}")


    @mcp.tool()
    async def create_ratingtable(ratingtable_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new rating table"""
        return await call_api("POST", "/ratingtables", json=ratingtable_data)


    @mcp.tool()
    async def update_ratingtable(ratingtable_id: int, ratingtable_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing rating table"""
        return await call_api("PUT", f"/ratingtables/{ratingtable_id}", json=ratingtable_data)


    @mcp.tool()
    async def delete_ratingtable(ratingtable_id: int) -> Dict[str, Any]:
        """Delete a rating table by ID"""
        return await call_api("DELETE", f"/ratingtables/{ratingtable_id}")


    # Algorithms endpoints
    @mcp.tool()
    async def get_algorithms(
        skip: int = 0,
        limit: int = 100,
        active: Union[bool, str, None] = None,
        algorithm_name: Optional[str] = None,
        company_id: Optional[int] = None,
        lob_id: Optional[int] = None,
        state_id: Optional[int] = None,
        product_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get a list of algorithms with optional filtering and pagination"""
        params = {"skip": skip, "limit": limit}
        active_bool = normalize_bool(active)
        if active_bool is not None:
            params["active"] = active_bool
        if algorithm_name:
            params["algorithm_name"] = algorithm_name
        if company_id is not None:
            params["company_id"] = company_id
        if lob_id is not None:
            params["lob_id"] = lob_id
        if state_id is not None:
            params["state_id"] = state_id
        if product_id is not None:
            params["product_id"] = product_id
        return await call_api("GET", "/algorithms", params=params)


    @mcp.tool()
    async def get_algorithm(algorithm_id: int) -> Dict[str, Any]:
        """Get a specific algorithm by ID"""
        return await call_api("GET", f"/algorithms/{algorithm_id}")


    @mcp.tool()
    async def create_algorithm(algorithm_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new algorithm"""
        return await call_api("POST", "/algorithms", json=algorithm_data)


    @mcp.tool()
    async def update_algorithm(algorithm_id: int, algorithm_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing algorithm"""
        return await call_api("PUT", f"/algorithms/{algorithm_id}", json=algorithm_data)


    @mcp.tool()
    async def delete_algorithm(algorithm_id: int) -> Dict[str, Any]:
        """Delete an algorithm by ID"""
        return await call_api("DELETE", f"/algorithms/{algorithm_id}")


    # Rating Manuals endpoints
    @mcp.tool()
    async def get_ratingmanuals(
        skip: int = 0,
        limit: int = 100,
        active: Union[bool, str, None] = None,
        manual_name: Optional[str] = None,
        company_id: Optional[int] = None,
        lob_id: Optional[int] = None,
        state_id: Optional[int] = None,
        product_id: Optional[int] = None,
        ratingtable_id: Optional[int] = None,
        effective_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get a list of rating manuals with optional filtering and pagination. Use limit to control response size for better performance."""
        # Cap limit to prevent excessive data transfer
        limit = min(limit, 500)
        params = {"skip": skip, "limit": limit}
        active_bool = normalize_bool(active)
        if active_bool is not None:
            params["active"] = active_bool
        if manual_name:
            params["manual_name"] = manual_name
        if company_id is not None:
            params["company_id"] = company_id
        if lob_id is not None:
            params["lob_id"] = lob_id
        if state_id is not None:
            params["state_id"] = state_id
        if product_id is not None:
            params["product_id"] = product_id
        if ratingtable_id is not None:
            params["ratingtable_id"] = ratingtable_id
        if effective_date:
            params["effective_date"] = effective_date
        return await call_api("GET", "/ratingmanuals", params=params)


    @mcp.tool()
    async def get_ratingmanual(ratingmanual_id: int) -> Dict[str, Any]:
        """Get a specific rating manual by ID"""
        return await call_api("GET", f"/ratingmanuals/{ratingmanual_id}")


    @mcp.tool()
    async def create_ratingmanual(ratingmanual_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new rating manual"""
        return await call_api("POST", "/ratingmanuals", json=ratingmanual_data)


    @mcp.tool()
    async def update_ratingmanual(ratingmanual_id: int, ratingmanual_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing rating manual"""
        return await call_api("PUT", f"/ratingmanuals/{ratingmanual_id}", json=ratingmanual_data)


    @mcp.tool()
    async def delete_ratingmanual(ratingmanual_id: int) -> Dict[str, Any]:
        """Delete a rating manual by ID"""
        return await call_api("DELETE", f"/ratingmanuals/{ratingmanual_id}")


    # Rating Plans endpoints
    @mcp.tool()
    async def get_ratingplans(
        skip: int = 0,
        limit: int = 100,
        active: Union[bool, str, None] = None,
        plan_name: Optional[str] = None,
        company_id: Optional[int] = None,
        lob_id: Optional[int] = None,
        state_id: Optional[int] = None,
        product_id: Optional[int] = None,
        algorithm_id: Optional[int] = None,
        effective_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get a list of rating plans with optional filtering and pagination. Use limit to control response size for better performance."""
        # Cap limit to prevent excessive data transfer
        limit = min(limit, 500)
        params = {"skip": skip, "limit": limit}
        active_bool = normalize_bool(active)
        if active_bool is not None:
            params["active"] = active_bool
        if plan_name:
            params["plan_name"] = plan_name
        if company_id is not None:
            params["company_id"] = company_id
        if lob_id is not None:
            params["lob_id"] = lob_id
        if state_id is not None:
            params["state_id"] = state_id
        if product_id is not None:
            params["product_id"] = product_id
        if algorithm_id is not None:
            params["algorithm_id"] = algorithm_id
        if effective_date:
            params["effective_date"] = effective_date
        return await call_api("GET", "/ratingplans", params=params)


    @mcp.tool()
    async def get_ratingplan(ratingplan_id: int) -> Dict[str, Any]:
        """Get a specific rating plan by ID"""
        return await call_api("GET", f"/ratingplans/{ratingplan_id}")


    @mcp.tool()
    async def create_ratingplan(ratingplan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new rating plan"""
        return await call_api("POST", "/ratingplans", json=ratingplan_data)


    @mcp.tool()
    async def update_ratingplan(ratingplan_id: int, ratingplan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing rating plan"""
        return await call_api("PUT", f"/ratingplans/{ratingplan_id}", json=ratingplan_data)


    @mcp.tool()
    async def delete_ratingplan(ratingplan_id: int) -> Dict[str, Any]:
        """Delete a rating plan by ID"""
        return await call_api("DELETE", f"/ratingplans/{ratingplan_id}")


    # Health check
    @mcp.tool()
    async def health_check() -> Dict[str, Any]:
        """Check the health status of the API and database"""
        return await call_api("GET", "/health")

    # After all tools are registered, populate TOOL_REGISTRY
    # Use globals() to get all functions defined in this module
    # This allows HTTP endpoints to access tools even if _tools is not populated at runtime
    import sys
    current_module = sys.modules[__name__]
    known_tool_names = [
        'get_companies', 'get_company', 'create_company', 'update_company', 'delete_company',
        'get_lobs', 'get_lob', 'create_lob', 'update_lob', 'delete_lob',
        'get_products', 'get_product', 'create_product', 'update_product', 'delete_product',
        'get_states', 'get_state', 'create_state', 'update_state', 'delete_state',
        'get_contexts', 'get_context', 'create_context', 'update_context', 'delete_context',
        'get_ratingtables', 'get_ratingtable', 'create_ratingtable', 'update_ratingtable', 'delete_ratingtable',
        'get_algorithms', 'get_algorithm', 'create_algorithm', 'update_algorithm', 'delete_algorithm',
        'get_ratingmanuals', 'get_ratingmanual', 'create_ratingmanual', 'update_ratingmanual', 'delete_ratingmanual',
        'get_ratingplans', 'get_ratingplan', 'create_ratingplan', 'update_ratingplan', 'delete_ratingplan',
        'health_check'
    ]
    for tool_name in known_tool_names:
        if tool_name in globals():
            tool_func = globals()[tool_name]
            if callable(tool_func):
                TOOL_REGISTRY[tool_name] = tool_func

# Export the MCP server instance and tool registry
__all__ = ["mcp", "client", "MCP_AVAILABLE", "call_api", "TOOL_REGISTRY"]

