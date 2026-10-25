"""Unit tests for database capabilities."""
import pytest
from pathlib import Path
from capabilities.database import sqlite_query, sqlite_create_table, sqlite_insert, sqlite_list_tables

def test_sqlite_create_table(tmp_path):
    """Test creating SQLite table."""
    db_path = tmp_path / "test.db"
    result = sqlite_create_table(str(db_path), "users", {"id": "INTEGER", "name": "TEXT"})
    assert isinstance(result, dict)
    assert result['success'] == True

def test_sqlite_insert(tmp_path):
    """Test inserting into SQLite table."""
    db_path = tmp_path / "test.db"
    sqlite_create_table(str(db_path), "users", {"id": "INTEGER", "name": "TEXT"})
    result = sqlite_insert(str(db_path), "users", {"id": 1, "name": "test"})
    assert isinstance(result, dict)
    assert result['success'] == True

def test_sqlite_query(tmp_path):
    """Test querying SQLite database."""
    db_path = tmp_path / "test.db"
    sqlite_create_table(str(db_path), "users", {"id": "INTEGER", "name": "TEXT"})
    sqlite_insert(str(db_path), "users", {"id": 1, "name": "test"})
    result = sqlite_query(str(db_path), "SELECT * FROM users")
    assert isinstance(result, dict)
    assert 'rows' in result

def test_sqlite_list_tables(tmp_path):
    """Test listing SQLite tables."""
    db_path = tmp_path / "test.db"
    sqlite_create_table(str(db_path), "users", {"id": "INTEGER", "name": "TEXT"})
    result = sqlite_list_tables(str(db_path))
    assert isinstance(result, dict)
    assert 'tables' in result
    assert 'users' in result['tables']
