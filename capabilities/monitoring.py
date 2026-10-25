"""Real-time system monitoring capabilities."""
import glob
import os
import re
import shutil
import subprocess
import time
from pathlib import Path


# ====================================================================
# Funciones originales (sin cambios)
# ====================================================================
def get_process_stats(limit=10):
    """Get process statistics sorted by CPU or memory usage."""
    try:
        result = subprocess.run(['ps', 'aux', '--sort=-%cpu'], capture_output=True, text=True, timeout=5)
        lines = result.stdout.split('\n')[1:limit+1]
        processes = []
        for line in lines:
            if not line.strip():
                continue
            parts = line.split(None, 10)
            if len(parts) >= 11:
                processes.append({
                    'user': parts[0], 'pid': parts[1], 'cpu': parts[2], 'mem': parts[3],
                    'vsz': parts[4], 'rss': parts[5], 'stat': parts[7], 'command': parts[10][:50]
                })
        return {'processes': processes, 'sort_by': 'cpu'}
    except Exception as e:
        return {'error': str(e)}


def get_memory_stats():
    """Get detailed memory statistics."""
    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = {}
            for line in f:
                parts = line.split(':')
                if len(parts) == 2:
                    meminfo[parts[0].strip()] = parts[1].strip().split()[0]
        return meminfo
    except Exception as e:
        return {'error': str(e)}


def get_cpu_stats():
    """Get CPU statistics."""
    try:
        with open('/proc/stat', 'r') as f:
            lines = f.readlines()
        parts = lines[0].split()
        return {'user': parts[1], 'nice': parts[2], 'system': parts[3], 'idle': parts[4],
                'iowait': parts[5] if len(parts) > 5 else '0'}
    except Exception as e:
        return {'error': str(e)}


def get_disk_stats():
    """Get disk usage statistics."""
    try:
        result = subprocess.run(['df', '-h'], capture_output=True, text=True, timeout=5)
        disks = []
        for line in result.stdout.split('\n')[1:]:
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 6:
                disks.append({'filesystem': parts[0], 'size': parts[1], 'used': parts[2],
                              'available': parts[3], 'use_percent': parts[4], 'mounted_on': parts[5]})
        return {'disks': disks}
    except Exception as e:
        return {'error': str(e)}


def get_network_stats():
    """Get network interface statistics."""
    try:
        with open('/proc/net/dev', 'r') as f:
            lines = f.readlines()[2:]
        interfaces = {}
        for line in lines:
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 17:
                interfaces[parts[0].rstrip(':')] = {'rx_bytes': parts[1], 'rx_packets': parts[2],
                                                    'tx_bytes': parts[9], 'tx_packets': parts[10]}
        return {'interfaces': interfaces}
    except Exception as e:
        return {'error': str(e)}


def get_system_load():
    """Get system load averages."""
    try:
        with open('/proc/loadavg', 'r') as f:
            parts = f.read().split()
        return {'1min': parts[0], '5min': parts[1], '15min': parts[2],
                'running': parts[3].split('/')[0], 'total': parts[3].split('/')[1]}
    except Exception as e:
        return {'error': str(e)}


# ====================================================================
# Utilidades internas
# ====================================================================
def _read(path, default=''):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return default


def _run(args, timeout=8):
    exe = shutil.which(args[0])
    if not exe:
        raise FileNotFoundError(f"Falta la utilidad '{args[0]}'")
    p = subprocess.run([exe, *map(str, args[1:])], capture_output=True, text=True, timeout=timeout)
    return p.stdout.strip()


def _clamp(value, low, high):
    return max(low, min(float(value), high))


def _safe(fn):
    """Los monitores devuelven {'error': ...} en lugar de lanzar, como los originales."""
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - se informa al usuario
            return {'error': str(exc)}
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


def _cpu_times():
    rows = {}
    for line in _read('/proc/stat').splitlines():
        if line.startswith('cpu'):
            parts = line.split()
            values = list(map(int, parts[1:9]))
            rows[parts[0]] = (sum(values), values[3] + values[4], values[4])
    return rows


