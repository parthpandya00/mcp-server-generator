import pytest
import json
import subprocess
import os


def test_stdio_mode_success():
    """
    Tests the stdio communication channel by activating the test mock.
    """
    # 1. Setup Environment
    test_env = os.environ.copy()
    test_env["TRANSPORT_MODE"] = "stdio"
    test_env["MCP_TEST_MODE_ACTIVE"] = "1"  # Activate the mock in run.py
    # MCP_CONFIG is not needed as the dispatcher is mocked

    # 2. Execute
    process = subprocess.Popen(
        ["python", "-u", "-m", "generic_mcp_server.run"],
        cwd="src",
        env=test_env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    rpc_request = {
        "jsonrpc": "2.0",
        "method": "any_method",
        "params": {},
        "id": 101
    }

    stdout, stderr = process.communicate(input=json.dumps(rpc_request) + "\n")

    # 3. Assert
    assert "MCP Server running in Stdio mode" in stderr

    response_data = json.loads(stdout)
    # Check for the mocked success message
    assert response_data["result"] == {"status": "mocked_success"}