"""Bounded process inspection and carefully targeted termination."""
import os, signal, time, subprocess, shutil
from pathlib import Path
def listing():
    rows=[]
    for p in Path('/proc').iterdir():
        if p.name.isdigit():
            try: rows.append({'pid':int(p.name),'name':(p/'comm').read_text().strip()})
            except OSError:pass
    return rows
def memory_top(limit=10):
    page_size=os.sysconf('SC_PAGE_SIZE');rows=[]
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():continue
        try:
            fields=(process/'statm').read_text().split()
            name=(process/'comm').read_text().strip()
            rss=int(fields[1])*page_size
            rows.append({'pid':int(process.name),'name':name,'rss_mib':round(rss/(1024**2),1)})
        except (OSError,ValueError,IndexError):continue
    return sorted(rows,key=lambda row:row['rss_mib'],reverse=True)[:max(1,min(int(limit),100))]
def inspect(pid):
    p=Path('/proc')/str(int(pid));return {'pid':int(pid),'name':(p/'comm').read_text().strip(),'status':(p/'status').read_text()[:10000]}
def terminate(pid,force=False):
    pid=int(pid)
    if pid<=1 or pid==os.getpid():raise ValueError('Refusing to terminate a protected process')
    os.kill(pid,signal.SIGKILL if force else signal.SIGTERM);return {'pid':pid,'signal':'KILL' if force else 'TERM'}

def cpu_top(limit=10, duration_seconds=1):
    """Monitor CPU usage in real-time."""
    if not shutil.which('top'):
        raise FileNotFoundError('top command is not available')
    
    cmd = ['top', '-b', '-n', str(duration_seconds + 1), '-d', '1']
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration_seconds + 10)
    
    processes = []
    for line in result.stdout.splitlines():
        if line and not line.startswith(('top', '%Cpu', 'Tasks', 'Mem', 'Swap')):
            parts = line.split()
            if len(parts) >= 12 and parts[0].isdigit():
                try:
                    processes.append({
                        'pid': int(parts[0]),
                        'user': parts[1],
                        'cpu_percent': float(parts[8]),
                        'mem_percent': float(parts[9]),
                        'command': ' '.join(parts[11:])
                    })
                except (ValueError, IndexError):
                    continue
    
    return sorted(processes, key=lambda x: x['cpu_percent'], reverse=True)[:limit]

def io_top(limit=10):
    """Monitor I/O usage using iotop if available."""
    if not shutil.which('iotop'):
        raise FileNotFoundError('iotop is not installed. Install with: sudo apt install iotop')
    
    if os.geteuid() != 0:
        raise PermissionError('iotop requires root privileges')
    
    cmd = ['iotop', '-b', '-n', '1', '-o']
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    
    processes = []
    for line in result.stdout.splitlines():
        if line and not line.startswith(('TOTAL', 'TID', 'TIME')):
            parts = line.split()
            if len(parts) >= 12:
                try:
                    processes.append({
                        'pid': int(parts[0]) if parts[0].isdigit() else None,
                        'io_read_kbs': float(parts[3]),
                        'io_write_kbs': float(parts[4]),
                        'command': ' '.join(parts[11:])
                    })
                except (ValueError, IndexError):
                    continue
    
    return sorted(processes, key=lambda x: (x.get('io_read_kbs', 0) + x.get('io_write_kbs', 0)), reverse=True)[:limit]

def process_temperatures():
    """Get process-related temperature information."""
    temps = {'cpu': [], 'gpu': [], 'other': []}
    
    if shutil.which('sensors'):
        try:
            result = subprocess.run(['sensors'], capture_output=True, text=True, timeout=5)
            current_sensor = None
            for line in result.stdout.splitlines():
                if line.startswith(('Core', 'CPU', 'Package')):
                    current_sensor = 'cpu'
                elif line.startswith(('GPU', 'NVIDIA', 'AMD')):
                    current_sensor = 'gpu'
                elif line.strip() == '':
                    current_sensor = 'other'
                
                if '°C' in line:
                    try:
                        temp_str = line.split('°C')[0].split()[-1]
                        temp = float(temp_str.replace('+', ''))
                        if current_sensor:
                            temps[current_sensor].append({'sensor': line.split(':')[0].strip(), 'celsius': temp})
                    except (ValueError, IndexError):
                        pass
        except subprocess.TimeoutExpired:
            pass
    
    for sensor_path in ['/sys/class/thermal', '/sys/class/hwmon']:
        try:
            for sensor in Path(sensor_path).iterdir():
                temp_file = sensor / 'temp1_input'
                if temp_file.exists():
                    temp_millidegrees = int(temp_file.read_text().strip())
                    temps['other'].append({'sensor': sensor.name, 'celsius': temp_millidegrees / 1000})
        except (OSError, ValueError):
            pass
    
    return temps

