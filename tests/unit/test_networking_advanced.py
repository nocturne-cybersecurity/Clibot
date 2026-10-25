"""Unit tests for advanced networking capabilities."""
import pytest
from capabilities.networking import public_ip, ping, firewall_status, vpn_status

def test_public_ip():
    """Test public IP retrieval."""
    try:
        result = public_ip()
        assert isinstance(result, dict)
        assert 'public_ip' in result or 'error' in result
    except Exception:
        pytest.skip("Network not available")

def test_ping():
    """Test ping functionality."""
    try:
        result = ping('8.8.8.8', count=2)
        assert isinstance(result, dict)
        assert 'host' in result
    except FileNotFoundError:
        pytest.skip("ping not available")

def test_firewall_status():
    """Test firewall status check."""
    result = firewall_status()
    assert isinstance(result, dict)
    assert 'active' in result
    assert 'type' in result

def test_vpn_status():
    """Test VPN status check."""
    result = vpn_status()
    assert isinstance(result, dict)
    assert 'connected' in result
