"""Read-only system facts from Linux procfs and standard library."""
import os, platform, shutil, socket, time, getpass, subprocess, json
from datetime import datetime
from pathlib import Path
def info():
    data={'hostname':socket.gethostname(),'os':platform.platform(),'kernel':platform.release(),'architecture':platform.machine(),'python':platform.python_version(),'user':getpass.getuser(),'uptime_seconds':None,'load_average':None,'memory':{}}
    try: data['uptime_seconds']=float(Path('/proc/uptime').read_text().split()[0])
    except (OSError,ValueError): pass
    try: data['load_average']=os.getloadavg()
    except OSError: pass
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            k,v=line.split(':',1); data['memory'][k]=v.strip()
    except OSError: pass
    return data
def current_time(include_date=False):
    """Return the local system clock and timezone without external services."""
    now=datetime.now().astimezone()
    weekdays=('lunes','martes','miércoles','jueves','viernes','sábado','domingo')
    months=('enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre')
    hour=now.strftime('%I').lstrip('0') or '12'; suffix='a. m.' if now.hour<12 else 'p. m.'
    return {'datetime':now.isoformat(timespec='seconds'),'date':f'{weekdays[now.weekday()]} {now.day} de {months[now.month-1]} de {now.year}','time':f'{hour}:{now.minute:02d} {suffix}','time_24h':now.strftime('%H:%M:%S'),'timezone':now.tzname() or now.strftime('%z')}

def ram():
    values={}
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            key,value=line.split(':',1); parts=value.split(); values[key]=int(parts[0])*1024
    except (OSError,ValueError,IndexError) as exc:raise RuntimeError(f'No pude leer /proc/meminfo: {exc}') from exc
    total=values.get('MemTotal'); available=values.get('MemAvailable')
    if total is None:raise RuntimeError('El kernel no expuso MemTotal en /proc/meminfo.')
    gib=1024**3
    return {'total_gib':round(total/gib,2),'available_gib':round(available/gib,2) if available is not None else None,'used_gib':round((total-available)/gib,2) if available is not None else None,'total_bytes':total,'available_bytes':available}

def identity():
    import os
    user=getpass.getuser()
    try:groups=__import__('grp').getgrgid(os.getegid()).gr_name
    except (ImportError,KeyError):groups=str(os.getegid())
    return {'user':user,'uid':os.getuid(),'primary_group':groups,'is_root':os.geteuid()==0,'working_directory':os.getcwd()}

def working_directory():return os.getcwd()
def logs(lines=100):
    """Return recent journal lines with a strict size cap for terminal safety."""
    from discovery.tool_detector import available
    if not available('journalctl'): raise FileNotFoundError('journalctl is unavailable; inspect /var/log with appropriate permissions')
    completed=subprocess.run(['journalctl','-n',str(max(1,min(lines,500))),'--no-pager','--output=short-iso'],capture_output=True,text=True,timeout=15)
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or f'journalctl terminó con código {completed.returncode}')
    output=completed.stdout.rstrip()
    limit=12000
    if len(output)>limit:
        output='[Salida recortada a los últimos 12 000 caracteres.\n]\n'+output[-limit:]
    return output

def environment_variables(filter_pattern=None):
    """Inspect environment variables with optional filtering."""
    env = dict(os.environ)
    if filter_pattern:
        import re
        pattern = re.compile(filter_pattern, re.IGNORECASE)
        env = {k: v for k, v in env.items() if pattern.search(k)}
    return env

def set_timezone(timezone):
    """Change system timezone (requires root and timedatectl)."""
    if os.geteuid() != 0:
        raise PermissionError('Changing timezone requires root privileges')
    exe = shutil.which('timedatectl')
    if not exe:
        raise FileNotFoundError('timedatectl is not installed')
    p = subprocess.run([exe, 'set-timezone', timezone], capture_output=True, text=True, timeout=10)
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or f'timedatectl exited {p.returncode}')
    return {'timezone': timezone, 'status': 'changed'}

def hardware_info():
    """Detailed hardware information from /sys and lspci if available."""
    info = {'cpu': {}, 'gpu': [], 'disks': [], 'temperature': {}}
    try:
        with open('/proc/cpuinfo') as f:
            cpuinfo = f.read()
            for line in cpuinfo.splitlines():
                if line.startswith('model name'):
                    info['cpu']['model'] = line.split(':', 1)[1].strip()
                elif line.startswith('cpu cores'):
                    info['cpu']['cores'] = int(line.split(':')[1].strip())
                elif line.startswith('processor'):
                    info['cpu']['processors'] = info['cpu'].get('processors', 0) + 1
    except OSError:
        pass
    
    if shutil.which('lspci'):
        try:
            p = subprocess.run(['lspci'], capture_output=True, text=True, timeout=10)
            info['gpu'] = [line for line in p.stdout.splitlines() if 'vga' in line.lower() or '3d' in line.lower()]
        except (subprocess.TimeoutExpired, RuntimeError):
            pass
    
    try:
        for device in Path('/sys/block').iterdir():
            if device.is_dir() and device.name.startswith(('sd', 'nvme', 'mmcblk')):
                size_path = device / 'size'
                if size_path.exists():
                    sectors = int(size_path.read_text().strip())
                    info['disks'].append({'device': device.name, 'size_gb': round(sectors * 512 / (1024**3), 2)})
    except OSError:
        pass
    
    for sensor_path in ['/sys/class/thermal', '/sys/class/hwmon']:
        try:
            for sensor in Path(sensor_path).iterdir():
                temp_file = sensor / 'temp1_input'
                if temp_file.exists():
                    temp_millidegrees = int(temp_file.read_text().strip())
                    info['temperature'][sensor.name] = {'celsius': temp_millidegrees / 1000}
        except (OSError, ValueError):
            pass
    
    return info