def detailed_inspect(pid):
    """Detailed process inspection including CPU, memory, and I/O stats."""
    p = Path('/proc') / str(int(pid))
    if not p.exists():
        raise FileNotFoundError(f'Process {pid} does not exist')
    
    info = {'pid': int(pid), 'name': (p / 'comm').read_text().strip()}
    
    try:
        with open(p / 'status') as f:
            status_lines = f.readlines()
        for line in status_lines:
            if line.startswith('State:'):
                info['state'] = line.split(':')[1].strip()
            elif line.startswith('Threads:'):
                info['threads'] = int(line.split(':')[1].strip())
            elif line.startswith('Uid:'):
                info['uid'] = int(line.split(':',1)[1].split()[0])
            elif line.startswith('Gid:'):
                info['gid'] = int(line.split(':',1)[1].split()[0])
    except OSError:
        pass
    
    try:
        with open(p / 'stat') as f:
            stat = f.read().split()
        info['utime'] = int(stat[13])
        info['stime'] = int(stat[14])
        info['cutime'] = int(stat[15])
        info['cstime'] = int(stat[16])
    except (OSError, IndexError):
        pass
    
    try:
        with open(p / 'statm') as f:
            statm = f.read().split()
        page_size = os.sysconf('SC_PAGE_SIZE')
        info['rss_pages'] = int(statm[1])
        info['rss_bytes'] = info['rss_pages'] * page_size
        info['rss_mib'] = round(info['rss_bytes'] / (1024**2), 2)
    except (OSError, IndexError):
        pass
    
    try:
        with open(p / 'io') as f:
            io_lines = f.readlines()
        for line in io_lines:
            if line.startswith('read_bytes:'):
                info['read_bytes'] = int(line.split()[1])
            elif line.startswith('write_bytes:'):
                info['write_bytes'] = int(line.split()[1])
    except OSError:
        pass
    
    try:
        info['cmdline'] = (p / 'cmdline').read_text().replace('\x00', ' ').strip()
    except OSError:
        pass
    
    return info

"""Ampliación de processes.py: búsqueda, árbol, recursos por proceso y control seguro.

Pega al final de tu processes.py (incluye sus imports) o importa con
``from .processes_extra import *``. Registra EXTRA_OPERATIONS como ``processes.<nombre>``.
"""
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

PROTECTED_NAMES = {'systemd', 'init', 'kthreadd', 'dbus-daemon', 'sshd', 'login', 'Xorg', 'Xwayland', 'gdm', 'gdm3',
                   'lightdm', 'sddm', 'gnome-shell', 'plasmashell', 'NetworkManager', 'systemd-logind', 'polkitd'}
SIGNALS = {'term': signal.SIGTERM, 'kill': signal.SIGKILL, 'hup': signal.SIGHUP, 'int': signal.SIGINT,
           'stop': signal.SIGSTOP, 'cont': signal.SIGCONT, 'usr1': signal.SIGUSR1, 'usr2': signal.SIGUSR2, 'quit': signal.SIGQUIT}
_STATES = {'R': 'running', 'S': 'sleeping', 'D': 'disk-wait', 'Z': 'zombie', 'T': 'stopped', 't': 'tracing', 'I': 'idle'}


def _read(path, default=''):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return default


def _proc(pid):
    pid = int(pid)
    if pid <= 0:
        raise ValueError('PID no válido')
    if not Path(f'/proc/{pid}').exists():
        raise ProcessLookupError(f'El proceso {pid} no existe')
    return Path(f'/proc/{pid}')


