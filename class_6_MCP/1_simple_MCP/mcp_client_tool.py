import asyncio
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def call_stdio_server():
  server_path = str(Path(__file__).resolve().parent / "mcp_server.py")
  server_params = StdioServerParameters(
    command=sys.executable,
    args=[server_path], env=None,
    # You can inject API keys or PATH variables here
  )

  async with stdio_client(server_params) as (read_stream, write_stream):
    async with ClientSession(read_stream, write_stream) as session:

      await session.initialize()
      print("Session initialized successfully.")

      while True:
        try:
          user_input = input("How many dice rolls should be made: ")
          n_dice = int(user_input.strip())
        except (ValueError, EOFError):
          break

        print("Sending tool execution call...")
        result = await session.call_tool(
          name="roll_dice",
          arguments={"n_dice": n_dice}
        )

        for content_item in result.content:
          if content_item.type == "text":
            print(f"Server Response: {content_item.text}")

if __name__ == "__main__":
  asyncio.run(call_stdio_server())
