# mcp_client_model.py
import asyncio
import os
import warnings
from pathlib import Path
from dotenv import load_dotenv
from fastmcp import Client, FastMCPDeprecationWarning
from google import genai
from google.genai import types
import google.genai._mcp_utils
from mcp.client.session import ClientSession

#-------------------------------------------------------------------------------------
# Suppress MCP v1 deprecation warnings from google.genai adapter
warnings.filterwarnings("ignore", category=FastMCPDeprecationWarning)

# Compatibility fix: allow ClientSession inside GenerateContentConfig deepcopy
ClientSession.__deepcopy__ = lambda self, memo: self

# Compatibility fix: prevent google.genai schema parser from crashing on boolean schemas
_orig_filter_to_supported_schema = google.genai._mcp_utils._filter_to_supported_schema

def _safe_filter_to_supported_schema(schema):
    if not isinstance(schema, dict):
        return schema
    return _orig_filter_to_supported_schema(schema)

google.genai._mcp_utils._filter_to_supported_schema = _safe_filter_to_supported_schema
#-------------------------------------------------------------------------------------

# Load environment variables from .env
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

# Constants from .env
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL = os.getenv("MODEL", "gemma-4-26b-a4b-it")

async def main():
    # 1. Point the client to your server script
    server_path = Path(__file__).resolve().parent / "mcp_server.py"
    mcp_client = Client(server_path)
    
    # 2. Initialize the modern Google GenAI Client
    gemini_client = genai.Client()

    # 3. Enter the MCP client session lifecycle
    async with mcp_client:
        print("Connected to MCP server.")

        while True:
            try:
                user_input = input("How many dice rolls should be made: ")
                n_dice = int(user_input.strip())
            except (ValueError, EOFError):
                break

            print("Querying Gemini...")
            # 4. Generate content and attach the live MCP session tools
            response = await gemini_client.aio.models.generate_content(
                model=MODEL,
                contents=f"Hey! Can you roll {n_dice} dice for me?",
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    tools=[mcp_client.session]  # Bridges MCP server tools directly into Gemini
                ),
            )
            
            print("\nGemini Response:")
            print(response.text)

if __name__ == "__main__":
    asyncio.run(main())
