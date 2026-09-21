# MCP Docker System - Update Walkthrough

The system has been updated to satisfy all new and revised requirements from [SPECIFICATIONS.md](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/2_MCP_docker/SPECIFICATIONS.md).

## What Was Updated

### 1. Client Server Status Check & Auto-start (`client.py`)
- **Automatic Status Check**: The client probes the server endpoints upon launch to verify whether they are reachable.
- **Auto-Start via Docker Compose**: If the servers are offline, `client.py` runs `docker compose -f docker-compose.yml up -d`, waits for the endpoints to become ready, and then proceeds with connecting.
- **Local Fallback**: If Docker is unavailable or the user specifies `--local`, it transparently runs the servers via local Python stdio processes.

### 2. Dual Response Output (Raw & Human-Readable)
- When a tool is invoked, the client prints:
  1. **RAW RESPONSE FROM SERVER**: The exact `CallToolResult` object returned over the MCP protocol.
  2. **FORMATTED RESULT (EASY TO READ)**:
     - For `search_people`: A neatly formatted ASCII table showing `#`, `Name`, `Position`, `City`, and `Country`.
     - For `rand_int` & `rand_real`: Formatted value labels with raw and rounded decimals.

### 3. Server Transport & Docker Compose Configurations
- Both [PeopleInfo_Server/server.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/2_MCP_docker/PeopleInfo_Server/server.py) and [RandomNum_Server/server.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/2_MCP_docker/RandomNum_Server/server.py) now support both **stdio** and **SSE** transport modes (configurable via CLI flags `--transport` or environment variables).
- [docker-compose.yml](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/2_MCP_docker/docker-compose.yml) configures `peopleinfo_server` on port `8001` and `randomnum_server` on port `8002`.

### 4. Cross-Platform Docker Installation Guide (`README.md`)
- [README.md](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/2_MCP_docker/README.md) has been updated with step-by-step installation instructions for:
  - **Linux** (Ubuntu/Debian, Fedora, Arch): Installing `docker.io`, `docker-compose-v2`, `docker-buildx`, non-root group permissions (`usermod -aG docker $USER`), and daemon enabling.
  - **macOS**: Docker Desktop via Homebrew or DMG, OrbStack option.
  - **Windows PC**: WSL2 prerequisite installation and Docker Desktop setup with WSL2 backend.
  - Detailed build and run instructions using `docker compose build` and `docker compose up -d`.

---

## Verification Results

### 1. Pytest Suite
```bash
$ pytest tests/test_system.py -v
============================= test session starts ==============================
collected 3 items

tests/test_system.py::test_people_info_server_local PASSED               [ 33%]
tests/test_system.py::test_random_num_server_local PASSED                [ 66%]
tests/test_system.py::test_client_integration PASSED                     [100%]

============================== 3 passed in 5.50s ===============================
```

### 2. Live Docker Auto-Start & Tool Execution
When running `python client.py` with servers stopped:
```text
[*] Checking whether MCP servers are running...
[-] MCP servers are not running. Starting them using docker-compose.yml...
[+] Containers launched. Waiting for server endpoints to become ready...
[+] Both MCP servers started successfully in Docker containers!

[*] Connecting to MCP servers over SSE transport...
[+] MCP servers connected and tools discovered successfully!

============================================================
Available MCP Tools:
1. search_people (PeopleInfo_Server)
2. rand_int (RandomNum_Server)
3. rand_real (RandomNum_Server)
4. Quit
============================================================
Select a tool [1-4]: 1
Selected Tool: search_people (PeopleInfo_Server)
Description: Searches employee records using fuzzy matching on the specified field.
Required parameters: search_for (string), field_name (string)
Enter parameters separated by commas (search_for, field_name): Alice, name
Calling 'search_people' on PeopleInfo_Server with arguments: {'search_for': 'Alice', 'field_name': 'name'} ...

============================================================
RAW RESPONSE FROM SERVER:
============================================================
CallToolResult(content=[TextContent(type='text', text='[{"name":"Alice Johnson","city":"New York","country":"USA","position":"Senior Software Engineer"}]', annotations=None, meta=None)], structured_content={'result': [{'name': 'Alice Johnson', 'city': 'New York', 'country': 'USA', 'position': 'Senior Software Engineer'}]}, meta={'fastmcp': {'wrap_result': True}}, data=[{'name': 'Alice Johnson', 'city': 'New York', 'country': 'USA', 'position': 'Senior Software Engineer'}], is_error=False)
============================================================

------------------------------------------------------------
FORMATTED RESULT (EASY TO READ):
------------------------------------------------------------
Found 1 matching person(s):

#   | Name          | Position                 | City     | Country
-------------------------------------------------------------------
1   | Alice Johnson | Senior Software Engineer | New York | USA    
------------------------------------------------------------
```