def _net_counters():
    rows = {}
    for line in _read('/proc/net/dev').splitlines()[2:]:
        name, _, rest = line.partition(':')
        p = rest.split()
        if len(p) >= 16:
            rows[name.strip()] = {'rx': int(p[0]), 'rx_pkts': int(p[1]), 'rx_err': int(p[2]), 'rx_drop': int(p[3]),
                                  'tx': int(p[8]), 'tx_pkts': int(p[9]), 'tx_err': int(p[10]), 'tx_drop': int(p[11])}
    return rows


def _diskstats():
    rows = {}
    for line in _read('/proc/diskstats').splitlines():
        p = line.split()
        if len(p) < 14 or re.match(r'(loop|ram|zram|dm-)', p[2]):
            continue
        if re.search(r'\d+$', p[2]) and not re.match(r'(nvme\d+n\d+|mmcblk\d+)$', p[2]):
            continue  # particiones: nos quedamos con el disco completo
        rows[p[2]] = (int(p[5]), int(p[9]), int(p[12]))  # sectores leídos, escritos, ms de E/S
    return rows


# ====================================================================
# CPU
# ====================================================================
@_safe
def get_cpu_usage(interval=1.0):
    """Porcentaje de uso total y por núcleo medido durante `interval` segundos."""
    interval = _clamp(interval, 0.2, 5)
    a = _cpu_times(); time.sleep(interval); b = _cpu_times()
    out = {}
    for name in b:
        total = b[name][0] - a[name][0]
        busy = total - (b[name][1] - a[name][1])
        out[name] = round(100 * busy / total, 1) if total else 0.0
    return {'total_percent': out.pop('cpu', 0.0), 'per_core': out, 'interval_s': interval}


@_safe
def get_iowait(interval=1.0):
    interval = _clamp(interval, 0.2, 5)
    a = _cpu_times()['cpu']; time.sleep(interval); b = _cpu_times()['cpu']
    total = b[0] - a[0]
    return {'iowait_percent': round(100 * (b[2] - a[2]) / total, 1) if total else 0.0}


@_safe
def get_load_vs_cores():
    one, five, fifteen = os.getloadavg()
    cores = os.cpu_count() or 1
    ratio = one / cores
    return {'load': [round(one, 2), round(five, 2), round(fifteen, 2)], 'cores': cores,
            'load_per_core': round(ratio, 2), 'state': 'high' if ratio > 1.5 else 'elevated' if ratio > 0.9 else 'normal'}


@_safe
def get_context_switches(interval=1.0):
    interval = _clamp(interval, 0.2, 5)
    def read():
        d = {}
        for line in _read('/proc/stat').splitlines():
            if line.startswith(('ctxt', 'intr', 'processes')):
                k, v = line.split()[:2]
                d[k] = int(v)
        return d
    a = read(); time.sleep(interval); b = read()
    return {'context_switches_per_s': round((b['ctxt'] - a['ctxt']) / interval),
            'interrupts_per_s': round((b['intr'] - a['intr']) / interval),
            'forks_per_s': round((b['processes'] - a['processes']) / interval, 1)}


@_safe
def get_pressure():
    """Pressure Stall Information (PSI): cuánto esperan las tareas por CPU, memoria o E/S."""
    out = {}
    for res in ('cpu', 'memory', 'io'):
        text = _read(f'/proc/pressure/{res}')
        if text:
            out[res] = {line.split()[0]: dict(kv.split('=') for kv in line.split()[1:]) for line in text.splitlines()}
    return out or {'available': False, 'reason': 'El kernel no expone /proc/pressure (PSI)'}


# ====================================================================
# Memoria
# ====================================================================
@_safe
def get_memory_usage():
    m = {}
    for line in _read('/proc/meminfo').splitlines():
        k, _, v = line.partition(':')
        try:
            m[k] = int(v.split()[0]) / 1024  # MiB
        except (ValueError, IndexError):
            pass
    total, avail = m['MemTotal'], m['MemAvailable']
    swap_t, swap_f = m.get('SwapTotal', 0), m.get('SwapFree', 0)
    return {'total_mib': round(total), 'available_mib': round(avail), 'used_percent': round(100 * (total - avail) / total, 1),
            'swap_total_mib': round(swap_t), 'swap_used_percent': round(100 * (swap_t - swap_f) / swap_t, 1) if swap_t else 0.0,
            'dirty_mib': round(m.get('Dirty', 0), 1), 'slab_mib': round(m.get('Slab', 0))}