def cpu_info():
    """Return focused CPU details, rather than the entire system summary."""
    return hardware_info()['cpu']

def gpu_info():
    """Return detected display/3D adapters, or an empty list if unavailable."""
    return hardware_info()['gpu']

def power_management(action, delay_minutes=0):
    """Shutdown or reboot system (requires root)."""
    if os.geteuid() != 0:
        raise PermissionError('Power management requires root privileges')
    if action not in {'shutdown', 'reboot'}:
        raise ValueError('Action must be shutdown or reboot')
    exe = shutil.which('shutdown')
    if not exe:
        raise FileNotFoundError('shutdown command is not available')
    cmd = [exe]
    if delay_minutes > 0:
        cmd.extend(['-h', f'+{delay_minutes}'])
    else:
        cmd.append('-h') if action == 'shutdown' else cmd.append('-r')
    cmd.append('now')
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or f'shutdown exited {p.returncode}')
    return {'action': action, 'delay_minutes': delay_minutes, 'status': 'scheduled'}

def audio_volume(device='default', set_volume=None):
    """Get or set audio volume using pactl (PulseAudio) or amixer (ALSA)."""
    if set_volume is not None:
        if not (0 <= set_volume <= 100):
            raise ValueError('Volume must be between 0 and 100')
    
    if shutil.which('pactl'):
        try:
            if set_volume is not None:
                subprocess.run(['pactl', 'set-sink-volume', device, f'{set_volume}%'], check=True, timeout=5)
            p = subprocess.run(['pactl', 'get-sink-volume', device], capture_output=True, text=True, timeout=5)
            match = __import__('re').search(r'(\d+)%', p.stdout)
            return {'volume': int(match.group(1)) if match else None, 'device': device}
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, AttributeError):
            pass
    
    if shutil.which('amixer'):
        try:
            if set_volume is not None:
                subprocess.run(['amixer', '-D', device, 'sset', 'Master', f'{set_volume}%'], check=True, timeout=5)
            p = subprocess.run(['amixer', '-D', device, 'get', 'Master'], capture_output=True, text=True, timeout=5)
            match = __import__('re').search(r'\[(\d+)%\]', p.stdout)
            return {'volume': int(match.group(1)) if match else None, 'device': device}
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, AttributeError):
            pass
    
    raise FileNotFoundError('Neither pactl nor amixer is available')

def screen_brightness(set_brightness=None):
    """Get or set screen brightness using brightnessctl or xbacklight."""
    if set_brightness is not None:
        if not (0 <= set_brightness <= 100):
            raise ValueError('Brightness must be between 0 and 100')
    
    if shutil.which('brightnessctl'):
        try:
            if set_brightness is not None:
                subprocess.run(['brightnessctl', 'set', f'{set_brightness}%'], check=True, timeout=5)
            p = subprocess.run(['brightnessctl', 'get'], capture_output=True, text=True, timeout=5)
            current = int(p.stdout.strip())
            return {'brightness': current, 'device': 'brightnessctl'}
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError):
            pass
    
    if shutil.which('xbacklight'):
        try:
            if set_brightness is not None:
                subprocess.run(['xbacklight', '-set', str(set_brightness)], check=True, timeout=5)
            p = subprocess.run(['xbacklight', '-get'], capture_output=True, text=True, timeout=5)
            current = int(float(p.stdout.strip()))
            return {'brightness': current, 'device': 'xbacklight'}
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError):
            pass
    
    raise FileNotFoundError('Neither brightnessctl nor xbacklight is available')

def boot_analysis():
    """Analyze boot performance and services."""
    if not shutil.which('systemd-analyze'):
        raise FileNotFoundError('systemd-analyze is not available')
    
    result = {'boot_time': None, 'slow_services': [], 'failed_services': []}
    
    try:
        p = subprocess.run(['systemd-analyze', 'time'], capture_output=True, text=True, timeout=10)
        match = __import__('re').search(r'(\d+\.\d+)', p.stdout)
        if match:
            result['boot_time'] = float(match.group(1))
    except (subprocess.TimeoutExpired, AttributeError):
        pass
    
    try:
        p = subprocess.run(['systemd-analyze', 'blame'], capture_output=True, text=True, timeout=15)
        for line in p.stdout.splitlines()[:10]:
            parts = line.split()
            if len(parts) >= 2:
                result['slow_services'].append({'service': parts[1], 'time_ms': parts[0]})
    except subprocess.TimeoutExpired:
        pass
    
    try:
        p = subprocess.run(['systemctl', 'list-units', '--failed', '--no-pager', '--no-legend'], capture_output=True, text=True, timeout=10)
        for line in p.stdout.splitlines():
            parts = line.split()
            if parts:
                result['failed_services'].append({'service': parts[0], 'state': parts[2] if len(parts) > 2 else 'unknown'})
    except subprocess.TimeoutExpired:
        pass
    
    return result

