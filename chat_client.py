#!/usr/bin/env python3
"""
Chat client integrated with the Chat API (Chat API -> Gemini MCP client -> MCP tools).

Flow: This client -> POST /api/v1/chat -> Chat API -> Gemini MCP Client -> MCP server tools -> Gemini -> response.

Usage:
  Interactive:  python chat_client.py
  One message: python chat_client.py --message "List all companies"
  With session: python chat_client.py --session my-session-123
"""
import argparse
import json
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import httpx

# Default base URL for the Ratings API (Chat API lives at /api/v1/chat)
DEFAULT_CHAT_API_BASE = os.getenv("CHAT_API_BASE", "http://localhost:8000/api/v1/chat")


class ChatAPIClient:
    """
    Client for the Chat API. Sends messages to the backend which uses
    Gemini MCP to answer (with MCP tools). Keeps session for multi-turn.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_CHAT_API_BASE,
        session_id: str | None = None,
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.session_id = session_id
        self.timeout = timeout
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "ChatAPIClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def send(
        self,
        message: str,
        session_id: str | None = None,
    ) -> dict:
        """
        Send a message to the Chat API and return the JSON response.

        Returns:
            dict with keys: response (str), session_id (str), model_used (str, optional).
            On HTTP error, raises; on API error body, returns dict with 'detail' or similar.
        """
        sid = session_id or self.session_id
        payload = {"message": message}
        if sid:
            payload["session_id"] = sid

        resp = self._get_client().post(
            f"{self.base_url}/",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    def get_history(self, session_id: str | None = None) -> dict:
        """Get chat history for a session. GET /api/v1/chat/history/{session_id}"""
        sid = session_id or self.session_id
        if not sid:
            return {"session_id": "", "history": [], "message_count": 0}
        resp = self._get_client().get(f"{self.base_url}/history/{sid}")
        resp.raise_for_status()
        return resp.json()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Chat client for Ratings API (Chat API -> Gemini MCP)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_CHAT_API_BASE,
        help=f"Chat API base URL (default: {DEFAULT_CHAT_API_BASE})",
    )
    parser.add_argument(
        "--session",
        default=None,
        help="Session ID for multi-turn (optional)",
    )
    parser.add_argument(
        "--message",
        "-m",
        default=None,
        help="Send a single message and print response (no interactive loop)",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Print history for --session and exit",
    )
    args = parser.parse_args()

    client = ChatAPIClient(base_url=args.base_url, session_id=args.session)

    try:
        if args.history:
            if not args.session:
                print("--history requires --session", file=sys.stderr)
                return 1
            data = client.get_history()
            print(json.dumps(data, indent=2))
            return 0

        if args.message is not None:
            data = client.send(args.message)
            print(data.get("response", data))
            if args.session is None and data.get("session_id"):
                print(f"\n(session_id: {data['session_id']})", file=sys.stderr)
            return 0

        # Interactive loop
        print("Chat client (Chat API -> Gemini MCP). Commands: /quit /session /history")
        print("Base URL:", client.base_url)
        if client.session_id:
            print("Session:", client.session_id)
        else:
            print("Session: (new session will be created on first message)")
        print()

        while True:
            try:
                line = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line.lower() in ("/quit", "/exit", "/q"):
                break
            if line.lower() == "/history":
                if not client.session_id:
                    print("No session yet. Send a message first.")
                else:
                    h = client.get_history()
                    for m in (h.get("history") or [])[-10:]:
                        role = m.get("role", "?")
                        parts = m.get("parts", [])
                        text = parts[0].get("text", "") if parts else ""
                        print(f"  [{role}] {text[:80]}...")
                continue
            if line.lower() == "/session":
                print("Session:", client.session_id or "(none yet)")
                continue

            try:
                data = client.send(line)
                reply = data.get("response", "")
                session_id = data.get("session_id", "")
                if session_id and not client.session_id:
                    client.session_id = session_id
                print("InsureAI:", reply)
                if data.get("model_used"):
                    print(f"  [model: {data['model_used']}]")
            except httpx.HTTPStatusError as e:
                print(f"Error: {e.response.status_code} - {e.response.text}")
            except Exception as e:
                print(f"Error: {e}")

    finally:
        client.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