@_safe
def get_vmstat():
    keys = ('pswpin', 'pswpout', 'pgfault', 'pgmajfault', 'oom_kill', 'pgscan_kswapd', 'pgscan_direct')
    d = dict(l.split() for l in _read('/proc/vmstat').splitlines() if len(l.split()) == 2)
    return {k: int(d[k]) for k in keys if k in d}


@_safe
def get_memory_by_user(limit=10):
    totals = {}
    for line in _run(['ps', '-eo', 'user:20,rss']).splitlines()[1:]:
        parts = line.split()
        if len(parts) == 2 and parts[1].isdigit():
            totals[parts[0]] = totals.get(parts[0], 0) + int(parts[1])
    rows = [{'user': u, 'rss_mib': round(kb / 1024, 1)} for u, kb in totals.items()]
    return sorted(rows, key=lambda r: r['rss_mib'], reverse=True)[:int(_clamp(limit, 1, 50))]


@_safe
def get_swap_by_process(limit=10):
    rows = []
    for status in glob.glob('/proc/[0-9]*/status'):
        text = _read(status)
        name = re.search(r'^Name:\s+(.+)$', text, re.M)
        swap = re.search(r'^VmSwap:\s+(\d+)', text, re.M)
        if name and swap and int(swap.group(1)) > 0:
            rows.append({'pid': int(status.split('/')[2]), 'name': name.group(1), 'swap_mib': round(int(swap.group(1)) / 1024, 1)})
    return sorted(rows, key=lambda r: r['swap_mib'], reverse=True)[:int(_clamp(limit, 1, 50))]


@_safe
def get_oom_events(limit=20):
    """Muertes por falta de memoria (OOM killer) en el log del kernel."""
    try:
        text = _run(['journalctl', '-k', '--no-pager', '-n', '2000', '--output=short-iso'], timeout=15)
    except FileNotFoundError:
        text = _run(['dmesg'], timeout=10)
    hits = [l for l in text.splitlines() if re.search(r'out of memory|oom-kill|killed process', l, re.I)]
    return {'events': hits[-int(_clamp(limit, 1, 100)):], 'count': len(hits)}


# ====================================================================
# Procesos
# ====================================================================
def _ps_top(sort, limit):
    cols = 'pid,user:16,%cpu,%mem,rss,etime,stat,comm'
    out = _run(['ps', '-eo', cols, f'--sort=-{sort}']).splitlines()[1:int(_clamp(limit, 1, 100)) + 1]
    rows = []
    for line in out:
        p = line.split(None, 7)
        if len(p) == 8:
            rows.append({'pid': int(p[0]), 'user': p[1], 'cpu': float(p[2]), 'mem': float(p[3]),
                         'rss_mib': round(int(p[4]) / 1024, 1), 'elapsed': p[5], 'state': p[6], 'command': p[7]})
    return rows


@_safe
def get_top_cpu(limit=10):
    return _ps_top('%cpu', limit)


@_safe
def get_top_memory(limit=10):
    return _ps_top('rss', limit)


@_safe
def get_process_states():
    counts = {}
    for stat in glob.glob('/proc/[0-9]*/stat'):
        text = _read(stat)
        match = re.search(r'\)\s+(\w)', text)
        if match:
            counts[match.group(1)] = counts.get(match.group(1), 0) + 1
    names = {'R': 'running', 'S': 'sleeping', 'D': 'disk_wait', 'Z': 'zombie', 'T': 'stopped', 'I': 'idle', 't': 'tracing'}
    return {'total': sum(counts.values()), 'by_state': {names.get(k, k): v for k, v in sorted(counts.items())}}