"""Ampliación de system.py: más de 60 consultas y acciones del sistema Linux.

Pega este bloque al final de tu system.py (ya incluye sus imports) o déjalo como
archivo aparte y haz ``from .system_extra import *`` en system.py. Al final está
EXTRA_OPERATIONS para registrar cada función como operación ``system.<nombre>``.
"""
import calendar as _calendar
import glob
import grp
import os
import platform
import re
import resource
import shutil
import signal
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------- utilidades
def _xrun(args, timeout=10, check=True):
    """Ejecuta una utilidad sin shell y devuelve stdout; errores claros si falta."""
    exe = shutil.which(args[0])
    if not exe:
        raise FileNotFoundError(f"Falta la utilidad '{args[0]}'")
    p = subprocess.run([exe, *map(str, args[1:])], capture_output=True, text=True, timeout=timeout)
    if check and p.returncode:
        raise RuntimeError((p.stderr or p.stdout).strip() or f'{args[0]} terminó con código {p.returncode}')
    return p.stdout.strip()


def _first_tool(candidates):
    """Devuelve el primer comando de la lista que exista en el sistema."""
    return next((c for c in candidates if shutil.which(c[0])), None)


def _read(path, default=''):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return default


def _need_root(what):
    if os.geteuid() != 0:
        raise PermissionError(f'{what} requiere privilegios de administrador (root)')


def _human_seconds(seconds):
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = [f'{days} d' if days else '', f'{hours} h' if hours else '', f'{minutes} min' if minutes else '']
    return ' '.join(p for p in parts if p) or f'{secs} s'


def _meminfo():
    values = {}
    for line in _read('/proc/meminfo').splitlines():
        key, _, rest = line.partition(':')
        try:
            values[key] = int(rest.split()[0]) * 1024
        except (ValueError, IndexError):
            pass
    return values


# ------------------------------------------------------- identidad y versión
def os_release():
    data = {}
    for line in _read('/etc/os-release').splitlines():
        if '=' in line:
            key, _, value = line.partition('=')
            data[key] = value.strip('"')
    return {'distribucion': data.get('PRETTY_NAME') or platform.platform(), 'id': data.get('ID'),
            'version': data.get('VERSION'), 'codename': data.get('VERSION_CODENAME'),
            'kernel': platform.release(), 'arquitectura': platform.machine()}


def kernel_version():
    u = platform.uname()
    return {'sistema': u.system, 'kernel': u.release, 'version': u.version, 'arquitectura': u.machine, 'host': u.node}


def hostname_info():
    try:
        return {'hostnamectl': _xrun(['hostnamectl'])}
    except (FileNotFoundError, RuntimeError):
        return {'hostname': socket.gethostname(), 'fqdn': socket.getfqdn()}


def summary():
    """Resumen estilo neofetch con lo esencial del equipo."""
    mem = _meminfo()
    gib = 1024 ** 3
    cpu = next((l.split(':', 1)[1].strip() for l in _read('/proc/cpuinfo').splitlines() if l.startswith('model name')), 'desconocida')
    root = shutil.disk_usage('/')
    return {'sistema': os_release(), 'cpu': cpu, 'nucleos': os.cpu_count(),
            'ram_total_gib': round(mem.get('MemTotal', 0) / gib, 2),
            'ram_disponible_gib': round(mem.get('MemAvailable', 0) / gib, 2),
            'disco_raiz': {'total_gib': round(root.total / gib, 1), 'libre_gib': round(root.free / gib, 1)},
            'uptime': uptime()['uptime'], 'shell': os.environ.get('SHELL'),
            'escritorio': os.environ.get('XDG_CURRENT_DESKTOP'), 'sesion': os.environ.get('XDG_SESSION_TYPE')}


# ------------------------------------------------------------ tiempo y carga
def uptime():
    try:
        seconds = float(_read('/proc/uptime').split()[0])
    except (ValueError, IndexError):
        raise RuntimeError('No pude leer /proc/uptime')
    return {'uptime': _human_seconds(seconds), 'segundos': int(seconds),
            'encendido_desde': datetime.fromtimestamp(time.time() - seconds).isoformat(timespec='seconds')}


def boot_time():
    for line in _read('/proc/stat').splitlines():
        if line.startswith('btime'):
            return {'ultimo_arranque': datetime.fromtimestamp(int(line.split()[1])).isoformat(timespec='seconds')}
    raise RuntimeError('No encontré btime en /proc/stat')


def load_average():
    one, five, fifteen = os.getloadavg()
    cores = os.cpu_count() or 1
    return {'1min': round(one, 2), '5min': round(five, 2), '15min': round(fifteen, 2), 'nucleos': cores,
            'carga_por_nucleo': round(one / cores, 2),
            'estado': 'alta' if one / cores > 1.5 else 'normal' if one / cores < 0.9 else 'elevada'}


