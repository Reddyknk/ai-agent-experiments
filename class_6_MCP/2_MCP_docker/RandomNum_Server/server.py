import argparse
import os
import random
from fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("RandomNum_Server")


@mcp.tool
def rand_int(max_number: int) -> int:
    """
    Generates a random integer from 1 to max_number (inclusive).

    Parameters:
        max_number: Upper bound integer for the random number range (must be >= 1).

    Returns:
        A random integer between 1 and max_number.
    """
    if max_number < 1:
        raise ValueError("max_number must be greater than or equal to 1")
    return random.randint(1, max_number)


@mcp.tool
def rand_real() -> float:
    """
    Generates a random real number from 0.0 to 1.0.

    Returns:
        A random float between 0.0 and 1.0.
    """
    return random.random()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RandomNum MCP Server")
    parser.add_argument(
        "--transport",
        default=os.getenv("TRANSPORT", "stdio"),
        choices=["stdio", "sse", "http", "streamable-http"],
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("HOST", "0.0.0.0"),
        help="Host to bind to for HTTP/SSE (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8002")),
        help="Port to bind to for HTTP/SSE (default: 8002)",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port, show_banner=False)
