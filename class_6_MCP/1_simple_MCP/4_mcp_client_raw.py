import asyncio
import json
import sys

async def call_raw_stdio_server():
    print("\n*** 1. Spawn the server process explicitly tracking stdin/stdout...")
    process = await asyncio.create_subprocess_exec(
        sys.executable, "server.py",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    init_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "raw-client",
                "version": "1.0.0"
            }
        }
    }
    print("\n*** 2. Performing the mandatory MCP 'initialize' handshake...\nPayload:\n",json.dumps(init_payload, indent=2))
    process.stdin.write((json.dumps(init_payload) + "\n").encode('utf-8'))
    await process.stdin.drain()
    init_response_bytes = await process.stdout.readline()
    init_response = json.loads(init_response_bytes.decode('utf-8'))
    print("\nReceived 'initialize' response:\n",json.dumps(init_response, indent=2))

    notif_payload = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized"
    }
    print("\n*** 3. Sending the mandatory 'notifications/initialized' notification...\nPayload:\n",json.dumps(notif_payload, indent=2))
    process.stdin.write((json.dumps(notif_payload) + "\n").encode('utf-8'))
    await process.stdin.drain()

    call_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "add_numbers",
            "arguments": {"a": 12.5, "b": 7.5}
        }
    }
    print("\n*** 4. Now that the session is initialized, calling the tool...\nPayload:\n",json.dumps(call_payload, indent=2))    
    message = json.dumps(call_payload) + "\n"
    process.stdin.write(message.encode('utf-8'))
    await process.stdin.drain()

    # Read the tool call response from server's stdout
    response_bytes = await process.stdout.readline()
    response_json = json.loads(response_bytes.decode('utf-8'))
    
    print("Received 'tools/call' response:")
    print(json.dumps(response_json, indent=2))

    # Clean up and close down the process
    process.terminate()
    await process.wait()

if __name__ == "__main__":
    asyncio.run(call_raw_stdio_server())