def _stat(pid):
    """Campos de /proc/<pid>/stat: (nombre, estado, ppid, nice, hilos, inicio_ticks, utime, stime)."""
    text = _read(f'/proc/{pid}/stat')
    head, _, tail = text.rpartition(')')
    f = tail.split()
    return {'name': head.partition('(')[2], 'state': f[0], 'ppid': int(f[1]), 'utime': int(f[11]), 'stime': int(f[12]),
            'nice': int(f[16]), 'threads': int(f[17]), 'start_ticks': int(f[19])}


def _owner(pid):
    m = re.search(r'^Uid:\s+(\d+)', _read(f'/proc/{pid}/status'), re.M)
    uid = int(m.group(1)) if m else -1
    try:
        import pwd
        return pwd.getpwuid(uid).pw_name
    except (ImportError, KeyError):
        return str(uid)


def _all_pids():
    return sorted(int(p.name) for p in Path('/proc').iterdir() if p.name.isdigit())


def _row(pid):
    st = _stat(pid)
    cmd = _read(f'/proc/{pid}/cmdline').replace('\x00', ' ').strip() or f"[{st['name']}]"
    return {'pid': pid, 'name': st['name'], 'user': _owner(pid), 'state': _STATES.get(st['state'], st['state']), 'cmd': cmd[:120]}


# ----------------------------------------------------------- búsqueda
def find_by_name(name, exact=False):
    needle = str(name).strip().lower()
    if not needle:
        raise ValueError('Indica el nombre del proceso')
    rows = []
    for pid in _all_pids():
        try:
            st = _stat(pid)
            cmd = _read(f'/proc/{pid}/cmdline').replace('\x00', ' ').lower()
            hit = st['name'].lower() == needle if exact else needle in st['name'].lower() or needle in cmd.split(' ')[0]
            if hit and pid != os.getpid():
                rows.append(_row(pid))
        except (OSError, ValueError, IndexError):
            continue
    return {'query': name, 'count': len(rows), 'running': bool(rows), 'processes': rows[:50]}


def is_running(name):
    result = find_by_name(name)
    return {'name': name, 'running': result['running'], 'instances': result['count']}


def by_user(user, limit=40):
    rows = [r for r in (_safe_row(p) for p in _all_pids()) if r and r['user'] == str(user)]
    return {'user': user, 'count': len(rows), 'processes': rows[:max(1, min(int(limit), 200))]}


def _safe_row(pid):
    try:
        return _row(pid)
    except (OSError, ValueError, IndexError):
        return None


def count():
    states = {}
    for pid in _all_pids():
        try:
            s = _STATES.get(_stat(pid)['state'], 'other')
            states[s] = states.get(s, 0) + 1
        except (OSError, ValueError, IndexError):
            continue
    return {'total': sum(states.values()), 'by_state': states}


def zombies():
    rows = [r for r in (_safe_row(p) for p in _all_pids()) if r and r['state'] == 'zombie']
    return {'count': len(rows), 'processes': rows}


def stopped():
    rows = [r for r in (_safe_row(p) for p in _all_pids()) if r and r['state'] == 'stopped']
    return {'count': len(rows), 'processes': rows}


# ----------------------------------------------------------- árbol y familia
def children(pid):
    _proc(pid)
    kids = []
    for p in _all_pids():
        try:
            if _stat(p)['ppid'] == int(pid):
                kids.append(_row(p))
        except (OSError, ValueError, IndexError):
            continue
    return {'parent': int(pid), 'children': kids}


def parents(pid):
    chain, current = [], int(pid)
    while current > 0 and len(chain) < 30:
        _proc(current)
        chain.append(_row(current))
        current = _stat(current)['ppid']
    return {'chain': chain}


def tree(limit=80):
    if shutil.which('pstree'):
        p = subprocess.run(['pstree', '-p', '-a', '-l'], capture_output=True, text=True, timeout=10)
        return p.stdout.splitlines()[:max(1, min(int(limit), 300))]
    p = subprocess.run(['ps', '-eo', 'pid,ppid,comm', '--forest'], capture_output=True, text=True, timeout=10)
    return p.stdout.splitlines()[:max(1, min(int(limit), 300))]


