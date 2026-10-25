"""Remote file transfer with rsync and scp."""
import shutil, subprocess
from pathlib import Path

def rsync(source, destination, options=None, dry_run=False):
    """Copy files/directories using rsync with optional options."""
    if not shutil.which('rsync'):
        raise FileNotFoundError('rsync is not installed')
    
    cmd = ['rsync', '-avz', '--progress']
    if dry_run:
        cmd.append('--dry-run')
    
    if options:
        if isinstance(options, str):
            cmd.extend(options.split())
        elif isinstance(options, list):
            cmd.extend(options)
    
    cmd.extend([source, destination])
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return {
        'exit_code': result.returncode,
        'stdout': result.stdout,
        'stderr': result.stderr,
        'source': source,
        'destination': destination,
        'dry_run': dry_run
    }

def scp(source, destination, recursive=False, port=None):
    """Copy files using scp."""
    if not shutil.which('scp'):
        raise FileNotFoundError('scp is not installed')
    
    cmd = ['scp']
    if recursive:
        cmd.append('-r')
    if port:
        cmd.extend(['-P', str(port)])
    
    cmd.extend([source, destination])
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return {
        'exit_code': result.returncode,
        'stdout': result.stdout,
        'stderr': result.stderr,
        'source': source,
        'destination': destination
    }

def extract_rar(archive, destination='.'):
    """Extract RAR archive (requires unrar)."""
    if not shutil.which('unrar'):
        raise FileNotFoundError('unrar is not installed. Install with: sudo apt install unrar')
    
    dest = Path(destination).expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    
    cmd = ['unrar', 'x', str(archive), str(dest)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f'unrar exited {result.returncode}')
    
    return {'archive': archive, 'destination': str(dest), 'extracted': True}

def extract_7z(archive, destination='.'):
    """Extract 7z archive (requires 7z or p7zip)."""
    exe = shutil.which('7z') or shutil.which('7zz') or shutil.which('7za')
    if not exe:
        raise FileNotFoundError('7z is not installed. Install with: sudo apt install p7zip-full')
    
    dest = Path(destination).expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    
    cmd = [exe, 'x', str(archive), f'-o{dest}', '-y']
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f'7z exited {result.returncode}')
    
    return {'archive': archive, 'destination': str(dest), 'extracted': True}

def create_7z(source, destination, compression_level=5):
    """Create 7z archive."""
    exe = shutil.which('7z') or shutil.which('7zz') or shutil.which('7za')
    if not exe:
        raise FileNotFoundError('7z is not installed. Install with: sudo apt install p7zip-full')
    
    cmd = [exe, 'a', f'-mx={compression_level}', str(destination), str(source)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f'7z exited {result.returncode}')
    
    return {'source': source, 'destination': destination, 'created': True}
