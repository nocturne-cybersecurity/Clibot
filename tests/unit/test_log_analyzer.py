"""Unit tests for log analyzer capabilities."""
import pytest
from capabilities.log_analyzer import analyze_journalctl, analyze_syslog

def test_analyze_journalctl():
    """Test journalctl log analysis."""
    try:
        result = analyze_journalctl(lines=10)
        assert isinstance(result, dict)
        assert 'errors' in result or 'message' in result
    except (FileNotFoundError, RuntimeError):
        pytest.skip("journalctl not available")

def test_analyze_syslog():
    """Test syslog analysis."""
    try:
        result = analyze_syslog(lines=10)
        assert isinstance(result, dict)
        assert 'errors' in result or 'message' in result
    except (FileNotFoundError, RuntimeError):
        pytest.skip("syslog not available")
