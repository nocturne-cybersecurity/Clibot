"""Unit tests for advanced system capabilities."""
import pytest
from capabilities.system import environment_variables, hardware_info, audio_volume, screen_brightness

def test_environment_variables():
    """Test environment variables inspection."""
    result = environment_variables()
    assert isinstance(result, dict)
    assert 'HOME' in result or 'USER' in result or 'PATH' in result

def test_hardware_info():
    """Test hardware information gathering."""
    result = hardware_info()
    assert isinstance(result, dict)
    assert 'cpu' in result or 'memory' in result or 'disks' in result

def test_audio_volume_get():
    """Test getting audio volume."""
    try:
        result = audio_volume()
        assert isinstance(result, dict)
    except FileNotFoundError:
        pytest.skip("Audio control not available")

def test_screen_brightness_get():
    """Test getting screen brightness."""
    try:
        result = screen_brightness()
        assert isinstance(result, dict)
    except FileNotFoundError:
        pytest.skip("Brightness control not available")
