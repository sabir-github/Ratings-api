from fastapi import APIRouter
from app.api.v1.endpoints import companies, lobs, products, states, contexts, upload, auth, users

api_router = APIRouter()


api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(companies.router, prefix="/companies", tags=["companies"])
api_router.include_router(lobs.router, prefix="/lobs", tags=["line-of-business"])
api_router.include_router(states.router, prefix="/states", tags=["states"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(contexts.router, prefix="/contexts", tags=["contexts"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])

