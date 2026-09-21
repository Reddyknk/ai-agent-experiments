# Simple MCP (Model Context Protocol) with Google GenAI

A minimal, working demonstration of building and connecting a **Model Context Protocol (MCP)** server with the modern **Google GenAI SDK (`google-genai`)** using **FastMCP**.

---

## Overview

This project demonstrates how an LLM agent powered by Google Gemini can dynamically discover and execute local tools exposed by an MCP server:

1. **MCP Server (`mcp_server.py`)**: Uses `FastMCP` to register and expose a tool (`roll_dice`) that simulates rolling 6-sided dice.
2. **MCP Client (`mcp_client.py`)**: Launches and connects to the MCP server session, bridges the exposed MCP tools directly into Gemini's `generate_content` call, and returns the model's response after executing the tool.

---

## File Structure

- [mcp_server.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/simple_MCP/mcp_server.py): FastMCP server definition with the `@mcp.tool` decorator for `roll_dice`.
- [mcp_client.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/simple_MCP/mcp_client.py): Async client managing the MCP session and delegating tool calls to Gemini via `google-genai`.
- [requirements.txt](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/simple_MCP/requirements.txt): Required Python dependencies (`fastmcp`, `google-genai`, `python-dotenv`).
- [.env.example](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/simple_MCP/.env.example): Template for environment variables and model configuration.
- [server.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/simple_MCP/server.py): Standalone server script mirror.

---

## Prerequisites

- **Python**: Version 3.10 or higher
- A **Google Gemini API Key** (from [Google AI Studio](https://aistudio.google.com/))

---

## Installation & Setup

### 1. Clone or Navigate to the Directory
```bash
cd /home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/simple_MCP
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
Copy [.env.example](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/simple_MCP/.env.example) to `.env`:
```bash
cp .env.example .env
```

Open `.env` and fill in your Gemini API key:
```dotenv
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=your_gemini_api_key_here

# Optional: customize model settings
MODEL="gemini-2.5-flash"
FALLBACK_MODEL="gemini-2.5-flash-lite"
```

---

## How to Run

### Run the Client (Recommended)
The client automatically initializes and manages the MCP server lifecycle in the background:

```bash
python mcp_client.py
```

**Expected Workflow:**
1. Loads environment variables from `.env`.
2. Connects to `mcp_server.py` via `fastmcp.Client`.
3. Sends the prompt `"Hey! Can you roll 3 dice for me?"` to Gemini with the MCP tools attached.
4. Gemini detects and invokes `roll_dice(n_dice=3)`.
5. The MCP server executes the function and returns random dice results back to Gemini.
6. Gemini crafts a friendly final response and prints it to the console.

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

In [mcp_client.py](file:///home/pi-net/Documents/agent_eng_labs/ai-agent-experiments/class_6_MCP/simple_MCP/mcp_client.py), a few compatibility bridges are applied to ensure smooth integration between `FastMCP` and `google.genai`:
- **Deprecation Warning Filter**: Suppresses `FastMCPDeprecationWarning` emitted during MCP v1 compatibility checks.
- **Deepcopy Patch (`ClientSession.__deepcopy__`)**: Allows `mcp_client.session` to be passed into `GenerateContentConfig(tools=[...])` without failing internal config deepcopying.
- **Schema Sanitizer (`_safe_filter_to_supported_schema`)**: Prevents crashes in `google.genai._mcp_utils` when non-dict/boolean tool schema constructs are parsed.
