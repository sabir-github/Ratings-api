"""
Chat Assistant API Endpoints
Exposes Gemini MCP Client for UI chat assistant integration
"""
from fastapi import APIRouter, HTTPException, Body, Query, Path, status
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import logging
import os
import sys
from pathlib import Path as PathLibPath
from app.core.config import settings

# Add project root to path to import gemini_mcp_client
project_root = PathLibPath(__file__).parent.parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from gemini_mcp_client import GeminiMCPClient
    GEMINI_MCP_AVAILABLE = True
except ImportError:
    GEMINI_MCP_AVAILABLE = False
    logging.warning("gemini_mcp_client not available. Chat endpoints will be disabled.")

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory storage for conversation histories (in production, use Redis or database)
conversation_histories: Dict[str, List[Dict[str, Any]]] = {}


# Pydantic models for request/response
class ChatMessage(BaseModel):
    """Chat message request model"""
    message: str = Field(..., description="User message")
    session_id: Optional[str] = Field(None, description="Session ID for conversation history")
    # Note: gemini_api_key, model_name, and max_iterations now come from config file, not request


class ChatResponse(BaseModel):
    """Chat response model"""
    response: str = Field(..., description="Assistant response")
    session_id: str = Field(..., description="Session ID")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="Tool calls made during conversation")
    model_used: Optional[str] = Field(None, description="Gemini model actually used")


class ChatHistoryResponse(BaseModel):
    """Chat history response model"""
    session_id: str = Field(..., description="Session ID")
    history: List[Dict[str, Any]] = Field(..., description="Conversation history")
    message_count: int = Field(..., description="Number of messages in history")


# Global client instance (kept active for the session)
_chat_client: Optional[GeminiMCPClient] = None
_client_initialized: bool = False


async def get_chat_client() -> GeminiMCPClient:
    """
    Get or create a Gemini MCP client instance using config file settings.
    
    The client is kept active across requests (singleton pattern).
    Automatically loads mcp.json configuration if available, otherwise falls back to HTTP.
    
    Returns:
        GeminiMCPClient instance (reused across requests)
    """
    global _chat_client, _client_initialized
    
    if not GEMINI_MCP_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini MCP client not available. Install dependencies."
        )
    
    # Return existing client if already initialized
    if _chat_client is not None and _client_initialized:
        return _chat_client
    
    # Get Gemini configuration from settings (which reads from .env file)
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gemini API key not configured. Set GEMINI_API_KEY in .env file or environment variable."
        )
    
    # Get model name and max iterations from settings (from .env file)
    model_name = settings.GEMINI_MODEL_NAME
    max_iterations = settings.GEMINI_MAX_ITERATIONS
    
    # MCP base URL is optional (only used if mcp.json not found)
    mcp_base_url = settings.MCP_BASE_URL
    
    # Create client - it will automatically try to load mcp.json config first
    # If mcp.json is found, it uses stdio connection; otherwise falls back to HTTP
    _chat_client = GeminiMCPClient(
        mcp_base_url=mcp_base_url,  # Fallback URL if mcp.json not found
        gemini_api_key=api_key,
        model_name=model_name,
        max_iterations=max_iterations
    )
    
    # Initialize the client (connect to MCP server, load tools)
    try:
        await _chat_client.initialize()
        await _chat_client.list_tools()
        _client_initialized = True
        logger.info("Gemini MCP client initialized and kept active for session")
    except Exception as e:
        logger.error(f"Failed to initialize Gemini MCP client: {e}", exc_info=True)
        _chat_client = None
        _client_initialized = False
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize Gemini MCP client: {str(e)}"
        )
    
    return _chat_client


@router.post("/", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat(
    chat_request: ChatMessage = Body(...)
):
    """
    Send a chat message and get a response from Gemini using MCP tools.
    
    This endpoint allows you to chat with Gemini AI, which can use MCP tools
    to interact with the Ratings API.
    
    Args:
        chat_request: Chat message request with message, session_id, and optional settings
        
    Returns:
        Chat response with assistant reply and session information
    """
    if not GEMINI_MCP_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat assistant not available. Gemini MCP client not installed."
        )
    
    try:
        # Get or create session ID
        session_id = chat_request.session_id or f"session_{os.urandom(8).hex()}"
        
        # Get conversation history
        conversation_history = conversation_histories.get(session_id, [])
        
        # Get chat client (reused across requests, kept active)
        client = await get_chat_client()
        
        # Chat with Gemini (max_iterations comes from client instance, which reads from .env)
        # Passing None uses the client's max_iterations from settings
        response_text = await client.chat_with_gemini(
            prompt=chat_request.message,
            conversation_history=conversation_history,
            max_iterations=None  # Uses self.max_iterations from settings/.env
        )
        
        # Update conversation history
        conversation_history.append({
            "role": "user",
            "parts": [{"text": chat_request.message}]
        })
        conversation_history.append({
            "role": "model",
            "parts": [{"text": response_text}]
        })
        conversation_histories[session_id] = conversation_history
        
        return ChatResponse(
            response=response_text,
            session_id=session_id,
            model_used=client.model_name or settings.GEMINI_MODEL_NAME
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing chat message: {str(e)}"
        )