# ----------------------------------------------------------- recursos
def cpu_hogs(limit=10, interval=1.0):
    """Top por CPU medido de verdad durante `interval` s, sin depender de top."""
    interval = max(0.2, min(float(interval), 5))
    ticks = os.sysconf('SC_CLK_TCK')
    def snap():
        d = {}
        for pid in _all_pids():
            try:
                st = _stat(pid)
                d[pid] = (st['utime'] + st['stime'], st['name'])
            except (OSError, ValueError, IndexError):
                continue
        return d
    a = snap(); time.sleep(interval); b = snap()
    rows = [{'pid': p, 'name': b[p][1], 'cpu_percent': round(100 * (b[p][0] - a[p][0]) / ticks / interval, 1)} for p in b if p in a]
    return sorted(rows, key=lambda r: r['cpu_percent'], reverse=True)[:max(1, min(int(limit), 100))]


def memory_detail(pid):
    p = _proc(pid)
    smaps = _read(p / 'smaps_rollup')
    def kib(key):
        m = re.search(rf'^{key}:\s+(\d+)', smaps, re.M)
        return round(int(m.group(1)) / 1024, 1) if m else None
    return {'pid': int(pid), 'name': _stat(pid)['name'], 'rss_mib': kib('Rss'), 'pss_mib': kib('Pss'),
            'private_mib': round((kib('Private_Dirty') or 0) + (kib('Private_Clean') or 0), 1), 'swap_mib': kib('Swap')}


def top_threads(limit=10):
    rows = []
    for pid in _all_pids():
        try:
            st = _stat(pid)
            rows.append({'pid': pid, 'name': st['name'], 'threads': st['threads']})
        except (OSError, ValueError, IndexError):
            continue
    return sorted(rows, key=lambda r: r['threads'], reverse=True)[:max(1, min(int(limit), 100))]


def open_files(pid, limit=40):
    p = _proc(pid)
    files = []
    try:
        for fd in sorted((p / 'fd').iterdir(), key=lambda x: int(x.name))[:max(1, min(int(limit), 200))]:
            try:
                files.append({'fd': int(fd.name), 'target': os.readlink(fd)})
            except OSError:
                continue
        total = len(list((p / 'fd').iterdir()))
    except PermissionError:
        return {'pid': int(pid), 'error': 'Sin permisos para ver los descriptores (prueba con sudo)'}
    return {'pid': int(pid), 'total': total, 'files': files}


def connections_of(pid):
    p = _proc(pid)
    try:
        inodes = {os.readlink(fd).split('[')[1].rstrip(']') for fd in (p / 'fd').iterdir() if os.readlink(fd).startswith('socket:')}
    except PermissionError:
        return {'pid': int(pid), 'error': 'Sin permisos para ver los sockets (prueba con sudo)'}
    rows = []
    for fam in ('tcp', 'tcp6', 'udp', 'udp6'):
        for line in _read(f'/proc/net/{fam}').splitlines()[1:]:
            f = line.split()
            if len(f) > 9 and f[9] in inodes:
                rows.append({'protocol': fam, 'local': _hex_addr(f[1]), 'remote': _hex_addr(f[2]), 'state': f[3]})
    return {'pid': int(pid), 'sockets': rows}


def _hex_addr(value):
    import socket
    import struct
    host, port = value.split(':')
    try:
        ip = socket.inet_ntoa(struct.pack('<I', int(host, 16))) if len(host) == 8 else f'[{host}]'
    except (OSError, ValueError):
        ip = host
    return f'{ip}:{int(port, 16)}'


def limits_of(pid):
    return _read(_proc(pid) / 'limits').splitlines()


def details(pid):
    """Ficha completa de un proceso: dueño, ruta, carpeta, argumentos, arranque, prioridad."""
    p = _proc(pid)
    st = _stat(pid)
    hz = os.sysconf('SC_CLK_TCK')
    try:
        uptime = float(_read('/proc/uptime').split()[0])
        running_for = round(uptime - st['start_ticks'] / hz)
    except (ValueError, IndexError):
        running_for = None
    def link(name):
        try:
            return os.readlink(p / name)
        except OSError:
            return None
    return {'pid': int(pid), 'name': st['name'], 'user': _owner(pid), 'state': _STATES.get(st['state'], st['state']),
            'ppid': st['ppid'], 'threads': st['threads'], 'nice': st['nice'], 'running_for_s': running_for,
            'exe': link('exe'), 'cwd': link('cwd'), 'cmdline': _read(p / 'cmdline').replace('\x00', ' ').strip(),
            'oom_score': _read(p / 'oom_score')}