@_safe
def get_zombies():
    rows = []
    for line in _run(['ps', '-eo', 'pid,ppid,stat,comm']).splitlines()[1:]:
        p = line.split(None, 3)
        if len(p) == 4 and p[2].startswith('Z'):
            rows.append({'pid': int(p[0]), 'ppid': int(p[1]), 'command': p[3]})
    return {'zombies': rows, 'count': len(rows)}


@_safe
def get_file_descriptors():
    allocated, _, maximum = _read('/proc/sys/fs/file-nr').split()
    return {'allocated': int(allocated), 'max': int(maximum), 'used_percent': round(100 * int(allocated) / int(maximum), 2)}


# ====================================================================
# Disco
# ====================================================================
@_safe
def get_disk_io(interval=1.0):
    interval = _clamp(interval, 0.2, 5)
    a = _diskstats(); time.sleep(interval); b = _diskstats()
    rows = {}
    for dev in b:
        if dev in a:
            rows[dev] = {'read_mb_s': round((b[dev][0] - a[dev][0]) * 512 / 1e6 / interval, 2),
                         'write_mb_s': round((b[dev][1] - a[dev][1]) * 512 / 1e6 / interval, 2),
                         'busy_percent': round(min(100, (b[dev][2] - a[dev][2]) / (interval * 10)), 1)}
    return rows


@_safe
def get_inode_usage():
    rows = []
    for line in _run(['df', '-i', '-x', 'tmpfs', '-x', 'devtmpfs']).splitlines()[1:]:
        p = line.split()
        if len(p) >= 6:
            rows.append({'filesystem': p[0], 'inodes': p[1], 'used_percent': p[4], 'mounted_on': p[5]})
    return rows


@_safe
def get_disk_smart_hint():
    """Pistas rápidas de salud del disco sin root: estado de lectura-escritura y errores de E/S."""
    ro = [l.split()[1] for l in _read('/proc/mounts').splitlines() if len(l.split()) > 3 and 'ro' in l.split()[3].split(',')
          and l.split()[2] in ('ext4', 'xfs', 'btrfs', 'f2fs')]
    return {'filesystems_read_only': ro, 'smartctl': shutil.which('smartctl') is not None,
            'tip': 'Ejecuta smartctl -H /dev/sdX con sudo para el diagnóstico SMART completo'}


# ====================================================================
# Red
# ====================================================================
@_safe
def get_network_throughput(interval=1.0):
    interval = _clamp(interval, 0.2, 5)
    a = _net_counters(); time.sleep(interval); b = _net_counters()
    return {n: {'rx_kb_s': round((b[n]['rx'] - a[n]['rx']) / 1024 / interval, 1),
                'tx_kb_s': round((b[n]['tx'] - a[n]['tx']) / 1024 / interval, 1)} for n in b if n in a}


@_safe
def get_network_errors():
    return {n: {k: v for k, v in c.items() if k.endswith(('err', 'drop'))} for n, c in _net_counters().items()}


@_safe
def get_connection_summary():
    text = _read('/proc/net/sockstat')
    out = {}
    for line in text.splitlines():
        proto, _, rest = line.partition(':')
        words = rest.split()
        out[proto] = dict(zip(words[::2], map(int, words[1::2])))
    return out


@_safe
def get_established_connections(limit=30):
    out = _run(['ss', '-H', '-tn', 'state', 'established']).splitlines()
    rows = []
    for line in out[:int(_clamp(limit, 1, 200))]:
        p = line.split()
        if len(p) >= 4:
            rows.append({'local': p[2], 'remote': p[3]})
    return {'count': len(out), 'connections': rows}


# ====================================================================
# Sensores y energía
# ====================================================================
@_safe
def get_temperatures():
    rows = []
    for temp in sorted(glob.glob('/sys/class/hwmon/hwmon*/temp*_input')):
        base = temp.rsplit('_', 1)[0]
        try:
            rows.append({'chip': _read(os.path.dirname(temp) + '/name', 'hwmon'),
                         'sensor': _read(base + '_label', os.path.basename(base)), 'celsius': round(int(_read(temp)) / 1000, 1)})
        except ValueError:
            pass
    return rows or {'available': False, 'reason': 'Sin sensores de temperatura accesibles'}


