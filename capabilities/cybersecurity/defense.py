"""Defensive security posture checks: firewall, logins, updates, exposure."""
import os
import re
import shutil
import subprocess
from pathlib import Path


def _run(cmd, timeout=15):
    exe = shutil.which(cmd[0])
    if not exe:
        return None
    try:
        return subprocess.run([exe, *cmd[1:]], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


def firewall_status():
    """Report which host firewall is active (ufw, firewalld, nftables, iptables)."""
    status = {'firewalls': {}, 'active': False}
    if shutil.which('ufw'):
        p = _run(['ufw', 'status'])
        active = bool(p and 'Status: active' in p.stdout)
        status['firewalls']['ufw'] = {'active': active,
                                      'rules': [l for l in (p.stdout.splitlines() if p else []) if l.strip()][:40]}
        status['active'] = status['active'] or active
    if shutil.which('firewall-cmd'):
        p = _run(['firewall-cmd', '--state'])
        active = bool(p and 'running' in p.stdout.lower())
        status['firewalls']['firewalld'] = {'active': active}
        status['active'] = status['active'] or active
    if shutil.which('nft'):
        p = _run(['nft', 'list', 'ruleset'])
        has_rules = bool(p and p.stdout.strip() and 'table' in p.stdout)
        status['firewalls']['nftables'] = {'active': has_rules}
        status['active'] = status['active'] or has_rules
    if shutil.which('iptables'):
        p = _run(['iptables', '-L', '-n', '--line-numbers'])
        status['firewalls']['iptables'] = {'active': bool(p and p.stdout.strip())}
    return status


def failed_logins(hours=24):
    """Count failed authentication attempts from the journal/auth log."""
    hours = max(1, min(int(hours), 24 * 30))
    attempts = {}
    sources = []
    if shutil.which('journalctl'):
        p = _run(['journalctl', '-u', 'ssh', '-u', 'sshd', '--since', f'{hours} hours ago',
                  '--no-pager', '-o', 'cat'], timeout=30)
        if p:
            sources.append('journalctl')
            for line in p.stdout.splitlines():
                m = re.search(r'Failed password for .* from ([0-9a-fA-F.:]+)', line)
                if m:
                    ip = m.group(1)
                    attempts[ip] = attempts.get(ip, 0) + 1
    auth_log = Path('/var/log/auth.log')
    if auth_log.exists():
        sources.append('auth.log')
        try:
            p = _run(['grep', '-E', r'Failed password|authentication failure', str(auth_log)], timeout=20)
            if p:
                for line in p.stdout.splitlines():
                    m = re.search(r'from ([0-9a-fA-F.:]+)', line)
                    if m:
                        ip = m.group(1)
                        attempts[ip] = attempts.get(ip, 0) + 1
        except Exception:
            pass
    ranked = sorted(attempts.items(), key=lambda kv: -kv[1])[:20]
    return {'window_hours': hours, 'sources': sources,
            'total_attempts': sum(attempts.values()),
            'unique_sources': len(attempts),
            'top_attackers': [{'ip': ip, 'attempts': n} for ip, n in ranked],
            'recommendation': ('Hay fuerza bruta activa: considera fail2ban y deshabilitar PasswordAuthentication '
                               'en SSH si no la necesitas.' if attempts else 'Sin intentos fallidos recientes detectados.')}


def pending_updates():
    """Count packages with pending security-relevant updates."""
    result = {'upgradable': None, 'security_updates': None, 'note': ''}
    if shutil.which('apt'):
        p = _run(['apt', 'list', '--upgradable'], timeout=30)
        if p:
            lines = [l for l in p.stdout.splitlines() if '/' in l and 'Listing' not in l]
            result['upgradable'] = len(lines)
            result['note'] = 'Paquetes desactualizados pueden contener vulnerabilidades conocidas; aplica parches con regularidad.'
    if shutil.which('dnf'):
        p = _run(['dnf', 'check-update', '--security'], timeout=30)
        if p:
            result['security_updates'] = max(0, len(p.stdout.splitlines()) - 1)
    if shutil.which('zypper'):
        p = _run(['zypper', '-n', 'list-updates', '--security'], timeout=30)
        if p:
            result['security_updates'] = len([l for l in p.stdout.splitlines() if l.strip() and not l.startswith('Loading')])
    return result


def exposed_services():
    """List listening TCP/UDP sockets and flag services exposed beyond localhost."""
    services = []
    exe = shutil.which('ss') or shutil.which('netstat')
    if not exe:
        return {'available': False, 'services': [], 'exposed': []}
    args = ['-tulnp'] if exe.endswith('ss') else ['-tulnp']
    p = _run([exe, *args], timeout=15)
    if not p:
        return {'available': False, 'services': [], 'exposed': []}
    exposed = []
    for line in p.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 5:
            continue
        local = parts[4] if exe.endswith('ss') else parts[3]
        if ':' not in local:
            continue
        addr, port = local.rsplit(':', 1)
        try:
            port = int(port)
        except ValueError:
            continue
        wildcard = addr in ('*', '0.0.0.0', '::', '[::]') or addr == ''
        name = parts[-1].strip('"') if parts else ''
        entry = {'address': addr or '*', 'port': port, 'process': name, 'exposed': wildcard}
        services.append(entry)
        if wildcard and port not in (22,):
            exposed.append(entry)
    return {'available': True, 'services': services[:200], 'exposed': exposed[:50],
            'note': 'Servicios en 0.0.0.0/* escuchan en todas las interfaces; revisa si deben ser públicos.'}


def password_policy():
    """Read local password-aging and quality settings."""
    policy = {}
    login_defs = Path('/etc/login.defs')
    if login_defs.exists():
        try:
            for line in login_defs.read_text(errors='replace').splitlines():
                line = line.strip()
                if line.startswith('#') or not line:
                    continue
                for key in ('PASS_MAX_DAYS', 'PASS_MIN_DAYS', 'PASS_MIN_LEN', 'PASS_WARN_AGE'):
                    if line.startswith(key):
                        policy[key.lower()] = line.split()[1]
        except OSError:
            pass
    pwquality = Path('/etc/security/pwquality.conf')
    if pwquality.exists():
        try:
            for line in pwquality.read_text(errors='replace').splitlines():
                line = line.strip()
                if line and not line.startswith(('#', ';')) and '=' in line:
                    k, v = line.split('=', 1)
                    policy[f'pwquality.{k.strip()}'] = v.strip()
        except OSError:
            pass
    policy['recommendation'] = ('PASS_MAX_DAYS alto o ausente permite contraseñas eternas; '
                                'PASS_MIN_LEN < 12 es débil; activa pwquality con minlen>=12, dcredit y ucredit.')
    return policy


def ssh_exposure():
    """Check whether SSH is reachable from the network and how it is configured."""
    result = {'listening': [], 'config': {}, 'warnings': []}
    p = _run(['ss', '-tlnp'], timeout=10) if shutil.which('ss') else None
    if p:
        for line in p.stdout.splitlines():
            if ':22' in line and ('ssh' in line or 'sshd' in line):
                result['listening'].append(line.strip()[:200])
    config = Path('/etc/ssh/sshd_config')
    if config.exists():
        try:
            for line in config.read_text(errors='replace').splitlines():
                line = line.strip()
                if line.startswith('#') or not line:
                    continue
                for key in ('PermitRootLogin', 'PasswordAuthentication', 'PubkeyAuthentication',
                            'Port', 'AllowUsers', 'MaxAuthTries'):
                    if line.lower().startswith(key.lower()):
                        result['config'][key] = line.split(None, 1)[1] if len(line.split(None, 1)) > 1 else ''
        except OSError:
            pass
    if result['config'].get('PermitRootLogin', 'prohibit-password').lower() in ('yes', 'without-password'):
        result['warnings'].append('PermitRootLogin permite root por SSH; usa claves y desactícalo si no es imprescindible.')
    if result['config'].get('PasswordAuthentication', 'yes').lower() == 'yes':
        result['warnings'].append('PasswordAuthentication yes expone SSH a fuerza bruta; prefiere claves.')
    if not result['listening']:
        result['warnings'].append('No se detectó sshd escuchando; verifica si el servicio está activo.')
    return result


def tools_status():
    """Availability of common authorized-security tools on this host."""
    tools = ['nmap', 'nikto', 'sqlmap', 'msfconsole', 'lynis', 'fail2ban-client',
             'ufw', 'firewall-cmd', 'tcpdump', 'tshark', 'openscap', 'ssh-audit',
             'chkrootkit', 'rkhunter', 'wpscan', 'hydra', 'john', 'hashcat', 'gobuster', 'dirb']
    return {tool: {'available': bool(shutil.which(tool)), 'path': shutil.which(tool)} for tool in tools}
