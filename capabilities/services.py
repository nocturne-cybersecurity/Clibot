"""systemd service inspection and explicitly requested changes."""
import os
import re
import shutil
import subprocess

# Nombres equivalentes entre distribuciones: el primero que exista en systemd se usa.
ALIAS_GROUPS = [
    ('apache2', 'httpd', 'apache'), ('mysql', 'mysqld', 'mariadb'), ('mariadb', 'mysql', 'mysqld'),
    ('redis', 'redis-server', 'valkey'), ('ssh', 'sshd'), ('sshd', 'ssh'), ('postgresql', 'postgres'),
    ('mongod', 'mongodb'), ('cron', 'crond'), ('crond', 'cron'), ('docker', 'docker.socket'),
    ('smbd', 'smb', 'samba'), ('nmbd', 'nmb'), ('nfs-server', 'nfs-kernel-server'),
    ('tomcat', 'tomcat9', 'tomcat10', 'tomcat8'), ('bind9', 'named'), ('named', 'bind9'),
    ('ntp', 'ntpd', 'chrony', 'chronyd', 'systemd-timesyncd'), ('gdm', 'gdm3'), ('gdm3', 'gdm'),
    ('php-fpm', 'php8.4-fpm', 'php8.3-fpm', 'php8.2-fpm', 'php8.1-fpm', 'php8.0-fpm', 'php7.4-fpm'),
    ('firewalld', 'ufw'), ('networkmanager', 'NetworkManager'), ('grafana', 'grafana-server'),
    ('rabbitmq', 'rabbitmq-server'), ('exim', 'exim4'), ('dhcpd', 'isc-dhcp-server'),
]
ACTIONS = {'start', 'stop', 'restart', 'reload', 'reload-or-restart', 'try-restart', 'enable', 'disable',
           'enable-now', 'disable-now', 'mask', 'unmask', 'reset-failed'}
_NAME = re.compile(r'^[A-Za-z0-9@._:\-]+$')


def _clean(name):
    name = str(name).strip()
    if not _NAME.match(name) or name.startswith('-'):
        raise ValueError(f'Nombre de servicio no válido: {name!r}')
    return name


def _systemctl(args, sudo=False, timeout=20):
    exe = shutil.which('systemctl')
    if not exe:
        raise FileNotFoundError('systemctl is unavailable on this system')
    cmd = [exe, *args]
    if sudo and os.geteuid() != 0 and shutil.which('sudo'):
        cmd = ['sudo', '-n', *cmd]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return {'exit_code': p.returncode, 'stdout': p.stdout.strip(), 'stderr': p.stderr.strip()}


def _text(args, timeout=20):
    result = _systemctl(args, timeout=timeout)
    return result['stdout'] or result['stderr']


def resolve_unit(name):
    """Devuelve el nombre real de la unidad probando alias de otras distribuciones."""
    name = _clean(name).removesuffix('.service')
    candidates = [name]
    for group in ALIAS_GROUPS:
        if name.lower() in (g.lower() for g in group):
            candidates += list(group)
    seen = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        out = _systemctl(['list-unit-files', f'{cand}.service', '--no-legend', '--no-pager'])['stdout']
        if out.strip():
            return cand
    return name


# ====================================================================
# Funciones originales
# ====================================================================
def status(name):
    return _systemctl(['status', resolve_unit(name), '--no-pager'])


def list_services():
    return _systemctl(['list-units', '--type=service', '--no-pager', '--no-legend'])


def logs(name, lines=50):
    exe = shutil.which('journalctl')
    if not exe:
        raise FileNotFoundError('journalctl is unavailable')
    p = subprocess.run([exe, '-u', resolve_unit(name), '-n', str(max(1, min(int(lines), 500))), '--no-pager'],
                       capture_output=True, text=True, timeout=20)
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip() or f'journalctl exited {p.returncode}')
    return p.stdout


def change(name, action):
    """start/stop/restart/reload/enable/disable/... con reintento por sudo -n si hace falta."""
    if action not in ACTIONS:
        raise ValueError('Unsupported service action')
    unit = resolve_unit(name)
    args = {'enable-now': ['enable', '--now'], 'disable-now': ['disable', '--now']}.get(action, [action])
    result = _systemctl([*args, unit], sudo=True)
    result.update({'unit': unit, 'action': action})
    if result['exit_code'] and re.search(r'authentication|permission|denied|password', result['stderr'], re.I):
        result['hint'] = 'Necesitas permisos: ejecuta el bot con sudo o configura sudo sin contraseña para systemctl.'
    elif result['exit_code'] == 0 and action in {'start', 'restart', 'enable-now'}:
        result['active'] = is_active(unit)['state']
    return result


# ====================================================================
# Consultas nuevas
# ====================================================================
def is_active(name):
    unit = resolve_unit(name)
    state = _systemctl(['is-active', unit])['stdout'] or 'unknown'
    return {'unit': unit, 'state': state, 'running': state == 'active'}


def is_enabled(name):
    unit = resolve_unit(name)
    state = _systemctl(['is-enabled', unit])['stdout'] or 'unknown'
    return {'unit': unit, 'state': state, 'starts_on_boot': state in {'enabled', 'enabled-runtime', 'static', 'alias'}}


def exists(name):
    unit = resolve_unit(name)
    out = _systemctl(['list-unit-files', f'{unit}.service', '--no-legend', '--no-pager'])['stdout']
    return {'unit': unit, 'exists': bool(out.strip())}


