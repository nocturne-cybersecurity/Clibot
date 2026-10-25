"""Package manager discovery and read-only package queries."""
import shutil, subprocess, os
MANAGERS=('apt','dnf','pacman','zypper')
def manager():return next((x for x in MANAGERS if shutil.which(x)),None)
def installed(name):
    m=manager()
    if not m:raise FileNotFoundError('No supported package manager found')
    if m=='apt':args=['dpkg-query','-W','-f=${Status}',name]
    elif m=='dnf':args=['rpm','-q',name]
    elif m=='pacman':args=['pacman','-Q',name]
    else:args=['rpm','-q',name]
    p=subprocess.run(args,capture_output=True,text=True,timeout=10);return {'installed':p.returncode==0,'details':p.stdout.strip()}
def search(query):
    m=manager()
    if not m:raise FileNotFoundError('No supported package manager found')
    args={'apt':['apt-cache','search',query],'dnf':['dnf','search',query],'pacman':['pacman','-Ss',query],'zypper':['zypper','search',query]}[m]
    if not shutil.which(args[0]):raise FileNotFoundError(f'{args[0]} is unavailable')
    return subprocess.run(args,capture_output=True,text=True,timeout=20).stdout[:20000]

def install(package_names, assume_yes=False):
    """Install packages (requires root)."""
    if os.geteuid() != 0:
        raise PermissionError('Package installation requires root privileges')
    
    m = manager()
    if not m:
        raise FileNotFoundError('No supported package manager found')
    
    if isinstance(package_names, str):
        package_names = [package_names]
    
    cmd_map = {
        'apt': ['apt-get', 'install', '-y'] if assume_yes else ['apt-get', 'install'],
        'dnf': ['dnf', 'install', '-y'] if assume_yes else ['dnf', 'install'],
        'pacman': ['pacman', '-S', '--noconfirm'] if assume_yes else ['pacman', '-S'],
        'zypper': ['zypper', 'install', '-y'] if assume_yes else ['zypper', 'install']
    }
    
    cmd = cmd_map[m] + package_names
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    
    return {
        'packages': package_names,
        'exit_code': result.returncode,
        'stdout': result.stdout,
        'stderr': result.stderr,
        'success': result.returncode == 0
    }

def remove(package_names, purge=False, assume_yes=False):
    """Remove packages (requires root)."""
    if os.geteuid() != 0:
        raise PermissionError('Package removal requires root privileges')
    
    m = manager()
    if not m:
        raise FileNotFoundError('No supported package manager found')
    
    if isinstance(package_names, str):
        package_names = [package_names]
    
    cmd_map = {
        'apt': ['apt-get', 'remove', '-y'] if assume_yes else ['apt-get', 'remove'],
        'dnf': ['dnf', 'remove', '-y'] if assume_yes else ['dnf', 'remove'],
        'pacman': ['pacman', '-R', '--noconfirm'] if assume_yes else ['pacman', '-R'],
        'zypper': ['zypper', 'remove', '-y'] if assume_yes else ['zypper', 'remove']
    }
    
    if purge and m == 'apt':
        cmd_map['apt'] = ['apt-get', 'purge', '-y'] if assume_yes else ['apt-get', 'purge']
    
    cmd = cmd_map[m] + package_names
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    
    return {
        'packages': package_names,
        'exit_code': result.returncode,
        'stdout': result.stdout,
        'stderr': result.stderr,
        'success': result.returncode == 0
    }

def update():
    """Update package lists (requires root)."""
    if os.geteuid() != 0:
        raise PermissionError('Package update requires root privileges')
    
    m = manager()
    if not m:
        raise FileNotFoundError('No supported package manager found')
    
    cmd_map = {
        'apt': ['apt-get', 'update'],
        'dnf': ['dnf', 'makecache'],
        'pacman': ['pacman', '-Sy'],
        'zypper': ['zypper', 'refresh']
    }
    
    cmd = cmd_map[m]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    
    return {
        'manager': m,
        'exit_code': result.returncode,
        'stdout': result.stdout,
        'stderr': result.stderr,
        'success': result.returncode == 0
    }