@_safe
def get_fans():
    rows = []
    for fan in sorted(glob.glob('/sys/class/hwmon/hwmon*/fan*_input')):
        rows.append({'chip': _read(os.path.dirname(fan) + '/name', 'hwmon'), 'fan': os.path.basename(fan).split('_')[0], 'rpm': _read(fan)})
    return rows or {'available': False, 'reason': 'Sin ventiladores reportados'}


@_safe
def get_battery():
    rows = []
    for base in sorted(glob.glob('/sys/class/power_supply/BAT*')):
        rows.append({'battery': os.path.basename(base), 'percent': _read(base + '/capacity'), 'status': _read(base + '/status'),
                     'power_now_uw': _read(base + '/power_now') or None})
    return rows or {'available': False, 'reason': 'Sin batería'}


@_safe
def get_gpu_stats():
    out = _run(['nvidia-smi', '--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw',
                '--format=csv,noheader,nounits'])
    rows = []
    for line in out.splitlines():
        n, u, mu, mt, t, pw = [x.strip() for x in line.split(',')]
        rows.append({'gpu': n, 'util_percent': float(u), 'vram_used_mib': float(mu), 'vram_total_mib': float(mt),
                     'temp_c': float(t), 'power_w': pw})
    return rows


# ====================================================================
# Sistema general
# ====================================================================
@_safe
def get_uptime():
    seconds = float(_read('/proc/uptime').split()[0])
    d, rem = divmod(int(seconds), 86400)
    h, rem = divmod(rem, 3600)
    return {'seconds': int(seconds), 'pretty': f'{d} d {h} h {rem // 60} min'}


@_safe
def get_entropy():
    return {'entropy_bits': int(_read('/proc/sys/kernel/random/entropy_avail') or 0)}


@_safe
def get_logged_in_count():
    lines = [l for l in _run(['who']).splitlines() if l.strip()]
    return {'sessions': len(lines), 'users': sorted({l.split()[0] for l in lines})}


@_safe
def get_failed_services_count():
    lines = [l for l in _run(['systemctl', '--failed', '--no-legend', '--no-pager']).splitlines() if l.strip()]
    return {'failed': len(lines), 'units': [l.split()[1] if l.startswith(('●', '*')) else l.split()[0] for l in lines]}


@_safe
def get_recent_errors(lines=20):
    n = str(int(_clamp(lines, 1, 200)))
    return _run(['journalctl', '-p', 'err', '-n', n, '--no-pager', '--output=short-iso'], timeout=15).splitlines()


# ====================================================================
# Vigilancia, umbrales y salud global
# ====================================================================
def _sample(metric):
    if metric == 'cpu':
        return get_cpu_usage(0.5).get('total_percent')
    if metric == 'memory':
        return get_memory_usage().get('used_percent')
    if metric == 'load':
        return get_load_vs_cores().get('load_per_core')
    if metric == 'swap':
        return get_memory_usage().get('swap_used_percent')
    if metric == 'temperature':
        temps = get_temperatures()
        return max((t['celsius'] for t in temps), default=None) if isinstance(temps, list) else None
    if metric == 'network':
        net = get_network_throughput(0.5)
        return round(sum(v['rx_kb_s'] + v['tx_kb_s'] for k, v in net.items() if k != 'lo'), 1) if 'error' not in net else None
    if metric == 'disk_io':
        io = get_disk_io(0.5)
        return round(sum(v['read_mb_s'] + v['write_mb_s'] for v in io.values()), 2) if 'error' not in io else None
    raise ValueError('Métrica no soportada: cpu, memory, load, swap, temperature, network, disk_io')


@_safe
def watch_metric(metric='cpu', duration=10, interval=1):
    """Toma muestras de una métrica durante unos segundos (máx. 60 s)."""
    duration = _clamp(duration, 1, 60)
    interval = _clamp(interval, 0.5, 10)
    samples, end = [], time.monotonic() + duration
    while time.monotonic() < end:
        value = _sample(metric)
        if value is not None:
            samples.append(value)
        time.sleep(interval)
    if not samples:
        return {'metric': metric, 'available': False}
    return {'metric': metric, 'samples': samples, 'min': min(samples), 'max': max(samples),
            'avg': round(sum(samples) / len(samples), 2)}


