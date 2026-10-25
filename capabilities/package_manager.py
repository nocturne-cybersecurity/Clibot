"""Package management operations for apt, pip, npm, and other package managers."""
import subprocess
import shutil
from pathlib import Path


def _check_command(cmd):
    """Check if a command is available."""
    return shutil.which(cmd) is not None


def apt_search(query):
    """Search for packages using apt."""
    if not _check_command('apt'):
        raise FileNotFoundError('apt command not found')
    result = subprocess.run(['apt', 'search', query], capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return {'results': result.stdout, 'count': result.stdout.count('\n')}


def apt_install(packages, assume_yes=False):
    """Install packages using apt."""
    if not _check_command('apt'):
        raise FileNotFoundError('apt command not found')
    cmd = ['apt', 'install']
    if assume_yes:
        cmd.append('-y')
    cmd.extend(packages if isinstance(packages, list) else [packages])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return {'success': result.returncode == 0, 'stdout': result.stdout, 'stderr': result.stderr, 'packages': packages}


def apt_remove(packages, assume_yes=False):
    """Remove packages using apt."""
    if not _check_command('apt'):
        raise FileNotFoundError('apt command not found')
    cmd = ['apt', 'remove']
    if assume_yes:
        cmd.append('-y')
    cmd.extend(packages if isinstance(packages, list) else [packages])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return {'success': result.returncode == 0, 'stdout': result.stdout, 'stderr': result.stderr, 'packages': packages}


def apt_update():
    """Update package lists using apt."""
    if not _check_command('apt'):
        raise FileNotFoundError('apt command not found')
    result = subprocess.run(['apt', 'update'], capture_output=True, text=True, timeout=300)
    return {'success': result.returncode == 0, 'stdout': result.stdout, 'stderr': result.stderr}


def apt_upgrade(assume_yes=False):
    """Upgrade packages using apt."""
    if not _check_command('apt'):
        raise FileNotFoundError('apt command not found')
    cmd = ['apt', 'upgrade']
    if assume_yes:
        cmd.append('-y')
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return {'success': result.returncode == 0, 'stdout': result.stdout, 'stderr': result.stderr}


def pip_search(query):
    """Search for packages using pip."""
    if not _check_command('pip'):
        raise FileNotFoundError('pip command not found')
    result = subprocess.run(['pip', 'search', query], capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return {'results': result.stdout, 'count': result.stdout.count('\n')}


def pip_install(packages, user=False, upgrade=False):
    """Install packages using pip."""
    if not _check_command('pip'):
        raise FileNotFoundError('pip command not found')
    cmd = ['pip', 'install']
    if user:
        cmd.append('--user')
    if upgrade:
        cmd.append('--upgrade')
    cmd.extend(packages if isinstance(packages, list) else [packages])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return {'success': result.returncode == 0, 'stdout': result.stdout, 'stderr': result.stderr, 'packages': packages}


def pip_uninstall(packages, assume_yes=False):
    """Uninstall packages using pip."""
    if not _check_command('pip'):
        raise FileNotFoundError('pip command not found')
    cmd = ['pip', 'uninstall']
    if assume_yes:
        cmd.append('-y')
    cmd.extend(packages if isinstance(packages, list) else [packages])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return {'success': result.returncode == 0, 'stdout': result.stdout, 'stderr': result.stderr, 'packages': packages}


def pip_list(outdated=False):
    """List installed packages using pip."""
    if not _check_command('pip'):
        raise FileNotFoundError('pip command not found')
    cmd = ['pip', 'list']
    if outdated:
        cmd.append('--outdated')
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return {'success': result.returncode == 0, 'stdout': result.stdout, 'stderr': result.stderr}


def npm_search(query):
    """Search for packages using npm."""
    if not _check_command('npm'):
        raise FileNotFoundError('npm command not found')
    result = subprocess.run(['npm', 'search', query], capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return {'results': result.stdout, 'count': result.stdout.count('\n')}


def npm_install(packages, global_=False, save=False):
    """Install packages using npm."""
    if not _check_command('npm'):
        raise FileNotFoundError('npm command not found')
    cmd = ['npm', 'install']
    if global_:
        cmd.append('-g')
    if save:
        cmd.append('--save')
    cmd.extend(packages if isinstance(packages, list) else [packages])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return {'success': result.returncode == 0, 'stdout': result.stdout, 'stderr': result.stderr, 'packages': packages}


def npm_uninstall(packages, global_=False):
    """Uninstall packages using npm."""
    if not _check_command('npm'):
        raise FileNotFoundError('npm command not found')
    cmd = ['npm', 'uninstall']
    if global_:
        cmd.append('-g')
    cmd.extend(packages if isinstance(packages, list) else [packages])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return {'success': result.returncode == 0, 'stdout': result.stdout, 'stderr': result.stderr, 'packages': packages}


def npm_list(global_=False):
    """List installed packages using npm."""
    if not _check_command('npm'):
        raise FileNotFoundError('npm command not found')
    cmd = ['npm', 'list']
    if global_:
        cmd.append('-g')
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return {'success': result.returncode == 0, 'stdout': result.stdout, 'stderr': result.stderr}
