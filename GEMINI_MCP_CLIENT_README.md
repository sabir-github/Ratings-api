# Gemini MCP Client

A Python client for integrating Google Gemini AI with the Ratings API MCP server. This client enables Gemini to interact with the Ratings API through function calling, allowing natural language queries to be translated into API calls.

## Features

- 🔌 **HTTP MCP Integration**: Connects to the MCP server via HTTP endpoints
- 🤖 **Gemini Function Calling**: Converts MCP tools to Gemini function calling format
- 💬 **Natural Language Interface**: Chat with Gemini to interact with the Ratings API
- 🔧 **Direct Tool Access**: Call MCP tools directly without Gemini
- 📦 **Async Support**: Fully asynchronous implementation
- 🛡️ **Error Handling**: Comprehensive error handling and logging

## Installation

1. Install the required dependencies:

```bash
pip install google-generativeai httpx
```

Or install from requirements.txt:

```bash
pip install -r requirements.txt
```

2. Get a Google Gemini API key:
   - Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Create a new API key
   - Set it as an environment variable: `export GEMINI_API_KEY=your_api_key_here`

## Quick Start

### Basic Usage

```python
import asyncio
from gemini_mcp_client import GeminiMCPClient

async def main():
    # Create and initialize client
    async with GeminiMCPClient(
        mcp_base_url="http://localhost:8000/api/v1/mcp",
        gemini_api_key="your_api_key_here"
    ) as client:
        # Chat with Gemini
        response = await client.chat_with_gemini("Get me all companies")
        print(response)

asyncio.run(main())
```

### Direct Tool Calls

```python
import asyncio
from gemini_mcp_client import GeminiMCPClient

async def main():
    async with GeminiMCPClient() as client:
        # Call MCP tools directly
        result = await client.call_mcp_tool("get_companies", {
            "skip": 0,
            "limit": 10
        })
        print(result)

asyncio.run(main())
```

## Usage Examples

### Example 1: Get Server Information

```python
async with GeminiMCPClient() as client:
    server_info = await client.get_server_info()
    print(f"Server: {server_info['serverInfo']['name']}")
    print(f"Tools: {server_info['tools']['count']}")
```

### Example 2: List Available Tools

```python
async with GeminiMCPClient() as client:
    tools = await client.list_tools()
    for tool in tools:
        print(f"{tool['name']}: {tool['description']}")
```

### Example 3: Chat with Gemini

```python
async with GeminiMCPClient(gemini_api_key="your_key") as client:
    # Ask Gemini to fetch data
    response = await client.chat_with_gemini(
        "Get all companies and show me their names"
    )
    print(response)
    
    # Ask Gemini to create data
    response = await client.chat_with_gemini(
        "Create a new company called 'Acme Corp' with code 'ACME'"
    )
    print(response)
```

### Example 4: Interactive Chat

```python
async with GeminiMCPClient(gemini_api_key="your_key") as client:
    conversation_history = []
    
    while True:
        user_input = input("You: ")
        if user_input.lower() == 'exit':
            break
        
        response = await client.chat_with_gemini(
            user_input,
            conversation_history=conversation_history
        )
        print(f"Gemini: {response}")
        
        # Update history
        conversation_history.append({"role": "user", "parts": [{"text": user_input}]})
        conversation_history.append({"role": "model", "parts": [{"text": response}]})
```

## API Reference

### GeminiMCPClient

#### Constructor

```python
GeminiMCPClient(
    mcp_base_url: str = "http://localhost:8000/api/v1/mcp",
    gemini_api_key: Optional[str] = None,
    model_name: str = "gemini-1.5-pro"
)
```

- `mcp_base_url`: Base URL for the MCP server
- `gemini_api_key`: Google Gemini API key (or set `GEMINI_API_KEY` env var)
- `model_name`: Gemini model to use (default: `gemini-1.5-pro`)

#### Methods

##### `initialize() -> Dict[str, Any]`
Initialize connection with the MCP server.

##### `get_server_info() -> Dict[str, Any]`
Get MCP server information including capabilities and available tools.

##### `list_tools(use_cache: bool = True) -> List[Dict[str, Any]]`
List all available MCP tools. Results are cached by default.

##### `get_gemini_functions() -> List[Dict[str, Any]]`
Get all MCP tools converted to Gemini function calling format.

##### `call_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]`
Call an MCP tool directly with the given arguments.

