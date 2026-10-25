"""Security auditing and forensic analysis tools."""
import os, subprocess, shutil, re
from pathlib import Path
from datetime import datetime

SECRET_PATTERNS = [
    (re.compile(r'(?i)(password|passwd|secret|api[_-]?key|token)\s*[=:]\s*[^\s,;]+'), 'credential'),
    (re.compile(r'(?i)bearer\s+[A-Za-z0-9._~+/=-]{20,}'), 'bearer_token'),
    (re.compile(r'-----BEGIN [^-]*PRIVATE KEY-----'), 'private_key'),
    (re.compile(r'(?i)aws[_-]?access[_-]?key[_-]?id\s*[=:]\s*[A-Z0-9]{20}'), 'aws_key'),
    (re.compile(r'(?i)sk-[a-z0-9]{32}'), 'openai_key'),
]

def ssh_audit():
    """Audit SSH configuration and access."""
    audit = {'config': {}, 'authorized_keys': [], 'recent_logins': []}
    
    ssh_config = Path('/etc/ssh/sshd_config')
    if ssh_config.exists():
        try:
            with open(ssh_config) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if 'PermitRootLogin' in line:
                            audit['config']['permit_root_login'] = line.split()[1]
                        if 'PasswordAuthentication' in line:
                            audit['config']['password_auth'] = line.split()[1]
                        if 'PubkeyAuthentication' in line:
                            audit['config']['pubkey_auth'] = line.split()[1]
        except OSError:
            pass
    
    auth_keys = Path.home() / '.ssh' / 'authorized_keys'
    if auth_keys.exists():
        try:
            with open(auth_keys) as f:
                for i, line in enumerate(f, 1):
                    if line.strip() and not line.startswith('#'):
                        key_type = line.split()[0] if line.split() else 'unknown'
                        audit['authorized_keys'].append({'line': i, 'type': key_type})
        except OSError:
            pass
    
    if shutil.which('last'):
        try:
            result = subprocess.run(['last', '-n', '10'], capture_output=True, text=True, timeout=10)
            for line in result.stdout.splitlines()[:10]:
                if line and not line.startswith('wtmp'):
                    parts = line.split()
                    if len(parts) >= 3:
                        audit['recent_logins'].append({
                            'user': parts[0],
                            'tty': parts[1],
                            'from': parts[2] if len(parts) > 2 else 'unknown',
                            'time': ' '.join(parts[3:]) if len(parts) > 3 else ''
                        })
        except subprocess.TimeoutExpired:
            pass
    
    return audit

def scan_secrets(path='.', max_files=1000):
    """Scan files for potential secrets and credentials."""
    secrets_found = []
    scanned = 0
    
    for item in Path(path).expanduser().rglob('*'):
        if scanned >= max_files:
            break
        if not item.is_file() or item.is_symlink():
            continue
        
        try:
            with open(item, 'r', errors='ignore') as f:
                content = f.read(10000)
                for pattern, secret_type in SECRET_PATTERNS:
                    match = pattern.search(content)
                    if match:
                        secrets_found.append({
                            'path': str(item),
                            'type': secret_type,
                            'line': content[:match.start()].count('\n') + 1,
                            'context': content[max(0, match.start()-50):match.end()+50]
                        })
                        break
        except (OSError, UnicodeError):
            pass
        scanned += 1
    
    return {'scanned_files': scanned, 'secrets_found': secrets_found, 'count': len(secrets_found)}

def find_suid_sgid():
    """Find files with SUID or SGID bits set."""
    if os.geteuid() != 0:
        raise PermissionError('Finding SUID/SGID files requires root privileges')
    
    suid_files = []
    sgid_files = []
    
    for root, dirs, files in os.walk('/', topdown=True):
        dirs[:] = [d for d in dirs if not d.startswith(('.', 'proc', 'sys', 'dev'))]
        
        for name in files + dirs:
            full_path = Path(root) / name
            try:
                mode = full_path.stat().st_mode
                if mode & 0o4000:
                    suid_files.append(str(full_path))
                if mode & 0o2000:
                    sgid_files.append(str(full_path))
            except OSError:
                pass
    
    return {'suid': suid_files, 'sgid': sgid_files, 'suid_count': len(suid_files), 'sgid_count': len(sgid_files)}

def check_rootkits():
    """Basic rootkit detection using chkrootkit or rkhunter if available."""
    findings = []
    
    if shutil.which('chkrootkit'):
        try:
            result = subprocess.run(['chkrootkit'], capture_output=True, text=True, timeout=120)
            for line in result.stdout.splitlines():
                if 'INFECTED' in line or 'WARNING' in line:
                    findings.append({'tool': 'chkrootkit', 'line': line})
        except subprocess.TimeoutExpired:
            findings.append({'tool': 'chkrootkit', 'error': 'timeout'})
    
    if shutil.which('rkhunter'):
        try:
            result = subprocess.run(['rkhunter', '--check', '--skip-keypress'], 
                                  capture_output=True, text=True, timeout=300)
            for line in result.stdout.splitlines():
                if 'Warning' in line or 'Found' in line:
                    findings.append({'tool': 'rkhunter', 'line': line})
        except subprocess.TimeoutExpired:
            findings.append({'tool': 'rkhunter', 'error': 'timeout'})
    
    return {'findings': findings, 'count': len(findings)}

