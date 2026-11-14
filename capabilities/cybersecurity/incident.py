"""Incident response helpers: containment and evidence collection (authorized use)."""
import ipaddress
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def _valid_ip(value):
    try:
        return str(ipaddress.ip_address(str(value).strip()))
    except ValueError:
        raise ValueError(f'IP no válida: {value!r}')


def _sudo_run(cmd, timeout=30):
    import os
    if not (hasattr(os, 'geteuid') and os.geteuid() != 0) or not shutil.which('sudo'):
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if subprocess.run(['sudo', '-n', 'true'], capture_output=True).returncode == 0:
        return subprocess.run(['sudo', *cmd], capture_output=True, text=True, timeout=timeout)
    import getpass
    try:
        password = getpass.getpass('[sudo] Contraseña: ')
    except (EOFError, KeyboardInterrupt):
        password = ''
    return subprocess.run(['sudo', '-S', *cmd], input=password + '\n',
                          capture_output=True, text=True, timeout=timeout)


def block_ip(ip, permanent=True):
    """Block an attacking IP with the host firewall (ufw or firewalld)."""
    target = _valid_ip(ip)
    if shutil.which('ufw'):
        rule = ['ufw', 'deny', 'from', target]
        if permanent:
            rule.append('comment')
            rule.append('clibot-block')
        p = _sudo_run(rule, timeout=30)
        if p.returncode == 0:
            return {'blocked': target, 'firewall': 'ufw', 'permanent': permanent,
                    'note': 'Regla deny añadida. Recuerda habilitar ufw si no está activo.'}
        raise RuntimeError(p.stderr.strip() or 'ufw deny falló')
    if shutil.which('firewall-cmd'):
        p = _sudo_run(['firewall-cmd', '--permanent', '--add-rich-rule',
                       f'rule family=ipv4 source address={target} drop'], timeout=30)
        if p.returncode == 0:
            _sudo_run(['firewall-cmd', '--reload'], timeout=15)
            return {'blocked': target, 'firewall': 'firewalld', 'permanent': True}
        raise RuntimeError(p.stderr.strip() or 'firewall-cmd falló')
    if shutil.which('iptables'):
        p = _sudo_run(['iptables', '-A', 'INPUT', '-s', target, '-j', 'DROP'], timeout=15)
        if p.returncode == 0:
            return {'blocked': target, 'firewall': 'iptables', 'permanent': False,
                    'note': 'Regla temporal; persístela con iptables-save o netfilter-persistent.'}
        raise RuntimeError(p.stderr.strip() or 'iptables falló')
    raise FileNotFoundError('No hay firewall disponible (ufw, firewalld o iptables)')


def unblock_ip(ip):
    """Remove a previously added block for an IP."""
    target = _valid_ip(ip)
    if shutil.which('ufw'):
        p = _sudo_run(['ufw', 'delete', 'deny', 'from', target], timeout=30)
        if p.returncode == 0:
            return {'unblocked': target, 'firewall': 'ufw'}
        raise RuntimeError(p.stderr.strip() or 'ufw delete falló')
    if shutil.which('firewall-cmd'):
        p = _sudo_run(['firewall-cmd', '--permanent', '--remove-rich-rule',
                       f'rule family=ipv4 source address={target} drop'], timeout=30)
        if p.returncode == 0:
            _sudo_run(['firewall-cmd', '--reload'], timeout=15)
            return {'unblocked': target, 'firewall': 'firewalld'}
        raise RuntimeError(p.stderr.strip() or 'firewall-cmd falló')
    if shutil.which('iptables'):
        p = _sudo_run(['iptables', '-D', 'INPUT', '-s', target, '-j', 'DROP'], timeout=15)
        if p.returncode == 0:
            return {'unblocked': target, 'firewall': 'iptables'}
        raise RuntimeError(p.stderr.strip() or 'iptables falló')
    raise FileNotFoundError('No hay firewall disponible')


def collect_evidence(output_dir, hours=24):
    """Gather logs and system state into a directory for post-incident analysis."""
    hours = max(1, min(int(hours), 24 * 30))
    dest = Path(output_dir).expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    case_dir = dest / f'case_{stamp}'
    case_dir.mkdir()
    collected = []

    def _dump(name, cmd, timeout=30):
        exe = shutil.which(cmd[0])
        if not exe:
            return
        try:
            p = subprocess.run([exe, *cmd[1:]], capture_output=True, text=True, timeout=timeout)
            (case_dir / name).write_text(p.stdout + '\n--- STDERR ---\n' + p.stderr, errors='replace')
            collected.append(name)
        except (OSError, subprocess.SubprocessError):
            pass

    _dump('auth.log.tail', ['tail', '-n', '5000', '/var/log/auth.log'])
    _dump('syslog.tail', ['tail', '-n', '5000', '/var/log/syslog'])
    _dump('journal_errors.log', ['journalctl', '-p', 'err', '--since', f'{hours} hours ago', '--no-pager'])
    _dump('journal_ssh.log', ['journalctl', '-u', 'ssh', '-u', 'sshd', '--since', f'{hours} hours ago', '--no-pager'])
    _dump('listening_ports.txt', ['ss', '-tulnp'])
    _dump('processes.txt', ['ps', 'auxww'])
    _dump('logged_users.txt', ['last', '-n', '50'])
    _dump('failed_logins.txt', ['journalctl', '--since', f'{hours} hours ago', '--no-pager', '-o', 'cat'])
    (case_dir / 'metadata.txt').write_text(
        f'Collected: {datetime.now(timezone.utc).isoformat()}\nWindow: last {hours}h\nHost: {os.uname().nodename}\n')
    collected.append('metadata.txt')
    return {'path': str(case_dir), 'files': collected, 'window_hours': hours,
            'next_steps': 'Revisa auth.log y journal_ssh.log para la línea temporal; correlaciona IPs con '
                          'failed_logins y listening_ports; documenta en un informe con severidad.'}
