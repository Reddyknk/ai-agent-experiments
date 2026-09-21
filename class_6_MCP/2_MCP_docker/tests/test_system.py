import asyncio
import os
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
import subprocess
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
PEOPLE_SERVER = BASE_DIR / "PeopleInfo_Server" / "server.py"
RANDOM_SERVER = BASE_DIR / "RandomNum_Server" / "server.py"


def test_people_info_server_local():
    async def _test():
        transport = StdioTransport(
            command=sys.executable,
            args=[str(PEOPLE_SERVER)],
            log_file=subprocess.DEVNULL,
        )
        client = Client(transport)
        async with client:
            tools = await client.list_tools()
            tool_names = [t.name for t in tools]
            assert "search_people" in tool_names

            # 1. Exact match
            res_exact = await client.call_tool("search_people", {"search_for": "Tokyo", "field_name": "city"})
            assert len(res_exact.data) >= 1
            assert res_exact.data[0]["city"] == "Tokyo"
            assert "name" in res_exact.data[0]
            assert "country" in res_exact.data[0]
            assert "position" in res_exact.data[0]

            # 2. Fuzzy match
            res_fuzzy = await client.call_tool("search_people", {"search_for": "Softwre", "field_name": "position"})
            assert len(res_fuzzy.data) >= 1
            assert any("Engineer" in p["position"] for p in res_fuzzy.data)

    asyncio.run(_test())


def test_random_num_server_local():
    async def _test():
        transport = StdioTransport(
            command=sys.executable,
            args=[str(RANDOM_SERVER)],
            log_file=subprocess.DEVNULL,
        )
        client = Client(transport)
        async with client:
            tools = await client.list_tools()
            tool_names = [t.name for t in tools]
            assert "rand_int" in tool_names
            assert "rand_real" in tool_names

            # 1. rand_int test
            for _ in range(5):
                res_int = await client.call_tool("rand_int", {"max_number": 15})
                assert isinstance(res_int.data, int)
                assert 1 <= res_int.data <= 15

            # 2. rand_real test
            for _ in range(5):
                res_real = await client.call_tool("rand_real", {})
                assert isinstance(res_real.data, float)
                assert 0.0 <= res_real.data <= 1.0

    asyncio.run(_test())


def test_client_integration():
    async def _test():
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(BASE_DIR / "client.py"),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdin_input = "1\nLondon, city\n2\n10\n3\n\n4\n"
        stdout, stderr = await process.communicate(input=stdin_input.encode())

        output = stdout.decode()
        assert process.returncode == 0
        assert "Available MCP Tools:" in output
        assert "1. search_people (PeopleInfo_Server)" in output
        assert "2. rand_int (RandomNum_Server)" in output
        assert "3. rand_real (RandomNum_Server)" in output
        assert "4. Quit" in output
        assert "FORMATTED RAW MESSAGE TO SERVER:" in output
        assert "FORMATTED RAW RESPONSE FROM SERVER:" in output
        assert "FORMATTED HUMAN-READABLE RESPONSE:" in output
        assert "Exiting MCP Client. Goodbye!" in output

    asyncio.run(_test())


if __name__ == "__main__":
    print("Running test_people_info_server_local...")
    test_people_info_server_local()
    print("Running test_random_num_server_local...")
    test_random_num_server_local()
    print("Running test_client_integration...")
    test_client_integration()
    print("All tests passed successfully!")
