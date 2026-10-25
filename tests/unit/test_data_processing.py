"""Unit tests for data processing capabilities."""
import pytest
from pathlib import Path
from capabilities.data_processing import read_csv, write_csv, csv_to_json, json_to_csv, read_json, write_json

def test_read_csv(tmp_path):
    """Test reading CSV file."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("name,age\nJohn,30\nJane,25")
    
    result = read_csv(str(csv_file))
    assert isinstance(result, dict)
    assert 'headers' in result
    assert result['headers'] == ['name', 'age']
    assert result['row_count'] == 2

def test_write_csv(tmp_path):
    """Test writing CSV file."""
    csv_file = tmp_path / "test.csv"
    data = [['name', 'age'], ['John', '30'], ['Jane', '25']]
    
    result = write_csv(str(csv_file), data, headers=['name', 'age'])
    assert isinstance(result, dict)
    assert result['success'] == True
    assert csv_file.exists()

def test_csv_to_json(tmp_path):
    """Test CSV to JSON conversion."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("name,age\nJohn,30\nJane,25")
    json_file = tmp_path / "test.json"
    
    result = csv_to_json(str(csv_file), str(json_file))
    assert isinstance(result, dict)
    assert result['success'] == True
    assert json_file.exists()

def test_json_to_csv(tmp_path):
    """Test JSON to CSV conversion."""
    json_file = tmp_path / "test.json"
    json_file.write_text('[{"name":"John","age":30},{"name":"Jane","age":25}]')
    csv_file = tmp_path / "test.csv"
    
    result = json_to_csv(str(json_file), str(csv_file))
    assert isinstance(result, dict)
    assert result['success'] == True
    assert csv_file.exists()

def test_read_json(tmp_path):
    """Test reading JSON file."""
    json_file = tmp_path / "test.json"
    json_file.write_text('{"name":"John","age":30}')
    
    result = read_json(str(json_file))
    assert isinstance(result, dict)
    assert 'data' in result
    assert result['data']['name'] == 'John'

def test_write_json(tmp_path):
    """Test writing JSON file."""
    json_file = tmp_path / "test.json"
    data = {"name": "John", "age": 30}
    
    result = write_json(str(json_file), data)
    assert isinstance(result, dict)
    assert result['success'] == True
    assert json_file.exists()