def timezone_info():
    try:
        return {'timedatectl': _xrun(['timedatectl'])}
    except (FileNotFoundError, RuntimeError):
        return {'zona': _read('/etc/timezone') or time.tzname[0]}


def ntp_status():
    out = _xrun(['timedatectl', 'show', '-p', 'NTP', '-p', 'NTPSynchronized', '-p', 'TimeUSec', '-p', 'Timezone'])
    return dict(line.split('=', 1) for line in out.splitlines() if '=' in line)


def calendar_text(year=None, month=None):
    now = datetime.now()
    return _calendar.month(int(year or now.year), int(month or now.month))


# ------------------------------------------------------------------ CPU / RAM
def _cpu_times():
    rows = {}
    for line in _read('/proc/stat').splitlines():
        if line.startswith('cpu'):
            parts = line.split()
            values = list(map(int, parts[1:9]))
            rows[parts[0]] = (sum(values), values[3] + values[4])
    return rows


def cpu_usage(interval=0.5):
    interval = max(0.1, min(float(interval), 5))
    a = _cpu_times()
    time.sleep(interval)
    b = _cpu_times()
    out = {}
    for name in b:
        total = b[name][0] - a[name][0]
        idle = b[name][1] - a[name][1]
        out[name] = round(100 * (total - idle) / total, 1) if total else 0.0
    return {'total_percent': out.pop('cpu', 0.0), 'por_nucleo': out}


def cpu_frequency():
    freqs = []
    for path in sorted(glob.glob('/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq')):
        try:
            freqs.append(round(int(_read(path)) / 1000))
        except ValueError:
            pass
    if not freqs:
        freqs = [round(float(l.split(':')[1])) for l in _read('/proc/cpuinfo').splitlines() if l.startswith('cpu MHz')]
    if not freqs:
        raise RuntimeError('El kernel no expone la frecuencia de la CPU')
    return {'mhz_por_nucleo': freqs, 'mhz_medio': round(sum(freqs) / len(freqs))}


def memory_summary():
    m = _meminfo()
    gib = 1024 ** 3
    total, avail = m.get('MemTotal', 0), m.get('MemAvailable', 0)
    swap_total, swap_free = m.get('SwapTotal', 0), m.get('SwapFree', 0)
    return {'total_gib': round(total / gib, 2), 'disponible_gib': round(avail / gib, 2),
            'usada_gib': round((total - avail) / gib, 2),
            'usada_percent': round(100 * (total - avail) / total, 1) if total else None,
            'cache_gib': round(m.get('Cached', 0) / gib, 2), 'buffers_gib': round(m.get('Buffers', 0) / gib, 2),
            'swap_total_gib': round(swap_total / gib, 2), 'swap_usada_gib': round((swap_total - swap_free) / gib, 2)}


def swap_info():
    devices = _read('/proc/swaps').splitlines()[1:]
    info = memory_summary()
    return {'swap_total_gib': info['swap_total_gib'], 'swap_usada_gib': info['swap_usada_gib'],
            'swappiness': _read('/proc/sys/vm/swappiness'), 'dispositivos': devices}


def battery():
    rows = []
    for base in sorted(glob.glob('/sys/class/power_supply/BAT*')):
        rows.append({'bateria': os.path.basename(base), 'carga_percent': _read(base + '/capacity'),
                     'estado': _read(base + '/status'), 'ciclos': _read(base + '/cycle_count') or None,
                     'salud': _read(base + '/health') or None})
    ac = [{'fuente': os.path.basename(p), 'conectada': _read(p + '/online') == '1'}
          for p in sorted(glob.glob('/sys/class/power_supply/A*'))]
    if not rows:
        return {'available': False, 'reason': 'Este equipo no reporta batería', 'corriente': ac}
    return {'baterias': rows, 'corriente': ac}


def temperatures():
    rows = []
    for temp in sorted(glob.glob('/sys/class/hwmon/hwmon*/temp*_input')):
        base = temp.rsplit('_', 1)[0]
        chip = _read(os.path.dirname(temp) + '/name', 'hwmon')
        try:
            rows.append({'chip': chip, 'sensor': _read(base + '_label', os.path.basename(base)),
                         'celsius': round(int(_read(temp)) / 1000, 1)})
        except ValueError:
            continue
    for zone in sorted(glob.glob('/sys/class/thermal/thermal_zone*')):
        try:
            rows.append({'chip': 'thermal', 'sensor': _read(zone + '/type', zone), 'celsius': round(int(_read(zone + '/temp')) / 1000, 1)})
        except ValueError:
            continue
    if not rows:
        return {'available': False, 'reason': 'No hay sensores de temperatura accesibles'}
    return rows


def gpu_usage():
    if shutil.which('nvidia-smi'):
        out = _xrun(['nvidia-smi', '--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu',
                     '--format=csv,noheader,nounits'])
        rows = []
        for line in out.splitlines():
            name, util, used, total, temp = [x.strip() for x in line.split(',')]
            rows.append({'gpu': name, 'uso_percent': float(util), 'vram_usada_mib': float(used),
                         'vram_total_mib': float(total), 'temperatura_c': float(temp)})
        return rows
    rows = [{'tarjeta': p.split('/')[4], 'uso_percent': _read(p)}
            for p in glob.glob('/sys/class/drm/card*/device/gpu_busy_percent')]
    return rows or {'available': False, 'reason': 'No encontré nvidia-smi ni contadores AMD de GPU'}


