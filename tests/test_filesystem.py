"""Tests for filesystem capabilities."""
import pytest
import tempfile
import shutil
from pathlib import Path
from capabilities import filesystem as fs


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    dir_path = Path(tempfile.mkdtemp())
    yield dir_path
    shutil.rmtree(dir_path)


def test_create_file(temp_dir):
    """Test creating a file."""
    file_path = temp_dir / "test.txt"
    result = fs.create_file(str(file_path), "test content")
    assert Path(result).exists()
    assert Path(result).read_text() == "test content"


def test_create_directory(temp_dir):
    """Test creating a directory."""
    dir_path = temp_dir / "new_dir"
    result = fs.create_directory(str(dir_path))
    assert Path(result).exists()
    assert Path(result).is_dir()


def test_delete_file(temp_dir):
    """Test deleting a file."""
    file_path = temp_dir / "to_delete.txt"
    file_path.write_text("content")
    result = fs.delete(str(file_path))
    assert not file_path.exists()


def test_move(temp_dir):
    """Test moving a file."""
    src = temp_dir / "source.txt"
    dst_dir = temp_dir / "dest"
    dst_dir.mkdir()
    src.write_text("content")
    result = fs.move(str(src), str(dst_dir))
    assert not src.exists()
    assert (dst_dir / "source.txt").exists()


def test_search_names(temp_dir):
    """Test searching for files by name."""
    (temp_dir / "test1.py").write_text("")
    (temp_dir / "test2.py").write_text("")
    (temp_dir / "other.txt").write_text("")
    results = fs.search_names(str(temp_dir), "*.py")
    assert len(results) == 2


def test_disk_usage(temp_dir):
    """Test getting disk usage."""
    result = fs.disk_usage(str(temp_dir))
    assert 'total' in result
    assert 'used' in result
    assert 'available' in result


def test_change_permissions(temp_dir):
    """Test changing file permissions."""
    file_path = temp_dir / "test.txt"
    file_path.write_text("content")
    result = fs.change_permissions(str(file_path), "644")
    assert result['success'] is True
