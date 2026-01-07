from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection
from app.api.v1.api import api_router
import logging

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS Configuration
# Handle CORS origins - support both specific origins and wildcard
cors_origins = settings.BACKEND_CORS_ORIGINS
if isinstance(cors_origins, str):
    # If it's a string, split by comma if it contains multiple origins
    if "," in cors_origins:
        cors_origins = [origin.strip() for origin in cors_origins.split(",")]
    else:
        cors_origins = [cors_origins]

# Check if we should allow all origins (development mode)
allow_all_origins = settings.CORS_ALLOW_ALL_ORIGINS
if not allow_all_origins and "*" in cors_origins:
    # If "*" is specified in the list, allow all origins
    allow_all_origins = True
elif len(cors_origins) == 1 and cors_origins[0] == "*":
    allow_all_origins = True

if allow_all_origins:
    # Allow all origins (development mode) - credentials must be False
    logger.warning("CORS: Allowing all origins - This should only be used in development!")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,  # Cannot use credentials with "*"
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=3600,
    )
    logger.info(f"CORS: Configured to allow all origins (development mode)")
else:
    # Use specific origins with credentials enabled
    # Filter out "*" if present with other origins
    cors_origins = [origin for origin in cors_origins if origin != "*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=3600,
    )
    logger.info(f"CORS: Configured to allow specific origins: {cors_origins}")

# Database events
@app.on_event("startup")
async def startup_event():
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_event():
    await close_mongo_connection()

# Include routers
app.include_router(api_router, prefix=settings.API_V1_STR)

# Initialize and integrate MCP server with FastAPI
try:
    from app.mcp_server import mcp, MCP_AVAILABLE
    if MCP_AVAILABLE and mcp is not None:
        # FastMCP can be integrated with FastAPI
        # The MCP server is already accessible via /api/v1/mcp endpoints
        # FastMCP tools are registered and available through the MCP protocol endpoints
        logger.info("MCP server initialized and integrated with FastAPI.")
        logger.info("MCP server is running on the same port as FastAPI (port 8000).")
        logger.info("MCP endpoints available at:")
        logger.info("  - /api/v1/mcp/tools - List all MCP tools")
        logger.info("  - /api/v1/mcp/protocol - MCP protocol endpoint (JSON-RPC)")
        logger.info("  - /api/v1/mcp/protocol/info - MCP server information")
        logger.info("  - /api/v1/mcp/status - MCP server status")
        
        # Try to include FastMCP router if available (some FastMCP versions expose this)
        try:
            if hasattr(mcp, 'router'):
                app.include_router(mcp.router, prefix="/mcp", tags=["mcp-protocol"])
                logger.info("FastMCP router included at /mcp")
        except Exception as router_error:
            logger.debug(f"FastMCP router not available or already included: {router_error}")
    else:
        logger.warning("MCP server not available. Install fastmcp to enable MCP functionality.")
except ImportError as e:
    logger.warning(f"fastmcp not available. MCP server functionality disabled. Error: {e}")
except Exception as e:
    logger.error(f"Failed to initialize MCP server: {e}")
    import traceback
    logger.error(traceback.format_exc())

@app.get("/")
async def root():
    return {"message": "Ratings Application CRUD API", "version": settings.VERSION}

@app.get("/health")
async def health_check():
    """Health check endpoint with database connection status"""
    from app.core.database import mongodb
    db_status = "connected" if mongodb.connected else "disconnected"
    is_healthy = mongodb.connected
    
    response_data = {
        "status": "healthy" if is_healthy else "degraded",
        "database": db_status
    }
    
    status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(content=response_data, status_code=status_code)

# Alias for compatibility with different uvicorn command formats
main = app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)