# ---------------------------------------------------- usuarios y sesiones
def list_users(include_system=False):
    users = []
    for line in _read('/etc/passwd').splitlines():
        parts = line.split(':')
        if len(parts) < 7:
            continue
        name, _, uid, gid, _, home, shell = parts[:7]
        human = int(uid) >= 1000 and not shell.endswith(('nologin', 'false')) and name != 'nobody'
        if include_system or human:
            users.append({'usuario': name, 'uid': int(uid), 'home': home, 'shell': shell})
    return users


def logged_users():
    try:
        return _xrun(['who', '-H']).splitlines()
    except FileNotFoundError:
        return _xrun(['loginctl', 'list-sessions', '--no-legend']).splitlines()


def last_logins(count=10):
    return _xrun(['last', '-n', str(max(1, min(int(count), 100))), '-F']).splitlines()


def my_groups():
    names = []
    for gid in os.getgroups():
        try:
            names.append(grp.getgrgid(gid).gr_name)
        except KeyError:
            names.append(str(gid))
    return {'usuario': os.environ.get('USER') or str(os.getuid()), 'grupos': sorted(set(names))}


def sudo_check():
    groups = my_groups()['grupos']
    in_group = any(g in groups for g in ('sudo', 'wheel', 'admin'))
    if os.geteuid() == 0:
        return {'es_root': True, 'puede_sudo': True}
    if not shutil.which('sudo'):
        return {'es_root': False, 'puede_sudo': False, 'motivo': 'sudo no está instalado'}
    passwordless = subprocess.run(['sudo', '-n', 'true'], capture_output=True, timeout=5).returncode == 0
    return {'es_root': False, 'en_grupo_sudo': in_group, 'sudo_sin_contrasena': passwordless}


# ------------------------------------------------------------- hardware
def usb_devices():
    return _xrun(['lsusb']).splitlines()


def pci_devices():
    return _xrun(['lspci']).splitlines()


def block_devices():
    try:
        import json
        data = json.loads(_xrun(['lsblk', '-J', '-o', 'NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS,MODEL']))
        return data.get('blockdevices', [])
    except (ValueError, RuntimeError):
        return _xrun(['lsblk']).splitlines()


def mounts():
    skip = {'proc', 'sysfs', 'devtmpfs', 'devpts', 'cgroup', 'cgroup2', 'securityfs', 'pstore', 'bpf', 'tracefs',
            'debugfs', 'configfs', 'fusectl', 'mqueue', 'hugetlbfs', 'autofs', 'binfmt_misc', 'efivarfs', 'squashfs'}
    rows = []
    for line in _read('/proc/mounts').splitlines():
        dev, mount, fs = line.split()[:3]
        if fs in skip:
            continue
        try:
            usage = shutil.disk_usage(mount)
            rows.append({'dispositivo': dev, 'montaje': mount, 'tipo': fs,
                         'usado_percent': round(100 * usage.used / usage.total, 1) if usage.total else 0,
                         'libre_gib': round(usage.free / 1024 ** 3, 2)})
        except OSError:
            rows.append({'dispositivo': dev, 'montaje': mount, 'tipo': fs})
    return rows


def disk_inodes():
    return _xrun(['df', '-i', '-x', 'tmpfs', '-x', 'devtmpfs']).splitlines()


def kernel_modules(limit=50):
    rows = []
    for line in _read('/proc/modules').splitlines():
        parts = line.split()
        if len(parts) >= 3:
            rows.append({'modulo': parts[0], 'bytes': int(parts[1]), 'usos': int(parts[2])})
    return sorted(rows, key=lambda r: r['bytes'], reverse=True)[:max(1, min(int(limit), 500))]


def display_info():
    tool = _first_tool([['xrandr', '--query'], ['wlr-randr']])
    if tool:
        out = _xrun(tool)
        return [l for l in out.splitlines() if ' connected' in l or '*' in l or tool[0] == 'wlr-randr'][:40]
    modes = [_read(p) for p in glob.glob('/sys/class/drm/card*-*/modes')]
    return [m.splitlines()[0] for m in modes if m] or {'available': False, 'reason': 'No encontré xrandr ni wlr-randr'}


def session_info():
    keys = ('XDG_SESSION_TYPE', 'XDG_CURRENT_DESKTOP', 'DESKTOP_SESSION', 'WAYLAND_DISPLAY', 'DISPLAY', 'XDG_SESSION_ID')
    return {k: os.environ.get(k) for k in keys}


def keyboard_layout():
    tool = _first_tool([['localectl', 'status'], ['setxkbmap', '-query']])
    if not tool:
        raise FileNotFoundError("Falta 'localectl' o 'setxkbmap'")
    return _xrun(tool).splitlines()


def locale_info():
    return dict(l.split('=', 1) for l in _xrun(['locale']).splitlines() if '=' in l)


