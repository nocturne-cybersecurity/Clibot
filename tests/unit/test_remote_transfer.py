"""Unit tests for remote transfer capabilities."""
import pytest
from capabilities.remote_transfer import rsync, scp

def test_rsync_command_validation():
    """Test rsync command validation."""
    try:
        result = rsync('source.txt', 'dest.txt', dry_run=True)
        assert isinstance(result, dict)
        assert 'exit_code' in result
    except FileNotFoundError:
        pytest.skip("rsync not available")

def test_scp_command_validation():
    """Test scp command validation."""
    try:
        result = scp('source.txt', 'dest.txt', recursive=False)
        assert isinstance(result, dict)
        assert 'exit_code' in result
    except FileNotFoundError:
        pytest.skip("scp not available")
