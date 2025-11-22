from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection
from app.api.v1.api import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS
# Handle CORS origins - if "*" is in the list and credentials are enabled, 
# we need to use a wildcard approach, but FastAPI doesn't support "*" with credentials
# So we filter out "*" and use explicit origins
cors_origins = settings.BACKEND_CORS_ORIGINS
if isinstance(cors_origins, str):
    cors_origins = [cors_origins]
elif "*" in cors_origins and len(cors_origins) == 1:
    # If only "*" is specified, allow common development origins
    cors_origins = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]
else:
    # Filter out "*" if present with other origins
    cors_origins = [origin for origin in cors_origins if origin != "*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database events
@app.on_event("startup")
async def startup_event():
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_event():
    await close_mongo_connection()

# Include routers
app.include_router(api_router, prefix=settings.API_V1_STR)

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)