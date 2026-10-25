"""Unit tests for advanced package management capabilities."""
import pytest
from capabilities.packages import list_installed, security_audit

def test_list_installed():
    """Test listing installed packages."""
    try:
        result = list_installed()
        assert isinstance(result, dict)
        assert 'packages' in result
        assert 'count' in result
    except FileNotFoundError:
        pytest.skip("Package manager not available")

def test_security_audit():
    """Test security update audit."""
    try:
        result = security_audit()
        assert isinstance(result, dict)
        assert 'manager' in result
        assert 'has_security_updates' in result
    except FileNotFoundError:
        pytest.skip("Package manager not available")
