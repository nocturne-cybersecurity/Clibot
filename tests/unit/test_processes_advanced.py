"""Unit tests for advanced process capabilities."""
import pytest
from capabilities.processes import cpu_top, process_temperatures, detailed_inspect

def test_cpu_top():
    """Test CPU usage monitoring."""
    try:
        result = cpu_top(limit=5)
        assert isinstance(result, list)
    except FileNotFoundError:
        pytest.skip("top not available")

def test_process_temperatures():
    """Test process temperature monitoring."""
    result = process_temperatures()
    assert isinstance(result, dict)
    assert 'cpu' in result or 'other' in result

def test_detailed_inspect():
    """Test detailed process inspection."""
    import os
    result = detailed_inspect(os.getpid())
    assert isinstance(result, dict)
    assert 'pid' in result
    assert 'name' in result
