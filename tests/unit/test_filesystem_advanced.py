"""Unit tests for advanced filesystem capabilities."""
import pytest
from pathlib import Path
from capabilities.filesystem import change_permissions, bulk_copy, bulk_delete

def test_change_permissions(tmp_path):
    """Test changing file permissions."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test")
    
    result = change_permissions(str(test_file), "644")
    assert result['success'] == True
    assert result['mode'] == '0o644'

def test_bulk_copy(tmp_path):
    """Test bulk file copy."""
    src_dir = tmp_path / "src"
    dst_dir = tmp_path / "dst"
    src_dir.mkdir()
    dst_dir.mkdir()
    
    (src_dir / "file1.txt").write_text("test1")
    (src_dir / "file2.txt").write_text("test2")
    
    result = bulk_copy("*.txt", str(dst_dir), pattern_type='glob', source_dir=str(src_dir))
    assert result['count'] == 2

def test_bulk_delete(tmp_path):
    """Test bulk file deletion."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    
    (test_dir / "file1.txt").write_text("test1")
    (test_dir / "file2.txt").write_text("test2")
    
    result = bulk_delete("*.txt", pattern_type='glob', source_dir=str(test_dir))
    assert result['count'] == 2
