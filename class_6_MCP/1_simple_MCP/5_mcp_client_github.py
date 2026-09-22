# This code access github mcp server.
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Load environment variables from .env
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

async def fetch_github_file_via_mcp():
    # 1. Ensure the required GitHub token is available in your .env or environment
    token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
    if not token:
        print("Error: GITHUB_PERSONAL_ACCESS_TOKEN is missing in your .env file or environment.")
        return

    # 2. Configure the official GitHub MCP server
    # We pass the required authentication token directly into the server's environment block
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={
            **os.environ,
            "GITHUB_PERSONAL_ACCESS_TOKEN": token
        }
    )

    print("Connecting to the remote GitHub MCP Server via STDIO...")
    
    # 3. Open the transport streams and initialize the protocol session
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            
            # 4. Define the target repository info and file path
            # For this example, we will fetch 'src/mcp/server/stdio.py' from python-sdk
            repo_owner = "modelcontextprotocol"
            repo_name = "python-sdk"
            file_path = "src/mcp/server/stdio.py"
            
            print(f"Calling 'get_file_contents' for {repo_owner}/{repo_name}/{file_path}...")
            
            # 5. Execute the GitHub MCP tool call
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
                
                # 6. Parse and print the retrieved source code content
                print("\n--- Source Code From GitHub ---")
                for content_item in result.content:
                    if content_item.type == "text":
                        print(content_item.text)

            except Exception as e:
                print(f"\nError executing tool: {e}")

if __name__ == "__main__":
    asyncio.run(fetch_github_file_via_mcp())
