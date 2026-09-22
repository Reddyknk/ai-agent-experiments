# Simple MCP (Model Context Protocol) with Google GenAI

A minimal, working demonstration of building and connecting a **Model Context Protocol (MCP)** server with both a direct tool client and an LLM-powered client using the modern **Google GenAI SDK (`google-genai`)** and **FastMCP**.

---

## Overview

This project demonstrates how tools exposed by an MCP server can be invoked across multiple client scenarios:

1. **Custom MCP Server (`mcp_server.py` / `server.py`)**: Uses `FastMCP` to register and expose custom tools (`roll_dice` and `add_numbers`).
2. **Client Implementations**:
   - **Client 1: Direct Tool Client (`1_mcp_client_tool.py`)**: Connects directly to the local MCP server using standard MCP `ClientSession` and stdio transport without requiring an LLM or API keys.
   - **Client 2: LLM Model Client (`2_mcp_client_model.py`)**: Bridges MCP tools directly into Google Gemini using `FastMCP` and `google-genai`. Gemini autonomously decides when and how to call tools, returning a natural language answer.
   - **Client 3: Local Git Community MCP Client (`3_mcp_client_git.py`)**: Demonstrates connecting to pre-built, open-source MCP servers (such as `mcp-server-git`) launched dynamically via `uvx`. It lists the server's discovered tools and programmatically calls `git_log`.
   - **Client 4: Low-Level Raw JSON-RPC Client (`4_mcp_client_raw.py`)**: Directly interacts with the MCP server over raw stdio subprocess pipes using raw JSON-RPC 2.0 messages, performing the mandatory protocol handshake (`initialize` -> `notifications/initialized` -> `tools/call`).
   - **Client 5: Remote GitHub MCP Client (`5_mcp_client_github.py`)**: Connects to the official `@modelcontextprotocol/server-github` via `npx`, reading `GITHUB_PERSONAL_ACCESS_TOKEN` from `.env`, and fetches repository files via `get_file_contents`.

Clients 1 & 2 run an interactive loop prompting `"How many dice rolls should be made: "` and continue until the user enters a non-number (e.g., `q` or `exit`).

---

## File Structure

- [mcp_server.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/mcp_server.py): FastMCP server definition with the `@mcp.tool()` decorators for `add_numbers` and `roll_dice`.
- [1_mcp_client_tool.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/1_mcp_client_tool.py): Direct MCP client using `ClientSession` and stdio communication to call `roll_dice` directly.
- [2_mcp_client_model.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/2_mcp_client_model.py): LLM agent client managing the MCP session and delegating tool calling to Gemini via `google-genai`.
- [3_mcp_client_git.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/3_mcp_client_git.py): Stdio client connecting to the open-source `mcp-server-git` via `uvx`, discovering tools, and running `git_log`.
- [4_mcp_client_raw.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/4_mcp_client_raw.py): Low-level raw JSON-RPC 2.0 client communicating over raw subprocess stdin/stdout pipes.
- [5_mcp_client_github.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/5_mcp_client_github.py): GitHub MCP client running `@modelcontextprotocol/server-github` via `npx` with authentication via `.env`.
- [requirements.txt](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/requirements.txt): Required Python dependencies (`fastmcp`, `google-genai`, `python-dotenv`, `uv`).
- [.env.example](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/.env.example): Template for environment variables (`GOOGLE_API_KEY`, `GITHUB_PERSONAL_ACCESS_TOKEN`, model configs).
- [server.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/server.py): Standalone server script mirror.

---

## Prerequisites

