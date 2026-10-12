
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "Medication Assistant",
    host="0.0.0.0",
    port=8000,
    stateless_http=True
)

@mcp.tool()
def hello_world() -> str:
    """Test whether the medication assistant MCP server is working."""
    return "Medication Assistant MCP server is connected!"

if __name__ == "__main__":
    mcp.run(transport="streamable-http")