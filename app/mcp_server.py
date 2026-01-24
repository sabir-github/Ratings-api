"""
MCP Server implementation for Ratings API
Exposes all existing API endpoints as MCP tools for AI model interaction
"""
import httpx
from typing import Any, Dict, List, Optional, Union
import logging
import os
from app.core.config import settings

# Import services for direct calls (more efficient than HTTP)
from app.services.company_service import company_service
from app.schemas.company import CompanyCreateSchema, CompanyUpdateSchema

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
        """
        Get a list of companies with full details including ID, code, name, and active status.
        
        Args:
            skip: Number of records to skip (default: 0)
            limit: Maximum number of records to return (default: 100, max: 1000)
            active: Filter by active status (True/False). Can be passed as boolean or string.
            company_name: Optional partial match filter for company name
            
        Returns a list of company objects with 'id', 'company_code', 'company_name', 'active', 
        'created_at', and 'updated_at' fields.
        """
        try:
            # Cap limit to prevent excessive data transfer
            limit = min(limit, 1000)
            filter_by = {}
            active_bool = normalize_bool(active)
            if active_bool is not None:
                filter_by["active"] = active_bool
            if company_name:
                filter_by["company_name"] = company_name
            
            results = await company_service.get_companies(
                skip=skip,
                limit=limit,
                filter_by=filter_by if filter_by else None
            )
            # Convert to list of dicts (compatible with Pydantic v1 and v2)
            items = []
            for r in results:
                if hasattr(r, 'model_dump'):
                    items.append(r.model_dump())
                elif hasattr(r, 'dict'):
                    items.append(r.dict())
                else:
                    items.append(r)
            return {"items": items, "count": len(items)}
        except Exception as e:
            logger.error(f"Error getting companies: {e}")
            return {"error": str(e), "status_code": 500}

    @mcp.tool()
    async def get_company(company_id: int) -> Dict[str, Any]:
        """
        Get detailed information about a specific company by its ID.
        
        Args:
            company_id: The unique integer ID of the company to retrieve.
            
        Returns the full company object including 'id', 'company_code', 'company_name', 
        'active', 'created_at', and 'updated_at'.
        """
        try:
            result = await company_service.get_company(company_id)
            if result is None:
                return {"error": f"Company with ID {company_id} not found", "status_code": 404}
            # Convert Pydantic model to dict (compatible with v1 and v2)
            if hasattr(result, 'model_dump'):
                return result.model_dump()
            elif hasattr(result, 'dict'):
                return result.dict()
            return result
        except Exception as e:
            logger.error(f"Error getting company: {e}")
            return {"error": str(e), "status_code": 500}

    @mcp.tool()
    async def create_company(
        company_code: str,
        company_name: str,
        active: bool = True
    ) -> Dict[str, Any]:
        """
        Create a new company in the Ratings API.
        
        Args:
            company_code: Unique code for the company (e.g., 'ABC', 'GLOB'). Max 10 characters.
            company_name: Full legal name of the company. Max 100 characters.
            active: Initial active status of the company (defaults to True).
            
        Use this tool when the user wants to add a new company to the system. 
        The 'id' will be automatically generated by the server.
        """
        try:
            logger.info(f"Creating company with code={company_code}, name={company_name}, active={active}")
            # Convert parameters to schema and call service directly (avoids auth issues)
            company_schema = CompanyCreateSchema(
                company_code=company_code,
                company_name=company_name,
                active=active
            )
            result = await company_service.create_company(company_schema)
            # Convert Pydantic model to dict (compatible with v1 and v2)
            if hasattr(result, 'model_dump'):
                response = result.model_dump()
            elif hasattr(result, 'dict'):
                response = result.dict()
            else:
                response = result
            
            logger.info(f"Successfully created company: {response.get('id', 'unknown')}")
            return response
        except ValueError as e:
            error_msg = str(e)
            logger.error(f"Validation error creating company: {error_msg}")
            # Re-raise ValueError so it can be properly handled by the protocol endpoint
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error creating company: {error_msg}")
            import traceback
            logger.error(traceback.format_exc())
            # Re-raise exception so it can be properly handled by the protocol endpoint
            raise

    @mcp.tool()
    async def update_company(company_id: int, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing company's information.
        
        Args:
            company_id: The unique integer ID of the company to update.
            company_data: A dictionary containing the fields to update (e.g., {"company_name": "New Name"}).
            
        Use this tool to modify the details of an existing company.
        """
        try:
            update_schema = CompanyUpdateSchema(**company_data)
            result = await company_service.update_company(company_id, update_schema)
            if result is None:
                return {"error": f"Company with ID {company_id} not found", "status_code": 404}
            # Convert Pydantic model to dict (compatible with v1 and v2)
            if hasattr(result, 'model_dump'):
                return result.model_dump()
            elif hasattr(result, 'dict'):
                return result.dict()
            return result
        except ValueError as e:
            logger.error(f"Validation error updating company: {e}")
            return {"error": str(e), "status_code": 400}
        except Exception as e:
            logger.error(f"Error updating company: {e}")
            return {"error": str(e), "status_code": 500}

    @mcp.tool()
    async def delete_company(company_id: int) -> Dict[str, Any]:
        """
        Delete a company by its unique ID.
        
        Args:
            company_id: The unique integer ID of the company to delete.
            
        Use this tool to permanently remove a company from the system. 
        Warning: This action cannot be undone.
        """
        try:
            result = await company_service.delete_company(company_id)
            if not result:
                return {"error": f"Company with ID {company_id} not found", "status_code": 404}
            return {"message": f"Company {company_id} deleted successfully", "deleted": True}
        except Exception as e:
            logger.error(f"Error deleting company: {e}")
            return {"error": str(e), "status_code": 500}


    # LOBs endpoints
    @mcp.tool()
    async def get_lobs(
        skip: int = 0,
        limit: int = 100,
        active: Union[bool, str, None] = None,
        lob_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get a list of lines of business (LOBs) with full details.
        
        Args:
            skip: Number of records to skip (default: 0)
            limit: Maximum number of records to return (default: 100)
            active: Filter by active status (True/False). Can be passed as boolean or string.
            lob_name: Optional partial match filter for LOB name
            
        Returns a list of LOB objects with 'id', 'lob_code', 'lob_name', and 'active' status.
        """
        params = {"skip": skip, "limit": limit}
        active_bool = normalize_bool(active)
        if active_bool is not None:
            params["active"] = active_bool
        if lob_name:
            params["lob_name"] = lob_name
        return await call_api("GET", "/lobs/", params=params)


    @mcp.tool()
    async def get_lob(lob_id: int) -> Dict[str, Any]:
        """Get a specific line of business by ID"""
        return await call_api("GET", f"/lobs/{lob_id}")


    @mcp.tool()
    async def create_lob(lob_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new Line of Business (LOB) in the Ratings API.
        
        Args:
            lob_data: Dictionary containing LOB details:
                - lob_code (str, required): Unique code for the LOB (e.g., 'AUTO', 'HOME').
                - lob_name (str, required): Full name of the LOB.
                - lob_abbreviation (str, required): Short abbreviation.
                - active (bool, optional): Initial active status (defaults to True).
                
        Use this tool to add a new business line. The 'id' is auto-generated.
        """
        return await call_api("POST", "/lobs/", json=lob_data)


    @mcp.tool()
    async def update_lob(lob_id: int, lob_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing Line of Business (LOB).
        
        Args:
            lob_id: The unique integer ID of the LOB to update.
            lob_data: Dictionary containing fields to update (e.g., {"lob_name": "New Name"}).
        """
        return await call_api("PUT", f"/lobs/{lob_id}", json=lob_data)


    @mcp.tool()
    async def delete_lob(lob_id: int) -> Dict[str, Any]:
        """
        Delete a Line of Business (LOB) by its unique ID.
        
        Warning: This action permanently removes the LOB.
        """
        return await call_api("DELETE", f"/lobs/{lob_id}")


    # Products endpoints
    @mcp.tool()
    async def get_products(
        skip: int = 0,
        limit: int = 100,
        active: Union[bool, str, None] = None,
        product_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get a list of products with full details.
        
        Args:
            skip: Number of records to skip (default: 0)
            limit: Maximum number of records to return (default: 100)
            active: Filter by active status (True/False). Can be passed as boolean or string.
            product_name: Optional partial match filter for product name
            
        Returns a list of product objects with 'id', 'product_code', 'product_name', and 'active' status.
        """
        params = {"skip": skip, "limit": limit}
        active_bool = normalize_bool(active)
        if active_bool is not None:
            params["active"] = active_bool
        if product_name:
            params["product_name"] = product_name
        return await call_api("GET", "/products/", params=params)


    @mcp.tool()
    async def get_product(product_id: int) -> Dict[str, Any]:
        """Get a specific product by ID"""
        return await call_api("GET", f"/products/{product_id}")


    @mcp.tool()
    async def create_product(product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new Product in the Ratings API.
        
        Args:
            product_data: Dictionary containing Product details:
                - product_code (str, required): Unique code for the product.
                - product_name (str, required): Full name of the product.
                - lob_id (int, required): ID of the Line of Business this product belongs to.
                - active (bool, optional): Initial active status (defaults to True).
                
        Use this tool to add a new insurance product. The 'id' is auto-generated.
        """
        return await call_api("POST", "/products/", json=product_data)


    @mcp.tool()
    async def update_product(product_id: int, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing Product.
        
        Args:
            product_id: The unique integer ID of the product to update.
            product_data: Dictionary containing fields to update (e.g., {"product_name": "New Name"}).
        """
        return await call_api("PUT", f"/products/{product_id}", json=product_data)


    @mcp.tool()
    async def delete_product(product_id: int) -> Dict[str, Any]:
        """
        Delete a Product by its unique ID.
        
        Warning: This action permanently removes the product.
        """
        return await call_api("DELETE", f"/products/{product_id}")


    # States endpoints
    @mcp.tool()
    async def get_states(
        skip: int = 0,
        limit: int = 100,
        active: Union[bool, str, None] = None,
        state_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get a list of states with full details.
        
        Args:
            skip: Number of records to skip (default: 0)
            limit: Maximum number of records to return (default: 100)
            active: Filter by active status (True/False). Can be passed as boolean or string.
            state_name: Optional partial match filter for state name
            
        Returns a list of state objects with 'id', 'state_code', 'state_name', and 'active' status.
        """
        params = {"skip": skip, "limit": limit}
        active_bool = normalize_bool(active)
        if active_bool is not None:
            params["active"] = active_bool
        if state_name:
            params["state_name"] = state_name
        return await call_api("GET", "/states/", params=params)


    @mcp.tool()
    async def get_state(state_id: int) -> Dict[str, Any]:
        """Get a specific state by ID"""
        return await call_api("GET", f"/states/{state_id}")


    @mcp.tool()
    async def create_state(state_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a new State to the Ratings API.
        
        Args:
            state_data: Dictionary containing State details:
                - state_code (str, required): 2-letter state code (e.g., 'NY', 'CA').
                - state_name (str, required): Full name of the state.
                - active (bool, optional): Initial active status (defaults to True).
        """
        return await call_api("POST", "/states/", json=state_data)


    @mcp.tool()
    async def update_state(state_id: int, state_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing State's details.
        
        Args:
            state_id: The unique integer ID of the state to update.
            state_data: Dictionary containing fields to update.
        """
        return await call_api("PUT", f"/states/{state_id}", json=state_data)


    @mcp.tool()
    async def delete_state(state_id: int) -> Dict[str, Any]:
        """
        Remove a State from the system by its ID.
        """
        return await call_api("DELETE", f"/states/{state_id}")


    # Contexts endpoints
    @mcp.tool()
    async def get_contexts(
        skip: int = 0,
        limit: int = 100,
        active: Union[bool, str, None] = None,
        context_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get a list of contexts with full details.
        
        Args:
            skip: Number of records to skip (default: 0)
            limit: Maximum number of records to return (default: 100)
            active: Filter by active status (True/False). Can be passed as boolean or string.
            context_name: Optional partial match filter for context name
            
        Returns a list of context objects with 'id', 'context_name', and 'active' status.
        """
        params = {"skip": skip, "limit": limit}
        active_bool = normalize_bool(active)
        if active_bool is not None:
            params["active"] = active_bool
        if context_name:
            params["context_name"] = context_name
        return await call_api("GET", "/contexts/", params=params)


    @mcp.tool()
    async def get_context(context_id: int) -> Dict[str, Any]:
        """Get a specific context by ID"""
        return await call_api("GET", f"/contexts/{context_id}")


    @mcp.tool()
    async def create_context(context_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new rating Context.
        
        Args:
            context_data: Dictionary containing Context details:
                - context_name (str, required): Name of the context (e.g., 'New Business', 'Renewal').
                - active (bool, optional): Initial active status (defaults to True).
        """
        return await call_api("POST", "/contexts/", json=context_data)


    @mcp.tool()
    async def update_context(context_id: int, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing Context.
        
        Args:
            context_id: The unique integer ID of the context to update.
            context_data: Dictionary containing fields to update.
        """
        return await call_api("PUT", f"/contexts/{context_id}", json=context_data)


    @mcp.tool()
    async def delete_context(context_id: int) -> Dict[str, Any]:
        """
        Delete a Context by its unique ID.
        """
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
        """
        Get a list of rating tables with full details.
        
        Args:
            skip: Number of records to skip (default: 0)
            limit: Maximum number of records to return (default: 100, max: 500)
            active: Filter by active status (True/False)
            table_name: Optional partial match filter for table name (e.g., 'Factors', 'Rates')
            table_type: Optional filter by table type (e.g., 'BASE', 'LOAD')
            company_id: Filter by the company's ID
            lob_id: Filter by the Line of Business (LOB) ID
            state_id: Filter by the State ID
            product_id: Filter by the Product ID
            context_id: Filter by the Context ID
            
        Returns a list of rating table objects with full metadata and configuration details.
        """
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
        return await call_api("GET", "/ratingtables/", params=params)


    @mcp.tool()
    async def get_ratingtable(ratingtable_id: int) -> Dict[str, Any]:
        """Get a specific rating table by ID"""
        return await call_api("GET", f"/ratingtables/{ratingtable_id}")


    @mcp.tool()
    async def create_ratingtable(ratingtable_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new Rating Table in the Ratings API.
        
        Args:
            ratingtable_data: Dictionary containing Rating Table details:
                - table_name (str, required): Name of the table.
                - table_type (str, required): Type of table (e.g., 'BASE', 'LOAD', 'FACTOR').
                - company_id (int, required): ID of the company this table belongs to.
                - lob_id (int, required): ID of the Line of Business.
                - state_id (int, required): ID of the State.
                - product_id (int, required): ID of the Product.
                - context_id (int, required): ID of the Context.
                - description (str, optional): Detailed description of the table.
                - active (bool, optional): Initial active status (defaults to True).
                
        Rating tables store the actual factors and rates used in premium calculations.
        """
        return await call_api("POST", "/ratingtables/", json=ratingtable_data)


    @mcp.tool()
    async def update_ratingtable(ratingtable_id: int, ratingtable_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing Rating Table.
        
        Args:
            ratingtable_id: The unique integer ID of the rating table to update.
            ratingtable_data: Dictionary containing fields to update.
        """
        return await call_api("PUT", f"/ratingtables/{ratingtable_id}", json=ratingtable_data)


    @mcp.tool()
    async def delete_ratingtable(ratingtable_id: int) -> Dict[str, Any]:
        """
        Delete a Rating Table by its unique ID.
        """
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
        """
        Get a list of algorithms with full details.
        
        Args:
            skip: Number of records to skip (default: 0)
            limit: Maximum number of records to return (default: 100)
            active: Filter by active status (True/False)
            algorithm_name: Optional partial match filter for algorithm name
            company_id: Filter by the company's ID
            lob_id: Filter by the Line of Business (LOB) ID
            state_id: Filter by the State ID
            product_id: Filter by the Product ID
            
        Returns a list of algorithm objects with logic and configuration details.
        """
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
        return await call_api("GET", "/algorithms/", params=params)


    @mcp.tool()
    async def get_algorithm(algorithm_id: int) -> Dict[str, Any]:
        """Get a specific algorithm by ID"""
        return await call_api("GET", f"/algorithms/{algorithm_id}")


    @mcp.tool()
    async def create_algorithm(algorithm_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new rating Algorithm.
        
        Args:
            algorithm_data: Dictionary containing Algorithm details:
                - algorithm_name (str, required): Name of the algorithm.
                - company_id (int, required): ID of the company.
                - lob_id (int, required): ID of the Line of Business.
                - state_id (int, required): ID of the State.
                - product_id (int, required): ID of the Product.
                - description (str, optional): Description of what the algorithm does.
                - logic (str, optional): The actual calculation logic or pseudo-code.
                - active (bool, optional): Initial active status (defaults to True).
        """
        return await call_api("POST", "/algorithms/", json=algorithm_data)


    @mcp.tool()
    async def update_algorithm(algorithm_id: int, algorithm_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing Algorithm.
        
        Args:
            algorithm_id: The unique integer ID of the algorithm to update.
            algorithm_data: Dictionary containing fields to update.
        """
        return await call_api("PUT", f"/algorithms/{algorithm_id}", json=algorithm_data)


    @mcp.tool()
    async def delete_algorithm(algorithm_id: int) -> Dict[str, Any]:
        """
        Delete an Algorithm by its unique ID.
        """
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
        """
        Get a list of rating manuals with full details.
        
        Args:
            skip: Number of records to skip (default: 0)
            limit: Maximum number of records to return (default: 100, max: 500)
            active: Filter by active status (True/False)
            manual_name: Optional partial match filter for manual name
            company_id: Filter by the company's ID
            lob_id: Filter by the Line of Business (LOB) ID
            state_id: Filter by the State ID
            product_id: Filter by the Product ID
            ratingtable_id: Filter by a specific rating table's ID
            effective_date: Optional filter by effective date (YYYY-MM-DD)
            
        Returns a list of rating manual objects with full configuration details.
        """
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
        return await call_api("GET", "/ratingmanuals/", params=params)


    @mcp.tool()
    async def get_ratingmanual(ratingmanual_id: int) -> Dict[str, Any]:
        """Get a specific rating manual by ID"""
        return await call_api("GET", f"/ratingmanuals/{ratingmanual_id}")


    @mcp.tool()
    async def create_ratingmanual(ratingmanual_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new Rating Manual.
        
        Args:
            ratingmanual_data: Dictionary containing Rating Manual details:
                - manual_name (str, required): Name of the manual.
                - company_id (int, required): ID of the company.
                - lob_id (int, required): ID of the Line of Business.
                - state_id (int, required): ID of the State.
                - product_id (int, required): ID of the Product.
                - ratingtable_id (int, required): ID of the primary rating table for this manual.
                - effective_date (str, required): Date when the manual becomes active (YYYY-MM-DD).
                - expiration_date (str, optional): Date when the manual expires (YYYY-MM-DD).
                - active (bool, optional): Initial active status (defaults to True).
        """
        return await call_api("POST", "/ratingmanuals/", json=ratingmanual_data)


    @mcp.tool()
    async def update_ratingmanual(ratingmanual_id: int, ratingmanual_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing Rating Manual.
        
        Args:
            ratingmanual_id: The unique integer ID of the rating manual to update.
            ratingmanual_data: Dictionary containing fields to update.
        """
        return await call_api("PUT", f"/ratingmanuals/{ratingmanual_id}", json=ratingmanual_data)


    @mcp.tool()
    async def delete_ratingmanual(ratingmanual_id: int) -> Dict[str, Any]:
        """
        Delete a Rating Manual by its unique ID.
        """
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
        """
        Get a list of rating plans with full details.
        
        Args:
            skip: Number of records to skip (default: 0)
            limit: Maximum number of records to return (default: 100, max: 500)
            active: Filter by active status (True/False)
            plan_name: Optional partial match filter for plan name
            company_id: Filter by the company's ID
            lob_id: Filter by the Line of Business (LOB) ID
            state_id: Filter by the State ID
            product_id: Filter by the Product ID
            algorithm_id: Filter by a specific algorithm's ID
            effective_date: Optional filter by effective date (YYYY-MM-DD)
            
        Returns a list of rating plan objects with full configuration details.
        """
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
        return await call_api("GET", "/ratingplans/", params=params)


    @mcp.tool()
    async def get_ratingplan(ratingplan_id: int) -> Dict[str, Any]:
        """Get a specific rating plan by ID"""
        return await call_api("GET", f"/ratingplans/{ratingplan_id}")


    @mcp.tool()
    async def create_ratingplan(ratingplan_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new Rating Plan.
        
        Args:
            ratingplan_data: Dictionary containing Rating Plan details:
                - plan_name (str, required): Name of the rating plan.
                - company_id (int, required): ID of the company.
                - lob_id (int, required): ID of the Line of Business.
                - state_id (int, required): ID of the State.
                - product_id (int, required): ID of the Product.
                - algorithm_id (int, required): ID of the algorithm used in this plan.
                - effective_date (str, required): Date when the plan becomes active (YYYY-MM-DD).
                - expiration_date (str, optional): Date when the plan expires (YYYY-MM-DD).
                - active (bool, optional): Initial active status (defaults to True).
        """
        return await call_api("POST", "/ratingplans/", json=ratingplan_data)


    @mcp.tool()
    async def update_ratingplan(ratingplan_id: int, ratingplan_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing Rating Plan.
        
        Args:
            ratingplan_id: The unique integer ID of the rating plan to update.
            ratingplan_data: Dictionary containing fields to update.
        """
        return await call_api("PUT", f"/ratingplans/{ratingplan_id}", json=ratingplan_data)


    @mcp.tool()
    async def delete_ratingplan(ratingplan_id: int) -> Dict[str, Any]:
        """
        Delete a Rating Plan by its unique ID.
        """
        return await call_api("DELETE", f"/ratingplans/{ratingplan_id}")


    # Health check
    @mcp.tool()
    async def health_check() -> Dict[str, Any]:
        """
        Check the connectivity and operational status of the Ratings API and its MongoDB database.
        
        Returns a status report indicating if the services are 'up' or 'down'.
        """
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

