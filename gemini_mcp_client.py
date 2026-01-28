#!/usr/bin/env python3
"""
Gemini AI Agent MCP Client
Integrates Google Gemini AI with the Ratings API MCP server.

This client:
1. Connects to the MCP server via HTTP
2. Converts MCP tools to Gemini function calling format
3. Enables Gemini to interact with the Ratings API through function calls
4. Handles tool execution and response formatting
"""

import httpx
import json
import asyncio
from typing import Any, Dict, List, Optional, Union
import logging
import os

# Try to import settings from app.core.config
try:
    from app.core.config import settings
except ImportError:
    settings = None

logger = logging.getLogger(__name__)

# Try to import Google Generative AI
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-generativeai not available. Install with: pip install google-generativeai")


class GeminiMCPClient:
    """
    Client for integrating Google Gemini AI with the Ratings API MCP server.
    
    This client bridges Gemini's function calling capabilities with the MCP server's tools,
    allowing Gemini to interact with the Ratings API naturally.
    """
    
    def __init__(
        self,
        mcp_base_url: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        max_iterations: Optional[int] = None,
    ):
        """
        Initialize the Gemini MCP Client.
        
        Configuration is loaded from settings (which reads from .env file) in this priority:
        1. Parameters passed to __init__ (highest priority)
        2. Settings from .env file (via app.core.config.settings)
        3. Environment variables (fallback)
        4. Hardcoded defaults (lowest priority)
        
        Args:
            mcp_base_url: Base URL for the MCP server (defaults to settings.MCP_BASE_URL from .env)
            gemini_api_key: Google Gemini API key (defaults to settings.GEMINI_API_KEY from .env)
            model_name: Gemini model to use (defaults to settings.GEMINI_MODEL_NAME from .env)
            max_iterations: Maximum tool-calling iterations (defaults to settings.GEMINI_MAX_ITERATIONS from .env)
        """
        # Priority: parameter > settings from .env > environment variable > default
        self.mcp_base_url = (
            mcp_base_url 
            or (settings.MCP_BASE_URL if settings else None)
            or os.getenv("MCP_BASE_URL", "http://localhost:8000/api/v1/mcp")
        )
        
        self.requested_model_name = (
            model_name
            or (settings.GEMINI_MODEL_NAME if settings else None)
            or os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash-lite")
        )
        
        self.max_iterations = (
            max_iterations
            or (settings.GEMINI_MAX_ITERATIONS if settings else None)
            or int(os.getenv("GEMINI_MAX_ITERATIONS", "5"))
        )
        
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=5.0),
            follow_redirects=True
        )
        self.request_id = 0
        self.initialized = False
        self.tools_cache: List[Dict[str, Any]] = []
        self.model_name: Optional[str] = None
        
        # Initialize Gemini - Priority: parameter > settings from .env > environment variable
        if GEMINI_AVAILABLE:
            api_key = (
                gemini_api_key
                or (settings.GEMINI_API_KEY if settings else None)
                or os.getenv("GEMINI_API_KEY")
            )
            if api_key:
                genai.configure(api_key=api_key)
                self.model = None
                logger.debug(f"Gemini API configured using {'parameter' if gemini_api_key else 'settings/.env' if settings and settings.GEMINI_API_KEY else 'environment variable'}")
            else:
                logger.warning(
                    "Gemini API key not provided. "
                    "Set GEMINI_API_KEY in .env file or pass gemini_api_key parameter."
                )
                self.model = None
        else:
            self.model = None

    @staticmethod
    def _normalize_model_name(name: str) -> str:
        """
        Normalize a model name to the format expected by the google-generativeai SDK.
        The SDK commonly uses names like 'models/gemini-pro'.
        """
        if not name:
            return name
        if name.startswith("models/"):
            return name
        return f"models/{name}"

    def list_available_gemini_models(self) -> List[Dict[str, Any]]:
        """
        List models visible to the current Gemini API key.
        Returns a simplified list for logging/diagnostics.
        """
        if not GEMINI_AVAILABLE:
            return []
        models = []
        try:
            for m in genai.list_models():
                methods = getattr(m, 'supported_generation_methods', [])
                if 'generateContent' in methods:
                    models.append({
                        'name': m.name,
                        'display_name': getattr(m, 'display_name', ''),
                        'description': getattr(m, 'description', '')
                    })
        except Exception as e:
            logger.warning(f"Failed to list Gemini models: {e}")
        return models

    def _ensure_model(self):
        """
        Initialize the Gemini model using the requested model name.
        """
        if not GEMINI_AVAILABLE:
            logger.warning("google-generativeai not available.")
            return
        if self.model is not None:
            return  # Already resolved
        
        try:
            normalized_requested = self._normalize_model_name(self.requested_model_name)
            self.model_name = normalized_requested
            
            # System instruction to help Gemini provide better responses
            #system_instruction = (
            #    "You are an expert Ratings API Assistant. Your goal is to help users interact with the Ratings API. "
            #    "When users ask to fetch or list entities (like companies, products, etc.), you should provide "
            #    "the full details returned by the tools unless they specifically ask for a summary. "
            #    "Always include IDs, codes, names, and status (active/inactive) in your responses. "
            #    "If many items are returned, you can use a table format for clarity.\n\n"
            #    "IMPORTANT: When a user asks to create, update, or delete an entity, you must first verify "
            #   "that you have all the required information. Refer to your available tools and their parameters "
            #   "to see what details are needed (e.g., company_code, company_name, etc.). If any required "
            #   "information is missing, do not call the tool. Instead, politely ask the user to provide the "
            #    "specific missing details before proceeding."
            #)
            system_instruction = None
            
            # Only pass system_instruction if it's not None (Gemini SDK doesn't accept empty values)
            if system_instruction:
                self.model = genai.GenerativeModel(
                    model_name=normalized_requested,
                    system_instruction=system_instruction
                )
                logger.info(f"Using Gemini model: {normalized_requested} with system instruction")
            else:
                self.model = genai.GenerativeModel(
                    model_name=normalized_requested
                )
                logger.info(f"Using Gemini model: {normalized_requested} without system instruction")
        except Exception as e:
            logger.error(f"Error initializing Gemini model: {e}")
            raise RuntimeError(f"Failed to initialize Gemini model '{self.requested_model_name}': {e}")
    
    async def _mcp_request(self, method: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make a JSON-RPC request to the MCP server.
        
        Args:
            method: MCP method name
            params: Method parameters
            
        Returns:
            JSON-RPC response
        """
        self.request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self.request_id
        }
        if params:
            payload["params"] = params
        
        try:
            response = await self.client.post(
                f"{self.mcp_base_url}/protocol",
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            # Check for JSON-RPC errors
            if "error" in result:
                error = result["error"]
                raise Exception(f"MCP Error {error.get('code')}: {error.get('message')} - {error.get('data', '')}")
            
            return result
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling MCP server: {e}")
            raise
        except Exception as e:
            logger.error(f"Error in MCP request: {e}")
            raise
    
    async def initialize(self) -> Dict[str, Any]:
        """
        Initialize connection with the MCP server.
        
        Returns:
            Initialization response
        """
        if self.initialized:
            return {"status": "already_initialized"}
        
        try:
            result = await self._mcp_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "gemini-mcp-client",
                    "version": "1.0.0"
                }
            })
            self.initialized = True
            logger.info("MCP connection initialized successfully")
            return result
        except Exception as e:
            logger.error(f"Failed to initialize MCP connection: {e}")
            raise
    
    async def get_server_info(self) -> Dict[str, Any]:
        """
        Get MCP server information.
        
        Returns:
            Server information including capabilities and tools
        """
        try:
            response = await self.client.get(f"{self.mcp_base_url}/protocol/info")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting server info: {e}")
            raise
    
    async def list_tools(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        List all available MCP tools.
        
        Args:
            use_cache: Whether to use cached tools if available
            
        Returns:
            List of MCP tools
        """
        if use_cache and self.tools_cache:
            return self.tools_cache
        
        try:
            result = await self._mcp_request("tools/list")
            tools = result.get("result", {}).get("tools", [])
            self.tools_cache = tools
            logger.info(f"Retrieved {len(tools)} tools from MCP server")
            return tools
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            raise
    
    def _convert_mcp_tool_to_gemini_function(self, mcp_tool: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert an MCP tool definition to Gemini function calling format.
        
        Args:
            mcp_tool: MCP tool definition
            
        Returns:
            Gemini function definition
        """
        tool_name = mcp_tool.get("name", "")
        tool_description = mcp_tool.get("description", "")
        
        # Extract input schema from MCP tool
        input_schema = mcp_tool.get("inputSchema", {})
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])
        
        # Convert properties to Gemini format
        gemini_properties = {}
        for prop_name, prop_def in properties.items():
            prop_type = prop_def.get("type", "string")
            prop_desc = prop_def.get("description", "")
            
            # Map MCP types to Gemini types
            gemini_type = prop_type
            if prop_type == "integer":
                gemini_type = "number"
            
            gemini_properties[prop_name] = {
                "type": gemini_type,
                "description": prop_desc
            }
            
            # Handle enum values
            if "enum" in prop_def:
                gemini_properties[prop_name]["enum"] = prop_def["enum"]
        
        return {
            "name": tool_name,
            "description": tool_description,
            "parameters": {
                "type": "object",
                "properties": gemini_properties,
                "required": required
            }
        }
    
    def get_gemini_functions(self) -> List[Dict[str, Any]]:
        """
        Get all MCP tools converted to Gemini function calling format.
        
        Returns:
            List of Gemini function definitions
        """
        if not self.tools_cache:
            raise RuntimeError("Tools not loaded. Call list_tools() first.")
        
        functions = []
        for tool in self.tools_cache:
            try:
                gemini_func = self._convert_mcp_tool_to_gemini_function(tool)
                functions.append(gemini_func)
            except Exception as e:
                logger.warning(f"Failed to convert tool {tool.get('name')} to Gemini format: {e}")
        
        return functions
    
    async def call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call an MCP tool with the given arguments.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            result = await self._mcp_request("tools/call", {
                "name": tool_name,
                "arguments": arguments
            })
            
            # Extract content from MCP response
            result_data = result.get("result", {})
            content = result_data.get("content", [])
            
            if content and len(content) > 0:
                # Extract text content
                text_content = content[0].get("text", "")
                try:
                    # Try to parse as JSON
                    return json.loads(text_content)
                except json.JSONDecodeError:
                    # Return as text if not JSON
                    return {"text": text_content}
            
            return result_data
        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {e}")
            raise
    
    async def chat_with_gemini(
        self,
        prompt: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        max_iterations: Optional[int] = None
    ) -> str:
        """
        Chat with Gemini, allowing it to use MCP tools.
        
        Args:
            prompt: User prompt
            conversation_history: Previous conversation messages
            max_iterations: Maximum number of function call iterations
                          (defaults to self.max_iterations from settings/.env)
            
        Returns:
            Gemini's response
        """
        # Use provided max_iterations or fall back to instance value from settings/.env
        if max_iterations is None:
            max_iterations = self.max_iterations
        if not GEMINI_AVAILABLE:
            raise RuntimeError("google-generativeai not installed. Run: pip install google-generativeai")

        # Ensure we have an accessible model for this API key.
        if self.model is None:
            self._ensure_model()
        if self.model is None:
            raise RuntimeError("Gemini model not initialized. Provide API key.")
        
        if not self.initialized:
            await self.initialize()
        
        if not self.tools_cache:
            await self.list_tools()
        
        # Get Gemini functions
        functions = self.get_gemini_functions()
        
        # Convert functions to Gemini format
        try:
            # Use the tools parameter if available
            tools_config = [{"function_declarations": functions}]
            
            # Start chat with tools
            chat = self.model.start_chat(history=conversation_history or [])
            
            # Send initial message
            response = chat.send_message(prompt, tools=tools_config)
            
            # Handle function calls iteratively
            iteration = 0
            while iteration < max_iterations:
                # Check if response contains function calls
                function_calls = []
                
                if hasattr(response, 'candidates') and response.candidates:
                    for candidate in response.candidates:
                        if hasattr(candidate, 'content') and candidate.content:
                            if hasattr(candidate.content, 'parts'):
                                for part in candidate.content.parts:
                                    if hasattr(part, 'function_call') and part.function_call:
                                        func_call = part.function_call
                                        function_calls.append({
                                            "name": func_call.name if hasattr(func_call, 'name') else None,
                                            "args": dict(func_call.args) if hasattr(func_call, 'args') else {}
                                        })
                
                if not function_calls:
                    # No more function calls, return the response
                    return response.text if hasattr(response, 'text') else str(response)
                
                # Process function calls
                function_responses = []
                for func_call in function_calls:
                    func_name = func_call.get("name")
                    func_args = func_call.get("args", {})
                    
                    if not func_name:
                        continue
                    
                    logger.info(f"Gemini calling function: {func_name} with args: {func_args}")
                    
                    try:
                        # Call the MCP tool
                        tool_result = await self.call_mcp_tool(func_name, func_args)
                        
                        function_responses.append({
                            "name": func_name,
                            "response": tool_result
                        })
                    except Exception as e:
                        logger.error(f"Error calling tool {func_name}: {e}")
                        function_responses.append({
                            "name": func_name,
                            "response": {"error": str(e)}
                        })
                
                # Send function responses back to Gemini
                if function_responses:
                    # Format function response for Gemini
                    response_parts = []
                    for func_resp in function_responses:
                        response_parts.append({
                            "function_response": {
                                "name": func_resp["name"],
                                "response": func_resp["response"]
                            }
                        })
                    
                    # Continue conversation with function results
                    response = chat.send_message(response_parts, tools=tools_config)
                    iteration += 1
                else:
                    break
            
            return response.text if hasattr(response, 'text') else str(response)
            
        except Exception as e:
            logger.error(f"Error in chat_with_gemini: {e}")
            # Fallback: try without tools
            try:
                chat = self.model.start_chat(history=conversation_history or [])
                response = chat.send_message(prompt)
                return response.text if hasattr(response, 'text') else str(response)
            except Exception as fallback_error:
                raise Exception(f"Both tool-enabled and fallback chat failed: {fallback_error}")
    
    async def process_gemini_function_calls(
        self,
        function_calls: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Process multiple function calls from Gemini.
        
        Args:
            function_calls: List of function calls from Gemini
            
        Returns:
            List of function responses
        """
        responses = []
        
        for func_call in function_calls:
            func_name = func_call.get("name")
            func_args = func_call.get("arguments", {})
            
            try:
                result = await self.call_mcp_tool(func_name, func_args)
                responses.append({
                    "name": func_name,
                    "response": result
                })
            except Exception as e:
                logger.error(f"Error processing function call {func_name}: {e}")
                responses.append({
                    "name": func_name,
                    "response": {"error": str(e)}
                })
        
        return responses
    
    async def close(self):
        """Close the HTTP client connection."""
        await self.client.aclose()
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        await self.list_tools()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Convenience function for quick usage
async def create_gemini_client(
    mcp_url: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
    model_name: Optional[str] = None
) -> GeminiMCPClient:
    """
    Create and initialize a Gemini MCP client.
    
    Args:
        mcp_url: MCP server URL
        gemini_api_key: Gemini API key
        model_name: Gemini model name
        
    Returns:
        Initialized GeminiMCPClient
    """
    client = GeminiMCPClient(mcp_url, gemini_api_key, model_name)
    await client.initialize()
    await client.list_tools()
    return client