def certificate_info(cert_path):
    """Extract information from X.509 certificates."""
    if not shutil.which('openssl'):
        raise FileNotFoundError('openssl is not available')
    
    p = Path(cert_path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f'Certificate file not found: {p}')
    
    cmd = ['openssl', 'x509', '-in', str(p), '-text', '-noout']
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    
    info = {'path': str(p), 'valid': False}
    
    for line in result.stdout.splitlines():
        if 'Subject:' in line:
            info['subject'] = line.split(':', 1)[1].strip()
        elif 'Issuer:' in line:
            info['issuer'] = line.split(':', 1)[1].strip()
        elif 'Not Before:' in line:
            info['not_before'] = line.split(':', 1)[1].strip()
        elif 'Not After:' in line:
            info['not_after'] = line.split(':', 1)[1].strip()
        elif 'DNS:' in line:
            info.setdefault('dns_names', []).append(line.split(':')[1].strip())
    
    if 'subject' in info:
        info['valid'] = True
    
    return info

def list_certificates(path='/etc/ssl/certs'):
    """List all certificates in a directory."""
    cert_dir = Path(path).expanduser()
    if not cert_dir.exists():
        raise FileNotFoundError(f'Certificate directory not found: {cert_dir}')
    
    certs = []
    for item in cert_dir.rglob('*.pem'):
        if item.is_file():
            try:
                info = certificate_info(item)
                certs.append(info)
            except Exception:
                pass
    
    return {'directory': str(cert_dir), 'certificates': certs, 'count': len(certs)}

def basic_sast(path='.', max_files=500):
    """Static Application Security Testing for common vulnerabilities."""
    vulnerabilities = []
    
    dangerous_functions = [
        (re.compile(r'eval\s*\('), 'eval_usage'),
        (re.compile(r'exec\s*\('), 'exec_usage'),
        (re.compile(r'system\s*\('), 'system_call'),
        (re.compile(r'subprocess\.call\s*\('), 'subprocess_call'),
        (re.compile(r'os\.system\s*\('), 'os_system'),
        (re.compile(r'pickle\.loads?\s*\('), 'pickle_deserialize'),
        (re.compile(r'shell\s*=\s*True'), 'shell_true'),
    ]
    
    scanned = 0
    for item in Path(path).expanduser().rglob('*.py'):
        if scanned >= max_files:
            break
        if not item.is_file():
            continue
        
        try:
            with open(item, 'r', errors='ignore') as f:
                content = f.read()
                for pattern, vuln_type in dangerous_functions:
                    match = pattern.search(content)
                    if match:
                        vulnerabilities.append({
                            'path': str(item),
                            'type': vuln_type,
                            'line': content[:match.start()].count('\n') + 1
                        })
                        break
        except OSError:
            pass
        scanned += 1
    
    return {'scanned_files': scanned, 'vulnerabilities': vulnerabilities, 'count': len(vulnerabilities)}

def forensic_timeline(days=7):
    """Generate a basic forensic timeline of system events."""
    timeline = []
    since = datetime.now().timestamp() - (days * 86400)
    
    if shutil.which('journalctl'):
        try:
            cmd = ['journalctl', '--since', f'{days} days ago', '--no-pager', '-o', 'json']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            for line in result.stdout.splitlines():
                try:
                    import json
                    entry = json.loads(line)
                    timestamp = entry.get('__REALTIME_TIMESTAMP')
                    if timestamp and float(timestamp) >= since:
                        timeline.append({
                            'timestamp': datetime.fromtimestamp(float(timestamp)).isoformat(),
                            'message': entry.get('MESSAGE', '')[:200],
                            'priority': entry.get('PRIORITY', 'info')
                        })
                except (json.JSONDecodeError, ValueError, KeyError):
                    pass
        except subprocess.TimeoutExpired:
            pass
    
    return {'days': days, 'events': timeline[:1000], 'count': len(timeline)}

def file_integrity_check(path='.', algorithm='sha256'):
    """Calculate file hashes for integrity checking."""
    import hashlib
    
    hashes = {}
    p = Path(path).expanduser()
    
    for item in p.rglob('*'):
        if not item.is_file() or item.is_symlink():
            continue
        
        try:
            h = hashlib.new(algorithm)
            with item.open('rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    h.update(chunk)
            hashes[str(item)] = h.hexdigest()
        except OSError:
            pass
    
    return {'path': str(p), 'algorithm': algorithm, 'files': len(hashes), 'hashes': hashes}
