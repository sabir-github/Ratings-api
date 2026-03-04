"""
MCP Server implementation for Ratings API
Exposes all existing API endpoints as MCP tools for AI model interaction
"""
import httpx
from typing import Any, Dict, List, Optional, Union
import logging
import os
from app.core.config import settings

# Import services for direct calls (more efficient than HTTP, avoids internal HTTP/auth issues)
from app.services.company_service import company_service
from app.services.evaluate_expression import evaluate_expression as evaluate_expression_service
from app.schemas.company import CompanyCreateSchema, CompanyUpdateSchema
from app.schemas.calculation import CalculationRequest
from app.core.database import get_database

try:
    from app.services.ratingplan_service import ratingplan_service as _ratingplan_service
except ImportError:
    _ratingplan_service = None

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


def _safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """Coerce value to int for API params; handle Gemini string IDs. Returns default if invalid."""
    if value is None:
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default

def _normalize_query_params(params: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Ensure query params are API-friendly: booleans as lowercase 'true'/'false' (FastAPI expects this)."""
    if params is None:
        return None
    out = {}
    for k, v in params.items():
        if isinstance(v, bool):
            out[k] = "true" if v else "false"
        else:
            out[k] = v
    return out


# Helper function to make API calls with performance optimizations
async def call_api(method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
    """Make an API call and return the response with optimized error handling"""
    try:
        if "params" in kwargs and kwargs["params"]:
            kwargs["params"] = _normalize_query_params(kwargs["params"])
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
        company_name: Optional[str] = None,
        company_code: Optional[str] = None,
        tax_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List insurance companies. Use when user asks to list companies, find company by name, code, or tax ID, or filter by active. Returns items (id, company_code, company_name, active, hq_address, tax_id) and count.
        
        Purpose:
        Retrieves insurance companies from the system. Companies are the top-level entities
        in the ratings hierarchy and represent insurance carriers or organizations that
        provide insurance products. Use this tool to browse, search, or filter companies by name,
        code, or tax ID when setting up rating configurations or managing company data.
        
        Usage Examples:
        - Get all active companies: active=True, limit=100
        - Search for a specific company: company_name="Global Insurance"
        - Search by company code: company_code="GLOB"
        - Search by tax ID: tax_id="12-3456789"
        - Get inactive companies: active=False
        - Paginate through companies: skip=100, limit=50
        
        Args:
            skip: Number of records to skip for pagination (default: 0)
            limit: Maximum number of records to return (default: 100, max: 1000)
            active: Filter by active status (True/False/None). None returns all.
            company_name: Optional partial match filter for company name (case-insensitive)
            company_code: Optional partial match filter for company code (case-insensitive)
            tax_id: Optional partial match filter for tax ID (case-insensitive)
            
        Returns:
            Dictionary with:
            - items: List of company objects, each containing:
              * id: Unique integer identifier
              * company_code: Short code (e.g., 'ABC', 'GLOB')
              * company_name: Full legal name
              * active: Boolean indicating if company is active
              * hq_address: Structured address object (optional) - Street1, Street2, City, State_Province, PostalCode, CountryCode
              * tax_id: Primary tax identification number for the parent group (optional)
              * created_at: Timestamp of creation
              * updated_at: Timestamp of last update
            - count: Number of items returned
            
        When to Use:
        - User asks to "list companies", "show all companies", "get companies"
        - Need to find a company by name, code, or tax ID
        - Setting up rating configurations that require company selection
        - Verifying company exists before creating related entities (LOBs, products, etc.)
        """
        params = {"skip": skip, "limit": limit}
        active_bool = normalize_bool(active)
        if active_bool is not None:
            params["active"] = active_bool
        if company_name:
            params["company_name"] = company_name
        if company_code:
            params["company_code"] = company_code
        if tax_id:
            params["tax_id"] = tax_id
        return await call_api("GET", "/companies/", params=params)

    @mcp.tool()
    async def get_legal_entities(
        skip: int = 0,
        limit: int = 100,
        active: Union[bool, str, None] = None,
        company_id: Optional[int] = None,
        legal_name: Optional[str] = None,
        entity_type: Optional[str] = None,
        jurisdiction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List legal entities. Use when user asks for legal entities, entities by company, or to find entities by name/type/jurisdiction. Returns items and count.

        Legal entities are registered entities that enter into legal contracts and hold insurance licenses.
        Each entity links to a parent Company. Returns: id, company_id, legal_name, entity_type,
        identifier (LEI), jurisdiction, registration_number, active, created_at, updated_at.

        Args:
            skip: Pagination offset (default: 0)
            limit: Max records to return (default: 100, max: 1000)
            active: Filter by active status (True/False/None)
            company_id: Filter by parent company ID
            legal_name: Partial match filter for legal name
            entity_type: Partial match for entity type (Corporation, Partnership, Trust, etc.)
            jurisdiction: Partial match for jurisdiction (state/country of registration)
        """
        params = {"skip": skip, "limit": limit}
        active_bool = normalize_bool(active)
        if active_bool is not None:
            params["active"] = active_bool
        if company_id is not None:
            params["company_id"] = int(company_id)
        if legal_name:
            params["legal_name"] = legal_name
        if entity_type:
            params["entity_type"] = entity_type
        if jurisdiction:
            params["jurisdiction"] = jurisdiction
        return await call_api("GET", "/legal-entities/", params=params)

    @mcp.tool()
    async def get_legal_entity_addresses(
        skip: int = 0,
        limit: int = 100,
        legal_entity_id: Optional[int] = None,
        address_type: Optional[str] = None,
        city: Optional[str] = None,
        country_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List legal entity addresses. Use when user asks for addresses of a legal entity, or addresses by type (Registered, Physical, Mailing). Returns items and count.

        Addresses can be Registered, Physical, or Mailing. Each address has full_address (string) and/or
        broken-down components (street1, street2, city, state_province, postal_code, country_code).

        Args:
            skip: Pagination offset (default: 0)
            limit: Max records to return (default: 100, max: 1000)
            legal_entity_id: Filter by legal entity ID
            address_type: Partial match for type (Registered, Physical, Mailing)
            city: Partial match for city
            country_code: Partial match for country code
        """
        params = {"skip": skip, "limit": limit}
        if legal_entity_id is not None:
            params["legal_entity_id"] = int(legal_entity_id)
        if address_type:
            params["address_type"] = address_type
        if city:
            params["city"] = city
        if country_code:
            params["country_code"] = country_code
        return await call_api("GET", "/legal-entity-addresses/", params=params)

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
    #         - hq_address: Structured address (Street1, Street2, City, State_Province, PostalCode, CountryCode) (optional)
    #         - tax_id: Primary tax identification number for the parent group (optional)
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

    # @mcp.tool()
    # async def create_company(
    #     company_code: str,
    #     company_name: str,
    #     active: bool = True
    # ) -> Dict[str, Any]:
    #     """Create a new insurance company. (Commented out - create/update/delete disabled.)"""
    #     return {"error": "create_company is disabled", "status_code": 403}

    # @mcp.tool()  # create/update/delete disabled
    # async def update_company(company_id: int, company_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Update company. (Commented out.)"""
    #     return {"error": "update_company is disabled", "status_code": 403}

    # @mcp.tool()  # create/update/delete disabled
    # async def delete_company(company_id: int) -> Dict[str, Any]:
    #     """Delete company. (Commented out.)"""
    #     return {"error": "delete_company is disabled", "status_code": 403}

    # LOBs endpoints
    @mcp.tool()
    async def get_lobs(
        skip: int = 0,
        limit: int = 100,
        active: Union[bool, str, None] = None,
        lob_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List lines of business (LOBs). Use when user asks for LOBs, lines of business, or to filter by company. Returns items (id, lob_code, lob_name, active) and count.
        
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
        try:
            # Coerce types in case Gemini sends strings or omits args
            skip_val = int(skip) if skip is not None else 0
            limit_val = min(int(limit) if limit is not None else 100, 1000)
            params = {"skip": skip_val, "limit": limit_val}
            active_bool = normalize_bool(active)
            if active_bool is not None:
                params["active"] = active_bool
            if lob_name is not None and str(lob_name).strip():
                params["lob_name"] = str(lob_name).strip()
            result = await call_api("GET", "/lobs/", params=params)
            return result
        except (TypeError, ValueError) as e:
            logger.warning(f"get_lobs argument error: {e}")
            return {"error": f"Invalid arguments: {e}", "status_code": 400}
        except Exception as e:
            logger.error(f"get_lobs failed: {e}", exc_info=True)
            return {"error": str(e), "status_code": 500}


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


    # @mcp.tool()  # create/update/delete disabled
    # async def create_lob(lob_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Create LOB. (Commented out.)"""
    #     return {"error": "create_lob is disabled", "status_code": 403}

    # @mcp.tool()  # create/update/delete disabled
    # async def update_lob(lob_id: int, lob_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Update LOB. (Commented out.)"""
    #     return {"error": "update_lob is disabled", "status_code": 403}

    # @mcp.tool()  # create/update/delete disabled
    # async def delete_lob(lob_id: int) -> Dict[str, Any]:
    #     """Delete LOB. (Commented out.)"""
    #     return {"error": "delete_lob is disabled", "status_code": 403}

    # Products endpoints
    @mcp.tool()
    async def get_products(
        skip: int = 0,
        limit: int = 100,
        active: Union[bool, str, None] = None,
        product_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List insurance products. Use when user asks for products or to filter by company/LOB. Returns items (id, product_code, product_name, lob_id, active) and count.
        
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


    # @mcp.tool()  # create/update/delete disabled
    # async def create_product(product_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Create product. (Commented out.)"""
    #     return {"error": "create_product is disabled", "status_code": 403}

    # @mcp.tool()  # create/update/delete disabled
    # async def update_product(product_id: int, product_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Update product. (Commented out.)"""
    #     return {"error": "update_product is disabled", "status_code": 403}

    # @mcp.tool()  # create/update/delete disabled
    # async def delete_product(product_id: int) -> Dict[str, Any]:
    #     """Delete product. (Commented out.)"""
    #     return {"error": "delete_product is disabled", "status_code": 403}


    # States endpoints
    @mcp.tool()
    async def get_states(
        skip: int = 0,
        limit: int = 100,
        active: Union[bool, str, None] = None,
        state_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List or find states from the system. Use when user asks to list states, show states, or to find a specific state by name or code (e.g. State = ALL, State = NY, California). Pass state_name to search: e.g. state_name="ALL" to find state ALL, state_name="NY" for New York. Returns items (id, state_code, state_name, active) and count.
        
        Purpose:
        Retrieves US states from the system (API/database). States are used in rating configurations
        to specify geographic jurisdictions for insurance products. Rating factors,
        tables, and plans are often state-specific. Use this to browse states, search
        for specific ones (including state code or name like ALL), or filter by status.
        
        Usage Examples:
        - Find State = ALL: state_name="ALL"
        - Find NY or New York: state_name="NY" or state_name="New York"
        - Get all states: limit=100 (omit state_name)
        - Get all active states: active=True, limit=100
        
        Args:
            skip: Number of records to skip for pagination (default: 0)
            limit: Maximum number of records to return (default: 100)
            active: Filter by active status (True/False/None). None returns all.
            state_name: Search by state name or code (partial match, case-insensitive). Use for "State = ALL" or any specific state.
            
        Returns:
            Dictionary with items list and count. Each state contains:
            id, state_code (2-letter code like 'NY', 'CA', or 'ALL'), state_name, active.
            
        When to Use:
        - User says "State = ALL", "find state ALL", or asks for a specific state by name/code
        - User asks to "list all states", "list states", "show states", "get states"
        - Need to find a state by name or code for rating configuration
        """
        try:
            # Coerce types in case Gemini sends strings or omits args
            skip_val = int(skip) if skip is not None else 0
            limit_val = min(int(limit) if limit is not None else 100, 1000)
            params = {"skip": skip_val, "limit": limit_val}
            active_bool = normalize_bool(active)
            if active_bool is not None:
                params["active"] = active_bool
            if state_name is not None and str(state_name).strip():
                params["state_name"] = str(state_name).strip()
            result = await call_api("GET", "/states/", params=params)
            return result
        except (TypeError, ValueError) as e:
            logger.warning(f"get_states argument error: {e}")
            return {"error": f"Invalid arguments: {e}", "status_code": 400}
        except Exception as e:
            logger.error(f"get_states failed: {e}", exc_info=True)
            return {"error": str(e), "status_code": 500}


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


    # @mcp.tool()  # create/update/delete disabled
    # async def create_state(state_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Create state. (Commented out.)"""
    #     return {"error": "create_state is disabled", "status_code": 403}

    # @mcp.tool()  # create/update/delete disabled
    # async def update_state(state_id: int, state_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Update state. (Commented out.)"""
    #     return {"error": "update_state is disabled", "status_code": 403}

    # @mcp.tool()  # create/update/delete disabled
    # async def delete_state(state_id: int) -> Dict[str, Any]:
    #     """Delete state. (Commented out.)"""
    #     return {"error": "delete_state is disabled", "status_code": 403}

    # Contexts endpoints
    @mcp.tool()
    async def get_contexts(
        skip: int = 0,
        limit: int = 100,
        active: Union[bool, str, None] = None,
        context_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List rating contexts (e.g. New Business, Renewal). Use when user asks for contexts or validation rules. Returns items and count.
        
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


    # @mcp.tool()  # create/update/delete disabled
    # async def create_context(context_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Create context. (Commented out.)"""
    #     return {"error": "create_context is disabled", "status_code": 403}

    # @mcp.tool()  # create/update/delete disabled
    # async def update_context(context_id: int, context_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Update context. (Commented out.)"""
    #     return {"error": "update_context is disabled", "status_code": 403}

    # @mcp.tool()  # create/update/delete disabled
    # async def delete_context(context_id: int) -> Dict[str, Any]:
    #     """Delete context. (Commented out.)"""
    #     return {"error": "delete_context is disabled", "status_code": 403}

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
        context_id: Optional[int] = None,
        entity_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        List rating tables (rates, factors, multipliers). Use when user asks for rating tables or to filter by company/LOB/state/product. Returns items and count.
        
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
            entity_id: Filter by legal entity ID
            
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
        try:
            skip_val = int(skip) if skip is not None else 0
            limit_val = min(int(limit) if limit is not None else 100, 500)
            params = {"skip": skip_val, "limit": limit_val}
            active_bool = normalize_bool(active)
            if active_bool is not None:
                params["active"] = active_bool
            if table_name:
                params["table_name"] = str(table_name).strip()
            if table_type:
                params["table_type"] = str(table_type).strip()
            if company_id is not None:
                params["company_id"] = int(company_id)
            if lob_id is not None:
                params["lob_id"] = int(lob_id)
            if state_id is not None:
                params["state_id"] = int(state_id)
            if product_id is not None:
                params["product_id"] = int(product_id)
            if context_id is not None:
                params["context_id"] = int(context_id)
            if entity_id is not None:
                params["entity_id"] = int(entity_id)
            return await call_api("GET", "/ratingtables/", params=params)
        except (TypeError, ValueError) as e:
            logger.warning(f"get_ratingtables argument error: {e}")
            return {"error": f"Invalid arguments: {e}", "status_code": 400}
        except Exception as e:
            logger.error(f"get_ratingtables failed: {e}", exc_info=True)
            return {"error": str(e), "status_code": 500}


    # @mcp.tool()  # disabled
    # async def get_ratingtable(ratingtable_id: int) -> Dict[str, Any]:
    #     """
    #     Get one rating table by ID. Use when you have a ratingtable_id and need full table details.
    #     """
    #     return await call_api("GET", f"/ratingtables/{ratingtable_id}")


    # @mcp.tool()  # create/update/delete disabled
    # async def create_ratingtable(ratingtable_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Create rating table. (Commented out.)"""
    #     return {"error": "create_ratingtable is disabled", "status_code": 403}

    # @mcp.tool()  # create/update/delete disabled
    # async def update_ratingtable(ratingtable_id: int, ratingtable_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Update rating table. (Commented out.)"""
    #     return {"error": "update_ratingtable is disabled", "status_code": 403}

    # @mcp.tool()  # create/update/delete disabled
    # async def delete_ratingtable(ratingtable_id: int) -> Dict[str, Any]:
    #     """Delete rating table. (Commented out.)"""
    #     return {"error": "delete_ratingtable is disabled", "status_code": 403}

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
        product_id: Optional[int] = None,
        entity_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        List rating algorithms (premium calculation logic). Use when user asks for algorithms or premium calculation steps. Returns items and count.
        
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
            entity_id: Filter by legal entity ID
            
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
        try:
            skip_val = _safe_int(skip, 0) or 0
            limit_val = min(_safe_int(limit, 100) or 100, 1000)
            params = {"skip": skip_val, "limit": limit_val}
            active_bool = normalize_bool(active)
            if active_bool is not None:
                params["active"] = active_bool
            if algorithm_name and str(algorithm_name).strip():
                params["algorithm_name"] = str(algorithm_name).strip()
            cid = _safe_int(company_id)
            if cid is not None:
                params["company_id"] = cid
            lid = _safe_int(lob_id)
            if lid is not None:
                params["lob_id"] = lid
            sid = _safe_int(state_id)
            if sid is not None:
                params["state_id"] = sid
            pid = _safe_int(product_id)
            if pid is not None:
                params["product_id"] = pid
            eid = _safe_int(entity_id)
            if eid is not None:
                params["entity_id"] = eid
            return await call_api("GET", "/algorithms/", params=params)
        except (TypeError, ValueError) as e:
            logger.warning(f"get_algorithms argument error: {e}")
            return {"error": f"Invalid arguments: {e}", "status_code": 400}
        except Exception as e:
            logger.error(f"get_algorithms failed: {e}", exc_info=True)
            return {"error": str(e), "status_code": 500}


    # @mcp.tool()  # disabled
    # async def get_algorithm(algorithm_id: int) -> Dict[str, Any]:
    #     """
    #     Get one algorithm by ID. Use when you have an algorithm_id and need formula or logic details.
    #     """
    #     return await call_api("GET", f"/algorithms/{algorithm_id}")


    # @mcp.tool()  # create/update/delete disabled
    # async def create_algorithm(algorithm_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Create algorithm. (Commented out.)"""
    #     return {"error": "create_algorithm is disabled", "status_code": 403}

    # @mcp.tool()  # create/update/delete disabled
    # async def update_algorithm(algorithm_id: int, algorithm_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Update algorithm. (Commented out.)"""
    #     return {"error": "update_algorithm is disabled", "status_code": 403}

    # @mcp.tool()  # create/update/delete disabled
    # async def delete_algorithm(algorithm_id: int) -> Dict[str, Any]:
    #     """Delete algorithm. (Commented out.)"""
    #     return {"error": "delete_algorithm is disabled", "status_code": 403}

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
        entity_id: Optional[int] = None,
        effective_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List rating manuals. Use when user asks for manuals or rating data by company/LOB/state/product. Returns items and count.
        
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
            entity_id: Filter by legal entity ID
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
        try:
            skip_val = int(skip) if skip is not None else 0
            limit_val = min(int(limit) if limit is not None else 100, 500)
            params = {"skip": skip_val, "limit": limit_val}
            active_bool = normalize_bool(active)
            if active_bool is not None:
                params["active"] = active_bool
            if manual_name:
                params["manual_name"] = str(manual_name).strip()
            if company_id is not None:
                params["company_id"] = int(company_id)
            if lob_id is not None:
                params["lob_id"] = int(lob_id)
            if state_id is not None:
                params["state_id"] = int(state_id)
            if product_id is not None:
                params["product_id"] = int(product_id)
            if ratingtable_id is not None:
                params["ratingtable_id"] = int(ratingtable_id)
            if entity_id is not None:
                params["entity_id"] = int(entity_id)
            if effective_date:
                params["effective_date"] = str(effective_date).strip()
            return await call_api("GET", "/ratingmanuals/", params=params)
        except (TypeError, ValueError) as e:
            logger.warning(f"get_ratingmanuals argument error: {e}")
            return {"error": f"Invalid arguments: {e}", "status_code": 400}
        except Exception as e:
            logger.error(f"get_ratingmanuals failed: {e}", exc_info=True)
            return {"error": str(e), "status_code": 500}


    @mcp.tool()
    async def get_ratingmanual(ratingmanual_id: int) -> Dict[str, Any]:
        """
        Get one rating manual by ID. Use when you have a ratingmanual_id and need manual details.
        
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


    # @mcp.tool()  # create/update/delete disabled
    # async def create_ratingmanual(ratingmanual_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Create rating manual. (Commented out.)"""
    #     return {"error": "create_ratingmanual is disabled", "status_code": 403}

    # @mcp.tool()  # create/update/delete disabled
    # async def update_ratingmanual(ratingmanual_id: int, ratingmanual_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Update rating manual. (Commented out.)"""
    #     return {"error": "update_ratingmanual is disabled", "status_code": 403}

    # @mcp.tool()  # create/update/delete disabled
    # async def delete_ratingmanual(ratingmanual_id: int) -> Dict[str, Any]:
    #     """Delete rating manual. (Commented out.)"""
    #     return {"error": "delete_ratingmanual is disabled", "status_code": 403}

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
        entity_id: Optional[int] = None,
        effective_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List rating plans. Use when user asks for rating plans or active plans. Returns items and count.
        
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
            entity_id: Filter by legal entity ID
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
        try:
            # Log request (incoming args)
            logger.info(
                "get_ratingplans request: skip=%s, limit=%s, active=%s, plan_name=%s, company_id=%s, lob_id=%s, state_id=%s, product_id=%s, algorithm_id=%s, effective_date=%s",
                skip, limit, active, plan_name, company_id, lob_id, state_id, product_id, algorithm_id, effective_date,
            )
            skip_val = _safe_int(skip, 0) or 0
            limit_val = min(_safe_int(limit, 100) or 100, 500)
            params = {"skip": skip_val, "limit": limit_val}
            active_bool = normalize_bool(active)
            if active_bool is not None:
                params["active"] = active_bool
            if plan_name and str(plan_name).strip():
                params["plan_name"] = str(plan_name).strip()
            cid = _safe_int(company_id)
            if cid is not None:
                params["company_id"] = cid
            lid = _safe_int(lob_id)
            if lid is not None:
                params["lob_id"] = lid
            sid = _safe_int(state_id)
            if sid is not None:
                params["state_id"] = sid
            pid = _safe_int(product_id)
            if pid is not None:
                params["product_id"] = pid
            aid = _safe_int(algorithm_id)
            if aid is not None:
                params["algorithm_id"] = aid
            eid = _safe_int(entity_id)
            if eid is not None:
                params["entity_id"] = eid
            if effective_date and str(effective_date).strip():
                params["effective_date"] = str(effective_date).strip()
            logger.info("get_ratingplans request params (resolved): %s", params)

            # Prefer direct service call when MCP runs in same process (avoids HTTP localhost/auth/timeout)
            result = None
            if _ratingplan_service is not None:
                try:
                    filter_by = {k: v for k, v in params.items() if k not in ("skip", "limit")}
                    plans = await _ratingplan_service.get_ratingplans(
                        skip=params["skip"],
                        limit=params["limit"],
                        filter_by=filter_by if filter_by else None,
                    )
                    items = [p.model_dump() if hasattr(p, "model_dump") else (p.dict() if hasattr(p, "dict") else p) for p in plans]
                    result = {"items": items, "count": len(items)}
                except Exception as e:
                    logger.warning("get_ratingplans direct service call failed, falling back to HTTP: %s", e)
                    result = None
            if result is None:
                result = await call_api("GET", "/ratingplans/", params=params)

            # Log response
            if isinstance(result, dict) and "error" in result:
                logger.warning(
                    "get_ratingplans response (error): %s (status_code=%s)",
                    result.get("error"),
                    result.get("status_code"),
                )
            else:
                items = result.get("items", []) if isinstance(result, dict) else []
                count = result.get("count", len(items)) if isinstance(result, dict) else 0
                logger.info("get_ratingplans response: count=%s, items_len=%s", count, len(items) if isinstance(items, list) else "n/a")
                logger.debug("get_ratingplans response full: %s", result)
            return result
        except (TypeError, ValueError) as e:
            logger.warning(f"get_ratingplans argument error: {e}")
            return {"error": f"Invalid arguments: {e}", "status_code": 400}
        except Exception as e:
            logger.error(f"get_ratingplans failed: {e}", exc_info=True)
            return {"error": str(e), "status_code": 500}


    # @mcp.tool()  # disabled
    # async def get_ratingplan(ratingplan_id: int) -> Dict[str, Any]:
    #     """
    #     Get one rating plan by ID. Use when you have a ratingplan_id and need plan details.
    #     """
    #     return await call_api("GET", f"/ratingplans/{ratingplan_id}")


    # @mcp.tool()  # create/update/delete disabled
    # async def create_ratingplan(ratingplan_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Create rating plan. (Commented out.)"""
    #     return {"error": "create_ratingplan is disabled", "status_code": 403}

    # @mcp.tool()  # create/update/delete disabled
    # async def update_ratingplan(ratingplan_id: int, ratingplan_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Update rating plan. (Commented out.)"""
    #     return {"error": "update_ratingplan is disabled", "status_code": 403}

    # @mcp.tool()  # create/update/delete disabled
    # async def delete_ratingplan(ratingplan_id: int) -> Dict[str, Any]:
    #     """Delete rating plan. (Commented out.)"""
    #     return {"error": "delete_ratingplan is disabled", "status_code": 403}

    # Health check
    @mcp.tool()
    async def health_check() -> Dict[str, Any]:
        """
        Check if the API and database are up. Use when user asks about system health or status. Returns status and database connection.
        
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
        # Health is at root /health, not under /api/v1; request full URL so base_url is not used
        try:
            response = await client.request("GET", f"{api_url.rstrip('/')}/health")
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {"data": data}
        except httpx.HTTPStatusError as e:
            logger.warning(f"Health check returned status {e.response.status_code}")
            return {"error": str(e), "status_code": e.response.status_code}
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"error": str(e), "status_code": None}

    @mcp.tool()
    async def evaluate_expression(
        expression: str,
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate a math expression with variables (e.g. for premium). Use when you need to compute a formula. Pass expression (string) and variables (dict).
        
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
    # Only list tools that are still registered (create/update/delete are commented out)
    known_tool_names = [
        'get_companies', 'get_legal_entities', 'get_legal_entity_addresses',
        'get_lobs', 'get_products', 'get_states', 'get_contexts',
        'get_ratingtables',  # 'get_ratingtable' disabled
        'get_algorithms',   # 'get_algorithm' disabled
        'get_ratingmanuals', 'get_ratingmanual',
        'get_ratingplans',  # 'get_ratingplan' disabled
        'health_check', 'evaluate_expression'
    ]
    for tool_name in known_tool_names:
        if tool_name in globals():
            tool_func = globals()[tool_name]
            if callable(tool_func):
                TOOL_REGISTRY[tool_name] = tool_func

# Export the MCP server instance and tool registry
__all__ = ["mcp", "client", "MCP_AVAILABLE", "call_api", "TOOL_REGISTRY"]

