# Chat Assistant API Usage Guide

This guide explains how to use the Chat Assistant API endpoints that integrate Gemini AI with the MCP server for UI chat assistant integration.

## Overview

The Chat Assistant API provides HTTP endpoints that allow a frontend UI to interact with Gemini AI, which can use MCP tools to access the Ratings API. This enables natural language interaction with your Ratings API through a chat interface.

## Available Endpoints

### 1. Chat Endpoint (POST)
**URL:** `POST /api/v1/chat`

Send a chat message and get a response from Gemini.

**Request Body:**
```json
{
  "message": "Get me all companies",
  "session_id": "optional-session-id"
}
```

**Note:** `gemini_api_key`, `model_name`, and `max_iterations` are now configured in the config file (`.env` or `app/core/config.py`), not in the request.

**Response:**
```json
{
  "response": "I found 2 companies in the database...",
  "session_id": "session_abc123",
  "model_used": "gemini-2.0-pro"
}
```

### 2. Stream Chat Endpoint (POST)
**URL:** `POST /api/v1/chat/stream`

Stream chat response using Server-Sent Events (SSE) for real-time updates.

**Request Body:** Same as chat endpoint

**Response:** Server-Sent Events stream

### 3. Get Chat History (GET)
**URL:** `GET /api/v1/chat/history/{session_id}`

Get conversation history for a session.

**Response:**
```json
{
  "session_id": "session_abc123",
  "history": [
    {
      "role": "user",
      "parts": [{"text": "Get me all companies"}]
    },
    {
      "role": "model",
      "parts": [{"text": "I found 2 companies..."}]
    }
  ],
  "message_count": 2
}
```

### 4. Clear Chat History (DELETE)
**URL:** `DELETE /api/v1/chat/history/{session_id}`

Clear conversation history for a session.

### 5. List Sessions (GET)
**URL:** `GET /api/v1/chat/sessions`

Get list of all active chat sessions.

### 6. Chat Status (GET)
**URL:** `GET /api/v1/chat/status`

Get chat service status and configuration.

## Usage Examples

### JavaScript/Fetch Example

```javascript
// Send a chat message
async function sendChatMessage(message, sessionId = null) {
      const response = await fetch('http://localhost:8000/api/v1/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: message,
          session_id: sessionId
          // Note: gemini_api_key and model_name are configured in config file, not in request
        })
      });
  
  const data = await response.json();
  return data;
}

// Usage
const result = await sendChatMessage("Get me all companies");
console.log(result.response); // Assistant's response
console.log(result.session_id); // Session ID for history
```

### Streaming Example (Server-Sent Events)

```javascript
// Stream chat response
async function streamChatMessage(message, sessionId, onChunk) {
  const response = await fetch('http://localhost:8000/api/v1/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message: message,
      session_id: sessionId
    })
  });
  
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (data === '[DONE]') return;
        
        try {
          const json = JSON.parse(data);
          onChunk(json);
        } catch (e) {
          console.error('Error parsing chunk:', e);
        }
      }
    }
  }
}

// Usage
streamChatMessage("Get me all companies", null, (chunk) => {
  console.log(chunk.response);
});
```

### React Example

```jsx
import { useState } from 'react';

function ChatAssistant() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState(null);
  const [loading, setLoading] = useState(false);
  
  const sendMessage = async () => {
    if (!input.trim()) return;
    
    setLoading(true);
    
    // Add user message
    setMessages(prev => [...prev, { role: 'user', text: input }]);
    
    try {
      const response = await fetch('http://localhost:8000/api/v1/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: input,
          session_id: sessionId
        })
      });
      
      const data = await response.json();
      
      // Update session ID if first message
      if (!sessionId) {
        setSessionId(data.session_id);
      }
      
      // Add assistant response
      setMessages(prev => [...prev, { role: 'assistant', text: data.response }]);
      setInput('');
    } catch (error) {
      console.error('Error:', error);
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        text: 'Sorry, there was an error processing your message.' 
      }]);
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="chat-container">
      <div className="messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            {msg.text}
          </div>
        ))}
      </div>
      
      <div className="input-area">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
          placeholder="Type your message..."
          disabled={loading}
        />
        <button onClick={sendMessage} disabled={loading || !input.trim()}>
          {loading ? 'Sending...' : 'Send'}
        </button>
      </div>
    </div>
  );
}

export default ChatAssistant;
```

### Python Example