##### `chat_with_gemini(prompt: str, conversation_history: Optional[List] = None, max_iterations: int = 5) -> str`
Chat with Gemini, allowing it to use MCP tools. Supports multi-turn conversations.

##### `process_gemini_function_calls(function_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]`
Process multiple function calls from Gemini.

##### `close()`
Close the HTTP client connection.

## Available MCP Tools

The client provides access to all Ratings API endpoints as MCP tools:

### Companies
- `get_companies` - List companies with filtering
- `get_company` - Get company by ID
- `create_company` - Create new company
- `update_company` - Update company
- `delete_company` - Delete company

### Lines of Business (LOBs)
- `get_lobs` - List LOBs
- `get_lob` - Get LOB by ID
- `create_lob` - Create new LOB
- `update_lob` - Update LOB
- `delete_lob` - Delete LOB

### Products
- `get_products` - List products
- `get_product` - Get product by ID
- `create_product` - Create new product
- `update_product` - Update product
- `delete_product` - Delete product

### States
- `get_states` - List states
- `get_state` - Get state by ID
- `create_state` - Create new state
- `update_state` - Update state
- `delete_state` - Delete state

### Contexts
- `get_contexts` - List contexts
- `get_context` - Get context by ID
- `create_context` - Create new context
- `update_context` - Update context
- `delete_context` - Delete context

### Rating Tables
- `get_ratingtables` - List rating tables
- `get_ratingtable` - Get rating table by ID
- `create_ratingtable` - Create new rating table
- `update_ratingtable` - Update rating table
- `delete_ratingtable` - Delete rating table

### Algorithms
- `get_algorithms` - List algorithms
- `get_algorithm` - Get algorithm by ID
- `create_algorithm` - Create new algorithm
- `update_algorithm` - Update algorithm
- `delete_algorithm` - Delete algorithm

### Rating Manuals
- `get_ratingmanuals` - List rating manuals
- `get_ratingmanual` - Get rating manual by ID
- `create_ratingmanual` - Create new rating manual
- `update_ratingmanual` - Update rating manual
- `delete_ratingmanual` - Delete rating manual

### Rating Plans
- `get_ratingplans` - List rating plans
- `get_ratingplan` - Get rating plan by ID
- `create_ratingplan` - Create new rating plan
- `update_ratingplan` - Update rating plan
- `delete_ratingplan` - Delete rating plan

### System
- `health_check` - Check API and database health

## Running Examples

The repository includes an example script demonstrating various usage patterns:

```bash
# Set your Gemini API key
export GEMINI_API_KEY=your_api_key_here

# Make sure the Ratings API server is running
# Then run the example script
python example_gemini_usage.py
```

## Configuration

### Environment Variables

- `GEMINI_API_KEY`: Google Gemini API key (required for chat functionality)
- `MCP_BASE_URL`: MCP server base URL (default: `http://localhost:8000/api/v1/mcp`)

### Model Selection

You can use different Gemini models by specifying the `model_name` parameter:

- `gemini-2.0-flash-lite` - Fast and efficient, good balance (default)
- `gemini-1.5-pro` - Best for complex tasks
- `gemini-1.5-flash` - Faster, good for simple tasks

## Error Handling

The client includes comprehensive error handling:

- **Connection Errors**: Handles HTTP connection failures gracefully
- **MCP Protocol Errors**: Parses and reports JSON-RPC errors
- **Tool Execution Errors**: Catches and reports tool execution failures
- **Gemini API Errors**: Handles Gemini API errors with fallback options

## Troubleshooting

### Cannot connect to MCP server

1. Ensure the Ratings API server is running on `http://localhost:8000`
2. Check that the MCP endpoints are accessible: `curl http://localhost:8000/api/v1/mcp/status`
3. Verify the `mcp_base_url` parameter is correct

### Gemini API key not working

1. Verify your API key is valid at [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Check that the `GEMINI_API_KEY` environment variable is set correctly
3. Ensure you have API access enabled for your Google Cloud project

### Function calling not working

1. Make sure you've initialized the client and loaded tools: `await client.initialize()` and `await client.list_tools()`
2. Check that the MCP server is returning tools in the correct format
3. Verify your Gemini model supports function calling (use `gemini-1.5-pro` or newer)

## License

This client is part of the Ratings API project and follows the same license.

## Support

For issues or questions:
- Check the [EXTERNAL_AGENTS_SETUP.md](EXTERNAL_AGENTS_SETUP.md) guide
- Review the MCP server logs
- Test MCP endpoints directly using curl or the test script