@router.post("/stream")
async def chat_stream(
    chat_request: ChatMessage = Body(...)
):
    """
    Stream chat response from Gemini (Server-Sent Events).
    
    This endpoint streams the response as it's generated, useful for
    real-time UI updates.
    
    Args:
        chat_request: Chat message request
        
    Returns:
        Streaming response with chat messages
    """
    if not GEMINI_MCP_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat assistant not available. Gemini MCP client not installed."
        )
    
    async def event_generator():
        """Generate SSE events for streaming chat"""
        try:
            session_id = chat_request.session_id or f"session_{os.urandom(8).hex()}"
            conversation_history = conversation_histories.get(session_id, [])
            
            # Get chat client (reused across requests, kept active)
            client = await get_chat_client()
            
            # For now, send complete response (streaming can be enhanced later)
            # Using max_iterations from config
            response_text = await client.chat_with_gemini(
                prompt=chat_request.message,
                conversation_history=conversation_history,
                max_iterations=settings.GEMINI_MAX_ITERATIONS
            )
            
            # Update conversation history
            conversation_history.append({
                "role": "user",
                "parts": [{"text": chat_request.message}]
            })
            conversation_history.append({
                "role": "model",
                "parts": [{"text": response_text}]
            })
            conversation_histories[session_id] = conversation_history
            
            # Send response as SSE event
            yield f"data: {JSONResponse(content={'response': response_text, 'session_id': session_id}).body.decode()}\n\n"
            yield "data: [DONE]\n\n"
                
        except Exception as e:
            logger.error(f"Error in chat stream: {e}", exc_info=True)
            error_data = {"error": str(e)}
            yield f"data: {JSONResponse(content=error_data, status_code=500).body.decode()}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/history/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: str = Path(..., description="Session ID")
):
    """
    Get conversation history for a session.
    
    Args:
        session_id: Session ID
        
    Returns:
        Conversation history
    """
    history = conversation_histories.get(session_id, [])
    
    return ChatHistoryResponse(
        session_id=session_id,
        history=history,
        message_count=len(history)
    )


@router.delete("/history/{session_id}", status_code=status.HTTP_200_OK)
async def clear_chat_history(
    session_id: str = Path(..., description="Session ID")
):
    """
    Clear conversation history for a session.
    
    Args:
        session_id: Session ID
        
    Returns:
        Success message
    """
    if session_id in conversation_histories:
        del conversation_histories[session_id]
    
    # Return success even if session didn't exist (it's "cleared" now)
    return {"message": f"Chat history cleared for session {session_id}", "session_id": session_id}


@router.get("/sessions")
async def list_sessions():
    """
    List all active chat sessions.
    
    Returns:
        List of active session IDs
    """
    return {
        "sessions": list(conversation_histories.keys()),
        "count": len(conversation_histories)
    }


@router.get("/status")
async def chat_status():
    """
    Get chat service status and configuration.
    
    Returns:
        Service status information
    """
    # Check if Gemini API key is configured (from .env file via settings)
    gemini_api_key_configured = bool(settings.GEMINI_API_KEY)
    
    return {
        "status": "available" if GEMINI_MCP_AVAILABLE else "unavailable",
        "gemini_mcp_client_available": GEMINI_MCP_AVAILABLE,
        "gemini_api_key_configured": gemini_api_key_configured,
        "gemini_model_name": settings.GEMINI_MODEL_NAME,
        "gemini_max_iterations": settings.GEMINI_MAX_ITERATIONS,
        "active_sessions": len(conversation_histories),
        "mcp_base_url": settings.MCP_BASE_URL,
        "client_initialized": _client_initialized,
        "configuration_source": ".env file via settings" if gemini_api_key_configured else "not configured"
    }


# Cleanup function for chat client (called on app shutdown)
async def cleanup_chat_client():
    """Close the global chat client on application shutdown."""
    global _chat_client, _client_initialized
    if _chat_client is not None:
        try:
            await _chat_client.close()
            logger.info("Chat client closed on application shutdown")
        except Exception as e:
            logger.warning(f"Error closing chat client: {e}")
        finally:
            _chat_client = None
            _client_initialized = False

