"""Tests for the GitHub MCP Tool."""

import pytest
import json
import os
import time
from unittest.mock import patch, MagicMock
from pathlib import Path
from typing import Dict, Any

from core.tools.github_mcp import (
    MCPServerConfig,
    MCPServerStatus,
    MCPServerMetrics,
    GitHubMCPServer,
    github_mcp_server
)

@pytest.fixture
def mock_psutil():
    """
    Mocks psutil's process iteration and process memory info for testing.
    
    Yields:
        A dictionary containing mocked 'process_iter' and 'Process' objects for use in tests.
    """
    with patch('psutil.process_iter') as process_iter, \
         patch('psutil.Process') as Process:
        
        # Mock process for server
        mock_process = MagicMock()
        mock_process.info = {
            'pid': 12345,
            'name': 'node',
            'cmdline': ['npx', '@modelcontextprotocol/server-github'],
            'create_time': time.time() - 3600  # Started 1 hour ago
        }
        process_iter.return_value = [mock_process]
        
        # Mock Process class
        mock_process_instance = MagicMock()
        mock_process_instance.memory_info.return_value.rss = 100 * 1024 * 1024  # 100MB
        Process.return_value = mock_process_instance
        
        yield {
            'process_iter': process_iter,
            'Process': Process
        }

@pytest.fixture
def mock_subprocess():
    """
    Yields a mocked version of subprocess.Popen for testing.
    
    This fixture provides a mock process with predefined PID, stdout, and stderr attributes.
    """
    with patch('subprocess.Popen') as Popen:
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()
        Popen.return_value = mock_process
        yield Popen

@pytest.fixture
def mock_aiohttp():
    """
    Pytest fixture that mocks aiohttp's ClientSession to simulate HTTP responses.
    
    All HTTP GET requests return a response with status 200 and a JSON body of {"status": "ok"}.
    """
    class MockResponse:
        def __init__(self, status):
            """
            Initializes the instance with the given status.
            
            Args:
                status: The status value to assign to the instance.
            """
            self.status = status
        async def json(self):
            """
            Asynchronously returns a JSON response indicating an OK status.
            
            Returns:
                A dictionary with a single key "status" set to "ok".
            """
            return {"status": "ok"}
        async def __aenter__(self):
            """
            Enables use of the async context manager protocol for this object.
            
            Returns:
                The current instance for use within an async with block.
            """
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            """
            Exits the asynchronous context manager for the server instance.
            """
            pass
    
    class MockClientSession:
        async def __aenter__(self):
            """
            Enables use of the async context manager protocol for the server instance.
            
            Returns:
                The server instance itself for use within an async with block.
            """
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            """
            Exits the asynchronous context manager for the server instance.
            """
            pass
        async def get(self, url, **kwargs):
            """
            Simulates an asynchronous HTTP GET request and returns a mock response.
            
            Args:
                url: The URL to request.
                **kwargs: Additional keyword arguments for the request.
            
            Returns:
                A mock response object with a status code of 200.
            """
            return MockResponse(200)
    
    with patch('aiohttp.ClientSession', return_value=MockClientSession()):
        yield

@pytest.fixture
def temp_config_file(tmp_path):
    """
    Creates a temporary JSON configuration file for the MCP server.
    
    Args:
        tmp_path: A pytest-provided temporary directory path.
    
    Returns:
        The path to the created configuration file containing test server settings.
    """
    config_file = tmp_path / "mcp_config.json"
    config_data = {
        "host": "localhost",
        "port": 8000,
        "auth_token": "test_token",
        "github_token": "github_token",
        "log_level": "DEBUG"
    }
    config_file.write_text(json.dumps(config_data))
    return config_file

@pytest.fixture
async def server():
    """
    Yields a GitHubMCPServer instance for use in tests and ensures cleanup after use.
    
    This asynchronous fixture provides a preconfigured GitHubMCPServer object and
    guarantees that the server is stopped after the test completes.
    """
    server = GitHubMCPServer(MCPServerConfig(
        host="localhost",
        port=8000,
        auth_token="test_token"
    ))
    yield server
    await server.stop_server()

@pytest.mark.asyncio
async def test_start_server(server, mock_subprocess, mock_psutil):
    """
    Tests that the server starts successfully and verifies the returned result and subprocess invocation.
    """
    result = await server.start_server()
    
    assert result["success"]
    assert result["message"] == "Server started successfully"
    assert result["pid"] == 12345
    
    mock_subprocess.assert_called_once()
    cmd_args = mock_subprocess.call_args[0][0]
    assert "@modelcontextprotocol/server-github" in cmd_args
    assert "--host" in cmd_args
    assert "--port" in cmd_args

@pytest.mark.asyncio
async def test_stop_server(server, mock_psutil):
    """
    Tests that the server can be stopped successfully.
    
    Asserts that the stop_server method returns a success flag and the expected message.
    """
    result = await server.stop_server()
    
    assert result["success"]
    assert result["message"] == "Server stopped successfully"