def upgrade(assume_yes=False):
    """Upgrade all packages (requires root)."""
    if os.geteuid() != 0:
        raise PermissionError('Package upgrade requires root privileges')
    
    m = manager()
    if not m:
        raise FileNotFoundError('No supported package manager found')
    
    cmd_map = {
        'apt': ['apt-get', 'upgrade', '-y'] if assume_yes else ['apt-get', 'upgrade'],
        'dnf': ['dnf', 'upgrade', '-y'] if assume_yes else ['dnf', 'upgrade'],
        'pacman': ['pacman', '-Syu', '--noconfirm'] if assume_yes else ['pacman', '-Syu'],
        'zypper': ['zypper', 'dup', '-y'] if assume_yes else ['zypper', 'dup']
    }
    
    cmd = cmd_map[m]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    
    return {
        'manager': m,
        'exit_code': result.returncode,
        'stdout': result.stdout,
        'stderr': result.stderr,
        'success': result.returncode == 0
    }

def security_audit():
    """Check for security updates."""
    m = manager()
    if not m:
        raise FileNotFoundError('No supported package manager found')
    
    if m == 'apt':
        if shutil.which('apt-list'):
            cmd = ['apt-list', '--security']
        else:
            cmd = ['apt-get', 'upgrade', '-s']
    elif m == 'dnf':
        cmd = ['dnf', 'updateinfo', 'list', 'security']
    elif m == 'pacman':
        cmd = ['pacman', '-Qu']
    else:
        cmd = ['zypper', 'list-updates', '--type', 'security']
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    
    return {
        'manager': m,
        'exit_code': result.returncode,
        'output': result.stdout,
        'has_security_updates': 'security' in result.stdout.lower() or result.returncode != 0
    }

def list_cron_jobs(user=None):
    """List cron jobs for a user or all users (requires root for all users)."""
    if user:
        if user != 'current' and os.geteuid() != 0:
            raise PermissionError('Listing other users cron jobs requires root privileges')
        
        if user == 'current':
            user = os.getlogin()
        
        cmd = ['crontab', '-l', '-u', user]
    else:
        if os.geteuid() != 0:
            raise PermissionError('Listing all cron jobs requires root privileges')
        cmd = ['crontab', '-l']
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    
    jobs = []
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            if line and not line.startswith('#'):
                jobs.append(line)
    
    return {
        'user': user or 'all',
        'jobs': jobs,
        'count': len(jobs),
        'raw_output': result.stdout
    }

def add_cron_job(cron_expression, command, user=None):
    """Add a cron job (requires root for other users)."""
    if user and user != 'current' and os.geteuid() != 0:
        raise PermissionError('Adding cron jobs for other users requires root privileges')
    
    if user == 'current':
        user = os.getlogin()
    
    existing_jobs = list_cron_jobs(user or 'current')
    new_crontab = existing_jobs['raw_output'] + f'\n{cron_expression} {command}\n'
    
    if user:
        cmd = ['crontab', '-u', user, '-']
    else:
        cmd = ['crontab', '-']
    
    result = subprocess.run(cmd, input=new_crontab, capture_output=True, text=True, timeout=10)
    
    return {
        'expression': cron_expression,
        'command': command,
        'user': user or 'current',
        'success': result.returncode == 0,
        'output': result.stdout,
        'error': result.stderr
    }

def list_installed():
    """List all installed packages."""
    m = manager()
    if not m:
        raise FileNotFoundError('No supported package manager found')
    
    cmd_map = {
        'apt': ['dpkg-query', '-W', '-f=${Package}\t${Version}\n'],
        'dnf': ['rpm', '-qa', '--queryformat', '%{NAME}\t%{VERSION}\n'],
        'pacman': ['pacman', '-Q'],
        'zypper': ['rpm', '-qa', '--queryformat', '%{NAME}\t%{VERSION}\n']
    }
    
    cmd = cmd_map[m]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    
    packages = []
    for line in result.stdout.splitlines():
        parts = line.split('\t')
        if len(parts) >= 2:
            packages.append({'name': parts[0], 'version': parts[1]})
    
    return {
        'manager': m,
        'packages': packages,
        'count': len(packages)
    }
