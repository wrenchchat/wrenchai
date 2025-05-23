"""Tests for the GitHub Tools."""

import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, Any

from core.tools.github_tools import (
    IssueState,
    PullRequestState,
    SearchType,
    IssueCreate,
    PullRequestCreate,
    FileContent,
    RepositoryCreate,
    create_repository,
    create_or_update_file,
    get_file_contents,
    create_issue,
    create_pull_request,
    search_repositories,
    search_code,
    list_issues,
    list_pull_requests,
    create_branch,
    fork_repository,
    merge_pull_request
)

@pytest.fixture
def mock_mcp_github():
    """
    Provides a pytest fixture that mocks all MCP GitHub API functions used by the GitHub tools.
    
    Yields:
        A dictionary mapping function names to their corresponding mock objects for use in tests.
    """
    with patch("core.tools.github_tools.mcp_github_create_repository") as create_repo, \
         patch("core.tools.github_tools.mcp_github_create_or_update_file") as update_file, \
         patch("core.tools.github_tools.mcp_github_get_file_contents") as get_contents, \
         patch("core.tools.github_tools.mcp_github_create_issue") as create_issue, \
         patch("core.tools.github_tools.mcp_github_create_pull_request") as create_pr, \
         patch("core.tools.github_tools.mcp_github_search_repositories") as search_repos, \
         patch("core.tools.github_tools.mcp_github_search_code") as search_code, \
         patch("core.tools.github_tools.mcp_github_list_issues") as list_issues, \
         patch("core.tools.github_tools.mcp_github_list_pull_requests") as list_prs, \
         patch("core.tools.github_tools.mcp_github_create_branch") as create_branch, \
         patch("core.tools.github_tools.mcp_github_fork_repository") as fork_repo, \
         patch("core.tools.github_tools.mcp_github_merge_pull_request") as merge_pr:
        
        yield {
            "create_repository": create_repo,
            "create_or_update_file": update_file,
            "get_file_contents": get_contents,
            "create_issue": create_issue,
            "create_pull_request": create_pr,
            "search_repositories": search_repos,
            "search_code": search_code,
            "list_issues": list_issues,
            "list_pull_requests": list_prs,
            "create_branch": create_branch,
            "fork_repository": fork_repo,
            "merge_pull_request": merge_pr
        }

@pytest.mark.asyncio
async def test_create_repository(mock_mcp_github):
    """
    Asynchronously tests that a repository can be created using the GitHub tools interface.
    
    Verifies that the repository creation function returns a success flag, the correct repository name, and that the underlying MCP GitHub API is called once.
    """
    mock_mcp_github["create_repository"].return_value = {
        "id": 123,
        "name": "test-repo",
        "full_name": "owner/test-repo"
    }
    
    repo_data = RepositoryCreate(
        name="test-repo",
        description="Test repository",
        private=True
    )
    
    result = await create_repository(repo_data)
    
    assert result["success"]
    assert result["repository"]["name"] == "test-repo"
    mock_mcp_github["create_repository"].assert_called_once()

@pytest.mark.asyncio
async def test_create_or_update_file(mock_mcp_github):
    """
    Tests asynchronous creation or update of a file in a GitHub repository.
    
    Mocks the underlying API call to simulate file creation or update, then verifies
    that the operation succeeds, the returned file path is correct, and the mock was
    invoked exactly once.
    """
    mock_mcp_github["create_or_update_file"].return_value = {
        "content": {
            "path": "test.txt",
            "sha": "abc123"
        }
    }
    
    file_content = FileContent(
        path="test.txt",
        content="Test content",
        message="Add test file"
    )
    
    result = await create_or_update_file("owner", "repo", file_content)
    
    assert result["success"]
    assert result["file"]["content"]["path"] == "test.txt"
    mock_mcp_github["create_or_update_file"].assert_called_once()

@pytest.mark.asyncio
async def test_get_file_contents(mock_mcp_github):
    """
    Tests asynchronous retrieval of file contents from a repository using the mocked MCP GitHub API.
    
    Verifies that the tool function returns a successful result containing the file content and that the underlying API mock is called once.
    """
    mock_mcp_github["get_file_contents"].return_value = {
        "type": "file",
        "content": "Test content",
        "sha": "abc123"
    }
    
    result = await get_file_contents("owner", "repo", "test.txt")
    
    assert result["success"]
    assert "content" in result["contents"]
    mock_mcp_github["get_file_contents"].assert_called_once()

@pytest.mark.asyncio
async def test_create_issue(mock_mcp_github):
    """
    Tests asynchronous creation of a GitHub issue using mocked API responses.
    
    Verifies that the issue is created successfully, the returned issue data matches expectations, and the underlying API function is called once.
    """
    mock_mcp_github["create_issue"].return_value = {
        "number": 1,
        "title": "Test issue",
        "state": "open"
    }
    
    issue_data = IssueCreate(
        title="Test issue",
        body="Test description",
        labels=["bug"]
    )
    
    result = await create_issue("owner", "repo", issue_data)
    
    assert result["success"]
    assert result["issue"]["title"] == "Test issue"
    mock_mcp_github["create_issue"].assert_called_once()

@pytest.mark.asyncio
async def test_create_pull_request(mock_mcp_github):
    """
    Tests asynchronous creation of a pull request using mocked MCP GitHub API.
    
    Verifies that the pull request is created successfully, the returned title matches
    the expected value, and the underlying API function is called once.
    """
    mock_mcp_github["create_pull_request"].return_value = {
        "number": 1,
        "title": "Test PR",
        "state": "open"
    }
    
    pr_data = PullRequestCreate(
        title="Test PR",
        body="Test description",
        head="feature-branch"
    )
    
    result = await create_pull_request("owner", "repo", pr_data)
    
    assert result["success"]
    assert result["pull_request"]["title"] == "Test PR"
    mock_mcp_github["create_pull_request"].assert_called_once()

