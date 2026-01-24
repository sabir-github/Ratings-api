from fastapi import APIRouter
from app.api.v1.endpoints import companies, lobs, products, states, contexts, upload, ratingtables, algorithms, ratingmanuals, ratingplans, mcp, chat, evaluate_expression
# from app.api.v1.endpoints import auth, users

api_router = APIRouter()


# api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
# api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(companies.router, prefix="/companies", tags=["companies"])
api_router.include_router(lobs.router, prefix="/lobs", tags=["line-of-business"])
api_router.include_router(states.router, prefix="/states", tags=["states"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(contexts.router, prefix="/contexts", tags=["contexts"])
api_router.include_router(ratingtables.router, prefix="/ratingtables", tags=["ratingtables"])
api_router.include_router(algorithms.router, prefix="/algorithms", tags=["algorithms"])
api_router.include_router(ratingmanuals.router, prefix="/ratingmanuals", tags=["ratingmanuals"])
api_router.include_router(ratingplans.router, prefix="/ratingplans", tags=["ratingplans"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(mcp.router, prefix="/mcp", tags=["mcp"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(evaluate_expression.router, prefix="/evaluate_expression", tags=["evaluate_expression"])

