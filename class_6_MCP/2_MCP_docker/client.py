import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.request
import urllib.error

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

BASE_DIR = Path(__file__).resolve().parent
COMPOSE_FILE = BASE_DIR / "docker-compose.yml"
PEOPLE_SERVER_SCRIPT = BASE_DIR / "PeopleInfo_Server" / "server.py"
RANDOM_SERVER_SCRIPT = BASE_DIR / "RandomNum_Server" / "server.py"

PEOPLE_SSE_URL = "http://127.0.0.1:8001/sse"
RANDOM_SSE_URL = "http://127.0.0.1:8002/sse"


def is_endpoint_reachable(url: str, timeout: float = 1.0) -> bool:
    """Checks if an HTTP/SSE endpoint is reachable and responding with HTTP 200."""
    try:
        req = urllib.request.Request(url, method="GET", headers={"Accept": "text/event-stream"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except urllib.error.HTTPError:
        # Any HTTP status error (e.g. 404, 502, 500) indicates the SSE server endpoint is not ready/valid
        return False
    except Exception:
        return False


def get_docker_compose_cmd() -> Optional[List[str]]:
    """Determines whether 'docker compose' or 'docker-compose' is available."""
    # Add common Windows Docker Desktop paths to PATH environment variable if needed
    possible_dirs = [
        r"C:\Users\nkonr\AppData\Local\Programs\DockerDesktop\resources\bin",
        r"C:\Program Files\Docker\Docker\resources\bin",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin"),
        os.path.expandvars(r"%ProgramFiles%\Docker\Docker\resources\bin"),
    ]
    for pdir in possible_dirs:
        if os.path.isdir(pdir) and pdir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = pdir + os.path.pathsep + os.environ.get("PATH", "")

    docker_path = shutil.which("docker")
    if docker_path:
        res = subprocess.run([docker_path, "compose", "version"], capture_output=True, text=True)
        if res.returncode == 0:
            return [docker_path, "compose"]

    docker_compose_path = shutil.which("docker-compose")
    if docker_compose_path:
        return [docker_compose_path]

    return None


def ensure_servers_running(use_local: bool = False) -> str:
    """
    Checks whether the MCP servers are running.
    If not, starts them using docker-compose.yml (or local processes if use_local).
    Returns the connection mode: 'sse' or 'stdio'.
    """
    if use_local:
        print("[*] Running in local Python mode.")
        return "stdio"

    print("[*] Checking whether MCP servers are running...")
    people_up = is_endpoint_reachable(PEOPLE_SSE_URL)
    random_up = is_endpoint_reachable(RANDOM_SSE_URL)

    if people_up and random_up:
        print("[+] Both MCP servers are already running and reachable via SSE.")
        return "sse"

    # Servers not running - attempt to start with docker-compose
    compose_cmd = get_docker_compose_cmd()
    if not compose_cmd:
        print("[!] Docker / Docker Compose is not installed or available in PATH.")
        print("[*] Falling back to local Python stdio mode.\n")
        return "stdio"

    print("[-] MCP servers are not running. Starting them using docker-compose.yml...")
    try:
        cmd = compose_cmd + ["-f", str(COMPOSE_FILE), "up", "-d"]
        result = subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[!] Warning: docker compose up failed:\n{result.stderr}")
            print("[*] Falling back to local Python stdio mode.\n")
            return "stdio"

        print("[+] Containers launched. Waiting for server endpoints to become ready...")
        max_wait = 25
        start_time = time.time()
        while time.time() - start_time < max_wait:
            if is_endpoint_reachable(PEOPLE_SSE_URL) and is_endpoint_reachable(RANDOM_SSE_URL):
                print("[+] Both MCP servers started successfully in Docker containers!\n")
                return "sse"
            time.sleep(1)

        print("[!] Timed out waiting for SSE endpoints. Falling back to local Python mode.\n")
        return "stdio"
    except Exception as e:
        print(f"[!] Error starting docker containers: {e}. Falling back to local Python mode.\n")
        return "stdio"


def format_parameter_display(input_schema: Dict[str, Any]) -> Tuple[str, List[Tuple[str, str]]]:
    """Extracts required parameters and their types from the tool's input schema."""
    properties = input_schema.get("properties", {})
    required = input_schema.get("required", list(properties.keys()))

    param_list = []
    for param_name in required:
        param_type = properties.get(param_name, {}).get("type", "string")
        param_list.append((param_name, param_type))

    if not param_list:
        return "None (no parameters required)", []

    display_str = ", ".join(f"{name} ({ptype})" for name, ptype in param_list)
    return display_str, param_list


def parse_user_parameters(
    raw_input: str, param_specs: List[Tuple[str, str]]
) -> Dict[str, Any]:
    """Parses comma-separated user inputs into the typed dictionary expected by the tool."""
    if not param_specs:
        return {}

    parts = [p.strip() for p in raw_input.split(",")]
    if len(parts) != len(param_specs):
        raise ValueError(
            f"Expected {len(param_specs)} parameters ({', '.join(name for name, _ in param_specs)}), "
            f"but received {len(parts)}."
        )

    parsed_args = {}
    for (name, ptype), val in zip(param_specs, parts):
        if ptype == "integer":
            try:
                parsed_args[name] = int(val)
            except ValueError:
                raise ValueError(f"Parameter '{name}' must be an integer, got: '{val}'")
        elif ptype == "number":
            try:
                parsed_args[name] = float(val)
            except ValueError:
                raise ValueError(f"Parameter '{name}' must be a number, got: '{val}'")
        elif ptype == "boolean":
            parsed_args[name] = val.lower() in ("true", "1", "yes", "y")
        else:
            parsed_args[name] = val

    return parsed_args


def format_raw_mcp_response(res: Any, req_id: str) -> str:
    """Formats the raw MCP CallToolResult as a standard pretty-printed JSON-RPC response."""
    content_list = []
    for c in getattr(res, "content", []):
        if hasattr(c, "model_dump"):
            content_list.append(c.model_dump(exclude_none=True))
        elif hasattr(c, "__dict__"):
            content_list.append({k: v for k, v in c.__dict__.items() if v is not None})
        else:
            content_list.append(str(c))

    result_obj: Dict[str, Any] = {
        "content": content_list,
        "isError": getattr(res, "is_error", False),
    }
    if getattr(res, "structured_content", None) is not None:
        result_obj["structuredContent"] = res.structured_content

    response_dict = {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result_obj,
    }
    return json.dumps(response_dict, indent=2)


def format_human_readable_output(tool_name: str, result_data: Any) -> str:
    """Formats the server response in an easy-to-read human-friendly layout."""
    lines = []
    if tool_name == "search_people":
        if isinstance(result_data, list):
            if not result_data:
                return "No matching people found for your query."
            lines.append(f"Found {len(result_data)} matching person(s):\n")
            col_w_name = max(max((len(p.get("name", "")) for p in result_data), default=4), 4)
            col_w_pos = max(max((len(p.get("position", "")) for p in result_data), default=8), 8)
            col_w_city = max(max((len(p.get("city", "")) for p in result_data), default=4), 4)
            col_w_country = max(max((len(p.get("country", "")) for p in result_data), default=7), 7)

            header = f"{'#':<3} | {'Name':<{col_w_name}} | {'Position':<{col_w_pos}} | {'City':<{col_w_city}} | {'Country':<{col_w_country}}"
            separator = "-" * len(header)
            lines.append(header)
            lines.append(separator)
            for idx, p in enumerate(result_data, start=1):
                name = p.get("name", "")
                pos = p.get("position", "")
                city = p.get("city", "")
                country = p.get("country", "")
                lines.append(f"{idx:<3} | {name:<{col_w_name}} | {pos:<{col_w_pos}} | {city:<{col_w_city}} | {country:<{col_w_country}}")
            return "\n".join(lines)
        else:
            return str(result_data)

    elif tool_name == "rand_int":
        return f"Random Integer Generated: {result_data}"

    elif tool_name == "rand_real":
        return f"Random Real Number Generated: {result_data:.6f} (raw: {result_data})"

    else:
        # Default fallback pretty format
        if isinstance(result_data, (dict, list)):
            return json.dumps(result_data, indent=2)
        return str(result_data)


async def run_client(use_local: bool = False):
    mode = ensure_servers_running(use_local=use_local)

    if mode == "sse":
        print("[*] Connecting to MCP servers over SSE transport...")
        client_people = Client(PEOPLE_SSE_URL)
        client_random = Client(RANDOM_SSE_URL)
    else:
        print("[*] Connecting to MCP servers over local Python stdio transport...")
        transport_people = StdioTransport(
            command=sys.executable,
            args=[str(PEOPLE_SERVER_SCRIPT)],
            log_file=subprocess.DEVNULL,
        )
        transport_random = StdioTransport(
            command=sys.executable,
            args=[str(RANDOM_SERVER_SCRIPT)],
            log_file=subprocess.DEVNULL,
        )
        client_people = Client(transport_people)
        client_random = Client(transport_random)

    server_clients = {
        "PeopleInfo_Server": client_people,
        "RandomNum_Server": client_random,
    }

    async with client_people, client_random:
        # Discover tools from each server
        tools_by_server: List[Tuple[str, Any, Client]] = []

        for server_name, client in server_clients.items():
            try:
                tools = await client.list_tools()
                for tool in tools:
                    tools_by_server.append((server_name, tool, client))
            except Exception as e:
                print(f"[!] Error fetching tools from {server_name}: {e}")

        if not tools_by_server:
            print("[!] No tools found from connected MCP servers. Exiting.")
            return

        print("[+] MCP servers connected and tools discovered successfully!\n")

        # Interactive loop
        while True:
            print("=" * 60)
            print("Available MCP Tools:")
            for idx, (server_name, tool, _) in enumerate(tools_by_server, start=1):
                print(f"{idx}. {tool.name} ({server_name})")
            quit_number = len(tools_by_server) + 1
            print(f"{quit_number}. Quit")
            print("=" * 60)

            user_choice = input(f"Select a tool [1-{quit_number}]: ").strip()
            if not user_choice:
                continue

            if user_choice.lower() in ("quit", "q") or user_choice == str(quit_number):
                print("\nExiting MCP Client. Goodbye!")
                break

            try:
                selected_idx = int(user_choice) - 1
                if not (0 <= selected_idx < len(tools_by_server)):
                    print(f"\n[!] Invalid selection. Please enter a number between 1 and {quit_number}.\n")
                    continue
            except ValueError:
                print(f"\n[!] Invalid input. Please enter a number between 1 and {quit_number}.\n")
                continue

            server_name, tool, client = tools_by_server[selected_idx]
            schema = getattr(tool, "input_schema", {}) or {}
            display_str, param_specs = format_parameter_display(schema)

            print(f"\nSelected Tool: {tool.name} ({server_name})")
            if getattr(tool, "description", None):
                print(f"Description: {tool.description.strip()}")
            print(f"Required parameters: {display_str}")

            if param_specs:
                param_names = [p[0] for p in param_specs]
                raw_params = input(f"Enter parameters separated by commas ({', '.join(param_names)}): ").strip()
                try:
                    call_args = parse_user_parameters(raw_params, param_specs)
                except ValueError as err:
                    print(f"\n[!] Parameter error: {err}\n")
                    continue
            else:
                input("Press <enter> to execute the tool...")
                call_args = {}

            # Construct the raw JSON-RPC message sent to the MCP server
            req_id = f"call_{tool.name}_{int(time.time())}"
            raw_request_message = {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": "tools/call",
                "params": {
                    "name": tool.name,
                    "arguments": call_args,
                },
            }

            # 1. Print formatted raw message to the server
            print("\n" + "=" * 60)
            print("FORMATTED RAW MESSAGE TO SERVER:")
            print("=" * 60)
            print(json.dumps(raw_request_message, indent=2))
            print("=" * 60)

            print(f"\nDispatching call to '{tool.name}' on {server_name}...")
            try:
                raw_response = await client.call_tool(tool.name, call_args)

                # 2. Print formatted raw response from the server
                print("\n" + "=" * 60)
                print("FORMATTED RAW RESPONSE FROM SERVER:")
                print("=" * 60)
                print(format_raw_mcp_response(raw_response, req_id))
                print("=" * 60)

                # 3. Print formatted human-readable response from the server
                print("\n" + "-" * 60)
                print("FORMATTED HUMAN-READABLE RESPONSE:")
                print("-" * 60)
                human_readable = format_human_readable_output(tool.name, raw_response.data)
                print(human_readable)
                print("-" * 60 + "\n")

            except Exception as err:
                print(f"\n[!] Error during tool call: {err}\n")


def main():
    parser = argparse.ArgumentParser(description="Interactive MCP Console Client")
    parser.add_argument(
        "--local",
        action="store_true",
        help="Connect to MCP servers running locally via Python stdio instead of Docker containers",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run_client(use_local=args.local))
    except (KeyboardInterrupt, EOFError):
        print("\nExiting MCP Client. Goodbye!")


if __name__ == "__main__":
    main()