def find_service(pattern):
    pattern = re.sub(r'[^A-Za-z0-9@._:\-*]', '', str(pattern))[:60]
    if not pattern:
        raise ValueError('Indica parte del nombre del servicio')
    out = _systemctl(['list-unit-files', '--type=service', '--no-legend', '--no-pager'])['stdout']
    rows = [l.split()[:2] for l in out.splitlines() if pattern.lower().replace('*', '') in l.lower()]
    return [{'unit': u, 'file_state': s} for u, s in rows[:50]]


def list_running():
    out = _systemctl(['list-units', '--type=service', '--state=running', '--no-legend', '--no-pager'])['stdout']
    return [{'unit': l.split()[0], 'description': ' '.join(l.split()[4:])} for l in out.splitlines() if l.strip()]


def list_enabled():
    out = _systemctl(['list-unit-files', '--type=service', '--state=enabled', '--no-legend', '--no-pager'])['stdout']
    return [l.split()[0] for l in out.splitlines() if l.strip()]


def list_failed():
    out = _systemctl(['list-units', '--type=service', '--state=failed', '--no-legend', '--no-pager'])['stdout']
    return [l.lstrip('●* ').split()[0] for l in out.splitlines() if l.strip()] or ['No hay servicios fallidos']


def show_properties(name, props=None):
    unit = resolve_unit(name)
    wanted = props or ['Description', 'ActiveState', 'SubState', 'MainPID', 'ExecMainStartTimestamp', 'MemoryCurrent',
                       'CPUUsageNSec', 'TasksCurrent', 'Restart', 'NRestarts', 'FragmentPath', 'User', 'UnitFileState']
    args = ['show', unit, '--no-pager'] + [f'--property={p}' for p in wanted if re.fullmatch(r'\w+', p)]
    out = _systemctl(args)['stdout']
    return dict(l.split('=', 1) for l in out.splitlines() if '=' in l)


def resource_usage(name):
    info = show_properties(name, ['MainPID', 'MemoryCurrent', 'CPUUsageNSec', 'TasksCurrent', 'ActiveState'])
    mem = info.get('MemoryCurrent', '')
    cpu = info.get('CPUUsageNSec', '')
    return {'unit': resolve_unit(name), 'state': info.get('ActiveState'), 'pid': info.get('MainPID'),
            'memory_mib': round(int(mem) / 1024 ** 2, 1) if mem.isdigit() else None,
            'cpu_seconds': round(int(cpu) / 1e9, 1) if cpu.isdigit() else None, 'tasks': info.get('TasksCurrent')}


def dependencies(name, reverse=False):
    args = ['list-dependencies', resolve_unit(name), '--no-pager', '--plain']
    if reverse:
        args.append('--reverse')
    return _text(args).splitlines()[:80]


def unit_file(name):
    result = _systemctl(['cat', resolve_unit(name), '--no-pager'])
    if result['exit_code']:
        raise RuntimeError(result['stderr'] or 'No pude leer el archivo de unidad')
    return result['stdout'][:12000]


def list_timers():
    return _text(['list-timers', '--all', '--no-pager']).splitlines()


def list_sockets():
    return _text(['list-sockets', '--all', '--no-pager']).splitlines()[:80]


def boot_blame(limit=15):
    exe = shutil.which('systemd-analyze')
    if not exe:
        raise FileNotFoundError('systemd-analyze is not available')
    p = subprocess.run([exe, 'blame', '--no-pager'], capture_output=True, text=True, timeout=20)
    return p.stdout.splitlines()[:max(1, min(int(limit), 100))]


def logs_since(name, since='1 hour ago', priority=None, lines=100):
    exe = shutil.which('journalctl')
    if not exe:
        raise FileNotFoundError('journalctl is unavailable')
    if not re.fullmatch(r'[\w :\-+]+', since):
        raise ValueError('Formato de fecha no válido')
    cmd = [exe, '-u', resolve_unit(name), '--since', since, '-n', str(max(1, min(int(lines), 500))), '--no-pager']
    if priority in {'emerg', 'alert', 'crit', 'err', 'warning', 'notice', 'info', 'debug'}:
        cmd += ['-p', priority]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    return p.stdout.splitlines()


def summary(name):
    """Todo lo importante de un servicio en una sola respuesta."""
    unit = resolve_unit(name)
    return {'active': is_active(unit), 'enabled': is_enabled(unit), 'resources': resource_usage(unit),
            'recent_logs': logs(unit, 8).splitlines()}


def ensure_running(name):
    """Arranca el servicio solo si no está activo."""
    current = is_active(name)
    if current['running']:
        return {**current, 'changed': False}
    return {**change(name, 'start'), 'changed': True}


def restart_failed():
    """Reinicia todos los servicios que estén en estado failed."""
    failed = [u for u in list_failed() if u.endswith('.service')]
    return [{'unit': u, 'exit_code': change(u, 'restart')['exit_code']} for u in failed[:20]]


def reload_daemon():
    return _systemctl(['daemon-reload'], sudo=True)


EXTRA_OPERATIONS = {
    'is_active': is_active, 'is_enabled': is_enabled, 'exists': exists, 'find_service': find_service,
    'list_running': list_running, 'list_enabled': list_enabled, 'list_failed': list_failed,
    'show_properties': show_properties, 'resource_usage': resource_usage, 'dependencies': dependencies,
    'unit_file': unit_file, 'list_timers': list_timers, 'list_sockets': list_sockets, 'boot_blame': boot_blame,
    'logs_since': logs_since, 'summary': summary, 'ensure_running': ensure_running,
    'restart_failed': restart_failed, 'reload_daemon': reload_daemon,
}