@pytest.mark.asyncio
async def test_get_status(server, mock_psutil):
    """Test getting server status."""
    result = await server.get_status()
    
    assert result["success"]
    assert result["status"]["is_running"]
    assert result["status"]["pid"] == 12345
    assert result["status"]["port"] == 8000
    assert result["status"]["uptime"] > 0

@pytest.mark.asyncio
async def test_get_metrics(server, mock_psutil):
    """
    Tests that server metrics are correctly reported after updating with both successful and failed requests.
    
    Verifies that the total, successful, and failed request counts, as well as memory usage, are accurately reflected in the metrics returned by the server.
    """
    # Update some metrics
    server.update_metrics(True, 0.1)
    server.update_metrics(False, 0.2)
    
    result = await server.get_metrics()
    
    assert result["success"]
    assert result["metrics"]["requests_total"] == 2
    assert result["metrics"]["requests_success"] == 1
    assert result["metrics"]["requests_failed"] == 1
    assert result["metrics"]["memory_usage_mb"] == 100.0

@pytest.mark.asyncio
async def test_update_config(server, mock_subprocess):
    """
    Tests that updating the server configuration applies new values and returns a success message.
    """
    new_config = MCPServerConfig(
        host="127.0.0.1",
        port=8001,
        auth_token="new_token"
    )
    
    result = await server.update_config(new_config)
    
    assert result["success"]
    assert result["message"] == "Configuration updated successfully"
    assert server.config.host == "127.0.0.1"
    assert server.config.port == 8001

@pytest.mark.asyncio
async def test_save_config(server, tmp_path):
    """
    Tests that the server configuration is correctly saved to a file.
    
    Verifies that the save operation reports success, the file is created, and the saved
    configuration contains the expected host and port values.
    """
    config_path = tmp_path / "test_config.json"
    
    result = await server.save_config(str(config_path))
    
    assert result["success"]
    assert config_path.exists()
    
    # Verify saved config
    config_data = json.loads(config_path.read_text())
    assert config_data["host"] == "localhost"
    assert config_data["port"] == 8000

@pytest.mark.asyncio
async def test_load_config(server, temp_config_file):
    """Test loading configuration from file."""
    result = await server.load_config(str(temp_config_file))
    
    assert result["success"]
    assert server.config.host == "localhost"
    assert server.config.port == 8000
    assert server.config.auth_token == "test_token"
    assert server.config.github_token == "github_token"
    assert server.config.log_level == "DEBUG"

@pytest.mark.asyncio
async def test_health_check(server, mock_aiohttp):
    """Test server health check."""
    result = await server.health_check()
    
    assert result["success"]
    assert result["status"] == "healthy"
    assert "details" in result

@pytest.mark.asyncio
async def test_metrics_update(server):
    """Test metrics updating."""
    # Initial state
    assert server._metrics.requests_total == 0
    assert server._metrics.average_response_time == 0.0
    
    # Add some metrics
    server.update_metrics(True, 0.1)
    assert server._metrics.requests_total == 1
    assert server._metrics.requests_success == 1
    assert server._metrics.average_response_time == 0.1
    
    server.update_metrics(False, 0.3)
    assert server._metrics.requests_total == 2
    assert server._metrics.requests_failed == 1
    assert server._metrics.average_response_time == 0.2  # (0.1 + 0.3) / 2

@pytest.mark.asyncio
async def test_error_handling(server):
    """Test error handling in server operations."""
    # Test with invalid config file
    result = await server.load_config("nonexistent.json")
    assert not result["success"]
    assert "error" in result
    
    # Test with invalid port
    invalid_config = MCPServerConfig(port=-1)
    result = await server.update_config(invalid_config)
    assert not result["success"]
    
    # Test health check with server down
    with patch('aiohttp.ClientSession.get', side_effect=Exception("Connection failed")):
        result = await server.health_check()
        assert not result["success"]
        assert "error" in result

def test_server_config_validation():
    """Test server configuration validation."""
    # Valid config
    config = MCPServerConfig(
        host="localhost",
        port=8000,
        auth_token="token"
    )
    assert config.host == "localhost"
    assert config.port == 8000
    
    # Test default values
    config = MCPServerConfig()
    assert config.host == "localhost"
    assert config.port == 8000
    assert config.log_level == "INFO"
    assert config.timeout == 30

def test_server_metrics_model():
    """
    Tests that the MCPServerMetrics model initializes all fields to their default zero values.
    """
    metrics = MCPServerMetrics()
    assert metrics.requests_total == 0
    assert metrics.requests_success == 0
    assert metrics.requests_failed == 0
    assert metrics.average_response_time == 0.0
    assert metrics.memory_usage_mb == 0.0

def test_server_status_model():
    """
    Tests the MCPServerStatus data model for correct field assignment.
    
    Verifies that MCPServerStatus correctly represents both running and not running server states, including PID, port, uptime, and error message fields.
    """
    # Running status
    status = MCPServerStatus(
        is_running=True,
        pid=12345,
        port=8000,
        uptime=3600
    )
    assert status.is_running
    assert status.pid == 12345
    
    # Not running status
    status = MCPServerStatus(
        is_running=False,
        error="Server stopped"
    )
    assert not status.is_running
    assert status.error == "Server stopped" 