- **Python**: Version 3.10 or higher
- A **Google Gemini API Key** (required for `2_mcp_client_model.py`, get one from [Google AI Studio](https://aistudio.google.com/))
- A **GitHub Personal Access Token** (required for `5_mcp_client_github.py`, get one from GitHub Settings -> Developer Settings)
- **`uv` / `uvx`** (required for `3_mcp_client_git.py` to pull and run open-source MCP servers dynamically: `pip install uv` or `pipx install uv`)
- **Node.js & `npx`** (required for `5_mcp_client_github.py` to run `@modelcontextprotocol/server-github`)

---

## Installation & Setup

### 1. Clone or Navigate to the Directory
```bash
cd ~/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP
```

### 2. Create and Activate a Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy [.env.example](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/.env.example) to `.env`:
```bash
cp .env.example .env
```

Open `.env` and configure your keys:
```dotenv
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=your_gemini_api_key_here
GITHUB_PERSONAL_ACCESS_TOKEN=your_github_personal_access_token_here

# Optional: customize model settings
MODEL="gemini-flash-lite-latest"
FALLBACK_MODEL="gemini-flash-latest"
```

---

## How to Run

### Client 1: Direct Tool Client (`1_mcp_client_tool.py`)
This client directly communicates with the MCP server over stdio without needing an LLM or API keys.

```bash
python 1_mcp_client_tool.py
```

**What it does:**
1. Spawns and initializes a connection to `mcp_server.py`.
2. Loops and prompts the console: `How many dice rolls should be made: `.
3. Sends a tool execution call to `roll_dice(n_dice=...)` on the MCP server.
4. Prints the raw server response list (e.g., `Server Response: [3, 6, 2]`).
5. Loops until the user enters a non-number (e.g. `q`, `exit`, or a letter) to terminate.

---

### Client 2: LLM Model Client (`2_mcp_client_model.py`)
This client uses Google Gemini with the MCP server session registered as live tools.

```bash
python 2_mcp_client_model.py
```

**What it does:**
1. Loads `.env` credentials and initializes the Google GenAI SDK client.
2. Connects to `mcp_server.py` via `fastmcp.Client`.
3. Loops and prompts the console: `How many dice rolls should be made: `.
4. Sends the request to Gemini with `mcp_client.session` attached in the tools config.
5. Gemini analyzes the prompt, autonomously invokes `roll_dice(n_dice=...)` on the MCP server, receives the dice results, and synthesizes a natural language response.
6. Prints the Gemini response to the console.
7. Loops until the user enters a non-number (e.g. `q`, `exit`, or a letter) to terminate.

---

### Client 3: Local Git MCP Client (`3_mcp_client_git.py`)
This client demonstrates how an MCP client can run and interact with third-party, pre-packaged open-source MCP servers using `uvx` over standard stdio:

```bash
python 3_mcp_client_git.py
```

**What it does:**
1. Spawns the official open-source `mcp-server-git` server dynamically on demand via `uvx`.
2. Establishes an MCP `ClientSession` over stdio.
3. Queries and prints all available Git tools registered on the server (`git_status`, `git_diff_unstaged`, `git_commit`, `git_log`, etc.).
4. Programmatically executes the `git_log` tool against the current Git repository and prints the latest commit history.

---

### Client 4: Low-Level Raw JSON-RPC Client (`4_mcp_client_raw.py`)
This client demonstrates how the MCP protocol works under the hood over raw stdio pipes without using the MCP SDK:

```bash
python 4_mcp_client_raw.py
```

**What it does:**
1. Spawns `server.py` using `asyncio.create_subprocess_exec` with piped stdin/stdout.
2. Performs the mandatory MCP `initialize` handshake request and reads server capabilities.
3. Sends the mandatory `notifications/initialized` acknowledgment.
4. Sends a raw `tools/call` request for `add_numbers` with arguments `{"a": 12.5, "b": 7.5}` and parses the returned JSON-RPC response.

---

### Client 5: Remote GitHub MCP Client (`5_mcp_client_github.py`)
This client connects to GitHub's MCP server via `npx` using your personal access token:

```bash
python 5_mcp_client_github.py
```

**What it does:**
1. Loads `GITHUB_PERSONAL_ACCESS_TOKEN` securely from `.env`.
2. Spawns `@modelcontextprotocol/server-github` via `npx -y`.
3. Calls the `get_file_contents` tool to retrieve source files directly from a target GitHub repository.

---

### Running the Server Standalone
If you want to run or inspect the MCP server directly:

```bash
python mcp_server.py
```

You can also inspect it with the FastMCP CLI:
```bash
fastmcp dev mcp_server.py
```

---

## Technical Details & Compatibility Notes

In [2_mcp_client_model.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/2_mcp_client_model.py), compatibility bridges are applied for smooth integration between `FastMCP` and `google.genai`:
- **Deprecation Warning Filter**: Suppresses `FastMCPDeprecationWarning` emitted during MCP v1 compatibility checks.
- **Deepcopy Patch (`ClientSession.__deepcopy__`)**: Allows `mcp_client.session` to be passed into `GenerateContentConfig(tools=[...])` without failing internal config deepcopying.
- **Schema Sanitizer (`_safe_filter_to_supported_schema`)**: Prevents crashes in `google.genai._mcp_utils` when non-dict/boolean tool schema constructs are parsed.

In [1_mcp_client_tool.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/1_mcp_client_tool.py) and [4_mcp_client_raw.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/4_mcp_client_raw.py), `sys.executable` is used to launch the server sub-process with the same active Python interpreter environment.
