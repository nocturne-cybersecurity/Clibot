"""Database operations for PostgreSQL and SQLite."""
import sqlite3
from pathlib import Path

def sqlite_query(db_path, query, params=None, fetch='all'):
    """Execute a query on a SQLite database."""
    db = Path(db_path).expanduser()
    if not db.exists():
        raise FileNotFoundError(f'Database file not found: {db}')
    
    conn = sqlite3.connect(str(db))
    cursor = conn.cursor()
    
    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if fetch == 'all':
            result = cursor.fetchall()
        elif fetch == 'one':
            result = cursor.fetchone()
        else:
            result = None
        
        conn.commit()
        
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        
        return {
            'database': str(db),
            'query': query,
            'columns': columns,
            'rows': result,
            'row_count': len(result) if result else 0
        }
    except sqlite3.Error as e:
        conn.rollback()
        raise RuntimeError(f'SQLite error: {e}')
    finally:
        conn.close()

def sqlite_create_table(db_path, table_name, columns):
    """Create a table in SQLite database."""
    db = Path(db_path).expanduser()
    
    conn = sqlite3.connect(str(db))
    cursor = conn.cursor()
    
    try:
        column_defs = ', '.join([f'{name} {dtype}' for name, dtype in columns.items()])
        query = f'CREATE TABLE IF NOT EXISTS {table_name} ({column_defs})'
        cursor.execute(query)
        conn.commit()
        
        return {
            'database': str(db),
            'table': table_name,
            'columns': columns,
            'success': True
        }
    except sqlite3.Error as e:
        conn.rollback()
        raise RuntimeError(f'SQLite error: {e}')
    finally:
        conn.close()

def sqlite_insert(db_path, table_name, data):
    """Insert data into a SQLite table."""
    db = Path(db_path).expanduser()
    
    conn = sqlite3.connect(str(db))
    cursor = conn.cursor()
    
    try:
        if isinstance(data, dict):
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data])
            values = list(data.values())
        elif isinstance(data, list) and all(isinstance(row, dict) for row in data):
            columns = ', '.join(data[0].keys())
            placeholders = ', '.join(['?' for _ in data[0]])
            values = [tuple(row.values()) for row in data]
        else:
            raise ValueError('Data must be a dict or list of dicts')
        
        query = f'INSERT INTO {table_name} ({columns}) VALUES ({placeholders})'
        
        if isinstance(values[0], tuple):
            cursor.executemany(query, values)
        else:
            cursor.execute(query, values)
        
        conn.commit()
        
        return {
            'database': str(db),
            'table': table_name,
            'inserted_count': cursor.rowcount,
            'success': True
        }
    except sqlite3.Error as e:
        conn.rollback()
        raise RuntimeError(f'SQLite error: {e}')
    finally:
        conn.close()

def sqlite_list_tables(db_path):
    """List all tables in a SQLite database."""
    db = Path(db_path).expanduser()
    if not db.exists():
        raise FileNotFoundError(f'Database file not found: {db}')
    
    conn = sqlite3.connect(str(db))
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        return {
            'database': str(db),
            'tables': tables,
            'count': len(tables)
        }
    finally:
        conn.close()

def sqlite_table_schema(db_path, table_name):
    """Get the schema of a SQLite table."""
    db = Path(db_path).expanduser()
    if not db.exists():
        raise FileNotFoundError(f'Database file not found: {db}')
    
    conn = sqlite3.connect(str(db))
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [{'name': row[1], 'type': row[2], 'not_null': bool(row[3]), 'pk': bool(row[5])} 
                   for row in cursor.fetchall()]
        
        return {
            'database': str(db),
            'table': table_name,
            'columns': columns
        }
    finally:
        conn.close()