@pytest.mark.asyncio
async def test_search_repositories(mock_mcp_github):
    """
    Tests asynchronous searching of repositories using the mocked MCP GitHub API.
    
    Verifies that the search returns the expected number of repository items and that the
    mocked search function is called exactly once.
    """
    mock_mcp_github["search_repositories"].return_value = {
        "total_count": 1,
        "items": [{"name": "test-repo"}]
    }
    
    result = await search_repositories("test")
    
    assert result["success"]
    assert len(result["repositories"]["items"]) == 1
    mock_mcp_github["search_repositories"].assert_called_once()

@pytest.mark.asyncio
async def test_search_code(mock_mcp_github):
    """
    Tests asynchronous code search functionality using a mocked MCP GitHub API.
    
    Verifies that searching for code returns the expected number of items and that the
    mocked search function is called exactly once.
    """
    mock_mcp_github["search_code"].return_value = {
        "total_count": 1,
        "items": [{"path": "test.py"}]
    }
    
    result = await search_code("test")
    
    assert result["success"]
    assert len(result["code"]["items"]) == 1
    mock_mcp_github["search_code"].assert_called_once()

@pytest.mark.asyncio
async def test_list_issues(mock_mcp_github):
    """
    Tests asynchronous listing of issues with filtering by state and labels using mocked MCP GitHub API responses.
    """
    mock_mcp_github["list_issues"].return_value = [
        {"number": 1, "title": "Test issue"}
    ]
    
    result = await list_issues(
        "owner",
        "repo",
        state=IssueState.OPEN,
        labels=["bug"]
    )
    
    assert result["success"]
    assert len(result["issues"]) == 1
    mock_mcp_github["list_issues"].assert_called_once()

@pytest.mark.asyncio
async def test_list_pull_requests(mock_mcp_github):
    """
    Asynchronously tests listing pull requests using the mocked MCP GitHub API.
    
    Verifies that the tool returns a successful response with the expected number of pull requests and that the underlying API function is called once.
    """
    mock_mcp_github["list_pull_requests"].return_value = [
        {"number": 1, "title": "Test PR"}
    ]
    
    result = await list_pull_requests(
        "owner",
        "repo",
        state=PullRequestState.OPEN
    )
    
    assert result["success"]
    assert len(result["pull_requests"]) == 1
    mock_mcp_github["list_pull_requests"].assert_called_once()

@pytest.mark.asyncio
async def test_create_branch(mock_mcp_github):
    """
    Tests asynchronous creation of a new branch from a base branch using the mocked GitHub API.
    
    Verifies that the branch is created successfully, the branch reference contains the expected name, and the underlying API function is called once.
    """
    mock_mcp_github["create_branch"].return_value = {
        "ref": "refs/heads/feature",
        "object": {"sha": "abc123"}
    }
    
    result = await create_branch(
        "owner",
        "repo",
        "feature",
        from_branch="main"
    )
    
    assert result["success"]
    assert "feature" in result["branch"]["ref"]
    mock_mcp_github["create_branch"].assert_called_once()

@pytest.mark.asyncio
async def test_fork_repository(mock_mcp_github):
    """
    Tests asynchronous forking of a GitHub repository using a mocked MCP GitHub API.
    
    Verifies that the fork operation returns a success flag, correct fork details, and that the underlying API function is called once.
    """
    mock_mcp_github["fork_repository"].return_value = {
        "id": 456,
        "name": "test-repo",
        "full_name": "new-owner/test-repo"
    }
    
    result = await fork_repository("owner", "repo")
    
    assert result["success"]
    assert result["fork"]["name"] == "test-repo"
    mock_mcp_github["fork_repository"].assert_called_once()

@pytest.mark.asyncio
async def test_merge_pull_request(mock_mcp_github):
    """
    Tests asynchronous merging of a pull request using a mocked MCP GitHub API.
    
    Verifies that the merge operation returns a successful result and that the merged flag is set to True.
    """
    mock_mcp_github["merge_pull_request"].return_value = {
        "sha": "abc123",
        "merged": True
    }
    
    result = await merge_pull_request(
        "owner",
        "repo",
        1,
        commit_title="Merge PR #1"
    )
    
    assert result["success"]
    assert result["merge"]["merged"]
    mock_mcp_github["merge_pull_request"].assert_called_once()

@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling in GitHub tools."""
    with patch("core.tools.github_tools.mcp_github_create_repository", 
              side_effect=Exception("API Error")):
        result = await create_repository(
            RepositoryCreate(name="test-repo")
        )
        
        assert not result["success"]
        assert "API Error" in result["error"]

def test_model_validation():
    """
    Validates instantiation and default values of GitHub-related data models.
    
    Creates instances of RepositoryCreate, IssueCreate, PullRequestCreate, and FileContent
    to verify correct field assignments and default or optional values.
    """
    # Valid repository creation
    repo = RepositoryCreate(name="test-repo")
    assert repo.name == "test-repo"
    assert not repo.private
    
    # Valid issue creation
    issue = IssueCreate(
        title="Test",
        body="Description",
        labels=["bug"]
    )
    assert issue.title == "Test"
    assert "bug" in issue.labels
    
    # Valid pull request creation
    pr = PullRequestCreate(
        title="Test PR",
        body="Description",
        head="feature"
    )
    assert pr.title == "Test PR"
    assert pr.base == "main"  # Default value
    
    # Valid file content
    file = FileContent(
        path="test.txt",
        content="content",
        message="commit message"
    )
    assert file.path == "test.txt"
    assert file.branch is None  # Optional field 