# ----------------------------------------------------- logs y diagnóstico
def _journal(args, lines):
    n = str(max(1, min(int(lines), 500)))
    return _xrun(['journalctl', *args, '-n', n, '--no-pager', '--output=short-iso'], timeout=20).splitlines()


def boot_errors(lines=50):
    return _journal(['-b', '-p', 'err'], lines)


def dmesg_errors(lines=50):
    try:
        return _journal(['-k', '-p', 'err'], lines)
    except (FileNotFoundError, RuntimeError):
        return _xrun(['dmesg', '--level=err,crit,alert,emerg'])[-12000:].splitlines()[-int(lines):]


def failed_units():
    out = _xrun(['systemctl', '--failed', '--no-legend', '--no-pager'])
    return out.splitlines() or ['No hay unidades fallidas']


def timers():
    return _xrun(['systemctl', 'list-timers', '--all', '--no-pager']).splitlines()


def reboot_required():
    if Path('/var/run/reboot-required').exists():
        return {'reinicio_necesario': True, 'paquetes': _read('/var/run/reboot-required.pkgs').splitlines()}
    return {'reinicio_necesario': False}


def sysctl_get(key):
    if not re.fullmatch(r'[a-z0-9_.\-/]+', str(key)):
        raise ValueError('Nombre de parámetro sysctl no válido')
    return {key: _xrun(['sysctl', '-n', key])}


def ulimits():
    names = {'procesos': resource.RLIMIT_NPROC, 'archivos_abiertos': resource.RLIMIT_NOFILE,
             'pila_bytes': resource.RLIMIT_STACK, 'memoria_virtual': resource.RLIMIT_AS, 'core': resource.RLIMIT_CORE}
    fmt = lambda v: 'ilimitado' if v == resource.RLIM_INFINITY else v
    return {k: {'blando': fmt(v[0]), 'duro': fmt(v[1])} for k, v in ((k, resource.getrlimit(r)) for k, r in names.items())}


def security_status():
    """Postura básica de seguridad del kernel y de los módulos MAC."""
    aslr = {'0': 'desactivado', '1': 'parcial', '2': 'completo'}.get(_read('/proc/sys/kernel/randomize_va_space'), 'desconocido')
    info = {'aslr': aslr, 'ptrace_scope': _read('/proc/sys/kernel/yama/ptrace_scope') or 'no disponible',
            'dmesg_restrict': _read('/proc/sys/kernel/dmesg_restrict'),
            'kptr_restrict': _read('/proc/sys/kernel/kptr_restrict'),
            'lockdown': _read('/sys/kernel/security/lockdown') or 'no disponible',
            'apparmor': _read('/sys/module/apparmor/parameters/enabled') or 'no disponible',
            'selinux': ('enforcing' if _read('/sys/fs/selinux/enforce') == '1' else 'permissive')
            if Path('/sys/fs/selinux/enforce').exists() else 'no disponible',
            'syn_cookies': _read('/proc/sys/net/ipv4/tcp_syncookies'),
            'ip_forward': _read('/proc/sys/net/ipv4/ip_forward')}
    try:
        info['secure_boot'] = _xrun(['mokutil', '--sb-state'])
    except (FileNotFoundError, RuntimeError):
        info['secure_boot'] = 'no disponible'
    return info


# ----------------------------------------------------------- variables / shell
_SECRET_NAME = re.compile(r'(KEY|TOKEN|SECRET|PASS|PWD|CREDENTIAL|AUTH)', re.I)


def env_get(name):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', str(name)):
        raise ValueError('Nombre de variable no válido')
    value = os.environ.get(name)
    if value is None:
        return {name: None, 'definida': False}
    return {name: '***' if _SECRET_NAME.search(name) else value, 'definida': True}


def path_dirs():
    return [{'directorio': d, 'existe': os.path.isdir(d)} for d in os.environ.get('PATH', '').split(os.pathsep) if d]


def shell_info():
    return {'shell': os.environ.get('SHELL'), 'disponibles': [l for l in _read('/etc/shells').splitlines() if l.startswith('/')]}


# ----------------------------------------------------- acciones de sesión
def lock_screen():
    tool = _first_tool([['loginctl', 'lock-session'], ['xdg-screensaver', 'lock'], ['gnome-screensaver-command', '-l']])
    if not tool:
        raise FileNotFoundError('No encontré loginctl, xdg-screensaver ni gnome-screensaver-command')
    _xrun(tool)
    return {'status': 'pantalla bloqueada'}


def suspend():
    _xrun(['systemctl', 'suspend'], timeout=15)
    return {'status': 'suspendiendo'}


def hibernate():
    _xrun(['systemctl', 'hibernate'], timeout=15)
    return {'status': 'hibernando'}


def logout():
    session = os.environ.get('XDG_SESSION_ID')
    if session and re.fullmatch(r'\w+', session):
        _xrun(['loginctl', 'terminate-session', session])
    else:
        _xrun(['loginctl', 'terminate-user', str(os.getuid())])
    return {'status': 'cerrando sesión'}


