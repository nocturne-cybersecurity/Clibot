"""Unit tests for advanced development capabilities."""
import pytest
from capabilities.development import git_branch, git_log, git_diff

def test_git_branch():
    """Test git branch listing."""
    try:
        result = git_branch('.')
        assert isinstance(result, dict)
        assert 'current' in result or 'branches' in result
    except FileNotFoundError:
        pytest.skip("git not available")

def test_git_log():
    """Test git log."""
    try:
        result = git_log('.', limit=5)
        assert isinstance(result, dict)
        assert 'commits' in result
    except FileNotFoundError:
        pytest.skip("git not available")

def test_git_diff():
    """Test git diff."""
    try:
        result = git_diff('.')
        assert isinstance(result, dict)
        assert 'diff' in result
    except FileNotFoundError:
        pytest.skip("git not available")
