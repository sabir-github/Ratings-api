#!/usr/bin/env python3
"""
Gemini AI Agent MCP Client
Integrates Google Gemini AI with the Ratings API MCP server.

This client:
1. Connects to the MCP server via HTTP or stdio (subprocess)
2. Converts MCP tools to Gemini function calling format
3. Enables Gemini to interact with the Ratings API through function calls
4. Handles tool execution and response formatting

Supports both HTTP and stdio-based MCP connections:
- Stdio: Connects to MCP server via subprocess stdin/stdout (default, auto-loads from mcp.json)
- HTTP: Connects to MCP server via HTTP endpoint (fallback if mcp.json not found)

By default, automatically searches for mcp.json in:
- Project root directory
- Current working directory
- ~/.cursor/mcp.json (Windows)
- ~/.config/cursor/mcp.json (Linux/Mac)
- Path specified in MCP_CONFIG_PATH environment variable
"""

import httpx
import json
import asyncio
from typing import Any, Dict, List, Optional, Union
import logging
import os
import subprocess
import sys

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
        mcp_command: Optional[List[str]] = None,
        mcp_args: Optional[List[str]] = None,
        mcp_env: Optional[Dict[str, str]] = None,
        use_stdio: Optional[bool] = None,
    ):
        """
        Initialize the Gemini MCP Client.
        
        By default, automatically loads mcp.json configuration from common locations.
        If mcp.json is found, uses stdio connection; otherwise falls back to HTTP.
        
        Configuration priority:
        1. Parameters passed to __init__ (highest priority)
        2. mcp.json file (auto-searched in common locations)
        3. Settings from .env file (via app.core.config.settings)
        4. Environment variables (fallback)
        5. Hardcoded defaults (lowest priority)
        
        Args:
            mcp_base_url: Base URL for the MCP server (used as fallback if mcp.json not found)
            gemini_api_key: Google Gemini API key (defaults to settings.GEMINI_API_KEY from .env)
            model_name: Gemini model to use (defaults to settings.GEMINI_MODEL_NAME from .env)
            max_iterations: Maximum tool-calling iterations (defaults to settings.GEMINI_MAX_ITERATIONS from .env)
            mcp_command: MCP server command (e.g., ["docker"]) for stdio connection (overrides mcp.json)
            mcp_args: MCP server command arguments (overrides mcp.json)
            mcp_env: Environment variables for MCP server process (merged with mcp.json env)
            use_stdio: Whether to use stdio connection (True) or HTTP (False). Auto-detect if None.
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
        
        # MCP stdio configuration (from mcp.json style config)
        # Priority: explicit params > mcp.json config > environment variables
        mcp_config_loaded = False
        
        if mcp_command is not None or mcp_args is not None:
            # Use explicitly provided command/args
            if mcp_command is not None:
                self.mcp_command = mcp_command
            else:
                env_cmd = os.getenv("MCP_COMMAND")
                self.mcp_command = env_cmd.split() if env_cmd else None
            
            if mcp_args is not None:
                self.mcp_args = mcp_args
            else:
                env_args = os.getenv("MCP_ARGS")
                self.mcp_args = env_args.split() if env_args else None
            
            self.mcp_env = mcp_env or {}
        else:
            # Try to load from mcp.json config file (default behavior)
            mcp_config = load_mcp_config_from_file(server_name="ratings-api")
            if mcp_config:
                # Load from mcp.json
                command = mcp_config.get("command", "")
                if isinstance(command, str):
                    self.mcp_command = [command]
                elif isinstance(command, list):
                    self.mcp_command = command
                else:
                    self.mcp_command = None
                
                self.mcp_args = mcp_config.get("args", [])
                self.mcp_env = mcp_config.get("env", {})
                mcp_config_loaded = True
                logger.info("Using MCP configuration from mcp.json file")
            else:
                # Fall back to environment variables
                env_cmd = os.getenv("MCP_COMMAND")
                self.mcp_command = env_cmd.split() if env_cmd else None
                
                env_args = os.getenv("MCP_ARGS")
                self.mcp_args = env_args.split() if env_args else None
                
                self.mcp_env = mcp_env or {}
        
        # Determine connection mode
        if use_stdio is None:
            # Auto-detect: use stdio if command/args provided, otherwise HTTP
            has_stdio_config = (self.mcp_command is not None and len(self.mcp_command) > 0 and 
                              self.mcp_args is not None and len(self.mcp_args) > 0)
            
            # Default to stdio if mcp.json was loaded, otherwise HTTP
            if mcp_config_loaded and has_stdio_config:
                self.use_stdio = True
                logger.info("Auto-detected stdio connection mode from mcp.json config")
            else:
                self.use_stdio = has_stdio_config
                if not self.use_stdio:
                    logger.info("No stdio config found, using HTTP connection mode")
        else:
            self.use_stdio = use_stdio
        
        # Initialize connection based on mode
        if self.use_stdio:
            # Stdio mode: will spawn subprocess
            self.client = None
            self.mcp_process: Optional[subprocess.Popen] = None
            self.mcp_stdin: Optional[Any] = None
            self.mcp_stdout: Optional[Any] = None
            logger.info("Using stdio-based MCP connection")
        else:
            # HTTP mode: use httpx client
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=5.0),
                follow_redirects=True
            )
            self.mcp_process = None
            self.mcp_stdin = None
            self.mcp_stdout = None
            logger.info(f"Using HTTP-based MCP connection: {self.mcp_base_url}")
        
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
            """
            system_instruction = (
                "You are an expert Ratings API Assistant. Your goal is to help users interact with the Ratings API. "
                "When users ask to fetch or list entities (like companies, products, etc.), you should provide "
                "the full details returned by the tools unless they specifically ask for a summary. "
                "Always include IDs, codes, names, and status (active/inactive) in your responses. "
                "If many items are returned, you can use a table format for clarity.\n\n"
                "IMPORTANT: When a user asks to create, update, or delete an entity, you must first verify "
               "that you have all the required information. Refer to your available tools and their parameters "
               "to see what details are needed (e.g., company_code, company_name, etc.). If any required "
               "information is missing, do not call the tool. Instead, politely ask the user to provide the "
                "specific missing details before proceeding."
            )
            """
            system_instruction = (
                """
                You are a helpful assistant connected to an MCP server and You are an expert in interacting with the Ratings API. 
                ## Your Name
                Your name is InsureAI.
                ## Your Task
                Validate the test cases based on user/underwriter inputs and use the algorithm steps fetched from MCP server for insurance rating workbench.
                Your goal is to ask the inputs from user for a given test case in a hierarchial way, and fetch the required values from MCP server using the available tools, and then calculate
                premium using those inputs and fetched values.
                Analyze data structures, formulas, calculations, and AI metadata for correctness and consistency.

                ## Schema Overview
                The system consists of 8 core collections:
                1. **COMPANY** - Insurance company records
                2. **LOB** - Lines of Business (EPL)
                3. **PRODUCT** - Insurance products (EPL Standard Coverage)
                4. **STATE** - All 51 US states + DC
                5. **CONTEXTS** - Rating questions and validation rules
                6. **rating_tables** - Premium rating tables (base rates, factors, multipliers)
                7. **algorithms** - Premium calculation formulas and workflows
                8. **rate_configurations** - Configuration linking all components.
                Your goal is to fetch product ratings and information using the available tools.
                Always explain your reasoning before calling a tool.

                Capabilities:
                1.  **Calculate premiums for insurance product**: Analyze the data inputs and algorithms, and make sure to follow the steps to calculate insurance premium    
                2.  **Ask user for inputs if missing**: Ask inputs from user in a structured way to calculate premium
                3.  **Show reasoning**: Guide users on how you have calculated insurance premium
                4.  **DO NOT ANSWER OTHER QUESTIONS**: Only answer the questions which are relevant to your goals, capabilities, and the data and tools available in MCP server
                """)

            
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
    
    async def _start_stdio_connection(self):
        """Start stdio-based MCP server process."""
        if self.mcp_process is not None:
            return  # Already started
        
        try:
            # Build command
            cmd = self.mcp_command + self.mcp_args
            
            # Merge environment variables
            env = os.environ.copy()
            env.update(self.mcp_env)
            
            # Start subprocess
            self.mcp_process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=0  # Unbuffered
            )
            
            self.mcp_stdin = self.mcp_process.stdin
            self.mcp_stdout = self.mcp_process.stdout
            
            logger.info(f"Started MCP server process: {' '.join(cmd)}")
        except FileNotFoundError as e:
            # Command not found (e.g., 'docker' not in PATH)
            logger.warning(f"Failed to start MCP server process: {e}")
            logger.warning("Falling back to HTTP connection mode")
            # Switch to HTTP mode
            self.use_stdio = False
            self.mcp_process = None
            self.mcp_stdin = None
            self.mcp_stdout = None
            # Initialize HTTP client
            if self.client is None:
                self.client = httpx.AsyncClient(
                    timeout=httpx.Timeout(30.0, connect=5.0),
                    follow_redirects=True
                )
            raise RuntimeError(f"Failed to start MCP server via stdio (command not found). Falling back to HTTP.")
        except Exception as e:
            logger.error(f"Failed to start MCP server process: {e}")
            raise RuntimeError(f"Failed to start MCP server: {e}")
    
    async def _mcp_request_stdio(self, method: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make a JSON-RPC request via stdio to the MCP server.
        
        Args:
            method: MCP method name
            params: Method parameters
            
        Returns:
            JSON-RPC response
        """
        if self.mcp_process is None:
            try:
                await self._start_stdio_connection()
            except RuntimeError as e:
                # If stdio fails (e.g., docker not found), fall back to HTTP
                if "Falling back to HTTP" in str(e):
                    logger.info("Switching to HTTP connection mode as fallback")
                    self.use_stdio = False
                    return await self._mcp_request_http(method, params)
                raise
        
        self.request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self.request_id
        }
        if params:
            payload["params"] = params
        
        try:
            # Send request
            request_json = json.dumps(payload) + "\n"
            self.mcp_stdin.write(request_json)
            self.mcp_stdin.flush()
            
            # Read response (MCP uses newline-delimited JSON)
            response_line = await asyncio.to_thread(self.mcp_stdout.readline)
            if not response_line:
                raise Exception("MCP server closed connection")
            
            result = json.loads(response_line.strip())
            
            # Check for JSON-RPC errors
            if "error" in result:
                error = result["error"]
                raise Exception(f"MCP Error {error.get('code')}: {error.get('message')} - {error.get('data', '')}")
            
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse MCP response: {e}")
            raise Exception(f"Invalid JSON response from MCP server: {e}")
        except Exception as e:
            logger.error(f"Error in stdio MCP request: {e}")
            raise
    
    async def _mcp_request_http(self, method: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make a JSON-RPC request via HTTP to the MCP server.
        
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
            logger.error(f"Error in HTTP MCP request: {e}")
            raise
    
    async def _mcp_request(self, method: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make a JSON-RPC request to the MCP server (HTTP or stdio).
        
        Args:
            method: MCP method name
            params: Method parameters
            
        Returns:
            JSON-RPC response
        """
        if self.use_stdio:
            return await self._mcp_request_stdio(method, params)
        else:
            return await self._mcp_request_http(method, params)
    
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
        if self.use_stdio:
            # For stdio, use initialize method to get server info
            try:
                result = await self._mcp_request("initialize", {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "gemini-mcp-client",
                        "version": "1.0.0"
                    }
                })
                return result.get("result", {})
            except Exception as e:
                logger.error(f"Error getting server info via stdio: {e}")
                raise
        else:
            # HTTP mode
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
        """Close the MCP connection (HTTP or stdio)."""
        if self.use_stdio:
            # Close stdio connection
            if self.mcp_process is not None:
                try:
                    # Try graceful shutdown
                    self.mcp_process.terminate()
                    try:
                        await asyncio.wait_for(
                            asyncio.to_thread(self.mcp_process.wait),
                            timeout=5.0
                        )
                    except asyncio.TimeoutError:
                        # Force kill if it doesn't terminate
                        self.mcp_process.kill()
                        await asyncio.to_thread(self.mcp_process.wait)
                except Exception as e:
                    logger.warning(f"Error closing MCP process: {e}")
                finally:
                    self.mcp_process = None
                    self.mcp_stdin = None
                    self.mcp_stdout = None
        else:
            # Close HTTP connection
            if self.client:
                await self.client.aclose()
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        await self.list_tools()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


def find_mcp_config_file() -> Optional[str]:
    """
    Search for mcp.json file in common locations.
    
    Returns:
        Path to mcp.json file if found, None otherwise
    """
    # Common locations to search
    search_paths = [
        # Project root (where gemini_mcp_client.py is located)
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp.json"),
        # Current working directory
        os.path.join(os.getcwd(), "mcp.json"),
        # User's .cursor directory (Windows)
        os.path.join(os.path.expanduser("~"), ".cursor", "mcp.json"),
        # User's .cursor directory (Linux/Mac)
        os.path.join(os.path.expanduser("~"), ".config", "cursor", "mcp.json"),
        # Environment variable override
        os.getenv("MCP_CONFIG_PATH"),
    ]
    
    for path in search_paths:
        if path and os.path.isfile(path):
            logger.info(f"Found MCP config file: {path}")
            return path
    
    return None


def load_mcp_config_from_file(config_path: Optional[str] = None, server_name: str = "ratings-api") -> Optional[Dict[str, Any]]:
    """
    Load MCP server configuration from mcp.json file.
    
    Args:
        config_path: Path to mcp.json file. If None, will search common locations.
        server_name: Name of the MCP server in the config (default: "ratings-api")
        
    Returns:
        MCP server configuration dict, or None if not found
    """
    if config_path is None:
        config_path = find_mcp_config_file()
        if config_path is None:
            return None
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        mcp_servers = config.get("mcpServers", {})
        if server_name not in mcp_servers:
            logger.warning(f"MCP server '{server_name}' not found in config file. Available servers: {list(mcp_servers.keys())}")
            return None
        
        logger.info(f"Loaded MCP config for server '{server_name}' from {config_path}")
        return mcp_servers[server_name]
    except FileNotFoundError:
        logger.debug(f"MCP config file not found: {config_path}")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in MCP config file {config_path}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error loading MCP config from {config_path}: {e}")
        return None


def create_client_from_mcp_config(
    mcp_config: Dict[str, Any],
    gemini_api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    max_iterations: Optional[int] = None
) -> GeminiMCPClient:
    """
    Create a Gemini MCP client from mcp.json style configuration.
    
    Args:
        mcp_config: MCP server configuration dict (from mcp.json mcpServers section)
                   Example: {
                       "command": "docker",
                       "args": ["exec", "-i", "ratings-api-api-1", "python", "/app/run_mcp_server.py"],
                       "env": {"API_URL": "http://localhost:8000", ...}
                   }
        gemini_api_key: Google Gemini API key
        model_name: Gemini model name
        max_iterations: Maximum tool-calling iterations
        
    Returns:
        GeminiMCPClient instance configured for stdio connection
    """
    # Handle command - can be string or list
    command = mcp_config.get("command", "")
    if isinstance(command, str):
        command = [command]  # Convert string to list
    elif not isinstance(command, list):
        command = []
    
    args = mcp_config.get("args", [])
    env = mcp_config.get("env", {})
    
    return GeminiMCPClient(
        mcp_command=command,
        mcp_args=args,
        mcp_env=env,
        use_stdio=True,
        gemini_api_key=gemini_api_key,
        model_name=model_name,
        max_iterations=max_iterations
    )


# Convenience function for quick usage
async def create_gemini_client(
    mcp_url: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    mcp_config: Optional[Dict[str, Any]] = None,
    mcp_config_path: Optional[str] = None,
    server_name: str = "ratings-api"
) -> GeminiMCPClient:
    """
    Create and initialize a Gemini MCP client.
    
    By default, automatically tries to load mcp.json configuration from common locations.
    Falls back to HTTP connection if mcp.json is not found.
    
    Args:
        mcp_url: MCP server URL (for HTTP connection, used as fallback)
        gemini_api_key: Gemini API key
        model_name: Gemini model name
        mcp_config: MCP server config dict (for stdio connection). If provided, uses stdio instead of HTTP.
        mcp_config_path: Path to mcp.json file. If None, searches common locations.
        server_name: Name of MCP server in config (default: "ratings-api")
        
    Returns:
        Initialized GeminiMCPClient
    """
    if mcp_config:
        # Use stdio connection from provided config dict
        client = create_client_from_mcp_config(mcp_config, gemini_api_key, model_name)
    elif mcp_config_path:
        # Load from specified file path
        config = load_mcp_config_from_file(mcp_config_path, server_name)
        if config:
            client = create_client_from_mcp_config(config, gemini_api_key, model_name)
        else:
            # Fall back to HTTP
            client = GeminiMCPClient(mcp_url, gemini_api_key, model_name)
    else:
        # Auto-load from mcp.json (default behavior)
        # GeminiMCPClient.__init__ will automatically search for mcp.json
        client = GeminiMCPClient(mcp_url, gemini_api_key, model_name)
    
    await client.initialize()
    await client.list_tools()
    return client