def screenshot(path=None):
    dest = Path(path).expanduser() if path else Path.home() / 'Pictures' / f'captura_{datetime.now():%Y%m%d_%H%M%S}.png'
    dest.parent.mkdir(parents=True, exist_ok=True)
    tool = _first_tool([['gnome-screenshot', '-f', str(dest)], ['grim', str(dest)], ['scrot', str(dest)],
                        ['spectacle', '-b', '-n', '-o', str(dest)], ['import', '-window', 'root', str(dest)]])
    if not tool:
        raise FileNotFoundError('Instala gnome-screenshot, grim, scrot o spectacle para capturar la pantalla')
    _xrun(tool, timeout=20)
    return {'archivo': str(dest), 'herramienta': tool[0]}


def notify(message, title='LLMAH'):
    _xrun(['notify-send', str(title)[:80], str(message)[:300]])
    return {'status': 'notificación enviada'}


def set_hostname(name):
    _need_root('Cambiar el nombre del equipo')
    if not re.fullmatch(r'[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?', str(name)):
        raise ValueError('Nombre de equipo no válido (letras, números y guiones)')
    _xrun(['hostnamectl', 'set-hostname', name])
    return {'hostname': name}


def power_schedule(action, delay_minutes=0):
    """Apagado/reinicio programado (corrige el uso de '+N now' en power_management)."""
    _need_root('Programar apagado o reinicio')
    if action not in {'shutdown', 'reboot'}:
        raise ValueError('La acción debe ser shutdown o reboot')
    delay = max(0, min(int(delay_minutes), 1440))
    when = 'now' if delay == 0 else f'+{delay}'
    _xrun(['shutdown', '-h' if action == 'shutdown' else '-r', when])
    return {'accion': action, 'cuando': when}


def cancel_shutdown():
    _need_root('Cancelar el apagado')
    _xrun(['shutdown', '-c'])
    return {'status': 'apagado cancelado'}


# ------------------------------------------------------ audio / brillo / BT
def audio_mute(mute=None):
    state = 'toggle' if mute is None else ('1' if mute else '0')
    if shutil.which('pactl'):
        _xrun(['pactl', 'set-sink-mute', '@DEFAULT_SINK@', state])
    else:
        _xrun(['amixer', 'sset', 'Master', {'toggle': 'toggle', '1': 'mute', '0': 'unmute'}[state]])
    return {'silenciado': {'toggle': 'alternado', '1': True, '0': False}[state]}


def audio_step(delta=5):
    delta = max(-50, min(int(delta), 50))
    if shutil.which('pactl'):
        _xrun(['pactl', 'set-sink-volume', '@DEFAULT_SINK@', f'{delta:+d}%'])
    else:
        _xrun(['amixer', 'sset', 'Master', f'{abs(delta)}%{"+" if delta > 0 else "-"}'])
    return {'cambio_volumen': delta}


def brightness_step(delta=10):
    delta = max(-100, min(int(delta), 100))
    if shutil.which('brightnessctl'):
        _xrun(['brightnessctl', 'set', f'{abs(delta)}%{"+" if delta > 0 else "-"}'])
    else:
        _xrun(['xbacklight', '-inc' if delta > 0 else '-dec', str(abs(delta))])
    return {'cambio_brillo': delta}


def bluetooth_status():
    out = {}
    if shutil.which('bluetoothctl'):
        out['controlador'] = _xrun(['bluetoothctl', 'show'], check=False).splitlines()[:12]
    if shutil.which('rfkill'):
        out['rfkill'] = [l for l in _xrun(['rfkill', 'list', 'bluetooth'], check=False).splitlines()]
    if not out:
        raise FileNotFoundError('Falta bluetoothctl o rfkill')
    return out


def bluetooth_power(on=True):
    if shutil.which('bluetoothctl'):
        _xrun(['bluetoothctl', 'power', 'on' if on else 'off'])
    else:
        _xrun(['rfkill', 'unblock' if on else 'block', 'bluetooth'])
    return {'bluetooth': 'encendido' if on else 'apagado'}


# -------------------------------------------------------------- portapapeles
def clipboard_copy(text):
    text = str(text)[:100000]
    tool = _first_tool([['wl-copy'], ['xclip', '-selection', 'clipboard'], ['xsel', '-ib']])
    if not tool:
        raise FileNotFoundError('Instala wl-clipboard, xclip o xsel')
    subprocess.run([shutil.which(tool[0]), *tool[1:]], input=text, text=True, timeout=5, check=True)
    return {'copiado_caracteres': len(text)}


def clipboard_paste():
    tool = _first_tool([['wl-paste', '-n'], ['xclip', '-selection', 'clipboard', '-o'], ['xsel', '-ob']])
    if not tool:
        raise FileNotFoundError('Instala wl-clipboard, xclip o xsel')
    return _xrun(tool)[:20000]


# ----------------------------------------------------- archivos y paquetes
def _walk_budget(path, seconds=20):
    deadline = time.monotonic() + seconds
    for root, dirs, files in os.walk(os.path.expanduser(path), onerror=lambda e: None):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
        for name in files:
            yield os.path.join(root, name)
        if time.monotonic() > deadline:
            return


