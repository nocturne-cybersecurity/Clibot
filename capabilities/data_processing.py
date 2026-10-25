"""Large-scale data processing for CSV, JSON, and complex conversions."""
import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Union

def read_csv(file_path, delimiter=',', has_header=True, encoding='utf-8', max_rows=None):
    """Read CSV file with support for large files."""
    p = Path(file_path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f'CSV file not found: {p}')
    
    rows = []
    headers = []
    
    with open(p, 'r', encoding=encoding) as f:
        reader = csv.reader(f, delimiter=delimiter)
        
        if has_header:
            headers = next(reader)
        
        for i, row in enumerate(reader):
            if max_rows and i >= max_rows:
                break
            rows.append(row)
    
    return {
        'file': str(p),
        'headers': headers,
        'rows': rows,
        'row_count': len(rows),
        'column_count': len(headers) if headers else len(rows[0]) if rows else 0
    }

def write_csv(file_path, data, headers=None, delimiter=',', encoding='utf-8'):
    """Write data to CSV file."""
    p = Path(file_path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    
    with open(p, 'w', encoding=encoding, newline='') as f:
        writer = csv.writer(f, delimiter=delimiter)
        
        if headers:
            writer.writerow(headers)
        
        if isinstance(data, list):
            writer.writerows(data)
        elif isinstance(data, dict):
            if headers is None:
                headers = list(data.keys())
                writer.writerow(headers)
            writer.writerow(data.values())
    
    return {
        'file': str(p),
        'rows_written': len(data) if isinstance(data, list) else 1,
        'success': True
    }

def csv_to_json(csv_path, json_path, delimiter=',', has_header=True, encoding='utf-8'):
    """Convert CSV file to JSON."""
    csv_data = read_csv(csv_path, delimiter, has_header, encoding)
    
    if has_header:
        json_data = [dict(zip(csv_data['headers'], row)) for row in csv_data['rows']]
    else:
        json_data = csv_data['rows']
    
    with open(json_path, 'w', encoding=encoding) as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    
    return {
        'source': str(csv_path),
        'destination': str(json_path),
        'records': len(json_data),
        'success': True
    }

def json_to_csv(json_path, csv_path, delimiter=',', encoding='utf-8'):
    """Convert JSON file to CSV."""
    p = Path(json_path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f'JSON file not found: {p}')
    
    with open(p, 'r', encoding=encoding) as f:
        data = json.load(f)
    
    if not data:
        raise ValueError('JSON file is empty')
    
    if isinstance(data, list):
        if isinstance(data[0], dict):
            headers = list(data[0].keys())
            rows = [[row.get(h, '') for h in headers] for row in data]
        else:
            headers = ['value']
            rows = [[row] for row in data]
    elif isinstance(data, dict):
        headers = list(data.keys())
        rows = [[data[h] for h in headers]]
    else:
        raise ValueError('Unsupported JSON structure')
    
    write_csv(csv_path, rows, headers, delimiter, encoding)
    
    return {
        'source': str(json_path),
        'destination': str(csv_path),
        'records': len(rows),
        'success': True
    }

def read_json(file_path, encoding='utf-8'):
    """Read JSON file."""
    p = Path(file_path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f'JSON file not found: {p}')
    
    with open(p, 'r', encoding=encoding) as f:
        data = json.load(f)
    
    return {
        'file': str(p),
        'data': data,
        'type': type(data).__name__
    }

def write_json(file_path, data, indent=2, encoding='utf-8'):
    """Write data to JSON file."""
    p = Path(file_path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    
    with open(p, 'w', encoding=encoding) as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
    
    return {
        'file': str(p),
        'success': True
    }

def filter_csv(csv_path, output_path, filter_func, delimiter=',', encoding='utf-8'):
    """Filter CSV rows based on a condition."""
    csv_data = read_csv(csv_path, delimiter, has_header=True, encoding=encoding)
    
    filtered_rows = []
    for row in csv_data['rows']:
        row_dict = dict(zip(csv_data['headers'], row))
        if filter_func(row_dict):
            filtered_rows.append(row)
    
    write_csv(output_path, filtered_rows, csv_data['headers'], delimiter, encoding)
    
    return {
        'source': str(csv_path),
        'destination': str(output_path),
        'original_rows': len(csv_data['rows']),
        'filtered_rows': len(filtered_rows),
        'success': True
    }

def merge_csv(input_paths, output_path, delimiter=',', encoding='utf-8'):
    """Merge multiple CSV files into one."""
    if isinstance(input_paths, str):
        input_paths = [input_paths]
    
    all_rows = []
    headers = None
    
    for path in input_paths:
        csv_data = read_csv(path, delimiter, has_header=True, encoding=encoding)
        if headers is None:
            headers = csv_data['headers']
        all_rows.extend(csv_data['rows'])
    
    write_csv(output_path, all_rows, headers, delimiter, encoding)
    
    return {
        'sources': input_paths,
        'destination': str(output_path),
        'total_rows': len(all_rows),
        'success': True
    }

def aggregate_csv(csv_path, group_by, aggregations, output_path, delimiter=',', encoding='utf-8'):
    """Aggregate CSV data by grouping columns."""
    csv_data = read_csv(csv_path, delimiter, has_header=True, encoding=encoding)
    
    groups = {}
    group_indices = [csv_data['headers'].index(col) for col in group_by]
    
    for row in csv_data['rows']:
        key = tuple(row[i] for i in group_indices)
        if key not in groups:
            groups[key] = []
        groups[key].append(row)
    
    result = []
    for key, rows in groups.items():
        aggregated = list(key)
        for agg_col, agg_func in aggregations.items():
            col_idx = csv_data['headers'].index(agg_col)
            values = [float(row[col_idx]) for row in rows if row[col_idx]]
            
            if agg_func == 'sum':
                aggregated.append(sum(values))
            elif agg_func == 'avg':
                aggregated.append(sum(values) / len(values))
            elif agg_func == 'min':
                aggregated.append(min(values))
            elif agg_func == 'max':
                aggregated.append(max(values))
            elif agg_func == 'count':
                aggregated.append(len(values))
        
        result.append(aggregated)
    
    output_headers = list(group_by) + [f'{col}_{agg}' for col, agg in aggregations.items()]
    write_csv(output_path, result, output_headers, delimiter, encoding)
    
    return {
        'source': str(csv_path),
        'destination': str(output_path),
        'groups': len(groups),
        'success': True
    }

def transform_json(json_path, output_path, transform_func, encoding='utf-8'):
    """Transform JSON data using a custom function."""
    data = read_json(json_path, encoding)
    
    if isinstance(data['data'], list):
        transformed = [transform_func(item) for item in data['data']]
    elif isinstance(data['data'], dict):
        transformed = transform_func(data['data'])
    else:
        raise ValueError('Unsupported JSON structure for transformation')
    
    write_json(output_path, transformed, encoding=encoding)
    
    return {
        'source': str(json_path),
        'destination': str(output_path),
        'success': True
    }

def convert_xml_to_json(xml_path, json_path, encoding='utf-8'):
    """Convert XML file to JSON."""
    try:
        import xml.etree.ElementTree as ET
    except ImportError:
        raise ImportError('xml.etree.ElementTree is required')
    
    p = Path(xml_path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f'XML file not found: {p}')
    
    def element_to_dict(element):
        result = {}
        for child in element:
            if len(child) == 0:
                result[child.tag] = child.text
            else:
                result[child.tag] = element_to_dict(child)
        if element.attrib:
            result.update({f'@{k}': v for k, v in element.attrib.items()})
        return result
    
    tree = ET.parse(p)
    root = tree.getroot()
    json_data = {root.tag: element_to_dict(root)}
    
    write_json(json_path, json_data, encoding=encoding)
    
    return {
        'source': str(xml_path),
        'destination': str(json_path),
        'success': True
    }

def convert_yaml_to_json(yaml_path, json_path, encoding='utf-8'):
    """Convert YAML file to JSON."""
    try:
        import yaml
    except ImportError:
        raise ImportError('PyYAML is required. Install with: pip install pyyaml')
    
    p = Path(yaml_path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f'YAML file not found: {p}')
    
    with open(p, 'r', encoding=encoding) as f:
        data = yaml.safe_load(f)
    
    write_json(json_path, data, encoding=encoding)
    
    return {
        'source': str(yaml_path),
        'destination': str(json_path),
        'success': True
    }

def batch_convert(input_dir, output_dir, from_format, to_format, encoding='utf-8'):
    """Batch convert files from one format to another."""
    input_path = Path(input_dir).expanduser()
    output_path = Path(output_dir).expanduser()
    output_path.mkdir(parents=True, exist_ok=True)
    
    extensions = {
        'csv': '*.csv',
        'json': '*.json',
        'xml': '*.xml',
        'yaml': '*.yaml',
        'yml': '*.yml'
    }
    
    pattern = extensions.get(from_format, f'*.{from_format}')
    files = list(input_path.glob(pattern))
    
    converted = []
    for file in files:
        output_file = output_path / file.with_suffix(f'.{to_format}').name
        
        try:
            if from_format == 'csv' and to_format == 'json':
                csv_to_json(file, output_file, encoding=encoding)
            elif from_format == 'json' and to_format == 'csv':
                json_to_csv(file, output_file, encoding=encoding)
            elif from_format == 'xml' and to_format == 'json':
                convert_xml_to_json(file, output_file, encoding=encoding)
            elif from_format in ['yaml', 'yml'] and to_format == 'json':
                convert_yaml_to_json(file, output_file, encoding=encoding)
            else:
                continue
            
            converted.append(str(file))
        except Exception:
            pass
    
    return {
        'input_dir': str(input_path),
        'output_dir': str(output_path),
        'from_format': from_format,
        'to_format': to_format,
        'converted': converted,
        'count': len(converted)
    }
