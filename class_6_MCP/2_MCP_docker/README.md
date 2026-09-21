# MCP Docker System

A Model Context Protocol (MCP) system featuring two containerized MCP servers (`PeopleInfo_Server` and `RandomNum_Server`) and an interactive console client that automatically manages, connects to, and invokes tools on the servers.

---

## What the App Does & How It Works

This project demonstrates an end-to-end implementation of the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/):

1. **Server Discovery & Orchestration**:
   - When launched, the root client (`client.py`) checks if the MCP servers are already up and running.
   - If the servers are not running, the client automatically starts them in the background using `docker-compose.yml`.
   - Once the endpoints are ready, the client performs the standard MCP protocol connection and tool discovery handshake.

2. **Interactive Console Menu**:
   - Lists all tools available across all connected MCP servers (one tool per line), identifying each tool's name and its parent MCP server.
   - Provides a clean exit option (`Quit`).

3. **Tool Execution & Parameter Prompting**:
   - When the user picks a tool number, the client inspects the tool's JSON schema and displays the required parameter names and types.
   - Prompts the user to enter parameters as a comma-separated list.
   - Dispatches the request via MCP protocol to the appropriate server.

4. **Dual Output (Raw & Human-Friendly)**:
   - Prints the **raw response** returned directly from the MCP server (`CallToolResult`).
   - Formats the response into an **easy-to-read, human-friendly presentation** (such as an aligned table for people search results, or clearly labeled values for random numbers).
   - Re-prompts the user in a continuous interactive loop until the user chooses `Quit`.

---

## System Architecture

```
+-----------------------------------------------------------------------------------------+
|                                    MCP Client (client.py)                               |
|                                                                                         |
|  1. Checks server status -> if offline, auto-starts with `docker compose up -d`        |
|  2. Connects over SSE transport (or local stdio fallback)                               |
|  3. Discovers tools dynamically: `list_tools()`                                         |
|  4. Interactive CLI: Select tool -> Enter comma-separated params -> Execute tool        |
|  5. Displays RAW response + FORMATTED human-readable table/card                         |
+------------------------------+------------------------------------+---------------------+
                               |                                    |
                HTTP / SSE     |                     HTTP / SSE     |
                Port 8001      |                     Port 8002      |
                               v                                    v
+----------------------------------------------+   +--------------------------------------+
|             PeopleInfo_Server                |   |          RandomNum_Server            |
|  - Container: peopleinfo_mcp_server          |   |  - Container: randomnum_mcp_server   |
|  - Transport: SSE on 0.0.0.0:8001            |   |  - Transport: SSE on 0.0.0.0:8002    |
|  - Data: employee_data.csv                   |   |  - Tools:                            |
|  - Tool: search_people                       |   |    1. rand_int(max_number)           |
|    Parameters: search_for, field_name        |   |    2. rand_real()                    |
|  - Features: Multi-field fuzzy search engine |   +--------------------------------------+
+----------------------------------------------+
```

---

## Directory Structure

```
.
├── PeopleInfo_Server/
│   ├── Dockerfile             # Container definition for PeopleInfo_Server (port 8001)
│   ├── employee_data.csv      # Employee records dataset (name, city, country, position)
│   ├── requirements.txt       # Dependencies (fastmcp, mcp, uvicorn, sse-starlette)
│   └── server.py              # FastMCP server implementing search_people with fuzzy matching
├── RandomNum_Server/
│   ├── Dockerfile             # Container definition for RandomNum_Server (port 8002)
│   ├── requirements.txt       # Dependencies (fastmcp, mcp, uvicorn, sse-starlette)
│   └── server.py              # FastMCP server implementing rand_int & rand_real
├── client.py                  # Interactive console client with auto-start & dual output
├── docker-compose.yml         # Compose configuration to build and run both servers
├── requirements.txt           # Root client dependencies
├── SPECIFICATIONS.md          # Project technical specifications
└── README.md                  # Complete documentation and setup guide
```

---

## Docker Installation Guide

To run the containerized MCP servers, Docker and Docker Compose are required. Follow the instructions below for your operating system:

### 1. Linux (Ubuntu / Debian / Raspberry Pi OS)

1. **Install Docker and Docker Compose**:
   ```bash
   sudo apt update
   sudo apt install -y docker.io docker-compose-v2 docker-buildx
   ```

2. **Add Your User to the `docker` Group** (allows running Docker without `sudo`):
   ```bash
   sudo usermod -aG docker $USER
   sudo chmod 666 /var/run/docker.sock
   ```

3. **Start and Enable the Docker Service**:
   ```bash
   sudo systemctl enable --now docker
   ```

4. **Verify the Installation**:
   ```bash
   docker --version
   docker compose version
   docker ps
   ```

*(For Fedora/RHEL, use `sudo dnf install -y docker-ce docker-compose-plugin`; for Arch Linux, use `sudo pacman -S docker docker-compose`).*

---

### 2. macOS

1. **Install via Homebrew**:
   ```bash
   brew install --cask docker
   ```
   *Alternatively, download the official installer directly from [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/) (select Apple Silicon or Intel depending on your Mac).*

2. **Launch Docker Desktop**:
   Open Docker from your `Applications` folder and complete the initial setup prompt.

