"""Unit tests for security audit capabilities."""
import pytest
from capabilities.security_audit import ssh_audit, find_suid_sgid, basic_sast

def test_ssh_audit():
    """Test SSH configuration audit."""
    result = ssh_audit()
    assert isinstance(result, dict)
    assert 'config' in result or 'authorized_keys' in result

def test_find_suid_sgid():
    """Test SUID/SGID file finding."""
    try:
        result = find_suid_sgid()
        assert isinstance(result, dict)
        assert 'suid' in result
        assert 'sgid' in result
    except PermissionError:
        pytest.skip("Root required")

def test_basic_sast(tmp_path):
    """Test basic static application security testing."""
    test_file = tmp_path / "test.py"
    test_file.write_text("import os; os.system('ls')")
    
    result = basic_sast(str(tmp_path))
    assert isinstance(result, dict)
    assert 'vulnerabilities' in result