def disk_hogs(path='.', limit=10):
    out = _xrun(['du', '-x', '-d1', '-B1M', os.path.expanduser(path)], timeout=90, check=False)
    rows = []
    for line in out.splitlines():
        size, _, name = line.partition('\t')
        if size.isdigit():
            rows.append({'ruta': name, 'mib': int(size)})
    return sorted(rows, key=lambda r: r['mib'], reverse=True)[:max(1, min(int(limit), 100))]


def large_files(path='.', limit=10, min_mb=50):
    found = []
    for file in _walk_budget(path):
        try:
            size = os.path.getsize(file)
        except OSError:
            continue
        if size >= int(min_mb) * 1024 ** 2:
            found.append({'ruta': file, 'mib': round(size / 1024 ** 2, 1)})
    return sorted(found, key=lambda r: r['mib'], reverse=True)[:max(1, min(int(limit), 100))]


def recent_files(path='.', limit=20, hours=24):
    cutoff = time.time() - max(1, int(hours)) * 3600
    found = []
    for file in _walk_budget(path):
        try:
            mtime = os.path.getmtime(file)
        except OSError:
            continue
        if mtime >= cutoff:
            found.append({'ruta': file, 'modificado': datetime.fromtimestamp(mtime).isoformat(timespec='seconds'), '_t': mtime})
    found.sort(key=lambda r: r['_t'], reverse=True)
    return [{k: v for k, v in r.items() if k != '_t'} for r in found[:max(1, min(int(limit), 200))]]


def empty_trash():
    trash = Path.home() / '.local' / 'share' / 'Trash'
    removed = 0
    for sub in ('files', 'info'):
        folder = trash / sub
        if not folder.is_dir():
            continue
        for item in folder.iterdir():
            if item.is_dir() and not item.is_symlink():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)
            removed += sub == 'files'
    return {'elementos_eliminados': removed}


def installed_packages_count():
    counts = {}
    for label, cmd in (('apt/dpkg', ['dpkg-query', '-f', '.\n', '-W']), ('rpm', ['rpm', '-qa']), ('pacman', ['pacman', '-Q']),
                       ('flatpak', ['flatpak', 'list', '--app']), ('snap', ['snap', 'list'])):
        if shutil.which(cmd[0]):
            counts[label] = len(_xrun(cmd, timeout=30, check=False).splitlines())
    return counts or {'available': False, 'reason': 'No detecté un gestor de paquetes conocido'}


def upgradable_packages(limit=30):
    tool = _first_tool([['apt', 'list', '--upgradable'], ['pacman', '-Qu'], ['dnf', 'check-update', '-q']])
    if not tool:
        raise FileNotFoundError('No detecté apt, pacman ni dnf')
    lines = [l for l in _xrun(tool, timeout=60, check=False).splitlines() if l and not l.startswith(('Listing', 'WARNING'))]
    return {'total': len(lines), 'paquetes': lines[:max(1, min(int(limit), 200))]}


EXTRA_OPERATIONS = {
    'os_release': os_release, 'kernel_version': kernel_version, 'hostname_info': hostname_info, 'summary': summary,
    'uptime': uptime, 'boot_time': boot_time, 'load_average': load_average, 'timezone_info': timezone_info,
    'ntp_status': ntp_status, 'calendar_text': calendar_text, 'cpu_usage': cpu_usage, 'cpu_frequency': cpu_frequency,
    'memory_summary': memory_summary, 'swap_info': swap_info, 'battery': battery, 'temperatures': temperatures,
    'gpu_usage': gpu_usage, 'list_users': list_users, 'logged_users': logged_users, 'last_logins': last_logins,
    'my_groups': my_groups, 'sudo_check': sudo_check, 'usb_devices': usb_devices, 'pci_devices': pci_devices,
    'block_devices': block_devices, 'mounts': mounts, 'disk_inodes': disk_inodes, 'kernel_modules': kernel_modules,
    'display_info': display_info, 'session_info': session_info, 'keyboard_layout': keyboard_layout,
    'locale_info': locale_info, 'boot_errors': boot_errors, 'dmesg_errors': dmesg_errors, 'failed_units': failed_units,
    'timers': timers, 'reboot_required': reboot_required, 'sysctl_get': sysctl_get, 'ulimits': ulimits,
    'security_status': security_status, 'env_get': env_get, 'path_dirs': path_dirs, 'shell_info': shell_info,
    'lock_screen': lock_screen, 'suspend': suspend, 'hibernate': hibernate, 'logout': logout,
    'screenshot': screenshot, 'notify': notify, 'set_hostname': set_hostname, 'power_schedule': power_schedule,
    'cancel_shutdown': cancel_shutdown, 'audio_mute': audio_mute, 'audio_step': audio_step,
    'brightness_step': brightness_step, 'bluetooth_status': bluetooth_status, 'bluetooth_power': bluetooth_power,
    'clipboard_copy': clipboard_copy, 'clipboard_paste': clipboard_paste, 'disk_hogs': disk_hogs,
    'large_files': large_files, 'recent_files': recent_files, 'empty_trash': empty_trash,
    'installed_packages_count': installed_packages_count, 'upgradable_packages': upgradable_packages,
}