def postgres_query(host, database, query, user=None, password=None, port=5432, params=None, fetch='all'):
    """Execute a query on a PostgreSQL database."""
    try:
        import psycopg2
    except ImportError:
        raise ImportError('psycopg2 is required for PostgreSQL. Install with: pip install psycopg2-binary')
    
    conn = psycopg2.connect(
        host=host,
        database=database,
        user=user,
        password=password,
        port=port
    )
    cursor = conn.cursor()
    
    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if fetch == 'all':
            result = cursor.fetchall()
        elif fetch == 'one':
            result = cursor.fetchone()
        else:
            result = None
        
        conn.commit()
        
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        
        return {
            'host': host,
            'database': database,
            'query': query,
            'columns': columns,
            'rows': result,
            'row_count': len(result) if result else 0
        }
    except psycopg2.Error as e:
        conn.rollback()
        raise RuntimeError(f'PostgreSQL error: {e}')
    finally:
        conn.close()

def postgres_list_tables(host, database, user=None, password=None, port=5432):
    """List all tables in a PostgreSQL database."""
    try:
        import psycopg2
    except ImportError:
        raise ImportError('psycopg2 is required for PostgreSQL. Install with: pip install psycopg2-binary')
    
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        return {
            'host': host,
            'database': database,
            'tables': tables,
            'count': len(tables)
        }
    finally:
        conn.close()

def postgres_table_schema(host, database, table_name, user=None, password=None, port=5432):
    """Get the schema of a PostgreSQL table."""
    try:
        import psycopg2
    except ImportError:
        raise ImportError('psycopg2 is required for PostgreSQL. Install with: pip install psycopg2-binary')
    
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = %s AND table_schema = 'public'
        """, (table_name,))
        
        columns = [
            {'name': row[0], 'type': row[1], 'nullable': row[2] == 'YES', 'default': row[3]}
            for row in cursor.fetchall()
        ]
        
        return {
            'host': host,
            'database': database,
            'table': table_name,
            'columns': columns
        }
    finally:
        conn.close()

def postgres_insert(host, database, table_name, data, user=None, password=None, port=5432):
    """Insert data into a PostgreSQL table."""
    try:
        import psycopg2
    except ImportError:
        raise ImportError('psycopg2 is required for PostgreSQL. Install with: pip install psycopg2-binary')
    
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cursor = conn.cursor()
    
    try:
        if isinstance(data, dict):
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['%s' for _ in data])
            values = list(data.values())
        elif isinstance(data, list) and all(isinstance(row, dict) for row in data):
            columns = ', '.join(data[0].keys())
            placeholders = ', '.join(['%s' for _ in data[0]])
            values = [tuple(row.values()) for row in data]
        else:
            raise ValueError('Data must be a dict or list of dicts')
        
        query = f'INSERT INTO {table_name} ({columns}) VALUES ({placeholders})'
        
        if isinstance(values[0], tuple):
            cursor.executemany(query, values)
        else:
            cursor.execute(query, values)
        
        conn.commit()
        
        return {
            'host': host,
            'database': database,
            'table': table_name,
            'inserted_count': cursor.rowcount,
            'success': True
        }
    except psycopg2.Error as e:
        conn.rollback()
        raise RuntimeError(f'PostgreSQL error: {e}')
    finally:
        conn.close()

def postgres_create_table(host, database, table_name, columns, user=None, password=None, port=5432):
    """Create a table in PostgreSQL database."""
    try:
        import psycopg2
    except ImportError:
        raise ImportError('psycopg2 is required for PostgreSQL. Install with: pip install psycopg2-binary')
    
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cursor = conn.cursor()
    
    try:
        column_defs = ', '.join([f'{name} {dtype}' for name, dtype in columns.items()])
        query = f'CREATE TABLE IF NOT EXISTS {table_name} ({column_defs})'
        cursor.execute(query)
        conn.commit()
        
        return {
            'host': host,
            'database': database,
            'table': table_name,
            'columns': columns,
            'success': True
        }
    except psycopg2.Error as e:
        conn.rollback()
        raise RuntimeError(f'PostgreSQL error: {e}')
    finally:
        conn.close()