def by_port(port):
    port = int(port)
    hex_port = f'{port:04X}'
    inodes = set()
    for fam in ('tcp', 'tcp6', 'udp', 'udp6'):
        for line in _read(f'/proc/net/{fam}').splitlines()[1:]:
            f = line.split()
            if len(f) > 9 and f[1].endswith(':' + hex_port):
                inodes.add(f[9])
    owners = []
    for pid in _all_pids():
        try:
            for fd in Path(f'/proc/{pid}/fd').iterdir():
                target = os.readlink(fd)
                if target.startswith('socket:[') and target[8:-1] in inodes:
                    owners.append(_row(pid)); break
        except OSError:
            continue
    return {'port': port, 'processes': owners, 'note': None if owners else 'Nadie visible usa ese puerto (puede requerir sudo para ver procesos de otros usuarios)'}


# ----------------------------------------------------------- control seguro
def _guard(pid):
    pid = int(pid)
    if pid <= 1 or pid == os.getpid() or pid == os.getppid():
        raise ValueError('Rechazo actuar sobre un proceso protegido (init, este asistente o su padre)')
    _proc(pid)
    name = _stat(pid)['name']
    if name in PROTECTED_NAMES:
        raise ValueError(f'«{name}» es un proceso crítico del sistema; no lo toco desde el asistente')
    return pid


def send_signal(pid, sig='term'):
    sig = str(sig).lower().removeprefix('sig')
    if sig not in SIGNALS:
        raise ValueError('Señal no permitida. Usa: ' + ', '.join(sorted(SIGNALS)))
    pid = _guard(pid)
    os.kill(pid, SIGNALS[sig])
    return {'pid': pid, 'signal': sig.upper()}


def suspend(pid):
    return send_signal(pid, 'stop')


def resume(pid):
    return send_signal(pid, 'cont')


def renice(pid, nice):
    pid = _guard(pid)
    nice = int(nice)
    if not -20 <= nice <= 19:
        raise ValueError('La prioridad (nice) va de -20 a 19')
    if nice < 0 and os.geteuid() != 0:
        raise PermissionError('Subir la prioridad por encima de 0 requiere root')
    os.setpriority(os.PRIO_PROCESS, pid, nice)
    return {'pid': pid, 'nice': nice}


def terminate_by_name(name, force=False, exact=True, max_matches=10):
    """Termina todos los procesos con ese nombre; se niega si coinciden demasiados."""
    name = str(name).strip()
    if not name or name in PROTECTED_NAMES:
        raise ValueError('Nombre no permitido')
    found = find_by_name(name, exact=exact)['processes']
    found = [r for r in found if r['pid'] not in (os.getpid(), os.getppid())]
    if not found:
        return {'name': name, 'terminated': [], 'note': 'No hay procesos con ese nombre'}
    if len(found) > int(max_matches):
        raise ValueError(f'Coinciden {len(found)} procesos; sé más específico o usa el PID')
    done, failed = [], []
    for r in found:
        try:
            os.kill(r['pid'], signal.SIGKILL if force else signal.SIGTERM)
            done.append(r['pid'])
        except OSError as exc:
            failed.append({'pid': r['pid'], 'error': str(exc)})
    return {'name': name, 'terminated': done, 'failed': failed, 'signal': 'KILL' if force else 'TERM'}


EXTRA_OPERATIONS = {
    'find_by_name': find_by_name, 'is_running': is_running, 'by_user': by_user, 'count': count, 'zombies': zombies,
    'stopped': stopped, 'children': children, 'parents': parents, 'tree': tree, 'cpu_hogs': cpu_hogs,
    'memory_detail': memory_detail, 'top_threads': top_threads, 'open_files': open_files, 'connections_of': connections_of,
    'limits_of': limits_of, 'details': details, 'by_port': by_port, 'send_signal': send_signal, 'suspend': suspend,
    'resume': resume, 'renice': renice, 'terminate_by_name': terminate_by_name,
}