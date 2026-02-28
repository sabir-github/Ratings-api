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

# Try to import Google Gen AI (google-genai package)
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    genai = None  # type: ignore
    types = None  # type: ignore
    GEMINI_AVAILABLE = False
    logger.warning("google-genai not available. Install with: pip install google-genai")


def _safe_response_text(response: Any) -> str:
    """
    Safely extract text from a generate_content response (google.genai SDK).
    Uses response.text when available; otherwise walks candidates/parts.
    """
    try:
        if hasattr(response, "text") and response.text is not None:
            return (response.text or "").strip()
        if hasattr(response, "candidates") and response.candidates:
            parts_text = []
            for candidate in response.candidates:
                if getattr(candidate, "content", None) and getattr(candidate.content, "parts", None):
                    for part in candidate.content.parts:
                        if getattr(part, "text", None):
                            parts_text.append(part.text)
            return "".join(parts_text).strip() if parts_text else ""
        return ""
    except Exception as e:
        logger.debug(f"Safe response text extraction failed: {e}")
        return ""


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
        
        # Initialize Google Gen AI client (google.genai package)
        self.genai_client: Any = None
        if GEMINI_AVAILABLE and genai is not None:
            api_key = (
                gemini_api_key
                or (settings.GEMINI_API_KEY if settings else None)
                or os.getenv("GEMINI_API_KEY")
            )
            if api_key:
                self.genai_client = genai.Client(api_key=api_key)
                logger.debug(f"Gemini client created using {'parameter' if gemini_api_key else 'settings/.env' if settings and settings.GEMINI_API_KEY else 'environment variable'}")
            else:
                logger.warning(
                    "Gemini API key not provided. "
                    "Set GEMINI_API_KEY in .env file or pass gemini_api_key parameter."
                )

    @staticmethod
    def _normalize_model_name(name: str) -> str:
        """
        Normalize model name for google.genai (e.g. gemini-2.0-flash -> models/gemini-2.0-flash).
        """
        if not name:
            return name
        if name.startswith("models/"):
            return name
        return f"models/{name}"

    def list_available_gemini_models(self) -> List[Dict[str, Any]]:
        """
        List models visible to the current Gemini API key.
        """
        if not GEMINI_AVAILABLE or not self.genai_client:
            return []
        models = []
        try:
            for m in self.genai_client.models.list():
                models.append({
                    "name": getattr(m, "name", str(m)),
                    "display_name": getattr(m, "display_name", ""),
                    "description": getattr(m, "description", ""),
                })
        except Exception as e:
            logger.warning(f"Failed to list Gemini models: {e}")
        return models
    """
    # System instruction for InsureAI (used in generate_content config)
    SYSTEM_INSTRUCTION = (
        "You are InsureAI, an insurance rating assistant. Use the provided MCP tools for every data query; never answer from memory or general knowledge. "
        "For questions about companies, states, LOBs, products, contexts, rating tables, algorithms, manuals, plans, or system health, call the matching tool first and respond only from its result. "
        "Use get_companies for companies, get_states for states, get_lobs for LOBs, get_products for products, get_contexts for contexts, get_ratingtables for rating tables, get_algorithms for algorithms, get_ratingmanuals for manuals, get_ratingplans for plans, health_check for status, and evaluate_expression for math or premium formulas. "
        "Base your reply only on what the tool returned; if it returns nothing or an error, say so. "
        "Answer only about insurance rating, premium calculation, and test case validation; for other topics, decline politely. "
        "Validate test cases from user or underwriter inputs using algorithm steps from the MCP server. "
        "Ask inputs hierarchically, fetch required values via tools, then calculate premium from those inputs and fetched values. "
        "Analyze data structures, formulas, and metadata for correctness. "
        "The system has COMPANY, LOB, PRODUCT, STATE, CONTEXTS, rating_tables, algorithms, and rate_configurations; fetch product ratings and information using the tools. "
        "Explain your reasoning before calling a tool. "
        "Calculate premiums by following algorithm steps; ask for missing inputs in a structured way; guide users on how you calculated premium. "
        "Answer only questions relevant to your goals and the available tools."
    )
    """
    SYSTEM_INSTRUCTION = ("""
            You are a helpful assistant connected to an MCP server and You are an expert in validating insurance rating algorithms.
            ## Your Name
            Your name is InsureAI.
            ## Your Task
            Validate the test cases based on user/underwriter inputs and use the algorithm steps fetched from MCP server for insurance rating workbench.
            Your goal is to ask the inputs from user for a given test case in a hierarchical way, and fetch the required values from MCP server using the available tools, and then calculate
            premium using those inputs and fetched values.
            Analyze data structures, formulas, calculations, and AI metadata for correctness and consistency.

            ## Reliability and no hallucinations
            Always ground every answer in MCP tool results and user-provided inputs. Never invent or assume companies, LOBs, products, states, contexts, rating tables, algorithms, rating plans, manuals, premiums, test cases, or scope IDs that are not present in tool responses or explicitly given by the user. If a required tool returns no items, partial data, or an error, clearly state that the information is unavailable or incomplete instead of guessing. Do not fabricate rating tables, factors, formulas, or outputs. When you are unsure or the data is ambiguous, ask a clear clarifying question about what is missing or which tool result is needed—do not hallucinate an answer.

            ## Required workflow (follow this order strictly)
            For premium calculation or rating validation, you MUST follow this hierarchy. Do not skip steps or call rating plans or algorithms before you have the scope. 
            1. **Get scope first**: Obtain company, LOB, state, and product. When the user asks to list states, show states, or which states are available, you MUST call get_states (do not answer from memory). When you need state_id or state options, call get_states. Similarly use get_companies, get_lobs, get_products to list or resolve options. If the user has not provided scope, you may ask—but if they ask "what states?" or "list states", call get_states immediately. When the user gives state name as "ALL" (in any case), always search for that record in the system: call get_states with state_name="ALL" to get the state_id and use it in rating plans, algorithms, and calculations—do not assume or skip this lookup. Once you have resolved scope, memorize or store the four scope IDs: company_id, lob_id, state_id, product_id.
            2. **When a rating plan or any other attribute is defined for state "ALL" in the system, it means that rating plan or attribute is applicable for any state regardless of user input. When there is no match for the user's state name (e.g. get_states returns no items, or get_ratingplans/get_algorithms return empty for that state_id), by default use the state "ALL": call get_states with state_name="ALL" to get the state_id and use that state_id for rating plans, algorithms, and calculations so the user still gets the corresponding attributes for "ALL".
            3. **Then get rating plans**: Once you have company_id, lob_id, state_id, and product_id, call get_ratingplans with those filters to find the applicable rating plan(s).
            4. **Then get algorithms**: Using the same scope (and algorithm_id from the plan if available), call get_algorithms to fetch the calculation logic (formula, calculation_steps, variables).
            5. **When prompting for user inputs from the calculation steps**: Ask only for inputs that are defined in the algorithm's calculation_steps (fetched from get_algorithms). Do not deviate from or add to those steps—do not ask questions from your own knowledge or invent inputs. Ask for one input at a time, in the order of the calculation steps. Do not ask for all inputs in a single message—prompt for each question or input from the calculation steps one by one, wait for the user's answer, then prompt for the next. Treat the user's answers as the input and intermediate values for the formula. If a step asks for state (code or name), the user's answer is for factor lookup only—never use it to change scope (see "State in calculation steps" below). Fetch any factor values (rates, factors, multipliers) from the corresponding rating_tables: call get_ratingtables with the same scope (company_id, lob_id, state_id, product_id) to get the relevant tables, then use the table data to look up factors that the algorithm expression needs.
            6. **Execute the calculation**: Pass the algorithm expression and all variables to evaluate_expression: (a) expression = the formula/expression from the algorithm, (b) variables = a dict combining the user's inputs (answers to the calculation-step queries), any intermediate variables from the algorithm, and the factor values fetched from the rating_tables. Then call evaluate_expression with that expression and variables to get the premium result. Guide the user on how you calculated the premium.

            ## Scope IDs: memorize and always use for rating tables, plans, algorithms
            Memorize or store the scope IDs (company_id, lob_id, state_id, product_id) once you have resolved them in step 1. Always use these same IDs when calling get_ratingtables, get_ratingplans, and get_algorithms—do not substitute names or re-lookup IDs for these scope parameters; use the stored IDs for every search in rating tables, rating plans, and rating algorithms.

            ## User inputs: calculation steps only (do not deviate or hallucinate)
            For a given algorithm, ask the user only for inputs that appear in that algorithm's calculation_steps. Do not deviate from the steps or ask questions from your own knowledge. Do not hallucinate or invent additional inputs—if the algorithm has N steps that require user input, ask exactly those N; no more, no less, and no different questions. Use only the questions/inputs defined in the algorithm data from get_algorithms.

            ## State in calculation steps (CRITICAL: do not change scope)
            The scope (company_id, lob_id, state_id, product_id) is fixed in step 1 and must never be updated from user answers to calculation-step questions. When the algorithm's calculation steps ask for a state code or state name (e.g. "What state?", "Enter state code"), the user's reply (e.g. "NY", "CA", "ALL") is for factor lookup only: use it for lookup to find the correct value in the rating table for that state. Do NOT use that state to look up or overwrite state_id in scope. Do NOT call get_states with the user's calculation-step state and then use that state_id for get_ratingplans, get_algorithms, or get_ratingtables. Always use the original state_id from step 1 for those tool calls. Summary: scope state_id = from step 1 only; state from calculation-step user input only for looking up a factor in the Rating tables, never for scope.

            ## Schema Overview
            The system consists of 8 core collections:
            1. **COMPANIES** - Insurance company records
            2. **LOBS** - Lines of Business (EPL)
            3. **PRODUCTS** - Insurance products (EPL Standard Coverage)
            4. **STATES** - All states that rating is applicable (except "ALL" which is applicable for any state)
            5. **CONTEXTS** - contains all Rating questions and validation rules associated with Rating tables and algorithms
            6. **ratingtables** - Premium rating tables (base rates, factors, multipliers)
            7. **algorithms** - Premium calculation formulas and workflows
            8. **ratingplans** - Configuration linking all components.
            Your goal is to fetch product ratings and information using the available tools.
            Always explain your reasoning before calling a tool.

            ## Search behavior
            Ignore case sensitivity for any search. When calling tools with name or text filters (e.g. state_name, company_name, plan_name, algorithm_name, product_name, lob_name), treat searches as case-insensitive: "NY", "ny", "Ny" and "all", "ALL", "All" are equivalent. Pass the user's input as-is; the system performs case-insensitive matching. When the user inputs state name as "ALL" (any case), always look up the state record in the system by calling get_states with state_name="ALL" and use the returned state_id for all downstream tool calls—never assume or skip this search. When there is no match for the user's state name (empty results from get_states or from get_ratingplans/get_algorithms for that state), by default use the state "ALL": look up get_states with state_name="ALL", get its state_id, and use that for rating plans, algorithms, and calculations so the user gets the corresponding attributes for "ALL".

            ## Variable and field name formatting
            Treat backslash-escaped underscores in variable or field names as equivalent to plain underscores. For example: Distribution\\_System\\_Credit = Distribution_System_Credit. When you see names like "Distribution\\_System\\_Credit" in algorithm steps, rating tables, or user input, use the form with plain underscores (Distribution_System_Credit) when building the variables dict for evaluate_expression and when matching keys from rating_tables or algorithm data, so the expression and variables use consistent names.

            Capabilities:
            1.  **Calculate premiums for insurance product**: Follow the workflow above: scope -> rating plans -> algorithms -> get user answers for calculation-step queries -> fetch factor values from rating_tables -> call evaluate_expression with the algorithm expression and variables (user inputs + factors from tables).
            2.  **Ask user for inputs if missing**: Ask for company, LOB, state, and product first; then ask only for the inputs required by the algorithm's calculation steps (from get_algorithms)—one by one (one question per message), not all at once. Do not ask for inputs that are not in the calculation steps; do not deviate or use your own knowledge. Use the user's answers as expression variables.
            3.  **Fetch factors from rating_tables**: Use get_ratingtables (same scope as the plan/algorithm) to obtain the tables; look up the factor values needed by the algorithm expression and add them to the variables dict for evaluate_expression.
            4.  **Show reasoning**: Guide users on how you have calculated insurance premium.
            5.  **DO NOT ANSWER OTHER QUESTIONS**: Only answer the questions which are relevant to your goals, capabilities, and the data and tools available in MCP server.
            """
    )   
    def _ensure_model(self) -> None:
        """Set model name for generate_content (client already created in __init__)."""
        if not GEMINI_AVAILABLE:
            logger.warning("google-genai not available.")
            return
        if self.model_name is not None:
            return
        self.model_name = self._normalize_model_name(self.requested_model_name)
        logger.info(f"Using Gemini model: {self.model_name}")
    
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
    
    # Common parameter descriptions so Gemini understands args when MCP omits them
    _PARAM_DESCRIPTIONS: Dict[str, str] = {
        "skip": "Number of records to skip for pagination (default 0).",
        "limit": "Maximum number of records to return (e.g. 100).",
        "active": "Filter by active status: true, false, or omit for all.",
        "company_name": "Filter by company name (partial match).",
        "company_code": "Filter by company code (partial match).",
        "tax_id": "Filter by tax ID (partial match).",
        "company_id": "Filter by company ID (integer).",
        "lob_id": "Filter by Line of Business ID.",
        "lob_name": "Filter by LOB name (partial match).",
        "product_id": "Filter by product ID.",
        "product_name": "Filter by product name (partial match).",
        "state_id": "Filter by state ID.",
        "state_name": "Search for a state by name or code (partial match). Use when user says State = ALL or asks for a specific state (e.g. state_name='ALL', state_name='NY').",
        "context_id": "Filter by context ID.",
        "context_name": "Filter by context name (partial match).",
        "ratingtable_id": "Rating table ID (integer).",
        "table_name": "Filter by rating table name (partial match).",
        "table_type": "Filter by table type (e.g. BASE, LOAD, FACTOR).",
        "algorithm_id": "Algorithm ID (integer).",
        "algorithm_name": "Filter by algorithm name (partial match).",
        "ratingmanual_id": "Rating manual ID (integer).",
        "manual_name": "Filter by manual name (partial match).",
        "ratingplan_id": "Rating plan ID (integer).",
        "plan_name": "Filter by plan name (partial match).",
        "effective_date": "Filter by effective date (YYYY-MM-DD).",
        "expression": "Mathematical expression to evaluate (e.g. 'base_rate * factor').",
        "variables": "Dict of variable names to values used in the expression.",
    }

    def _tool_description_for_gemini(self, tool_name: str, raw_description: str) -> str:
        """Build a short, clear tool description so Gemini knows when and how to use it."""
        if not raw_description or not raw_description.strip():
            # Fallback one-liners for known tools
            fallbacks = {
                "get_companies": "List insurance companies. Use first (step 1) to get company_id for premium scope. Also when user asks to list companies or find company by name, code, or tax ID. Returns items (id, company_code, company_name, active, hq_address={Street1,Street2,City,State_Province,PostalCode,CountryCode}, tax_id) and count.",
                "get_legal_entities": "List legal entities (registered entities with contracts/licenses). Use when user asks for legal entities, entities by company, or by name/type/jurisdiction. Returns id, company_id, legal_name, entity_type, identifier (LEI), jurisdiction, registration_number, active.",
                "get_legal_entity_addresses": "List legal entity addresses (Registered, Physical, Mailing). Use when user asks for addresses of a legal entity. Filter by legal_entity_id, address_type. Returns full_address and components (street1, city, state_province, postal_code, country_code).",
                "get_lobs": "List lines of business (LOB). Use first (step 1) to get lob_id for premium scope. Also when user asks for LOBs or to filter by company. Returns items and count.",
                "get_products": "List insurance products. Use first (step 1) to get product_id for premium scope. Also when user asks for products or to filter by company/LOB. Returns items and count.",
                "get_states": "List or find states. Call this whenever the user asks to list states, show states, what states are available, or when you need state_id or state options (e.g. step 1 of premium). For State = ALL use state_name='ALL'; for NY use state_name='NY'. Returns (id, state_code, state_name, active). Always use this tool for state data—never answer about states without calling it.",
                "get_contexts": "List rating contexts (questions/rules). Use when user asks for contexts or validation rules. Returns items and count.",
                "get_ratingtables": "List rating tables (rates, factors). Use when user asks for rating tables or to filter by company/LOB/state/product/entity. Returns items and count.",
                "get_ratingtable": "Get one rating table by ID. Use when you have a ratingtable_id and need full details.",
                "get_algorithms": "List rating algorithms (calculation logic). Call only AFTER you have company_id, lob_id, state_id, product_id, entity_id (from step 1 and 2). Use to get algorithm steps for premium calculation. Returns items and count.",
                "get_algorithm": "Get one algorithm by ID. Use when you have an algorithm_id and need formula or logic.",
                "get_ratingmanuals": "List rating manuals. Use when user asks for manuals or rating data by company/LOB/state/product/entity. Returns items and count.",
                "get_ratingmanual": "Get one rating manual by ID.",
                "get_ratingplans": "List rating plans. Call only AFTER you have company_id, lob_id, state_id, product_id, entity_id (from get_companies, get_lobs, get_states, get_products, get_legal_entities). Use to find plans for that scope. Returns items and count.",
                "get_ratingplan": "Get one rating plan by ID.",
                "health_check": "Check if the API and database are up. Use when user asks about system health or status. Returns status and database connection.",
                "evaluate_expression": "Evaluate a math expression with variables (e.g. for premium). Use last (step 4) after you have the algorithm and variable values. Pass expression (string) and variables (dict).",
            }
            return fallbacks.get(tool_name, f"Call MCP tool: {tool_name}.")
        # Use first paragraph or first ~400 chars; strip extra newlines
        first = raw_description.strip().split("\n\n")[0]
        first = first.replace("\n", " ").strip()
        if len(first) > 380:
            first = first[:377].rsplit(" ", 1)[0] + "..."
        return first

    def _convert_mcp_tool_to_gemini_function(self, mcp_tool: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert an MCP tool definition to Gemini function calling format.
        Enriches descriptions so Gemini can choose and use tools correctly.
        """
        tool_name = mcp_tool.get("name", "")
        raw_description = mcp_tool.get("description", "")
        tool_description = self._tool_description_for_gemini(tool_name, raw_description)

        # Extract input schema from MCP tool
        input_schema = mcp_tool.get("inputSchema", {})
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])

        # Convert properties to Gemini format; fill missing param descriptions
        gemini_properties = {}

        # Core ID parameters we want to accept as either string or number.
        # MCP tools (_safe_int, _id_match) already handle both; this avoids
        # Gemini-side validation errors like "'100000001' is not valid under any of the given schemas".
        id_param_names = {
            "company_id",
            "legal_entity_id",
            "lob_id",
            "state_id",
            "product_id",
            "algorithm_id",
            "ratingplan_id",
            "ratingtable_id",
            "ratingmanual_id",
            "context_id",
        }

        for prop_name, prop_def in properties.items():
            prop_type = prop_def.get("type", "string")
            prop_desc = (prop_def.get("description") or "").strip()
            if not prop_desc:
                prop_desc = self._PARAM_DESCRIPTIONS.get(
                    prop_name,
                    prop_name.replace("_", " ").title() + ".",
                )

            # For ID parameters, allow both string and number so Gemini can pass
            # IDs like "100000001" or 100000001 without schema errors.
            if prop_name in id_param_names:
                gemini_properties[prop_name] = {
                    "anyOf": [
                        {"type": "string"},
                        {"type": "number"},
                    ],
                    "description": prop_desc,
                }
                continue

            gemini_type = prop_type
            if prop_type == "integer":
                gemini_type = "number"

            gemini_properties[prop_name] = {
                "type": gemini_type,
                "description": prop_desc,
            }
            if "enum" in prop_def:
                gemini_properties[prop_name]["enum"] = prop_def["enum"]

        return {
            "name": tool_name,
            "description": tool_description,
            "parameters": {
                "type": "object",
                "properties": gemini_properties,
                "required": required,
            },
        }
    
    def get_gemini_functions(self) -> List[Dict[str, Any]]:
        """
        Get all MCP tools converted to Gemini function calling format (dict).
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

    def _build_genai_tool(self) -> Any:
        """Build google.genai types.Tool from get_gemini_functions() for GenerateContentConfig."""
        if not GEMINI_AVAILABLE or types is None:
            return None
        funcs = self.get_gemini_functions()
        declarations = []
        for f in funcs:
            declarations.append(
                types.FunctionDeclaration(
                    name=f["name"],
                    description=f.get("description", ""),
                    parameters_json_schema=f.get("parameters", {"type": "object", "properties": {}, "required": []}),
                )
            )
        return types.Tool(function_declarations=declarations) if declarations else None
    
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
    
    def _part_to_dict(self, part: Any) -> Dict[str, Any]:
        """Serialize a Part to a dict for storing in conversation history (like Gemini CLI context)."""
        if getattr(part, "text", None) is not None and part.text != "":
            return {"text": part.text}
        if getattr(part, "function_call", None):
            fc = part.function_call
            args = getattr(fc, "args", None)
            return {"function_call": {"name": getattr(fc, "name", ""), "args": dict(args) if args and hasattr(args, "items") else {}}}
        if getattr(part, "function_response", None):
            fr = part.function_response
            return {"function_response": {"name": getattr(fr, "name", ""), "response": getattr(fr, "response", {})}}
        return {"text": getattr(part, "text", "") or ""}

    def _content_to_dict(self, content: Any) -> Dict[str, Any]:
        """Serialize a Content to a dict for conversation history."""
        parts = getattr(content, "parts", None) or []
        return {"role": getattr(content, "role", "model"), "parts": [self._part_to_dict(p) for p in parts]}

    def _history_to_contents(self, conversation_history: List[Dict[str, Any]]) -> List[Any]:
        """Convert conversation_history (role/parts) to google.genai types.Content list. Supports text, function_call, and function_response parts (like Gemini CLI)."""
        if not GEMINI_AVAILABLE or types is None:
            return []
        contents = []
        for msg in conversation_history:
            role = (msg.get("role") or "user").lower()
            parts = msg.get("parts") or []
            part_objs = []
            for p in parts:
                if isinstance(p, dict):
                    if "text" in p and p.get("text") is not None:
                        part_objs.append(types.Part.from_text(text=p["text"] or ""))
                    elif "function_call" in p:
                        fc = p["function_call"]
                        try:
                            fc_obj = types.FunctionCall(name=fc.get("name", ""), args=fc.get("args") or {})
                            part_objs.append(types.Part(function_call=fc_obj))
                        except (TypeError, AttributeError):
                            part_objs.append(types.Part.from_text(text=f"(tool call: {fc.get('name', '')})"))
                    elif "function_response" in p:
                        fr = p["function_response"]
                        part_objs.append(types.Part.from_function_response(name=fr.get("name", ""), response=fr.get("response", {})))
                elif hasattr(p, "text") and p.text is not None:
                    part_objs.append(types.Part.from_text(text=p.text))
                elif getattr(p, "function_call", None):
                    part_objs.append(p)
                elif getattr(p, "function_response", None):
                    part_objs.append(p)
            if part_objs:
                contents.append(types.Content(role=role, parts=part_objs))
        return contents

    async def chat_with_gemini(
        self,
        prompt: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        max_iterations: Optional[int] = None,
        return_turn_contents: bool = False,
    ):
        """
        Chat with Gemini using MCP tools (google.genai client.aio.models.generate_content).
        If return_turn_contents is True, returns (response_text, turn_contents) so the caller can persist
        model/tool turns in history (like Gemini CLI) for correct follow-up context.
        """
        if max_iterations is None:
            max_iterations = self.max_iterations
        if not GEMINI_AVAILABLE:
            raise RuntimeError("google-genai not installed. Run: pip install google-genai")
        self._ensure_model()
        if not self.genai_client:
            raise RuntimeError("Gemini client not initialized. Provide API key.")
        if self.model_name is None:
            raise RuntimeError("Gemini model name not set.")
        if not self.initialized:
            await self.initialize()
        if not self.tools_cache:
            await self.list_tools()

        tool = self._build_genai_tool()
        # Generation config aligned with Gemini CLI (chat-base: temperature 0.7, topP 1.0, etc.)
        config_kw: Dict[str, Any] = {
            "system_instruction": self.SYSTEM_INSTRUCTION,
            "temperature": getattr(settings, "GEMINI_TEMPERATURE", 0.7),
            "top_p": getattr(settings, "GEMINI_TOP_P", 1.0),
            "top_k": getattr(settings, "GEMINI_TOP_K", 40),
        }
        max_tokens = getattr(settings, "GEMINI_MAX_OUTPUT_TOKENS", None)
        if max_tokens is not None and max_tokens > 0:
            config_kw["max_output_tokens"] = max_tokens
        if tool is not None:
            config_kw["tools"] = [tool]
            logger.info(f"Chat start: {len(self.get_gemini_functions())} function declaration(s)")

        # Build contents: history + new user message
        contents: List[Any] = self._history_to_contents(conversation_history or [])
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=prompt)]))
        initial_len = len(contents)

        def _get_function_call_name_and_args(fc: Any) -> tuple:
            """Extract (name, args) from a function-call part or FunctionCall object."""
            name = None
            args = {}
            if getattr(fc, "function_call", None):
                name = getattr(fc.function_call, "name", None)
                a = getattr(fc.function_call, "args", None)
                if a is not None:
                    args = dict(a) if hasattr(a, "items") else {}
            if name is None:
                name = getattr(fc, "name", None)
            if not args and hasattr(fc, "args"):
                a = fc.args
                args = dict(a) if a and hasattr(a, "items") else {}
            return (name, args)

        def _format_tool_result_fallback(tool_name: str, tool_result: Dict[str, Any]) -> str:
            """Format tool result as readable text when model returns empty (e.g. list companies)."""
            if isinstance(tool_result, dict) and "error" in tool_result:
                return f"Tool {tool_name} error: {tool_result.get('error', 'Unknown')}"
            items = tool_result.get("items") if isinstance(tool_result, dict) else None
            count = tool_result.get("count") if isinstance(tool_result, dict) else None
            if items is not None and isinstance(items, list):
                lines = [f"Found {count or len(items)} item(s):"]
                for i, row in enumerate(items[:50], 1):
                    if isinstance(row, dict):
                        parts = [f"{k}={v}" for k, v in list(row.items())[:6]]
                        lines.append(f"  {i}. " + ", ".join(parts))
                    else:
                        lines.append(f"  {i}. {row}")
                if items and len(items) > 50:
                    lines.append(f"  ... and {len(items) - 50} more")
                return "\n".join(lines)
            return json.dumps(tool_result, default=str)[:2000]

        try:
            response = await self.genai_client.aio.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(**config_kw),
            )
            iteration = 0
            last_tool_results: List[Dict[str, Any]] = []  # for fallback when model returns empty

            while iteration < max_iterations:
                # Collect function calls from response.function_calls or candidates[0].content.parts
                function_calls: List[Any] = []
                if getattr(response, "function_calls", None):
                    function_calls = list(response.function_calls)
                if not function_calls and getattr(response, "candidates", None) and response.candidates:
                    c0 = response.candidates[0]
                    if getattr(c0, "content", None) and getattr(c0.content, "parts", None):
                        for part in c0.content.parts:
                            if getattr(part, "function_call", None):
                                function_calls.append(part)

                if not function_calls:
                    text = _safe_response_text(response)
                    if text:
                        if return_turn_contents:
                            return (text, [{"role": "model", "parts": [{"text": text}]}])
                        return text
                    # Model returned no text; if we have last tool results, show them
                    if last_tool_results:
                        fallback_lines = []
                        for tr in last_tool_results:
                            fallback_lines.append(_format_tool_result_fallback(tr["name"], tr["response"]))
                        fallback_text = "\n\n".join(fallback_lines)
                        contents.append(types.Content(role="model", parts=[types.Part.from_text(text=fallback_text)]))
                        if return_turn_contents:
                            return (fallback_text, [self._content_to_dict(c) for c in contents[initial_len:]])
                        return fallback_text
                    out = text or "(No response from model.)"
                    if return_turn_contents:
                        return (out, [{"role": "model", "parts": [{"text": out}]}])
                    return out

                # Append model content (function calls) to history
                if response.candidates and response.candidates[0].content:
                    contents.append(types.Content(role="model", parts=response.candidates[0].content.parts))

                # Call MCP tools and build tool response content
                tool_parts = []
                last_tool_results = []
                for fc in function_calls:
                    name, args = _get_function_call_name_and_args(fc)
                    if not name:
                        continue
                    logger.info(f"Gemini calling function: {name} with args: {args}")
                    try:
                        tool_result = await self.call_mcp_tool(name, args)
                    except Exception as e:
                        logger.error(f"Error calling tool {name}: {e}")
                        tool_result = {"error": str(e)}
                    last_tool_results.append({"name": name, "response": tool_result})
                    tool_parts.append(types.Part.from_function_response(name=name, response=tool_result))

                if not tool_parts:
                    break
                contents.append(types.Content(role="tool", parts=tool_parts))
                response = await self.genai_client.aio.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(**config_kw),
                )
                iteration += 1

            text = _safe_response_text(response)
            if text:
                contents.append(types.Content(role="model", parts=[types.Part.from_text(text=text)]))
                if return_turn_contents:
                    return (text, [self._content_to_dict(c) for c in contents[initial_len:]])
                return text
            if last_tool_results:
                fallback_lines = [_format_tool_result_fallback(tr["name"], tr["response"]) for tr in last_tool_results]
                fallback_text = "\n\n".join(fallback_lines)
                contents.append(types.Content(role="model", parts=[types.Part.from_text(text=fallback_text)]))
                if return_turn_contents:
                    return (fallback_text, [self._content_to_dict(c) for c in contents[initial_len:]])
                return fallback_text
            out = text or "(No response from model.)"
            contents.append(types.Content(role="model", parts=[types.Part.from_text(text=out)]))
            if return_turn_contents:
                return (out, [self._content_to_dict(c) for c in contents[initial_len:]])
            return out

        except Exception as e:
            logger.error(f"Error in chat_with_gemini: {e}")
            try:
                # Fallback without tools
                contents_fallback = self._history_to_contents(conversation_history or [])
                contents_fallback.append(types.Content(role="user", parts=[types.Part.from_text(text=prompt)]))
                response = await self.genai_client.aio.models.generate_content(
                    model=self.model_name,
                    contents=contents_fallback,
                    config=types.GenerateContentConfig(
                        system_instruction=self.SYSTEM_INSTRUCTION,
                        temperature=getattr(settings, "GEMINI_TEMPERATURE", 0.7),
                        top_p=getattr(settings, "GEMINI_TOP_P", 1.0),
                        top_k=getattr(settings, "GEMINI_TOP_K", 40),
                        **({"max_output_tokens": settings.GEMINI_MAX_OUTPUT_TOKENS} if getattr(settings, "GEMINI_MAX_OUTPUT_TOKENS", 0) > 0 else {}),
                    ),
                )
                fallback_text = _safe_response_text(response)
                if return_turn_contents:
                    return (fallback_text, [{"role": "model", "parts": [{"text": fallback_text}]}])
                return fallback_text
            except Exception as fallback_error:
                raise Exception(f"Both tool-enabled and fallback chat failed: {fallback_error}") from e
    
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


def _normalize_mcp_config_paths(config: Dict[str, Any], config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Normalize MCP server paths for local dev. If args reference /app/run_mcp_server.py
    and that path doesn't exist (e.g. not running in Docker), use project-root path
    so stdio works like the CLI.
    """
    import copy
    config = copy.deepcopy(config)
    args = config.get("args", [])
    if not args:
        return config
    project_root = os.path.dirname(os.path.abspath(__file__))
    local_script = os.path.join(project_root, "run_mcp_server.py")
    normalized = []
    for a in args:
        if isinstance(a, str) and "/app/" in a and "run_mcp_server" in a:
            if not os.path.isfile(a) and os.path.isfile(local_script):
                normalized.append(local_script)
                logger.info(f"MCP config: using local path {local_script} instead of {a}")
                continue
        normalized.append(a)
    if normalized != args:
        config["args"] = normalized
    return config


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
        config = mcp_servers[server_name]
        # Normalize paths for local dev: /app/... often doesn't exist outside Docker
        config = _normalize_mcp_config_paths(config, config_path)
        return config
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