3. **Verify the Installation**:
   Open Terminal and check:
   ```bash
   docker --version
   docker compose version
   ```

---

### 3. Windows PC

1. **Ensure WSL 2 is Installed**:
   Open PowerShell as Administrator and run:
   ```powershell
   wsl --install
   ```
   Restart your PC if prompted.

2. **Install Docker Desktop for Windows**:
   - Download the installer from [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/).
   - Run the installer and ensure the option **"Use WSL 2 instead of Hyper-V"** is checked.
   - Start Docker Desktop from the Start menu.

3. **Verify the Installation**:
   In PowerShell or Command Prompt, verify:
   ```powershell
   docker --version
   docker compose version
   ```

---

## Building and Running the Containers

### Using Docker Compose (Recommended)

1. **Build the Container Images**:
   ```bash
   docker compose build
   ```

2. **Start the Servers in Background**:
   ```bash
   docker compose up -d
   ```

3. **Check Container Status**:
   ```bash
   docker compose ps
   ```
   You will see:
   - `peopleinfo_mcp_server` listening on port `8001`
   - `randomnum_mcp_server` listening on port `8002`

4. **Stop the Servers**:
   ```bash
   docker compose down
   ```

### Using Standalone Docker CLI

You can also build and run each container individually:

```bash
# Build images
docker build -t peopleinfo_server ./PeopleInfo_Server
docker build -t randomnum_server ./RandomNum_Server

# Run containers exposing ports
docker run -d --name peopleinfo_mcp_server -p 8001:8001 peopleinfo_server
docker run -d --name randomnum_mcp_server -p 8002:8002 randomnum_server
```

---

## Setting Up and Running the Client

### 1. Python Virtual Environment Setup

Create and activate a virtual environment, then install requirements:

```bash
python3 -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Running the Client

#### Standard Mode (with Auto-Start)
Simply run:
```bash
python client.py
```
> **Note**: If the server containers are not already running, `client.py` will **automatically start them using `docker-compose.yml`**, wait for the endpoints to become healthy, and then connect seamlessly.

#### Local Python Mode (without Docker)
If you prefer running the servers directly as local Python processes without Docker:
```bash
python client.py --local
```

---

## Example Interactive Session Walkthrough

```text
$ python client.py
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

============================================================
FORMATTED RAW MESSAGE TO SERVER:
============================================================
{
  "jsonrpc": "2.0",
  "id": "call_search_people_1790026928",
  "method": "tools/call",
  "params": {
    "name": "search_people",
    "arguments": {
      "search_for": "Alice",
      "field_name": "name"
    }
  }
}
============================================================

Dispatching call to 'search_people' on PeopleInfo_Server...

============================================================
FORMATTED RAW RESPONSE FROM SERVER:
============================================================
{
  "jsonrpc": "2.0",
  "id": "call_search_people_1790026928",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "[{\"name\":\"Alice Johnson\",\"city\":\"New York\",\"country\":\"USA\",\"position\":\"Senior Software Engineer\"}]"
      }
    ],
    "isError": false,
    "structuredContent": {
      "result": [
        {
          "name": "Alice Johnson",
          "city": "New York",
          "country": "USA",
          "position": "Senior Software Engineer"
        }
      ]
    }
  }
}
============================================================

------------------------------------------------------------
FORMATTED HUMAN-READABLE RESPONSE:
------------------------------------------------------------
Found 1 matching person(s):

#   | Name          | Position                 | City     | Country
-------------------------------------------------------------------
1   | Alice Johnson | Senior Software Engineer | New York | USA    
------------------------------------------------------------

============================================================
Available MCP Tools:
1. search_people (PeopleInfo_Server)
2. rand_int (RandomNum_Server)
3. rand_real (RandomNum_Server)
4. Quit
============================================================
Select a tool [1-4]: 2

Selected Tool: rand_int (RandomNum_Server)
Description: Generates a random integer from 1 to max_number (inclusive).
Required parameters: max_number (integer)
Enter parameters separated by commas (max_number): 50

============================================================
FORMATTED RAW MESSAGE TO SERVER:
============================================================
{
  "jsonrpc": "2.0",
  "id": "call_rand_int_1790026928",
  "method": "tools/call",
  "params": {
    "name": "rand_int",
    "arguments": {
      "max_number": 50
    }
  }
}
============================================================

Dispatching call to 'rand_int' on RandomNum_Server...

============================================================
FORMATTED RAW RESPONSE FROM SERVER:
============================================================
{
  "jsonrpc": "2.0",
  "id": "call_rand_int_1790026928",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "23"
      }
    ],
    "isError": false,
    "structuredContent": {
      "result": 23
    }
  }
}
============================================================

------------------------------------------------------------
FORMATTED HUMAN-READABLE RESPONSE:
------------------------------------------------------------
Random Integer Generated: 23
------------------------------------------------------------

============================================================
Available MCP Tools:
1. search_people (PeopleInfo_Server)
2. rand_int (RandomNum_Server)
3. rand_real (RandomNum_Server)
4. Quit
============================================================
Select a tool [1-4]: 4

Exiting MCP Client. Goodbye!
```

---

## Running the Automated Test Suite

To run all automated verification tests:

```bash
pytest tests/test_system.py -v
```
