# This code access github mcp server.
import asyncio
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Load environment variables from .env
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

async def fetch_github_file_via_mcp():
    # Ensure the required GitHub token is available in your .env or environment
    token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
    if not token:
        print("Error: GITHUB_PERSONAL_ACCESS_TOKEN is missing in your .env file or environment.")
        return

    # 1. Configure the official GitHub MCP server
    # [ Python Client ] -> [STDIO] -> [Network (HTTPS REST API)] -> [Remote Github MCP Server]
    # We pass the required authentication token directly into the server's environment block
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={
            **os.environ,
            "GITHUB_PERSONAL_ACCESS_TOKEN": token
        }
    )

    print("*** 1. Connecting to the remote git MCP Server via STDIO then use it to access GitHub...")
    
    # 3. Open the transport streams and initialize the protocol session
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            
            tools_response = await session.list_tools()
            print("\n*** 2. Getting Available Tools from GitHub MCP Server\n--- Available Tools on this Server ---")
            for tool in tools_response.tools:
                print(f"- {tool.name}: {tool.description}")

            # Define the target repository info and file path
            # For this example, we will fetch 'src/mcp/server/stdio.py' from python-sdk
            repo_owner = "modelcontextprotocol"
            repo_name = "python-sdk"
            file_path = "src/mcp/server/stdio.py"
            
            print(f"\n*** 3. Calling 'get_file_contents' for {repo_owner}/{repo_name}/{file_path}...")
            
            # Execute the GitHub MCP tool call
            # Optional: Add a "branch" parameter inside arguments if you need a specific branch/tag/commit hash
            try:
                result = await session.call_tool(
                    name="get_file_contents",
                    arguments={
                        "owner": repo_owner,
                        "repo": repo_name,
                        "path": file_path
                    }
                )
                
                # Parse and print the retrieved source code content
                print("--- Text Content From GitHub ---")
                for content_item in result.content:
                    if content_item.type == "text":
                        try:
                            data = json.loads(content_item.text)
                            if isinstance(data, dict) and "content" in data:
                                print(data["content"])
                            else:
                                print(content_item.text)
                        except json.JSONDecodeError:
                            print(content_item.text)

            except Exception as e:
                print(f"\nError executing tool: {e}")

if __name__ == "__main__":
    asyncio.run(fetch_github_file_via_mcp())
