# mcp_server.py
import json
from mcp.server.fastmcp import FastMCP

# Initialize the MCP Server
mcp = FastMCP("CitizenRegistry")

# Simulated Database (In production, this connects to PostgreSQL, Redis, etc.)
CITIZEN_DB = {
    "1900101123456": {"name": "Ion Popescu", "status": "Clean Record"},
    "2950505987654": {"name": "Maria Ionescu", "status": "Pending Fines"}
}

# The @mcp.tool() decorator automatically converts this Python function 
# into a strict JSON Schema tool that LLMs and MCP Clients can read.
@mcp.tool()
def verify_cnp(cnp: str) -> str:
    """Checks the national registry to verify if a 13-digit CNP is valid."""
    if cnp in CITIZEN_DB:
        return json.dumps({"valid": True, "data": CITIZEN_DB[cnp]})
    return json.dumps({"valid": False, "error": "CNP not found in national registry."})

if __name__ == "__main__":
    # Runs the server using standard input/output (stdio), 
    # the default secure protocol for local MCP communication.
    mcp.run()