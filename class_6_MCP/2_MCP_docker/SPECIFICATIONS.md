# SPECIFICATION: MCP System (Server & Client App)

Create a system of Model Context Protocol (MCP) servers and an interactive client application.

## Server - People Info
- Place all server code in the `PeopleInfo_Server/` folder.
- Maintain dependency requirements in `PeopleInfo_Server/requirements.txt` (`fastmcp`, `mcp`, `uvicorn`, `sse-starlette`).
- Containerize the MCP server using Docker listening on port 8001 with SSE transport (`http://0.0.0.0:8001/sse`).
- Implement the `search_people` tool:
  - Accepts two string parameters: `search_for` (query string) and `field_name` (column name to search, e.g. `name`, `city`, `country`, `position`).
  - Performs multi-tier fuzzy matching (exact substring, sequence ratio similarity, and word-level matching).
  - Loads employee dataset from `PeopleInfo_Server/employee_data.csv`.

## Server - Random Number
- Place all server code in the `RandomNum_Server/` folder.
- Maintain dependency requirements in `RandomNum_Server/requirements.txt` (`fastmcp`, `mcp`, `uvicorn`, `sse-starlette`).
- Containerize the MCP server using Docker listening on port 8002 with SSE transport (`http://0.0.0.0:8002/sse`).
- Implement two MCP tools:
  - `rand_int`: Accepts one integer parameter `max_number` and returns a random integer between 1 and `max_number` (inclusive).
  - `rand_real`: Accepts no parameters and returns a random real float between 0.0 and 1.0.

## Client
- Place root client application code in `client.py`.
- Maintain root dependencies in `requirements.txt` (`fastmcp`, `mcp`, `pytest`).
- Implement full MCP client protocol lifecycle:
  - Check whether MCP server SSE endpoints are active and returning HTTP 200 OK.
  - Automatically launch missing servers via `docker-compose.yml` if endpoints are not active.
  - Auto-resolve Docker Desktop environment paths on Windows host machines.
  - Support a `--local` CLI flag to fall back to running servers directly via local Python `stdio` transport.
  - Display an interactive console menu listing all discovered tools across servers, indicating tool index, tool name, server name, and a Quit option.
  - Parse tool input schemas, dynamically format required parameters, and prompt user for comma-separated inputs.
  - Construct and print the formatted raw JSON-RPC request message, execute the tool call, print the formatted raw JSON-RPC response, and output a formatted human-readable presentation.
  - Re-prompt continuously until the user selects Quit.

## Other Requirements & Testing
- Orchestrate container builds and deployments via `docker-compose.yml`.
- Include automated system test coverage in `tests/test_system.py` runnable via `pytest tests/test_system.py -v` or `python -m pytest tests/test_system.py -v`.
- Provide comprehensive `README.md` documentation containing Linux, macOS, and Windows Docker installation guides, container execution instructions, virtual environment setup, and example CLI session walkthroughs.
