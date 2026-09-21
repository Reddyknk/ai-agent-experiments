# server.py
import random
from fastmcp import FastMCP

# Initialize the FastMCP server
mcp = FastMCP(name="Math Wizard")

@mcp.tool
def roll_dice(n_dice: int) -> list[int]:
    """
    Rolls n_dice number of 6-sided dice and returns the results.
    Use this whenever the user wants to simulate rolling dice.
    """
    return [random.randint(1, 6) for _ in range(n_dice)]

if __name__ == "__main__":
    mcp.run()
