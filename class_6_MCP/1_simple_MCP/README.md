# Simple MCP (Model Context Protocol) with Google GenAI

A minimal, working demonstration of building and connecting a **Model Context Protocol (MCP)** server with both a direct tool client and an LLM-powered client using the modern **Google GenAI SDK (`google-genai`)** and **FastMCP**.

---

## Overview

This project demonstrates how tools exposed by an MCP server can be invoked across multiple client scenarios:

1. **Custom MCP Server (`mcp_server.py`)**: Uses `FastMCP` to register and expose a custom tool (`roll_dice`) that simulates rolling 6-sided dice.
2. **Client Options**:
   - **Option 1: Direct Tool Client (`mcp_client_tool.py`)**: Connects directly to the local MCP server using standard MCP `ClientSession` and stdio transport. Directly invokes the `roll_dice` tool without requiring an LLM or API keys.
   - **Option 2: LLM Model Client (`mcp_client_model.py`)**: Bridges MCP tools directly into Google Gemini using `FastMCP` and `google-genai`. Gemini autonomously decides when and how to call `roll_dice`, returning a natural language answer.
   - **Option 3: External Community MCP Client (`mcp_client_git.py`)**: Demonstrates connecting to pre-built, open-source MCP servers (such as `mcp-server-git`) launched dynamically via `uvx`. It lists the server's discovered tools and programmatically calls `git_log`.

Options 1 & 2 run an interactive loop prompting `"How many dice rolls should be made: "` and continue until the user enters a non-number (e.g., `q` or `exit`).

---

## File Structure

- [mcp_server.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/mcp_server.py): FastMCP server definition with the `@mcp.tool` decorator for `roll_dice`.
- [mcp_client_tool.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/mcp_client_tool.py): Direct MCP client using `ClientSession` and stdio communication to call `roll_dice` directly.
- [mcp_client_model.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/mcp_client_model.py): LLM agent client managing the MCP session and delegating tool calling to Gemini via `google-genai`.
- [mcp_client_git.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/mcp_client_git.py): Stdio client connecting to the open-source `mcp-server-git` via `uvx`, discovering tools, and running `git_log`.
- [requirements.txt](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/requirements.txt): Required Python dependencies (`fastmcp`, `google-genai`, `python-dotenv`).
- [.env.example](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/.env.example): Template for environment variables and model configuration.
- [server.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/server.py): Standalone server script mirror.

---

## Prerequisites

- **Python**: Version 3.10 or higher
- A **Google Gemini API Key** (required for `mcp_client_model.py`, get one from [Google AI Studio](https://aistudio.google.com/))
- **`uv` / `uvx`** (required for `mcp_client_git.py` to pull and run open-source MCP servers dynamically: `pip install uv` or `pipx install uv`)

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
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy [.env.example](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/.env.example) to `.env`:
```bash
cp .env.example .env
```

Open `.env` and fill in your Gemini API key (needed for the model client):
```dotenv
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=your_gemini_api_key_here

# Optional: customize model settings
MODEL="gemini-flash-lite-latest"
FALLBACK_MODEL="gemini-flash-latest"
```

---

## How to Run

### Option 1: Direct Tool Client (`mcp_client_tool.py`)
This client directly communicates with the MCP server over stdio without needing an LLM or API keys.

```bash
python mcp_client_tool.py
```

**What it does:**
1. Spawns and initializes a connection to `mcp_server.py`.
2. Loops and prompts the console: `How many dice rolls should be made: `.
3. Sends a tool execution call to `roll_dice(n_dice=...)` on the MCP server.
4. Prints the raw server response list (e.g., `Server Response: [3, 6, 2]`).
5. Loops until the user enters a non-number (e.g. `q`, `exit`, or a letter) to terminate.

---

### Option 2: LLM Model Client (`mcp_client_model.py`)
This client uses Google Gemini with the MCP server session registered as live tools.

```bash
python mcp_client_model.py
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

### Option 3: External Git MCP Client (`mcp_client_git.py`)
This client demonstrates how an MCP client can run and interact with third-party, pre-packaged open-source MCP servers using `uvx` over standard stdio:

```bash
python mcp_client_git.py
```

**What it does:**
1. Spawns the official open-source `mcp-server-git` server dynamically on demand via `uvx`.
2. Establishes an MCP `ClientSession` over stdio.
3. Queries and prints all available Git tools registered on the server (`git_status`, `git_diff_unstaged`, `git_commit`, `git_log`, etc.).
4. Programmatically executes the `git_log` tool against the current Git repository and prints the latest commit history.

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

In [mcp_client_model.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/mcp_client_model.py), compatibility bridges are applied for smooth integration between `FastMCP` and `google.genai`:
- **Deprecation Warning Filter**: Suppresses `FastMCPDeprecationWarning` emitted during MCP v1 compatibility checks.
- **Deepcopy Patch (`ClientSession.__deepcopy__`)**: Allows `mcp_client.session` to be passed into `GenerateContentConfig(tools=[...])` without failing internal config deepcopying.
- **Schema Sanitizer (`_safe_filter_to_supported_schema`)**: Prevents crashes in `google.genai._mcp_utils` when non-dict/boolean tool schema constructs are parsed.

In [mcp_client_tool.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/1_simple_MCP/mcp_client_tool.py), `sys.executable` is used to launch the server sub-process with the same active Python interpreter environment.
