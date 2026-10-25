"""Safe local filesystem operations."""
from pathlib import Path
import hashlib, shutil, tarfile, zipfile, os, stat, time, subprocess

def listing(path='.', all_entries=False):
    p=Path(path).expanduser(); items=[]
    for x in sorted(p.iterdir(), key=lambda q:q.name.lower()):
        if all_entries or not x.name.startswith('.'): items.append({'name':x.name,'type':'directory' if x.is_dir() else 'file' if x.is_file() else 'other','size':x.stat(follow_symlinks=False).st_size})
    return items
def metadata(path):
    p=Path(path).expanduser(); s=p.lstat(); return {'path':str(p),'size':s.st_size,'mode':oct(s.st_mode & 0o7777),'modified':s.st_mtime,'is_symlink':p.is_symlink(),'is_file':p.is_file(),'is_dir':p.is_dir()}
def read_text(path, limit=65536):
    p=Path(path).expanduser()
    if p.stat().st_size>limit: raise ValueError(f'File exceeds read limit ({limit} bytes)')
    return p.read_text(errors='replace')
def search_names(path, pattern):
    """Search names below a directory without following symlinks or wandering system trees."""
    root = Path(path).expanduser()
    if not root.is_dir():
        raise NotADirectoryError(f'No es una carpeta accesible: {root}')
    if not pattern or len(pattern) > 255:
        raise ValueError('El texto de búsqueda debe tener entre 1 y 255 caracteres.')
    found = []
    visited = 0
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False, onerror=lambda _error: None):
        dirs[:] = [name for name in dirs if not (Path(current) / name).is_symlink()]
        visited += 1
        if visited > 10000:
            break
        for name in (*dirs, *files):
            if pattern.casefold() in name.casefold():
                found.append(str(Path(current) / name))
                if len(found) >= 500:
                    return found
    return found
def search_text(path, query):
    out=[]
    for p in Path(path).expanduser().rglob('*'):
        if len(out)>=1000: break
        if p.is_file() and not p.is_symlink():
            try:
                with p.open(errors='replace') as f:
                    for n,line in enumerate(f,1):
                        if query.casefold() in line.casefold(): out.append({'path':str(p),'line':n,'text':line.rstrip()[:500]})
            except (OSError,UnicodeError): pass
    return out
def create_directory(path): Path(path).expanduser().mkdir(parents=True,exist_ok=False); return str(Path(path).expanduser())
def create_file(path, content=''):
    p=Path(path).expanduser()
    if not p.parent.is_dir():raise FileNotFoundError(f'La carpeta de destino no existe: {p.parent}')
    with p.open('x') as f: f.write(content)
    return str(p)
def write(path, content=''):
    p=Path(path).expanduser()
    if not p.parent.is_dir():raise FileNotFoundError(f'La carpeta de destino no existe: {p.parent}')
    with p.open('w') as f: f.write(content)
    return str(p)
def copy(source,destination):
    a,b=Path(source).expanduser(),Path(destination).expanduser()
    if b.exists(): raise FileExistsError(b)
    return shutil.copytree(a,b,symlinks=True) if a.is_dir() else shutil.copy2(a,b,follow_symlinks=False)
def move(source,destination):
    a,b=Path(source).expanduser(),Path(destination).expanduser()
    if b.is_dir():b=b/a.name
    if b.exists(): raise FileExistsError(b)
    if not b.parent.is_dir():raise FileNotFoundError(f'La carpeta de destino no existe: {b.parent}')
    return shutil.move(str(a),str(b))
def delete(path):
    p=Path(path).expanduser()
    if p.is_symlink() or p.is_file(): p.unlink()
    elif p.is_dir(): shutil.rmtree(p)
    else: raise FileNotFoundError(p)
    return str(p)
def digest(path, algorithm='sha256'):
    h=hashlib.new(algorithm)
    with Path(path).expanduser().open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()
def disk_usage(path='.'): return shutil.disk_usage(Path(path).expanduser())._asdict()
def find_large(path='.', minimum_bytes=100_000_000):
    return [{'path':str(p),'size':p.stat().st_size} for p in Path(path).expanduser().rglob('*') if p.is_file() and not p.is_symlink() and p.stat().st_size>=minimum_bytes][:1000]
def extract(archive,destination='.'):
    src,dst=Path(archive).expanduser(),Path(destination).expanduser().resolve(); dst.mkdir(parents=True,exist_ok=True)
    if zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as z:
            if any((dst/n).resolve().parent!=dst and dst not in (dst/n).resolve().parents for n in z.namelist()): raise ValueError('Archive contains path traversal')
            z.extractall(dst)
    elif tarfile.is_tarfile(src):
        with tarfile.open(src) as t:
            for m in t.getmembers():
                target=(dst/m.name).resolve()
                if dst not in target.parents and target!=dst: raise ValueError('Archive contains path traversal')
            t.extractall(dst,filter='data')
    else: raise ValueError('Unsupported archive (supported: zip, tar variants)')
    return str(dst)
