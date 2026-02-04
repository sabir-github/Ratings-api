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
from app.services.evaluate_expression import evaluate_expression as evaluate_expression_service
from app.schemas.company import CompanyCreateSchema, CompanyUpdateSchema
from app.schemas.calculation import CalculationRequest
from app.core.database import get_database

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
# Note: MCP_BASE_URL in settings (from .env) is used by Gemini client, not here
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


# Helper function to ensure database is initialized before tool execution
async def ensure_database_initialized():
    """Ensure database connection is initialized (lazy initialization)"""
    try:
        await get_database()
    except Exception as e:
        logger.warning(f"Database initialization warning: {e}")
        # Don't raise - let the tool handle the error

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
        Get a list of insurance companies with full details.
        
        Purpose:
        Retrieves insurance companies from the system. Companies are the top-level entities
        in the ratings hierarchy and represent insurance carriers or organizations that
        provide insurance products. Use this tool to browse, search, or filter companies by name
        when setting up rating configurations or managing company data.
        
        Usage Examples:
        - Get all active companies: active=True, limit=100
        - Search for a specific company: company_name="Global Insurance"
        - Get inactive companies: active=False
        - Paginate through companies: skip=100, limit=50
        
        Args:
            skip: Number of records to skip for pagination (default: 0)
            limit: Maximum number of records to return (default: 100, max: 1000)
            active: Filter by active status (True/False/None). None returns all.
            company_name: Optional partial match filter for company name (case-insensitive)
            
        Returns:
            Dictionary with:
            - items: List of company objects, each containing:
              * id: Unique integer identifier
              * company_code: Short code (e.g., 'ABC', 'GLOB')
              * company_name: Full legal name
              * active: Boolean indicating if company is active
              * created_at: Timestamp of creation
              * updated_at: Timestamp of last update
            - count: Number of items returned
            
        When to Use:
        - User asks to "list companies", "show all companies", "get companies"
        - Need to find a company by name or code
        - Setting up rating configurations that require company selection
        - Verifying company exists before creating related entities (LOBs, products, etc.)
        """
        params = {"skip": skip, "limit": limit}
        active_bool = normalize_bool(active)
        if active_bool is not None:
            params["active"] = active_bool
        if company_name:
            params["company_name"] = company_name
        return await call_api("GET", "/companies/", params=params)

    # @mcp.tool()
    # async def get_company(company_id: int) -> Dict[str, Any]:
    #     """
    #     Get detailed information about a specific company by its ID.
    #     
    #     Purpose:
    #     Retrieves complete details for a single insurance company. Use this when you
    #     have a company ID and need to verify its details, check its active status,
    #     or retrieve its information for use in other operations.
    #     
    #     Usage Examples:
    #     - Get company with ID 1: company_id=1
    #     - Verify company exists before updating: get_company(5) to check if company 5 exists
    #     - Retrieve company details for display: get_company(company_id)
    #     
    #     Args:
    #         company_id: The unique integer ID of the company to retrieve.
    #         
    #     Returns:
    #         Company object with fields:
    #         - id: Unique integer identifier
    #         - company_code: Short code (e.g., 'ABC', 'GLOB')
    #         - company_name: Full legal name
    #         - active: Boolean indicating if company is active
    #         - created_at: Timestamp of creation
    #         - updated_at: Timestamp of last update
    #         
    #     When to Use:
    #     - User provides a company ID and asks for details
    #     - Need to verify company exists before creating related entities
    #     - Displaying company information in responses
    #     - Checking company status before operations
    #     """
    #     try:
    #         result = await company_service.get_company(company_id)
    #         if result is None:
    #             return {"error": f"Company with ID {company_id} not found", "status_code": 404}
    #         # Convert Pydantic model to dict (compatible with v1 and v2)
    #         if hasattr(result, 'model_dump'):
    #             return result.model_dump()
    #         elif hasattr(result, 'dict'):
    #             return result.dict()
    #         return result
    #     except Exception as e:
    #         logger.error(f"Error getting company: {e}")
    #         return {"error": str(e), "status_code": 500}

    @mcp.tool()
    async def create_company(
        company_code: str,
        company_name: str,
        active: bool = True
    ) -> Dict[str, Any]:
        """
        Create a new insurance company in the Ratings API.
        
        Purpose:
        Adds a new insurance company to the system. Companies are the foundation of the
        rating hierarchy - all rating configurations (LOBs, products, states, etc.)
        are associated with a company. Before creating rating plans or tables, you must
        first create or identify the company.
        
        Usage Examples:
        - Create active company: company_code="ABC", company_name="ABC Insurance Corp", active=True
        - Create inactive company: company_code="XYZ", company_name="XYZ Insurance", active=False
        - Company code should be short and unique (e.g., "GLOB", "PNC", "STATE")
        
        Args:
            company_code: Unique short code for the company (e.g., 'ABC', 'GLOB', 'PNC').
                         Max 10 characters. Must be unique across all companies.
            company_name: Full legal name of the company. Max 100 characters.
                         Example: "Global Insurance Corporation" or "ABC Insurance Company"
            active: Initial active status (defaults to True). Set to False to create
                   an inactive company that won't appear in active listings.
            
        Returns:
            Created company object with all fields including auto-generated 'id',
            'created_at', and 'updated_at' timestamps.
            
        When to Use:
        - User says "create company", "add company", "new company"
        - Setting up a new insurance carrier in the system
        - Need to establish company before creating rating configurations
        - Importing company data from external sources
        
        Important Notes:
        - The 'id' is automatically generated - do not provide it
        - Company code must be unique - check existing companies first
        - Company name should be the full legal name
        """
        try:
            # Ensure database is initialized (for stdio MCP connections)
            await ensure_database_initialized()
            
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
        
        Purpose:
        Modifies one or more fields of an existing insurance company. Use this to change
        company name, update active status, or correct company information. Only the
        fields provided in company_data will be updated; other fields remain unchanged.
        
        Usage Examples:
        - Update company name: company_data={"company_name": "New Company Name"}
        - Deactivate company: company_data={"active": False}
        - Update multiple fields: company_data={"company_name": "New Name", "active": True}
        - Change company code: company_data={"company_code": "NEWCODE"}
        
        Args:
            company_id: The unique integer ID of the company to update.
            company_data: Dictionary containing fields to update. Valid fields:
                         - company_name: Full legal name (max 100 chars)
                         - company_code: Short code (max 10 chars, must be unique)
                         - active: Boolean status
            
        Returns:
            Updated company object with all fields, including updated 'updated_at' timestamp.
            Returns error if company not found.
            
        When to Use:
        - User says "update company", "change company", "modify company"
        - Need to correct company information
        - Activating or deactivating a company
        - Renaming a company due to merger or rebranding
        
        Important Notes:
        - Company code must remain unique if changed
        - Only provide fields that need updating
        - Company ID cannot be changed
        """
        try:
            # Ensure database is initialized (for stdio MCP connections)
            await ensure_database_initialized()
            
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
        
        Purpose:
        Permanently removes an insurance company from the system. This is a destructive
        operation that should be used with caution. Consider deactivating the company
        (update with active=False) instead of deleting, as deletion may affect related
        rating configurations, products, and historical data.
        
        Usage Examples:
        - Delete company with ID 5: company_id=5
        - Should typically verify company exists first: get_company(5) then delete_company(5)
        
        Args:
            company_id: The unique integer ID of the company to delete.
            
        Returns:
            Dictionary with success message and deleted flag, or error if company not found.
            
        When to Use:
        - User explicitly requests to "delete company", "remove company"
        - Data cleanup operations
        - Removing test or duplicate companies
        
        Warning:
        - This action is PERMANENT and CANNOT be undone
        - May affect related entities (LOBs, products, rating tables, etc.)
        - Consider deactivating (active=False) instead of deleting
        - Always verify company ID before deletion
        """
        try:
            # Ensure database is initialized (for stdio MCP connections)
            await ensure_database_initialized()
            
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
        
        Purpose:
        Retrieves insurance lines of business (LOBs) from the system. LOBs represent
        different types of insurance coverage such as Auto, Home, Commercial, etc.
        They are the second level in the rating hierarchy (Company -> LOB -> Product).
        Use this to browse available LOBs, search for specific ones, or filter by status.
        
        Usage Examples:
        - Get all active LOBs: active=True, limit=100
        - Search for Auto LOB: lob_name="Auto"
        - Get inactive LOBs: active=False
        - Paginate through LOBs: skip=50, limit=25
        
        Args:
            skip: Number of records to skip for pagination (default: 0)
            limit: Maximum number of records to return (default: 100)
            active: Filter by active status (True/False/None). None returns all.
            lob_name: Optional partial match filter for LOB name (case-insensitive)
            
        Returns:
            Dictionary with:
            - items: List of LOB objects, each containing:
              * id: Unique integer identifier
              * lob_code: Short code (e.g., 'AUTO', 'HOME', 'COMM')
              * lob_name: Full name (e.g., 'Automobile', 'Homeowners')
              * lob_abbreviation: Short abbreviation
              * active: Boolean indicating if LOB is active
            - count: Number of items returned
            
        When to Use:
        - User asks to "list LOBs", "show lines of business", "get LOBs"
        - Need to find a LOB by name or code
        - Setting up rating configurations that require LOB selection
        - Verifying LOB exists before creating products
        """
        params = {"skip": skip, "limit": limit}
        active_bool = normalize_bool(active)
        if active_bool is not None:
            params["active"] = active_bool
        if lob_name:
            params["lob_name"] = lob_name
        return await call_api("GET", "/lobs/", params=params)


    # @mcp.tool()
    # async def get_lob(lob_id: int) -> Dict[str, Any]:
    #     """
    #     Get detailed information about a specific line of business by its ID.
    #     
    #     Purpose:
    #     Retrieves complete details for a single LOB. Use this when you have a LOB ID
    #     and need to verify its details, check its active status, or retrieve its
    #     information for use in other operations.
    #     
    #     Args:
    #         lob_id: The unique integer ID of the LOB to retrieve.
    #         
    #     Returns:
    #         LOB object with fields: id, lob_code, lob_name, lob_abbreviation, active,
    #         created_at, updated_at.
    #         
    #     When to Use:
    #     - User provides a LOB ID and asks for details
    #     - Need to verify LOB exists before creating related entities
    #     - Displaying LOB information in responses
    #     """
    #     return await call_api("GET", f"/lobs/{lob_id}")


    @mcp.tool()
    async def create_lob(lob_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new Line of Business (LOB) in the Ratings API.
        
        Purpose:
        Adds a new insurance line of business to the system. LOBs categorize different
        types of insurance coverage (e.g., Auto, Home, Commercial). They are required
        before creating products and rating configurations. Common LOBs include Auto,
        Homeowners, Commercial General Liability, Workers Compensation, etc.
        
        Usage Examples:
        - Create Auto LOB: lob_data={"lob_code": "AUTO", "lob_name": "Automobile", "lob_abbreviation": "AUTO"}
        - Create Home LOB: lob_data={"lob_code": "HOME", "lob_name": "Homeowners", "lob_abbreviation": "HO"}
        - Create inactive LOB: lob_data={..., "active": False}
        
        Args:
            lob_data: Dictionary containing LOB details:
                - lob_code (str, required): Unique code (e.g., 'AUTO', 'HOME', 'COMM'). Max 10 chars.
                - lob_name (str, required): Full name (e.g., 'Automobile Insurance').
                - lob_abbreviation (str, required): Short abbreviation (e.g., 'AUTO', 'HO').
                - active (bool, optional): Initial active status (defaults to True).
                
        Returns:
            Created LOB object with all fields including auto-generated 'id'.
            
        When to Use:
        - User says "create LOB", "add line of business", "new LOB"
        - Setting up new insurance coverage types
        - Importing LOB data from external sources
        
        Important Notes:
        - The 'id' is automatically generated - do not provide it
        - LOB code must be unique
        """
        return await call_api("POST", "/lobs/", json=lob_data)


    @mcp.tool()
    async def update_lob(lob_id: int, lob_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing Line of Business (LOB).
        
        Purpose:
        Modifies one or more fields of an existing LOB. Use this to change LOB name,
        update active status, or correct LOB information. Only the fields provided
        in lob_data will be updated.
        
        Args:
            lob_id: The unique integer ID of the LOB to update.
            lob_data: Dictionary containing fields to update. Valid fields:
                     - lob_name: Full name
                     - lob_code: Short code (must be unique)
                     - lob_abbreviation: Short abbreviation
                     - active: Boolean status
            
        Returns:
            Updated LOB object with all fields, including updated 'updated_at' timestamp.
            
        When to Use:
        - User says "update LOB", "change LOB", "modify line of business"
        - Need to correct LOB information
        - Activating or deactivating a LOB
        """
        return await call_api("PUT", f"/lobs/{lob_id}", json=lob_data)


    @mcp.tool()
    async def delete_lob(lob_id: int) -> Dict[str, Any]:
        """
        Delete a Line of Business (LOB) by its unique ID.
        
        Purpose:
        Permanently removes a LOB from the system. This is a destructive operation.
        Consider deactivating the LOB (update with active=False) instead of deleting,
        as deletion may affect related products and rating configurations.
        
        Args:
            lob_id: The unique integer ID of the LOB to delete.
            
        Returns:
            Dictionary with success message and deleted flag, or error if LOB not found.
            
        When to Use:
        - User explicitly requests to "delete LOB", "remove line of business"
        - Data cleanup operations
        
        Warning:
        - This action is PERMANENT and CANNOT be undone
        - May affect related entities (products, rating tables, etc.)
        - Consider deactivating (active=False) instead of deleting
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
        Get a list of insurance products with full details.
        
        Purpose:
        Retrieves insurance products from the system. Products are specific insurance
        offerings within a Line of Business (e.g., "Standard Auto", "Preferred Auto"
        under the Auto LOB). They are the third level in the rating hierarchy
        (Company -> LOB -> Product -> State/Context). Use this to browse products,
        search for specific ones, or filter by status.
        
        Usage Examples:
        - Get all active products: active=True, limit=100
        - Search for product: product_name="Standard Auto"
        - Get products for a specific LOB: Use get_products then filter by lob_id in results
        
        Args:
            skip: Number of records to skip for pagination (default: 0)
            limit: Maximum number of records to return (default: 100)
            active: Filter by active status (True/False/None). None returns all.
            product_name: Optional partial match filter for product name (case-insensitive)
            
        Returns:
            Dictionary with items list and count. Each product contains:
            id, product_code, product_name, lob_id, active, created_at, updated_at.
            
        When to Use:
        - User asks to "list products", "show products", "get products"
        - Need to find a product by name
        - Setting up rating configurations that require product selection
        """
        params = {"skip": skip, "limit": limit}
        active_bool = normalize_bool(active)
        if active_bool is not None:
            params["active"] = active_bool
        if product_name:
            params["product_name"] = product_name
        return await call_api("GET", "/products/", params=params)


    # @mcp.tool()
    # async def get_product(product_id: int) -> Dict[str, Any]:
    #     """
    #     Get detailed information about a specific product by its ID.
    #     
    #     Purpose:
    #     Retrieves complete details for a single product. Use this when you have a product ID
    #     and need to verify its details, check its LOB association, or retrieve its information.
    #     
    #     Args:
    #         product_id: The unique integer ID of the product to retrieve.
    #         
    #     Returns:
    #         Product object with fields: id, product_code, product_name, lob_id, active,
    #         created_at, updated_at.
    #         
    #     When to Use:
    #     - User provides a product ID and asks for details
    #     - Need to verify product exists before creating rating configurations
    #     """
    #     return await call_api("GET", f"/products/{product_id}")


    @mcp.tool()
    async def create_product(product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new insurance product in the Ratings API.
        
        Purpose:
        Adds a new insurance product to the system. Products are specific offerings within
        a Line of Business (e.g., "Standard Auto", "Preferred Auto" under Auto LOB).
        Products must be associated with an existing LOB. They are required before creating
        rating tables, algorithms, and rating plans.
        
        Usage Examples:
        - Create Standard Auto product: product_data={"product_code": "STD_AUTO", "product_name": "Standard Automobile", "lob_id": 1}
        - Create Preferred Home product: product_data={"product_code": "PREF_HO", "product_name": "Preferred Homeowners", "lob_id": 2, "active": True}
        
        Args:
            product_data: Dictionary containing:
                - product_code (str, required): Unique code (e.g., 'STD_AUTO', 'PREF_HO')
                - product_name (str, required): Full name (e.g., 'Standard Automobile Insurance')
                - lob_id (int, required): ID of the Line of Business this product belongs to
                - active (bool, optional): Initial active status (defaults to True)
                
        Returns:
            Created product object with all fields including auto-generated 'id'.
            
        When to Use:
        - User says "create product", "add product", "new product"
        - Setting up new insurance product offerings
        - Need to verify LOB exists first (use get_lob or get_lobs)
        
        Important Notes:
        - The 'id' is automatically generated
        - lob_id must reference an existing LOB
        - Product code should be unique
        """
        return await call_api("POST", "/products/", json=product_data)


    @mcp.tool()
    async def update_product(product_id: int, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing product.
        
        Purpose:
        Modifies one or more fields of an existing product. Use this to change product name,
        update active status, change LOB association, or correct product information.
        
        Args:
            product_id: The unique integer ID of the product to update.
            product_data: Dictionary containing fields to update:
                         - product_name: Full name
                         - product_code: Unique code (must be unique)
                         - lob_id: Line of Business ID (must exist)
                         - active: Boolean status
            
        Returns:
            Updated product object with all fields.
            
        When to Use:
        - User says "update product", "change product", "modify product"
        - Need to correct product information or change LOB association
        """
        return await call_api("PUT", f"/products/{product_id}", json=product_data)


    @mcp.tool()
    async def delete_product(product_id: int) -> Dict[str, Any]:
        """
        Delete a product by its unique ID.
        
        Purpose:
        Permanently removes a product from the system. This is a destructive operation.
        Consider deactivating the product (update with active=False) instead of deleting.
        
        Args:
            product_id: The unique integer ID of the product to delete.
            
        Returns:
            Dictionary with success message and deleted flag, or error if not found.
            
        Warning:
        - This action is PERMANENT and CANNOT be undone
        - May affect related rating configurations
        - Consider deactivating (active=False) instead of deleting
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
        Get a list of US states with full details.
        
        Purpose:
        Retrieves US states from the system. States are used in rating configurations
        to specify geographic jurisdictions for insurance products. Rating factors,
        tables, and plans are often state-specific. Use this to browse states, search
        for specific ones, or filter by status.
        
        Usage Examples:
        - Get all active states: active=True, limit=100
        - Search for California: state_name="California" or state_name="CA"
        - Get all states: limit=100 (typically 50 US states)
        
        Args:
            skip: Number of records to skip for pagination (default: 0)
            limit: Maximum number of records to return (default: 100)
            active: Filter by active status (True/False/None). None returns all.
            state_name: Optional partial match filter for state name (case-insensitive)
            
        Returns:
            Dictionary with items list and count. Each state contains:
            id, state_code (2-letter code like 'NY', 'CA'), state_name, active.
            
        When to Use:
        - User asks to "list states", "show states", "get states"
        - Need to find a state by name or code
        - Setting up state-specific rating configurations
        """
        params = {"skip": skip, "limit": limit}
        active_bool = normalize_bool(active)
        if active_bool is not None:
            params["active"] = active_bool
        if state_name:
            params["state_name"] = state_name
        return await call_api("GET", "/states/", params=params)


    # @mcp.tool()
    # async def get_state(state_id: int) -> Dict[str, Any]:
    #     """
    #     Get detailed information about a specific state by its ID.
    #     
    #     Purpose:
    #     Retrieves complete details for a single US state. Use this when you have
    #     a state ID and need to verify its details or retrieve its information.
    #     
    #     Args:
    #         state_id: The unique integer ID of the state to retrieve.
    #         
    #     Returns:
    #         State object with fields: id, state_code (2-letter), state_name, active.
    #         
    #     When to Use:
    #     - User provides a state ID and asks for details
    #     - Need to verify state exists before creating rating configurations
    #     """
    #     return await call_api("GET", f"/states/{state_id}")


    @mcp.tool()
    async def create_state(state_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a new US state to the Ratings API.
        
        Purpose:
        Adds a new US state to the system. States are required for state-specific
        rating configurations. Typically, you'll add all 50 US states during initial
        system setup. State codes should follow standard 2-letter USPS codes.
        
        Usage Examples:
        - Create New York: state_data={"state_code": "NY", "state_name": "New York", "active": True}
        - Create California: state_data={"state_code": "CA", "state_name": "California"}
        
        Args:
            state_data: Dictionary containing:
                - state_code (str, required): 2-letter USPS state code (e.g., 'NY', 'CA', 'TX')
                - state_name (str, required): Full name (e.g., 'New York', 'California')
                - active (bool, optional): Initial active status (defaults to True)
                
        Returns:
            Created state object with all fields including auto-generated 'id'.
            
        When to Use:
        - User says "create state", "add state", "new state"
        - Initial system setup to add all US states
        - Adding territories or new jurisdictions
        
        Important Notes:
        - The 'id' is automatically generated
        - State code should be standard 2-letter USPS code
        - State code should be unique
        """
        return await call_api("POST", "/states/", json=state_data)


    @mcp.tool()
    async def update_state(state_id: int, state_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing state's details.
        
        Purpose:
        Modifies one or more fields of an existing state. Use this to change state name,
        update active status, or correct state information.
        
        Args:
            state_id: The unique integer ID of the state to update.
            state_data: Dictionary containing fields to update:
                       - state_name: Full name
                       - state_code: 2-letter code (must be unique)
                       - active: Boolean status
            
        Returns:
            Updated state object with all fields.
            
        When to Use:
        - User says "update state", "change state", "modify state"
        - Need to correct state information
        """
        return await call_api("PUT", f"/states/{state_id}", json=state_data)


    @mcp.tool()
    async def delete_state(state_id: int) -> Dict[str, Any]:
        """
        Remove a state from the system by its ID.
        
        Purpose:
        Permanently removes a state from the system. This is rarely used as states
        are typically permanent entities. Consider deactivating instead of deleting.
        
        Args:
            state_id: The unique integer ID of the state to delete.
            
        Returns:
            Dictionary with success message and deleted flag, or error if not found.
            
        Warning:
        - This action is PERMANENT and CANNOT be undone
        - May affect related rating configurations
        - Consider deactivating (active=False) instead of deleting
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
        Get a list of rating contexts with full details.
        
        Purpose:
        Retrieves rating contexts from the system. Contexts represent different business
        scenarios or transaction types for insurance rating (e.g., "New Business",
        "Renewal", "Endorsement", "Cancellation"). They are used in rating configurations
        to apply different rating rules based on the business context. Use this to browse
        contexts, search for specific ones, or filter by status.
        
        Usage Examples:
        - Get all active contexts: active=True, limit=100
        - Search for Renewal context: context_name="Renewal"
        - Get all contexts: limit=100
        
        Args:
            skip: Number of records to skip for pagination (default: 0)
            limit: Maximum number of records to return (default: 100)
            active: Filter by active status (True/False/None). None returns all.
            context_name: Optional partial match filter for context name (case-insensitive)
            
        Returns:
            Dictionary with items list and count. Each context contains:
            id, context_name, active, created_at, updated_at.
            
        When to Use:
        - User asks to "list contexts", "show contexts", "get contexts"
        - Need to find a context by name
        - Setting up rating configurations that require context selection
        """
        params = {"skip": skip, "limit": limit}
        active_bool = normalize_bool(active)
        if active_bool is not None:
            params["active"] = active_bool
        if context_name:
            params["context_name"] = context_name
        return await call_api("GET", "/contexts/", params=params)


    # @mcp.tool()
    # async def get_context(context_id: int) -> Dict[str, Any]:
    #     """
    #     Get detailed information about a specific context by its ID.
    #     
    #     Purpose:
    #     Retrieves complete details for a single rating context. Use this when you have
    #     a context ID and need to verify its details or retrieve its information.
    #     
    #     Args:
    #         context_id: The unique integer ID of the context to retrieve.
    #         
    #     Returns:
    #         Context object with fields: id, context_name, active, created_at, updated_at.
    #         
    #     When to Use:
    #     - User provides a context ID and asks for details
    #     - Need to verify context exists before creating rating configurations
    #     """
    #     return await call_api("GET", f"/contexts/{context_id}")


    @mcp.tool()
    async def create_context(context_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new rating context.
        
        Purpose:
        Adds a new rating context to the system. Contexts represent different business
        scenarios for insurance rating. Common contexts include "New Business", "Renewal",
        "Endorsement", "Cancellation", "Reinstatement", etc. They are used in rating
        configurations to apply context-specific rating rules and factors.
        
        Usage Examples:
        - Create New Business context: context_data={"context_name": "New Business", "active": True}
        - Create Renewal context: context_data={"context_name": "Renewal"}
        - Create Endorsement context: context_data={"context_name": "Endorsement"}
        
        Args:
            context_data: Dictionary containing:
                - context_name (str, required): Name of the context
                  Examples: 'New Business', 'Renewal', 'Endorsement', 'Cancellation'
                - active (bool, optional): Initial active status (defaults to True)
                
        Returns:
            Created context object with all fields including auto-generated 'id'.
            
        When to Use:
        - User says "create context", "add context", "new context"
        - Setting up rating contexts for different business scenarios
        - Adding new transaction types to the system
        
        Important Notes:
        - The 'id' is automatically generated
        - Context name should be descriptive and unique
        """
        return await call_api("POST", "/contexts/", json=context_data)


    @mcp.tool()
    async def update_context(context_id: int, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing context.
        
        Purpose:
        Modifies one or more fields of an existing context. Use this to change context name
        or update active status.
        
        Args:
            context_id: The unique integer ID of the context to update.
            context_data: Dictionary containing fields to update:
                         - context_name: Name of the context
                         - active: Boolean status
            
        Returns:
            Updated context object with all fields.
            
        When to Use:
        - User says "update context", "change context", "modify context"
        - Need to correct context information
        """
        return await call_api("PUT", f"/contexts/{context_id}", json=context_data)


    @mcp.tool()
    async def delete_context(context_id: int) -> Dict[str, Any]:
        """
        Delete a context by its unique ID.
        
        Purpose:
        Permanently removes a rating context from the system. This is a destructive operation.
        Consider deactivating the context (update with active=False) instead of deleting.
        
        Args:
            context_id: The unique integer ID of the context to delete.
            
        Returns:
            Dictionary with success message and deleted flag, or error if not found.
            
        Warning:
        - This action is PERMANENT and CANNOT be undone
        - May affect related rating configurations
        - Consider deactivating (active=False) instead of deleting
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
        
        Purpose:
        Retrieves rating tables from the system. Rating tables store the actual factors,
        rates, and multipliers used in premium calculations. They are scoped to specific
        combinations of Company, LOB, State, Product, and Context. Tables can be of
        different types (e.g., 'BASE', 'LOAD', 'FACTOR') and contain the lookup data
        needed by rating algorithms. Use this to browse tables, filter by various criteria,
        or find tables for specific rating configurations.
        
        Usage Examples:
        - Get tables for a company: company_id=1, limit=100
        - Find base rate tables: table_type="BASE", active=True
        - Get tables for Auto LOB in NY: lob_id=1, state_id=5 (NY)
        - Search by name: table_name="Base Rates"
        
        Args:
            skip: Number of records to skip for pagination (default: 0)
            limit: Maximum number of records to return (default: 100, max: 500)
            active: Filter by active status (True/False/None). None returns all.
            table_name: Optional partial match filter for table name (case-insensitive)
            table_type: Optional filter by table type (e.g., 'BASE', 'LOAD', 'FACTOR')
            company_id: Filter by company ID
            lob_id: Filter by Line of Business ID
            state_id: Filter by State ID
            product_id: Filter by Product ID
            context_id: Filter by Context ID
            
        Returns:
            Dictionary with items list and count. Each rating table contains:
            id, table_name, table_type, company_id, lob_id, state_id, product_id,
            context_id, description, active, created_at, updated_at.
            
        When to Use:
        - User asks to "list rating tables", "show tables", "get tables"
        - Need to find tables for a specific rating configuration
        - Setting up or reviewing rating data
        - Verifying table existence before creating rating plans
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
        """
        Get detailed information about a specific rating table by its ID.
        
        Purpose:
        Retrieves complete details for a single rating table. Use this when you have
        a rating table ID and need to verify its details, check its configuration,
        or retrieve its information for use in rating plans or calculations.
        
        Args:
            ratingtable_id: The unique integer ID of the rating table to retrieve.
            
        Returns:
            Rating table object with fields: id, table_name, table_type, company_id,
            lob_id, state_id, product_id, context_id, description, active,
            created_at, updated_at.
            
        When to Use:
        - User provides a rating table ID and asks for details
        - Need to verify table exists before creating rating manuals
        - Displaying table information in responses
        - Checking table configuration for rating calculations
        """
        return await call_api("GET", f"/ratingtables/{ratingtable_id}")


    @mcp.tool()
    async def create_ratingtable(ratingtable_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new rating table in the Ratings API.
        
        Purpose:
        Adds a new rating table to the system. Rating tables store the actual factors,
        rates, and multipliers used in premium calculations. They are scoped to specific
        combinations of Company, LOB, State, Product, and Context. Tables can be of
        different types (e.g., 'BASE' for base rates, 'LOAD' for load factors,
        'FACTOR' for rating factors). These tables are referenced by rating algorithms
        and used in premium calculations.
        
        Usage Examples:
        - Create base rate table: ratingtable_data={"table_name": "Base Rates NY Auto", "table_type": "BASE", "company_id": 1, "lob_id": 1, "state_id": 5, "product_id": 1, "context_id": 1, "description": "Base rates for NY Auto"}
        - Create load factor table: ratingtable_data={..., "table_type": "LOAD", "table_name": "Load Factors"}
        - Create rating factor table: ratingtable_data={..., "table_type": "FACTOR", "table_name": "Territory Factors"}
        
        Args:
            ratingtable_data: Dictionary containing:
                - table_name (str, required): Descriptive name (e.g., 'Base Rates NY Auto')
                - table_type (str, required): Type of table. Common types:
                  * 'BASE': Base rates/premiums
                  * 'LOAD': Load factors/multipliers
                  * 'FACTOR': Rating factors
                - company_id (int, required): ID of the company (must exist)
                - lob_id (int, required): ID of the Line of Business (must exist)
                - state_id (int, required): ID of the State (must exist)
                - product_id (int, required): ID of the Product (must exist)
                - context_id (int, required): ID of the Context (must exist)
                - description (str, optional): Detailed description of the table's purpose
                - active (bool, optional): Initial active status (defaults to True)
                
        Returns:
            Created rating table object with all fields including auto-generated 'id'.
            
        When to Use:
        - User says "create rating table", "add table", "new table"
        - Setting up rating data for specific company/LOB/state/product/context combinations
        - Creating lookup tables for rating algorithms
        
        Important Notes:
        - The 'id' is automatically generated
        - All referenced IDs (company, LOB, state, product, context) must exist
        - Table type should be descriptive and consistent
        - Tables are typically created before rating manuals and plans
        """
        return await call_api("POST", "/ratingtables/", json=ratingtable_data)


    @mcp.tool()
    async def update_ratingtable(ratingtable_id: int, ratingtable_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing rating table.
        
        Purpose:
        Modifies one or more fields of an existing rating table. Use this to change
        table name, update description, change active status, or correct table information.
        Note that changing scoping fields (company_id, lob_id, etc.) may affect related
        rating configurations.
        
        Args:
            ratingtable_id: The unique integer ID of the rating table to update.
            ratingtable_data: Dictionary containing fields to update:
                             - table_name: Name of the table
                             - table_type: Type of table (BASE, LOAD, FACTOR)
                             - description: Detailed description
                             - active: Boolean status
                             - company_id, lob_id, state_id, product_id, context_id:
                               Scoping fields (use with caution)
            
        Returns:
            Updated rating table object with all fields.
            
        When to Use:
        - User says "update rating table", "change table", "modify table"
        - Need to correct table information
        - Activating or deactivating a table
        - Updating table description
        
        Important Notes:
        - Changing scoping fields may affect related rating configurations
        - Only provide fields that need updating
        """
        return await call_api("PUT", f"/ratingtables/{ratingtable_id}", json=ratingtable_data)


    @mcp.tool()
    async def delete_ratingtable(ratingtable_id: int) -> Dict[str, Any]:
        """
        Delete a rating table by its unique ID.
        
        Purpose:
        Permanently removes a rating table from the system. This is a destructive operation.
        Consider deactivating the table (update with active=False) instead of deleting,
        as deletion may affect related rating manuals, plans, and calculations.
        
        Args:
            ratingtable_id: The unique integer ID of the rating table to delete.
            
        Returns:
            Dictionary with success message and deleted flag, or error if not found.
            
        When to Use:
        - User explicitly requests to "delete rating table", "remove table"
        - Data cleanup operations
        - Removing obsolete or incorrect tables
        
        Warning:
        - This action is PERMANENT and CANNOT be undone
        - May affect related rating manuals and plans that reference this table
        - Consider deactivating (active=False) instead of deleting
        - Always verify table ID and check for dependencies before deletion
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
        Get a list of rating algorithms with full details.
        
        Purpose:
        Retrieves rating algorithms from the system. Algorithms define the calculation
        logic and formulas used to compute insurance premiums. They are scoped to
        specific combinations of Company, LOB, State, and Product. Algorithms contain
        the business logic (often as formulas or pseudo-code) that reference rating
        tables and apply rating factors. They are used by rating plans to perform
        actual premium calculations. Use this to browse algorithms, filter by various
        criteria, or find algorithms for specific rating configurations.
        
        Usage Examples:
        - Get algorithms for a company: company_id=1, limit=100
        - Find algorithms for Auto LOB: lob_id=1, active=True
        - Search by name: algorithm_name="Standard Premium"
        - Get algorithms for NY Auto: state_id=5 (NY), lob_id=1 (Auto), product_id=1
        
        Args:
            skip: Number of records to skip for pagination (default: 0)
            limit: Maximum number of records to return (default: 100)
            active: Filter by active status (True/False/None). None returns all.
            algorithm_name: Optional partial match filter for algorithm name (case-insensitive)
            company_id: Filter by company ID
            lob_id: Filter by Line of Business ID
            state_id: Filter by State ID
            product_id: Filter by Product ID
            
        Returns:
            Dictionary with items list and count. Each algorithm contains:
            id, algorithm_name, company_id, lob_id, state_id, product_id, description,
            logic, active, created_at, updated_at.
            
        When to Use:
        - User asks to "list algorithms", "show algorithms", "get algorithms"
        - Need to find algorithms for a specific rating configuration
        - Setting up or reviewing rating calculation logic
        - Verifying algorithm exists before creating rating plans
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
        """
        Get detailed information about a specific algorithm by its ID.
        
        Purpose:
        Retrieves complete details for a single rating algorithm, including its
        calculation logic. Use this when you have an algorithm ID and need to verify
        its details, review its logic, or retrieve its information for use in rating plans.
        
        Args:
            algorithm_id: The unique integer ID of the algorithm to retrieve.
            
        Returns:
            Algorithm object with fields: id, algorithm_name, company_id, lob_id,
            state_id, product_id, description, logic (calculation logic/pseudo-code),
            active, created_at, updated_at.
            
        When to Use:
        - User provides an algorithm ID and asks for details
        - Need to review algorithm logic before using in rating plans
        - Displaying algorithm information in responses
        - Verifying algorithm configuration
        """
        return await call_api("GET", f"/algorithms/{algorithm_id}")


    @mcp.tool()
    async def create_algorithm(algorithm_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new rating algorithm.
        
        Purpose:
        Adds a new rating algorithm to the system. Algorithms define the calculation
        logic and formulas used to compute insurance premiums. They are scoped to
        specific combinations of Company, LOB, State, and Product. The algorithm's
        logic field typically contains formulas, pseudo-code, or descriptions of the
        calculation steps. Algorithms reference rating tables and apply factors to
        calculate premiums. They are used by rating plans to perform actual premium
        calculations.
        
        Usage Examples:
        - Create standard premium algorithm: algorithm_data={"algorithm_name": "Standard Premium Calc", "company_id": 1, "lob_id": 1, "state_id": 5, "product_id": 1, "description": "Standard premium calculation", "logic": "base_rate * territory_factor * age_factor"}
        - Create with detailed logic: algorithm_data={..., "logic": "Step 1: Get base rate from table. Step 2: Apply territory factor. Step 3: Apply age factor. Step 4: Apply discounts."}
        
        Args:
            algorithm_data: Dictionary containing:
                - algorithm_name (str, required): Descriptive name (e.g., 'Standard Premium Calculation')
                - company_id (int, required): ID of the company (must exist)
                - lob_id (int, required): ID of the Line of Business (must exist)
                - state_id (int, required): ID of the State (must exist)
                - product_id (int, required): ID of the Product (must exist)
                - description (str, optional): Description of what the algorithm does
                - logic (str, optional): Calculation logic, formula, or pseudo-code.
                  Can reference rating tables, factors, and use mathematical expressions.
                  Example: "base_rate * state_factor * hazard_factor"
                - active (bool, optional): Initial active status (defaults to True)
                
        Returns:
            Created algorithm object with all fields including auto-generated 'id'.
            
        When to Use:
        - User says "create algorithm", "add algorithm", "new algorithm"
        - Setting up rating calculation logic for specific configurations
        - Defining premium calculation formulas
        - Creating algorithms before rating plans
        
        Important Notes:
        - The 'id' is automatically generated
        - All referenced IDs (company, LOB, state, product) must exist
        - Logic can reference variables, tables, and use mathematical expressions
        - Algorithms are typically created before rating plans
        - Consider using evaluate_expression tool to test algorithm logic
        """
        return await call_api("POST", "/algorithms/", json=algorithm_data)


    @mcp.tool()
    async def update_algorithm(algorithm_id: int, algorithm_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing algorithm.
        
        Purpose:
        Modifies one or more fields of an existing algorithm. Use this to change
        algorithm name, update calculation logic, modify description, change active
        status, or correct algorithm information. Note that changing scoping fields
        (company_id, lob_id, etc.) may affect related rating plans.
        
        Args:
            algorithm_id: The unique integer ID of the algorithm to update.
            algorithm_data: Dictionary containing fields to update:
                           - algorithm_name: Name of the algorithm
                           - description: Description of what the algorithm does
                           - logic: Calculation logic, formula, or pseudo-code
                           - active: Boolean status
                           - company_id, lob_id, state_id, product_id:
                             Scoping fields (use with caution)
            
        Returns:
            Updated algorithm object with all fields.
            
        When to Use:
        - User says "update algorithm", "change algorithm", "modify algorithm"
        - Need to correct algorithm information or update calculation logic
        - Activating or deactivating an algorithm
        - Refining algorithm formulas
        
        Important Notes:
        - Changing scoping fields may affect related rating plans
        - Updating logic may change premium calculation results
        - Only provide fields that need updating
        - Test updated logic before activating
        """
        return await call_api("PUT", f"/algorithms/{algorithm_id}", json=algorithm_data)


    @mcp.tool()
    async def delete_algorithm(algorithm_id: int) -> Dict[str, Any]:
        """
        Delete an algorithm by its unique ID.
        
        Purpose:
        Permanently removes a rating algorithm from the system. This is a destructive
        operation. Consider deactivating the algorithm (update with active=False)
        instead of deleting, as deletion may affect related rating plans that use
        this algorithm.
        
        Args:
            algorithm_id: The unique integer ID of the algorithm to delete.
            
        Returns:
            Dictionary with success message and deleted flag, or error if not found.
            
        When to Use:
        - User explicitly requests to "delete algorithm", "remove algorithm"
        - Data cleanup operations
        - Removing obsolete or incorrect algorithms
        
        Warning:
        - This action is PERMANENT and CANNOT be undone
        - May affect related rating plans that reference this algorithm
        - Consider deactivating (active=False) instead of deleting
        - Always verify algorithm ID and check for dependencies before deletion
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
        
        Purpose:
        Retrieves rating manuals from the system. Rating manuals are collections of
        rating tables and configurations organized for specific Company/LOB/State/Product
        combinations. They serve as the authoritative source of rating data and are
        versioned with effective and expiration dates. Manuals reference rating tables
        and are used to organize rating data for specific jurisdictions and products.
        Use this to browse manuals, filter by various criteria, or find manuals for
        specific rating configurations.
        
        Usage Examples:
        - Get manuals for a company: company_id=1, limit=100
        - Find active manuals: active=True, effective_date="2024-01-01"
        - Get manuals for NY Auto: state_id=5 (NY), lob_id=1 (Auto)
        - Find manuals using a specific table: ratingtable_id=10
        - Get current manuals: effective_date="2024-12-01" (current date)
        
        Args:
            skip: Number of records to skip for pagination (default: 0)
            limit: Maximum number of records to return (default: 100, max: 500)
            active: Filter by active status (True/False/None). None returns all.
            manual_name: Optional partial match filter for manual name (case-insensitive)
            company_id: Filter by company ID
            lob_id: Filter by Line of Business ID
            state_id: Filter by State ID
            product_id: Filter by Product ID
            ratingtable_id: Filter by rating table ID (manuals that reference this table)
            effective_date: Optional filter by effective date (YYYY-MM-DD format).
                          Returns manuals effective on or before this date.
            
        Returns:
            Dictionary with items list and count. Each rating manual contains:
            id, manual_name, company_id, lob_id, state_id, product_id, ratingtable_id,
            effective_date, expiration_date, active, created_at, updated_at.
            
        When to Use:
        - User asks to "list rating manuals", "show manuals", "get manuals"
        - Need to find manuals for a specific rating configuration
        - Setting up or reviewing rating data organization
        - Finding current or historical rating manuals
        - Verifying manual existence before creating rating plans
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
        """
        Get detailed information about a specific rating manual by its ID.
        
        Purpose:
        Retrieves complete details for a single rating manual, including its effective
        dates and associated rating table. Use this when you have a rating manual ID
        and need to verify its details, check its effective dates, or retrieve its
        information for use in rating plans.
        
        Args:
            ratingmanual_id: The unique integer ID of the rating manual to retrieve.
            
        Returns:
            Rating manual object with fields: id, manual_name, company_id, lob_id,
            state_id, product_id, ratingtable_id, effective_date, expiration_date,
            active, created_at, updated_at.
            
        When to Use:
        - User provides a rating manual ID and asks for details
        - Need to verify manual exists and check effective dates
        - Displaying manual information in responses
        - Verifying manual configuration before creating rating plans
        """
        return await call_api("GET", f"/ratingmanuals/{ratingmanual_id}")


    @mcp.tool()
    async def create_ratingmanual(ratingmanual_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new rating manual.
        
        Purpose:
        Adds a new rating manual to the system. Rating manuals are collections of
        rating tables and configurations organized for specific Company/LOB/State/Product
        combinations. They serve as the authoritative source of rating data and are
        versioned with effective and expiration dates. Manuals reference a primary
        rating table and organize rating data for specific jurisdictions and products.
        They are used to manage different versions of rating data over time.
        
        Usage Examples:
        - Create manual for NY Auto: ratingmanual_data={"manual_name": "NY Auto Manual 2024", "company_id": 1, "lob_id": 1, "state_id": 5, "product_id": 1, "ratingtable_id": 10, "effective_date": "2024-01-01", "active": True}
        - Create with expiration: ratingmanual_data={..., "expiration_date": "2024-12-31"}
        - Create future-dated manual: ratingmanual_data={..., "effective_date": "2025-01-01"}
        
        Args:
            ratingmanual_data: Dictionary containing:
                - manual_name (str, required): Descriptive name (e.g., 'NY Auto Manual 2024')
                - company_id (int, required): ID of the company (must exist)
                - lob_id (int, required): ID of the Line of Business (must exist)
                - state_id (int, required): ID of the State (must exist)
                - product_id (int, required): ID of the Product (must exist)
                - ratingtable_id (int, required): ID of the primary rating table (must exist)
                - effective_date (str, required): Date when manual becomes active (YYYY-MM-DD format)
                - expiration_date (str, optional): Date when manual expires (YYYY-MM-DD format).
                                                If not provided, manual has no expiration.
                - active (bool, optional): Initial active status (defaults to True)
                
        Returns:
            Created rating manual object with all fields including auto-generated 'id'.
            
        When to Use:
        - User says "create rating manual", "add manual", "new manual"
        - Setting up rating data organization for specific configurations
        - Creating versioned rating data (e.g., annual updates)
        - Organizing rating tables into manuals
        
        Important Notes:
        - The 'id' is automatically generated
        - All referenced IDs (company, LOB, state, product, ratingtable) must exist
        - Effective date should be in YYYY-MM-DD format
        - Manuals are typically created after rating tables
        - Use expiration_date to manage manual versions over time
        """
        return await call_api("POST", "/ratingmanuals/", json=ratingmanual_data)


    @mcp.tool()
    async def update_ratingmanual(ratingmanual_id: int, ratingmanual_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing rating manual.
        
        Purpose:
        Modifies one or more fields of an existing rating manual. Use this to change
        manual name, update effective/expiration dates, change active status, update
        rating table reference, or correct manual information. Note that changing
        scoping fields (company_id, lob_id, etc.) may affect related rating plans.
        
        Args:
            ratingmanual_id: The unique integer ID of the rating manual to update.
            ratingmanual_data: Dictionary containing fields to update:
                              - manual_name: Name of the manual
                              - ratingtable_id: Primary rating table ID (must exist)
                              - effective_date: Effective date (YYYY-MM-DD)
                              - expiration_date: Expiration date (YYYY-MM-DD)
                              - active: Boolean status
                              - company_id, lob_id, state_id, product_id:
                                Scoping fields (use with caution)
            
        Returns:
            Updated rating manual object with all fields.
            
        When to Use:
        - User says "update rating manual", "change manual", "modify manual"
        - Need to correct manual information or update dates
        - Extending expiration dates
        - Activating or deactivating a manual
        
        Important Notes:
        - Changing scoping fields may affect related rating plans
        - Updating effective/expiration dates may change which manual is current
        - Only provide fields that need updating
        - Date format must be YYYY-MM-DD
        """
        return await call_api("PUT", f"/ratingmanuals/{ratingmanual_id}", json=ratingmanual_data)


    @mcp.tool()
    async def delete_ratingmanual(ratingmanual_id: int) -> Dict[str, Any]:
        """
        Delete a rating manual by its unique ID.
        
        Purpose:
        Permanently removes a rating manual from the system. This is a destructive
        operation. Consider deactivating the manual (update with active=False) instead
        of deleting, as deletion may affect related rating plans that reference this manual.
        
        Args:
            ratingmanual_id: The unique integer ID of the rating manual to delete.
            
        Returns:
            Dictionary with success message and deleted flag, or error if not found.
            
        When to Use:
        - User explicitly requests to "delete rating manual", "remove manual"
        - Data cleanup operations
        - Removing obsolete or incorrect manuals
        
        Warning:
        - This action is PERMANENT and CANNOT be undone
        - May affect related rating plans that reference this manual
        - Consider deactivating (active=False) instead of deleting
        - Always verify manual ID and check for dependencies before deletion
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
        
        Purpose:
        Retrieves rating plans from the system. Rating plans are the top-level
        configuration that ties together all rating components (Company, LOB, State,
        Product, Algorithm) to create a complete rating solution. Plans are versioned
        with effective and expiration dates and reference algorithms that perform the
        actual premium calculations. They represent the complete rating configuration
        for a specific jurisdiction and product. Use this to browse plans, filter by
        various criteria, or find plans for specific rating configurations.
        
        Usage Examples:
        - Get plans for a company: company_id=1, limit=100
        - Find active plans: active=True, effective_date="2024-12-01"
        - Get plans for NY Auto: state_id=5 (NY), lob_id=1 (Auto)
        - Find plans using a specific algorithm: algorithm_id=10
        - Get current plans: effective_date="2024-12-01" (current date)
        
        Args:
            skip: Number of records to skip for pagination (default: 0)
            limit: Maximum number of records to return (default: 100, max: 500)
            active: Filter by active status (True/False/None). None returns all.
            plan_name: Optional partial match filter for plan name (case-insensitive)
            company_id: Filter by company ID
            lob_id: Filter by Line of Business ID
            state_id: Filter by State ID
            product_id: Filter by Product ID
            algorithm_id: Filter by algorithm ID (plans that use this algorithm)
            effective_date: Optional filter by effective date (YYYY-MM-DD format).
                          Returns plans effective on or before this date.
            
        Returns:
            Dictionary with items list and count. Each rating plan contains:
            id, plan_name, company_id, lob_id, state_id, product_id, algorithm_id,
            effective_date, expiration_date, active, created_at, updated_at.
            
        When to Use:
        - User asks to "list rating plans", "show plans", "get plans"
        - Need to find plans for a specific rating configuration
        - Setting up or reviewing complete rating solutions
        - Finding current or historical rating plans
        - Verifying plan existence for premium calculations
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
        """
        Get detailed information about a specific rating plan by its ID.
        
        Purpose:
        Retrieves complete details for a single rating plan, including its effective
        dates and associated algorithm. Use this when you have a rating plan ID and
        need to verify its details, check its effective dates, or retrieve its
        information for premium calculations.
        
        Args:
            ratingplan_id: The unique integer ID of the rating plan to retrieve.
            
        Returns:
            Rating plan object with fields: id, plan_name, company_id, lob_id,
            state_id, product_id, algorithm_id, effective_date, expiration_date,
            active, created_at, updated_at.
            
        When to Use:
        - User provides a rating plan ID and asks for details
        - Need to verify plan exists and check effective dates
        - Displaying plan information in responses
        - Verifying plan configuration before premium calculations
        """
        return await call_api("GET", f"/ratingplans/{ratingplan_id}")


    @mcp.tool()
    async def create_ratingplan(ratingplan_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new rating plan.
        
        Purpose:
        Adds a new rating plan to the system. Rating plans are the top-level
        configuration that ties together all rating components (Company, LOB, State,
        Product, Algorithm) to create a complete rating solution. Plans are versioned
        with effective and expiration dates and reference algorithms that perform the
        actual premium calculations. They represent the complete rating configuration
        for a specific jurisdiction and product. Plans are the final piece needed to
        perform premium calculations.
        
        Usage Examples:
        - Create plan for NY Auto: ratingplan_data={"plan_name": "NY Auto Plan 2024", "company_id": 1, "lob_id": 1, "state_id": 5, "product_id": 1, "algorithm_id": 10, "effective_date": "2024-01-01", "active": True}
        - Create with expiration: ratingplan_data={..., "expiration_date": "2024-12-31"}
        - Create future-dated plan: ratingplan_data={..., "effective_date": "2025-01-01"}
        
        Args:
            ratingplan_data: Dictionary containing:
                - plan_name (str, required): Descriptive name (e.g., 'NY Auto Plan 2024')
                - company_id (int, required): ID of the company (must exist)
                - lob_id (int, required): ID of the Line of Business (must exist)
                - state_id (int, required): ID of the State (must exist)
                - product_id (int, required): ID of the Product (must exist)
                - algorithm_id (int, required): ID of the algorithm to use (must exist)
                - effective_date (str, required): Date when plan becomes active (YYYY-MM-DD format)
                - expiration_date (str, optional): Date when plan expires (YYYY-MM-DD format).
                                                If not provided, plan has no expiration.
                - active (bool, optional): Initial active status (defaults to True)
                
        Returns:
            Created rating plan object with all fields including auto-generated 'id'.
            
        When to Use:
        - User says "create rating plan", "add plan", "new plan"
        - Setting up complete rating solutions for specific configurations
        - Creating versioned rating plans (e.g., annual updates)
        - Finalizing rating configuration after creating all components
        
        Important Notes:
        - The 'id' is automatically generated
        - All referenced IDs (company, LOB, state, product, algorithm) must exist
        - Algorithm must be created before the plan
        - Effective date should be in YYYY-MM-DD format
        - Plans are typically created after all other components (tables, algorithms, manuals)
        - Use expiration_date to manage plan versions over time
        - A plan is required to perform premium calculations
        """
        return await call_api("POST", "/ratingplans/", json=ratingplan_data)


    @mcp.tool()
    async def update_ratingplan(ratingplan_id: int, ratingplan_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing rating plan.
        
        Purpose:
        Modifies one or more fields of an existing rating plan. Use this to change
        plan name, update effective/expiration dates, change active status, update
        algorithm reference, or correct plan information. Note that changing scoping
        fields (company_id, lob_id, etc.) or algorithm_id may significantly affect
        premium calculations.
        
        Args:
            ratingplan_id: The unique integer ID of the rating plan to update.
            ratingplan_data: Dictionary containing fields to update:
                            - plan_name: Name of the plan
                            - algorithm_id: Algorithm ID (must exist, use with caution)
                            - effective_date: Effective date (YYYY-MM-DD)
                            - expiration_date: Expiration date (YYYY-MM-DD)
                            - active: Boolean status
                            - company_id, lob_id, state_id, product_id:
                              Scoping fields (use with extreme caution)
            
        Returns:
            Updated rating plan object with all fields.
            
        When to Use:
        - User says "update rating plan", "change plan", "modify plan"
        - Need to correct plan information or update dates
        - Extending expiration dates
        - Activating or deactivating a plan
        - Updating algorithm reference (rare, may affect calculations)
        
        Important Notes:
        - Changing scoping fields or algorithm_id may significantly affect premium calculations
        - Updating effective/expiration dates may change which plan is current
        - Only provide fields that need updating
        - Date format must be YYYY-MM-DD
        - Test plan after updating algorithm_id
        """
        return await call_api("PUT", f"/ratingplans/{ratingplan_id}", json=ratingplan_data)


    @mcp.tool()
    async def delete_ratingplan(ratingplan_id: int) -> Dict[str, Any]:
        """
        Delete a rating plan by its unique ID.
        
        Purpose:
        Permanently removes a rating plan from the system. This is a destructive
        operation. Consider deactivating the plan (update with active=False) instead
        of deleting, as deletion may affect premium calculations and historical data.
        
        Args:
            ratingplan_id: The unique integer ID of the rating plan to delete.
            
        Returns:
            Dictionary with success message and deleted flag, or error if not found.
            
        When to Use:
        - User explicitly requests to "delete rating plan", "remove plan"
        - Data cleanup operations
        - Removing obsolete or incorrect plans
        
        Warning:
        - This action is PERMANENT and CANNOT be undone
        - May affect premium calculations and historical data
        - Consider deactivating (active=False) instead of deleting
        - Always verify plan ID and check for dependencies before deletion
        - Deletion may impact active rating operations
        """
        return await call_api("DELETE", f"/ratingplans/{ratingplan_id}")


    # Health check
    @mcp.tool()
    async def health_check() -> Dict[str, Any]:
        """
        Check the connectivity and operational status of the Ratings API and its MongoDB database.
        
        Purpose:
        Verifies that the Ratings API service and its MongoDB database are operational.
        This is a diagnostic tool that checks system health, database connectivity,
        and service availability. Use this to troubleshoot issues, verify system status,
        or perform health monitoring.
        
        Usage Examples:
        - Check system health: health_check()
        - Verify before critical operations: Check health before bulk data operations
        - Monitor system status: Regular health checks for system monitoring
        
        Returns:
            Dictionary containing:
            - status: "healthy" if all services are up, "degraded" if database is down
            - database: "connected" or "disconnected" indicating MongoDB connection status
            
        When to Use:
        - User asks about "system status", "health", "is the system working"
        - Troubleshooting connection issues
        - Verifying system is ready before operations
        - System monitoring and diagnostics
        
        Important Notes:
        - Returns HTTP 200 if healthy, HTTP 503 if degraded
        - Checks both API service and MongoDB database connectivity
        - Useful for automated monitoring and alerting
        """
        return await call_api("GET", "/health")

    @mcp.tool()
    async def evaluate_expression(
        expression: str,
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate a mathematical expression using variables provided in the payload.
        
        Purpose:
        This tool evaluates mathematical formulas and expressions commonly used in insurance
        rating calculations. It supports arithmetic operations, mathematical functions,
        and custom variables. This is particularly useful for calculating premiums, factors,
        and other rating-related computations.
        
        Payload Format:
        The tool accepts two parameters:
        - expression: A string containing the mathematical formula to evaluate
        - variables: A dictionary where keys are variable names and values are their numeric values
        
        Supported Operations:
        - Arithmetic: +, -, *, /, ** (power), % (modulo)
        - Functions: MAX, MIN, ABS, ROUND, SQRT, SIN, COS, TAN, LOG, LOG10, EXP, CEIL, FLOOR, POW, SUM
        - Constants: PI, E
        - Both lowercase and uppercase function names are supported (e.g., max, MAX, Min, MIN)
        
        Example Usage:
        Expression: "MAX((base_rate * state_factor * hazard_factor), minimum_premium)"
        Variables: {
            "base_rate": 1000.0,
            "state_factor": 1.25,
            "hazard_factor": 1.15,
            "minimum_premium": 500.0
        }
        
        Another Example:
        Expression: "(x + y) * multiplier + sqrt(100)"
        Variables: {
            "x": 10,
            "y": 20,
            "multiplier": 1.5
        }
        
        Args:
            expression: The mathematical formula to evaluate. Can include variables, functions,
                       and constants. Example: "MAX(x * y, min_value)" or "sqrt(area) * factor"
            variables: Dictionary of variable names (keys) and their numeric values.
                     Variable names must match those used in the expression.
                     Example: {"x": 10, "y": 5, "min_value": 20}
        
        Returns:
            Dictionary containing:
            - result: The numeric result of the evaluation
            - expression: The expression that was evaluated
            - variables: The variables that were used
            - status: "success" or "error"
            - error: Error message (only if status is "error")
        
        Use Cases:
        - Calculate insurance premiums using rating formulas
        - Evaluate rating factors and multipliers
        - Compute complex mathematical expressions with multiple variables
        - Apply minimum/maximum constraints to calculations
        - Perform statistical calculations for rating algorithms
        """
        try:
            logger.info(f"MCP tool: Evaluating expression '{expression}' with variables {variables}")
            result = evaluate_expression_service.evaluate(expression, variables)
            return {
                "result": result,
                "expression": expression,
                "variables": variables,
                "status": "success"
            }
        except ValueError as e:
            logger.error(f"MCP tool: Evaluation error - {e}")
            return {
                "error": str(e),
                "expression": expression,
                "variables": variables,
                "status": "error"
            }
        except Exception as e:
            logger.error(f"MCP tool: Unexpected error - {e}")
            return {
                "error": f"Unexpected error: {str(e)}",
                "expression": expression,
                "variables": variables,
                "status": "error"
            }

    # After all tools are registered, populate TOOL_REGISTRY
    # Use globals() to get all functions defined in this module
    # This allows HTTP endpoints to access tools even if _tools is not populated at runtime
    import sys
    current_module = sys.modules[__name__]
    known_tool_names = [
        'get_companies', 'create_company', 'update_company', 'delete_company',
        # 'get_company',  # Commented out - not in tools list
        'get_lobs', 'create_lob', 'update_lob', 'delete_lob',
        # 'get_lob',  # Commented out
        'get_products', 'create_product', 'update_product', 'delete_product',
        # 'get_product',  # Commented out
        'get_states', 'create_state', 'update_state', 'delete_state',
        # 'get_state',  # Commented out
        'get_contexts', 'create_context', 'update_context', 'delete_context',
        # 'get_context',  # Commented out
        'get_ratingtables', 'get_ratingtable', 'create_ratingtable', 'update_ratingtable', 'delete_ratingtable',
        'get_algorithms', 'get_algorithm', 'create_algorithm', 'update_algorithm', 'delete_algorithm',
        'get_ratingmanuals', 'get_ratingmanual', 'create_ratingmanual', 'update_ratingmanual', 'delete_ratingmanual',
        'get_ratingplans', 'get_ratingplan', 'create_ratingplan', 'update_ratingplan', 'delete_ratingplan',
        'health_check', 'evaluate_expression'
    ]
    for tool_name in known_tool_names:
        if tool_name in globals():
            tool_func = globals()[tool_name]
            if callable(tool_func):
                TOOL_REGISTRY[tool_name] = tool_func

# Export the MCP server instance and tool registry
__all__ = ["mcp", "client", "MCP_AVAILABLE", "call_api", "TOOL_REGISTRY"]