@_safe
def check_thresholds(cpu=90, memory=90, disk=90, load_per_core=1.5, temp=85, swap=60):
    alerts = []
    c = get_cpu_usage(0.5).get('total_percent', 0)
    if c >= cpu:
        alerts.append(f'CPU al {c}%')
    mem = get_memory_usage()
    if mem.get('used_percent', 0) >= memory:
        alerts.append(f"RAM al {mem['used_percent']}%")
    if mem.get('swap_used_percent', 0) >= swap:
        alerts.append(f"Swap al {mem['swap_used_percent']}%")
    if get_load_vs_cores().get('load_per_core', 0) >= load_per_core:
        alerts.append('Carga por núcleo alta')
    for d in get_disk_stats().get('disks', []):
        pct = d['use_percent'].rstrip('%')
        if pct.isdigit() and int(pct) >= disk and not d['filesystem'].startswith(('tmpfs', 'udev', 'overlay')):
            alerts.append(f"Disco {d['mounted_on']} al {pct}%")
    temps = get_temperatures()
    if isinstance(temps, list):
        alerts += [f"{t['sensor']} a {t['celsius']} °C" for t in temps if t['celsius'] >= temp]
    return {'alerts': alerts, 'ok': not alerts}


@_safe
def health_check():
    """Diagnóstico global: ok / warning / critical con los motivos."""
    findings, level = [], 0
    def flag(severity, text):
        nonlocal level
        level = max(level, severity); findings.append(text)
    mem = get_memory_usage()
    if mem['used_percent'] > 95: flag(2, f"RAM casi llena ({mem['used_percent']}%)")
    elif mem['used_percent'] > 85: flag(1, f"RAM alta ({mem['used_percent']}%)")
    if mem['swap_used_percent'] > 50: flag(1, f"Swap en uso ({mem['swap_used_percent']}%)")
    load = get_load_vs_cores()
    if load['load_per_core'] > 2: flag(2, 'Carga muy alta')
    elif load['load_per_core'] > 1.2: flag(1, 'Carga elevada')
    for d in get_disk_stats().get('disks', []):
        pct = d['use_percent'].rstrip('%')
        if pct.isdigit() and not d['filesystem'].startswith(('tmpfs', 'udev', 'overlay', 'shm')):
            if int(pct) >= 95: flag(2, f"Disco {d['mounted_on']} al {pct}%")
            elif int(pct) >= 85: flag(1, f"Disco {d['mounted_on']} al {pct}%")
    zombies = get_zombies()
    if zombies.get('count', 0) > 5: flag(1, f"{zombies['count']} procesos zombie")
    failed = get_failed_services_count()
    if failed.get('failed'): flag(1, f"{failed['failed']} servicios fallidos")
    temps = get_temperatures()
    if isinstance(temps, list) and max(t['celsius'] for t in temps) >= 90: flag(2, 'Temperatura crítica')
    oom = get_oom_events(5)
    if oom.get('count'): flag(1, f"{oom['count']} eventos OOM en el log")
    return {'status': ['ok', 'warning', 'critical'][level], 'findings': findings or ['Todo en orden']}


@_safe
def snapshot():
    """Instantánea compacta para mostrar en una sola respuesta."""
    return {'cpu': get_cpu_usage(0.5), 'memory': get_memory_usage(), 'load': get_load_vs_cores(), 'uptime': get_uptime(),
            'disks': get_disk_stats().get('disks', [])[:8], 'top_cpu': get_top_cpu(5), 'top_memory': get_top_memory(5),
            'processes': get_process_states()}


EXTRA_OPERATIONS = {name: fn for name, fn in globals().items()
                    if name.startswith('get_') or name in {'watch_metric', 'check_thresholds', 'health_check', 'snapshot'}}