def archive(source,destination):
    src,dst=Path(source).expanduser(),Path(destination).expanduser()
    if dst.exists(): raise FileExistsError(dst)
    if dst.suffix=='.zip':
        with zipfile.ZipFile(dst,'w',zipfile.ZIP_DEFLATED) as z:
            for p in ([src] if src.is_file() else src.rglob('*')):
                if p.is_file() and not p.is_symlink(): z.write(p,p.relative_to(src.parent))
    else:
        with tarfile.open(dst,'w:gz') as t: t.add(src,arcname=src.name,recursive=True)
    return str(dst)

def change_permissions(path, mode, recursive=False):
    """Change file/directory permissions (octal mode like 755 or 644)."""
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f'Path does not exist: {p}')
    
    if isinstance(mode, str):
        try:
            mode = int(mode, 8)
        except ValueError:
            raise ValueError('Mode must be an octal string (e.g., "755") or integer')
    
    if recursive and p.is_dir():
        for item in p.rglob('*'):
            item.chmod(mode)
    p.chmod(mode)
    return {'success': True, 'path': str(p), 'mode': oct(mode), 'recursive': recursive}

def change_owner(path, user=None, group=None, recursive=False):
    """Change file/directory owner and group (requires root)."""
    if os.geteuid() != 0:
        raise PermissionError('Changing ownership requires root privileges')
    
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f'Path does not exist: {p}')
    
    if not shutil.which('chown'):
        raise FileNotFoundError('chown command is not available')
    
    cmd = ['chown']
    if recursive:
        cmd.append('-R')
    
    ownership = ''
    if user:
        ownership += user
    if group:
        ownership += f':{group}'
    
    if not ownership:
        raise ValueError('At least user or group must be specified')
    
    cmd.extend([ownership, str(p)])
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f'chown exited {result.returncode}')
    
    return {'path': str(p), 'user': user, 'group': group, 'recursive': recursive}

def bulk_copy(source_pattern, destination_dir, pattern_type='glob', source_dir='.'):
    """Copy multiple files matching a pattern to a destination directory."""
    dest = Path(destination_dir).expanduser()
    source_root = Path(source_dir).expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    
    copied = []
    if pattern_type == 'glob':
        for source in source_root.glob(source_pattern):
            if source.is_file():
                target=dest / source.name
                if target.exists():raise FileExistsError(target)
                shutil.copy2(source, target)
                copied.append(str(source))
    elif pattern_type == 'regex':
        import re
        pattern = re.compile(source_pattern)
        for source in source_root.iterdir():
            if source.is_file() and pattern.search(source.name):
                target=dest / source.name
                if target.exists():raise FileExistsError(target)
                shutil.copy2(source, target)
                copied.append(str(source))
    else:
        raise ValueError('pattern_type must be "glob" or "regex"')
    
    return {'copied': copied, 'count': len(copied), 'destination': str(dest)}

def bulk_delete(source_pattern, pattern_type='glob', source_dir='.'):
    """Delete multiple files matching a pattern (destructive)."""
    deleted = []
    source_root=Path(source_dir).expanduser()
    if pattern_type == 'glob':
        for source in source_root.glob(source_pattern):
            if source.is_file():
                source.unlink()
                deleted.append(str(source))
    elif pattern_type == 'regex':
        import re
        pattern = re.compile(source_pattern)
        for source in source_root.iterdir():
            if source.is_file() and pattern.search(source.name):
                source.unlink()
                deleted.append(str(source))
    else:
        raise ValueError('pattern_type must be "glob" or "regex"')
    
    return {'deleted': deleted, 'count': len(deleted)}

def watch_path(path, events=('modify', 'create', 'delete'), duration_seconds=60):
    """Monitor a path for filesystem changes (requires watchdog library)."""
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        raise ImportError('watchdog library is required for file watching. Install with: pip install watchdog')
    
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f'Path does not exist: {p}')
    
    changes = []
    
    class Handler(FileSystemEventHandler):
        def __init__(self, changes_list):
            self.changes = changes_list
        
        def on_modified(self, event):
            if not event.is_directory:
                self.changes.append({'event': 'modify', 'path': event.src_path, 'time': time.time()})
        
        def on_created(self, event):
            if not event.is_directory:
                self.changes.append({'event': 'create', 'path': event.src_path, 'time': time.time()})
        
        def on_deleted(self, event):
            if not event.is_directory:
                self.changes.append({'event': 'delete', 'path': event.src_path, 'time': time.time()})
    
    observer = Observer()
    handler = Handler(changes)
    observer.schedule(handler, str(p), recursive=True)
    observer.start()
    
    time.sleep(duration_seconds)
    observer.stop()
    observer.join()
    
    return {'path': str(p), 'duration_seconds': duration_seconds, 'changes': changes, 'count': len(changes)}
