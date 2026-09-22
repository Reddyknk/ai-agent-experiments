# This code access a local Git MCP server

import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def run_free_mcp_server():
    # 1. Configure the free, open-source Git MCP server. We use 'uvx' (or 'npx' for JS servers) to pull and execute the server instantly
    server_params = StdioServerParameters( command="uvx",
        args=["mcp-server-git"], env=None )

    print("Connecting to the free Git MCP Server...")
    
    # 2. Establish the Stdio connection session
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            
            # Initialize the protocol session with the server
            await session.initialize()
            
            # 3. List the available tools provided by this free server
            tools_response = await session.list_tools()
            print("\n--- Available Tools on this Server ---")
            for tool in tools_response.tools:
                print(f"- {tool.name}: {tool.description}")
            
            # 4. Programmatically execute one of the free tools
            # Let's call the 'git_log' tool provided by this server (requires 'repo_path')
            from pathlib import Path
            repo_path = str(Path(__file__).resolve().parents[2])
            print(f"\nExecuting 'git_log' tool call on repo: {repo_path}...")
            result = await session.call_tool(
                name="git_log", 
                arguments={"repo_path": repo_path, "max_count": 3}
            )
            
            # Print the tool's text output
            print("\n--- Server Execution Response ---")
            for content_item in result.content:
                if content_item.type == "text":
                    print(content_item.text)

if __name__ == "__main__":
    asyncio.run(run_free_mcp_server())