```python
import httpx
import asyncio

async def chat_with_assistant(message: str, session_id: str = None):
    """Send a chat message to the assistant"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/chat",
            json={
                "message": message,
                "session_id": session_id
                # Note: model_name is configured in config file
            }
        )
        response.raise_for_status()
        return response.json()

# Usage
async def main():
    result = await chat_with_assistant("Get me all companies")
    print(f"Response: {result['response']}")
    print(f"Session ID: {result['session_id']}")

asyncio.run(main())
```

### cURL Examples

```bash
# Send a chat message
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Get me all companies"
  }'

# Get chat history
curl http://localhost:8000/api/v1/chat/history/session_abc123

# Clear chat history
curl -X DELETE http://localhost:8000/api/v1/chat/history/session_abc123

# Check chat status
curl http://localhost:8000/api/v1/chat/status

# List all sessions
curl http://localhost:8000/api/v1/chat/sessions
```

## Configuration

### Config File Settings

AI/Chat settings are configured in the config file (`.env` file or `app/core/config.py`):

**Required Settings:**
- `GEMINI_API_KEY`: Google Gemini API key (required)

**Optional Settings:**
- `GEMINI_MODEL_NAME`: Gemini model to use (default: `gemini-2.0-pro`)
- `GEMINI_AUTO_FALLBACK_MODEL`: Auto-fallback to available model if requested one isn't available (default: `True`)
- `GEMINI_MAX_ITERATIONS`: Maximum function call iterations (default: `5`)
- `MCP_BASE_URL`: MCP server base URL (default: `http://localhost:8000/api/v1/mcp`)

### Example `.env` Configuration

```bash
# AI/Chat Assistant Configuration
GEMINI_API_KEY=your_google_gemini_api_key_here
GEMINI_MODEL_NAME=gemini-2.0-pro
GEMINI_AUTO_FALLBACK_MODEL=True
GEMINI_MAX_ITERATIONS=5
MCP_BASE_URL=http://localhost:8000/api/v1/mcp
```

### Request Parameters

- `message` (required): User message to send
- `session_id` (optional): Session ID for conversation history

**Note:** `gemini_api_key`, `model_name`, and `max_iterations` are no longer accepted in requests - they must be configured in the config file.

## Features

1. **Conversation History**: Maintains conversation context across messages using session IDs
2. **MCP Tool Integration**: Gemini can use all MCP tools to interact with the Ratings API
3. **Streaming Support**: Real-time streaming responses using SSE
4. **Multiple Sessions**: Support for multiple concurrent chat sessions
5. **Model Selection**: Choose which Gemini model to use
6. **Error Handling**: Comprehensive error handling and status reporting

## Example Chat Interactions

### Example 1: Getting Data

```
User: Get me all companies
Assistant: I found 2 companies in the database:
1. C001 (C001)
2. C002 (c002)
Would you like more details about any specific company?
```

### Example 2: Creating Data

```
User: Create a new company called "Acme Corp" with code "ACME"
Assistant: I've created the company "Acme Corp" with code "ACME". The company has been assigned ID 100000003.
```

### Example 3: Complex Queries

```
User: Get all companies, then create a new product called "Product A" for company 100000001
Assistant: I found 2 companies. I've created "Product A" for company C001. The product has been assigned ID 100000001.
```

## Error Handling

The API returns standard HTTP status codes:

- `200 OK`: Successful request
- `400 Bad Request`: Invalid request (missing API key, etc.)
- `404 Not Found`: Session not found
- `500 Internal Server Error`: Server error
- `503 Service Unavailable`: Chat service not available

## Best Practices

1. **Session Management**: Use session IDs to maintain conversation context
2. **API Keys**: Set `GEMINI_API_KEY` environment variable for security
3. **Error Handling**: Always handle errors in your UI
4. **Loading States**: Show loading indicators during chat requests
5. **History Management**: Clear old sessions periodically to manage memory

## Troubleshooting

### Chat not working

1. Check that the Gemini API key is set: `curl http://localhost:8000/api/v1/chat/status`
2. Ensure the MCP server is running
3. Check server logs for errors

### No conversation history

- Make sure you're using the same `session_id` for all messages in a conversation
- Check that the session exists: `GET /api/v1/chat/sessions`

### Model errors

- Try a different model name (e.g., `gemini-1.5-flash`)
- Check available models in the error message
- Ensure your API key has access to the requested model

