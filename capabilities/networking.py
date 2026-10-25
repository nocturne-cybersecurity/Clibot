"""Read-only networking diagnostics."""
import socket, subprocess, shutil, json, os, struct, time
def _run(args, timeout=8):
    exe=shutil.which(args[0])
    if not exe: raise FileNotFoundError(f"Required utility '{args[0]}' is not installed")
    p=subprocess.run([exe,*map(str,args[1:])],capture_output=True,text=True,timeout=timeout)
    if p.returncode: raise RuntimeError(p.stderr.strip() or f'{args[0]} exited {p.returncode}')
    return p.stdout
def interfaces():
    try:
        records=json.loads(_run(['ip','-j','address','show']))
        return [{'interface':r.get('ifname'),'state':r.get('operstate','UNKNOWN'),'addresses':[a.get('local','')+'/'+str(a.get('prefixlen','')) for a in r.get('addr_info',[])]} for r in records]
    except (ValueError,KeyError,RuntimeError,FileNotFoundError):return _proc_interfaces()
def routes():
    try:
        rows=json.loads(_run(['ip','-j','route','show']))
        return [{'destination':r.get('dst','default'),'gateway':r.get('gateway','-'),'device':r.get('dev','-'),'protocol':r.get('protocol','-')} for r in rows]
    except (ValueError,KeyError,RuntimeError,FileNotFoundError):return _proc_routes()
def dns_config():
    try: return '\n'.join(x for x in open('/etc/resolv.conf').read().splitlines() if x.startswith(('nameserver','search','domain')))
    except OSError as e: return str(e)
def resolve(host): return sorted({x[4][0] for x in socket.getaddrinfo(host,None)})
def tcp_test(host,port,timeout=3):
    try:
        with socket.create_connection((host,int(port)),timeout=timeout): return {'reachable':True,'host':host,'port':int(port)}
    except OSError as e: return {'reachable':False,'host':host,'port':int(port),'error':str(e)}
def listening_ports():
    try:text=_run(['ss','-H','-lntup'])
    except (RuntimeError,FileNotFoundError):return _proc_listening_ports()
    rows=[]
    for line in text.splitlines():
        parts=line.split(None,6)
        if len(parts)>=5:rows.append({'protocol':parts[0],'state':parts[1],'local_address':parts[4],'process':parts[6] if len(parts)>6 else ''})
    return rows
def local_addresses():
    rows=interfaces()
    if not isinstance(rows,list):return rows
    found=[{'interface':r['interface'],'state':r['state'],'address':addr} for r in rows for addr in r['addresses'] if not addr.startswith(('127.','::1/'))]
    if not found:
        # A UDP connect selects a local route without sending a packet and can work
        # when netlink enumeration is blocked by a container policy.
        try:
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
                sock.connect(('192.0.2.1',9));address=sock.getsockname()[0]
                if address and not address.startswith('127.'):found.append({'interface':'route-selected','state':'UP','address':address})
        except OSError:pass
    return found if found else {'available':False,'reason':'El sistema restringe sockets y no se pudieron obtener direcciones locales desde /proc.'}

def _proc_interfaces():
    try:names=[name for _,name in socket.if_nameindex()]
    except OSError:
        try:names=os.listdir('/sys/class/net')
        except OSError:names=[]
    rows={name:{'interface':name,'state':'UNKNOWN','addresses':[]} for name in names}
    for name in names:
        try:rows[name]['state']=open(f'/sys/class/net/{name}/operstate').read().strip().upper()
        except OSError:pass
    try:
        import fcntl
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
            for name in names:
                try:
                    raw=fcntl.ioctl(sock.fileno(),0x8915,struct.pack('256s',name.encode()[:15]))
                    mask=fcntl.ioctl(sock.fileno(),0x891b,struct.pack('256s',name.encode()[:15]))
                    prefix=sum(bin(byte).count('1') for byte in mask[20:24])
                    rows[name]['addresses'].append(socket.inet_ntoa(raw[20:24])+f'/{prefix}')
                except OSError:pass
    except (ImportError,OSError):pass
    try:
        for line in open('/proc/net/if_inet6'):
            address,index,prefix,scope,flag,name=line.split()
            addr=socket.inet_ntop(socket.AF_INET6,bytes.fromhex(address))
            if name in rows:rows[name]['addresses'].append(f'{addr}/{int(prefix,16)}')
    except (OSError,ValueError):pass
    return list(rows.values())

def _proc_routes():
    rows=[]
    try:
        lines=open('/proc/net/route').read().splitlines()[1:]
        for line in lines:
            parts=line.split()
            if len(parts)<8:continue
            device,destination,gateway,flags,_,_,metric,mask=parts[:8]
            ip=lambda value:socket.inet_ntoa(struct.pack('<I',int(value,16)))
            rows.append({'destination':ip(destination),'gateway':ip(gateway),'device':device,'metric':int(metric),'mask':ip(mask)})
    except (OSError,ValueError):pass
    return rows

def _proc_listening_ports():
    rows=[]
    for family in ('tcp','tcp6','udp','udp6'):
        try:lines=open(f'/proc/net/{family}').read().splitlines()[1:]
        except OSError:continue
        for line in lines:
            parts=line.split()
            if len(parts)<4:continue
            address,port=parts[1].split(':')
            if family.startswith('tcp') and parts[3]!='0A':continue
            if int(port,16)==0:continue
            if family.endswith('6'):host='['+address+']'
            else:
                try:host=socket.inet_ntoa(struct.pack('<I',int(address,16)))
                except (OSError,ValueError):host=address
            rows.append({'protocol':family.upper(),'state':'LISTEN' if family.startswith('tcp') else 'BOUND','local_address':f'{host}:{int(port,16)}','process':''})
    return rows
def diagnose():
    result={'interfaces':None,'routes':None,'dns':dns_config(),'gateway_test':None,'dns_test':None}
    for key,fn in [('interfaces',interfaces),('routes',routes)]:
        try: result[key]=fn()
        except (OSError,RuntimeError,subprocess.TimeoutExpired) as e: result[key]={'error':str(e)}
    try: result['dns_test']=resolve('example.com')
    except OSError as e: result['dns_test']={'error':str(e)}
    try:
        route=_run(['ip','route','show','default']).split()
        gw=route[2] if len(route)>2 and route[0]=='default' else None
        result['gateway_test']=tcp_test(gw,53) if gw else {'error':'No default gateway found'}
    except Exception as e: result['gateway_test']={'error':str(e)}
    return result

def public_ip():
    """Get public IP address using external services."""
    services = [
        'https://api.ipify.org',
        'https://ifconfig.me/ip',
        'https://icanhazip.com'
    ]
    
    for service in services:
        try:
            import urllib.request
            with urllib.request.urlopen(service, timeout=5) as response:
                ip = response.read().decode().strip()
                if ip:
                    return {'public_ip': ip, 'source': service}
        except Exception:
            continue
    
    return {'error': 'Could not retrieve public IP from any service'}

def ping(host, count=4, timeout=2):
    """Ping a host with ICMP packets."""
    if not shutil.which('ping'):
        raise FileNotFoundError('ping command is not available')
    
    cmd = ['ping', '-c', str(count), '-W', str(timeout), host]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    
    output = result.stdout
    stats = {}
    
    try:
        lines = output.splitlines()
        for line in lines:
            if 'packets transmitted' in line:
                parts = line.split(',')
                for part in parts:
                    if 'received' in part:
                        stats['received'] = int(part.strip().split()[0])
                    if 'packet loss' in part:
                        stats['loss_percent'] = float(part.strip().split()[0])
            if 'rtt min/avg/max/mdev' in line or 'rtt min/avg/max' in line:
                rtt_line = line.split('=')[1].strip()
                rtt_parts = rtt_line.split('/')
                stats['rtt_min'] = float(rtt_parts[0])
                stats['rtt_avg'] = float(rtt_parts[1])
                stats['rtt_max'] = float(rtt_parts[2])
    except (IndexError, ValueError):
        pass
    
    return {
        'host': host,
        'exit_code': result.returncode,
        'stats': stats,
        'output': output[:1000]
    }

def traceroute(host, max_hops=30):
    """Trace route to a host."""
    if not shutil.which('traceroute'):
        raise FileNotFoundError('traceroute is not available')
    
    cmd = ['traceroute', '-m', str(max_hops), host]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    
    hops = []
    for line in result.stdout.splitlines():
        if line and not line.startswith('traceroute to'):
            parts = line.split()
            if parts and parts[0].isdigit():
                hops.append({'hop': int(parts[0]), 'line': line})
    
    return {
        'host': host,
        'exit_code': result.returncode,
        'hops': hops,
        'output': result.stdout
    }

def http_request(url, method='GET', headers=None, data=None, timeout=10):
    """Make an HTTP request."""
    import urllib.request
    import urllib.parse
    
    if headers is None:
        headers = {}
    
    if data:
        data = urllib.parse.urlencode(data).encode() if isinstance(data, dict) else data.encode()
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return {
                'url': url,
                'status_code': response.status,
                'headers': dict(response.headers),
                'body': response.read(100000).decode(errors='replace')
            }
    except urllib.error.HTTPError as e:
        return {
            'url': url,
            'status_code': e.code,
            'error': str(e),
            'body': e.read(100000).decode(errors='replace') if hasattr(e, 'read') else None
        }
    except urllib.error.URLError as e:
        return {'url': url, 'error': str(e)}
    except Exception as e:
        return {'url': url, 'error': str(e)}

def speed_test(server=None):
    """Basic network speed test using speedtest-cli if available."""
    if not shutil.which('speedtest-cli'):
        raise FileNotFoundError('speedtest-cli is not installed. Install with: sudo apt install speedtest-cli')
    
    cmd = ['speedtest-cli', '--json']
    if server:
        cmd.extend(['--server', server])
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'speedtest-cli failed')
    
    try:
        import json
        data = json.loads(result.stdout)
        return {
            'download_mbps': data.get('download') / 1_000_000 if data.get('download') else None,
            'upload_mbps': data.get('upload') / 1_000_000 if data.get('upload') else None,
            'ping_ms': data.get('ping'),
            'server': data.get('server', {}).get('name')
        }
    except (json.JSONDecodeError, AttributeError):
        return {'raw_output': result.stdout}

def firewall_status():
    """Check firewall status (iptables, ufw, or firewalld)."""
    status = {'active': False, 'type': None, 'rules': []}
    
    if shutil.which('ufw'):
        status['type'] = 'ufw'
        try:
            result = subprocess.run(['ufw', 'status'], capture_output=True, text=True, timeout=10)
            status['active'] = 'Status: active' in result.stdout
            status['output'] = result.stdout
        except subprocess.TimeoutExpired:
            pass
    
    elif shutil.which('firewall-cmd'):
        status['type'] = 'firewalld'
        try:
            result = subprocess.run(['firewall-cmd', '--state'], capture_output=True, text=True, timeout=10)
            status['active'] = result.returncode == 0
            status['output'] = result.stdout
        except subprocess.TimeoutExpired:
            pass
    
    elif shutil.which('iptables'):
        status['type'] = 'iptables'
        try:
            result = subprocess.run(['iptables', '-L', '-n'], capture_output=True, text=True, timeout=10)
            status['output'] = result.stdout
            status['active'] = len(result.stdout.splitlines()) > 3
        except subprocess.TimeoutExpired:
            pass
    
    return status

def vpn_status():
    """Check VPN connection status."""
    vpn_info = {'connected': False, 'type': None, 'details': {}}
    
    if shutil.which('nmcli'):
        try:
            result = subprocess.run(['nmcli', 'connection', 'show', '--active'], 
                                  capture_output=True, text=True, timeout=10)
            for line in result.stdout.splitlines():
                if 'vpn' in line.lower() or 'tun' in line.lower() or 'tap' in line.lower():
                    vpn_info['connected'] = True
                    vpn_info['type'] = 'NetworkManager'
                    vpn_info['details']['connection'] = line
                    break
        except subprocess.TimeoutExpired:
            pass
    
    if not vpn_info['connected']:
        try:
            for interface in os.listdir('/sys/class/net'):
                if interface.startswith(('tun', 'tap', 'wg')):
                    vpn_info['connected'] = True
                    vpn_info['type'] = 'kernel'
                    vpn_info['details']['interface'] = interface
                    break
        except OSError:
            pass
    
    return vpn_info

"""Ampliación de networking.py: diagnóstico, Wi-Fi, DNS y servidores locales bajo demanda.

Pega al final de tu networking.py (incluye sus imports) o importa con
``from .networking_extra import *``. Registra EXTRA_OPERATIONS como ``networking.<nombre>``.
Los servidores HTTP se levantan en 127.0.0.1 salvo que se pida explícitamente otra interfaz.
"""
import ipaddress
import json
import os
import re
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------- utilidades
def _xrun(args, timeout=10, check=True):
    exe = shutil.which(args[0])
    if not exe:
        raise FileNotFoundError(f"Falta la utilidad '{args[0]}'")
    p = subprocess.run([exe, *map(str, args[1:])], capture_output=True, text=True, timeout=timeout)
    if check and p.returncode:
        raise RuntimeError((p.stderr or p.stdout).strip() or f'{args[0]} terminó con código {p.returncode}')
    return p.stdout.strip()


def _read(path, default=''):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return default


_HOST = re.compile(r'^[A-Za-z0-9]([A-Za-z0-9.\-]{0,251}[A-Za-z0-9])?$|^[0-9a-fA-F:]+$')


def _host(value):
    value = str(value).strip()
    if not _HOST.match(value) or value.startswith('-'):
        raise ValueError(f'Host no válido: {value!r}')
    return value


def _url(value):
    value = str(value).strip()
    if not re.match(r'^https?://[^\s]+$', value):
        raise ValueError('La URL debe empezar por http:// o https://')
    return value


# ------------------------------------------------------ estado de la red
def default_gateway():
    for line in _read('/proc/net/route').splitlines()[1:]:
        p = line.split()
        if len(p) > 3 and p[1] == '00000000' and int(p[3], 16) & 2:
            gw = socket.inet_ntoa(bytes.fromhex(p[2])[::-1])
            return {'gateway': gw, 'interface': p[0]}
    return {'gateway': None, 'reason': 'No hay puerta de enlace predeterminada'}


def dns_servers():
    servers = [l.split()[1] for l in _read('/etc/resolv.conf').splitlines() if l.startswith('nameserver') and len(l.split()) > 1]
    info = {'resolv_conf': servers}
    if shutil.which('resolvectl'):
        info['resolvectl'] = [l.strip() for l in _xrun(['resolvectl', 'status'], check=False).splitlines()
                              if 'DNS Server' in l or 'Current DNS' in l][:6]
    return info


def mac_addresses():
    base = Path('/sys/class/net')
    return [{'interface': p.name, 'mac': _read(p / 'address'), 'mtu': _read(p / 'mtu')} for p in sorted(base.iterdir())] if base.is_dir() else []


def link_speed():
    rows = []
    for p in sorted(Path('/sys/class/net').iterdir()):
        if p.name == 'lo':
            continue
        speed = _read(p / 'speed')
        rows.append({'interface': p.name, 'link': 'up' if _read(p / 'carrier') == '1' else 'down',
                     'speed_mbps': int(speed) if speed.lstrip('-').isdigit() and int(speed) > 0 else None,
                     'duplex': _read(p / 'duplex') or None})
    return rows


def interface_stats():
    rows = []
    for line in _read('/proc/net/dev').splitlines()[2:]:
        name, _, rest = line.partition(':')
        p = rest.split()
        if len(p) >= 16:
            rows.append({'interface': name.strip(), 'rx_mib': round(int(p[0]) / 1024 ** 2, 2), 'tx_mib': round(int(p[8]) / 1024 ** 2, 2),
                         'rx_errors': int(p[2]), 'tx_errors': int(p[10]), 'rx_dropped': int(p[3]), 'tx_dropped': int(p[11])})
    return rows


def arp_table():
    """Dispositivos vistos en tu red local (solo lectura, sin escanear)."""
    try:
        return _xrun(['ip', 'neigh', 'show']).splitlines()
    except (FileNotFoundError, RuntimeError):
        return [l for l in _read('/proc/net/arp').splitlines()[1:]]


def hosts_file():
    return [l for l in _read('/etc/hosts').splitlines() if l.strip() and not l.lstrip().startswith('#')]


def network_connections(state='established', limit=50):
    state = state if state in {'established', 'listening', 'time-wait', 'syn-sent', 'close-wait', 'all'} else 'established'
    flag = ['-l'] if state == 'listening' else []
    filt = [] if state in {'all', 'listening'} else ['state', state]
    out = _xrun(['ss', '-H', '-tnp', *flag, *filt], check=False).splitlines()
    return {'total': len(out), 'connections': out[:max(1, min(int(limit), 300))]}


def connection_summary():
    return _xrun(['ss', '-s']).splitlines()


def network_manager_connections():
    return _xrun(['nmcli', '-t', '-f', 'NAME,TYPE,DEVICE,STATE', 'connection', 'show']).splitlines()


# -------------------------------------------------------------- DNS y latencia
def dns_lookup(host, record='A'):
    host = _host(host)
    record = str(record).upper()
    if record in {'A', 'AAAA'}:
        family = socket.AF_INET if record == 'A' else socket.AF_INET6
        return {'host': host, 'record': record, 'answers': sorted({x[4][0] for x in socket.getaddrinfo(host, None, family)})}
    if record not in {'MX', 'TXT', 'NS', 'CNAME', 'SOA', 'PTR', 'SRV', 'CAA'}:
        raise ValueError('Tipo de registro no soportado')
    tool = next((c for c in (['dig', '+short', host, record], ['host', '-t', record, host], ['nslookup', f'-type={record}', host])
                 if shutil.which(c[0])), None)
    if not tool:
        raise FileNotFoundError('Instala dig (dnsutils/bind-utils) para consultar registros ' + record)
    return {'host': host, 'record': record, 'answers': _xrun(tool, timeout=15, check=False).splitlines()}


def reverse_dns(ip):
    ip = str(ipaddress.ip_address(str(ip).strip()))
    try:
        name, aliases, _ = socket.gethostbyaddr(ip)
        return {'ip': ip, 'name': name, 'aliases': aliases}
    except OSError as exc:
        return {'ip': ip, 'name': None, 'error': str(exc)}


def _tcp_time(host, port, timeout=3):
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return round((time.perf_counter() - start) * 1000, 1)
    except OSError:
        return None


def latency_check(hosts=None):
    targets = hosts or [('1.1.1.1', 443), ('8.8.8.8', 53), ('9.9.9.9', 443), ('google.com', 443)]
    return [{'host': h, 'port': p, 'ms': _tcp_time(h, p), 'reachable': _tcp_time(h, p, 1) is not None} for h, p in targets]


def check_internet():
    tests = [_tcp_time('1.1.1.1', 443), _tcp_time('8.8.8.8', 53)]
    try:
        dns_ok = bool(socket.getaddrinfo('example.com', 443))
    except OSError:
        dns_ok = False
    ip_ok = any(t is not None for t in tests)
    verdict = ('Conectado' if ip_ok and dns_ok else 'Hay conexión pero falla el DNS' if ip_ok
               else 'Sin salida a Internet' if default_gateway().get('gateway') else 'Sin red: no hay puerta de enlace')
    return {'verdict': verdict, 'ip_connectivity': ip_ok, 'dns': dns_ok, 'latency_ms': [t for t in tests if t is not None]}


def bandwidth_now(interval=1.0):
    interval = max(0.2, min(float(interval), 5))
    def read():
        return {r['interface']: (r['rx_mib'], r['tx_mib']) for r in interface_stats()}
    a = read(); time.sleep(interval); b = read()
    return {n: {'down_mbit_s': round((b[n][0] - a[n][0]) * 8 / interval, 2), 'up_mbit_s': round((b[n][1] - a[n][1]) * 8 / interval, 2)}
            for n in b if n in a and n != 'lo'}


# ------------------------------------------------------------ web y TLS
def check_site_up(url):
    url = _url(url)
    req = urllib.request.Request(url, headers={'User-Agent': 'llmah/1.0'})
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return {'url': url, 'up': True, 'status': r.status, 'ms': round((time.perf_counter() - start) * 1000), 'final_url': r.geturl()}
    except urllib.error.HTTPError as exc:
        return {'url': url, 'up': exc.code < 500, 'status': exc.code, 'ms': round((time.perf_counter() - start) * 1000)}
    except (urllib.error.URLError, OSError) as exc:
        return {'url': url, 'up': False, 'error': str(getattr(exc, 'reason', exc))}


def http_headers(url):
    url = _url(url)
    req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'llmah/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return {'url': url, 'status': r.status, 'headers': dict(r.headers)}
    except urllib.error.HTTPError as exc:
        return {'url': url, 'status': exc.code, 'headers': dict(exc.headers)}


def ssl_expiry(host, port=443):
    host = _host(host)
    ctx = ssl.create_default_context()
    with socket.create_connection((host, int(port)), timeout=8) as raw, ctx.wrap_socket(raw, server_hostname=host) as tls:
        cert = tls.getpeercert()
    expires = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z').replace(tzinfo=timezone.utc)
    days = (expires - datetime.now(timezone.utc)).days
    issuer = dict(x[0] for x in cert.get('issuer', ()))
    return {'host': host, 'expires': expires.date().isoformat(), 'days_left': days,
            'issuer': issuer.get('organizationName') or issuer.get('commonName'), 'status': 'ok' if days > 14 else 'renovar pronto'}


# ------------------------------------------------------------ Wi-Fi y redes
def wifi_status():
    return _xrun(['nmcli', '-t', '-f', 'DEVICE,TYPE,STATE,CONNECTION', 'device']).splitlines()


def wifi_networks(limit=20):
    out = _xrun(['nmcli', '-t', '-f', 'IN-USE,SSID,SIGNAL,SECURITY,CHAN', 'device', 'wifi', 'list'], timeout=20).splitlines()
    rows = []
    for line in out:
        use, ssid, signal_, sec, chan = (line.replace('\\:', '\0').split(':') + [''] * 5)[:5]
        if ssid:
            rows.append({'connected': use.strip() == '*', 'ssid': ssid.replace('\0', ':'), 'signal': signal_, 'security': sec or 'abierta', 'channel': chan})
    return sorted(rows, key=lambda r: int(r['signal'] or 0), reverse=True)[:max(1, min(int(limit), 60))]


def wifi_toggle(on=True):
    _xrun(['nmcli', 'radio', 'wifi', 'on' if on else 'off'])
    return {'wifi': 'encendido' if on else 'apagado'}


def network_restart():
    _xrun(['nmcli', 'networking', 'off'], timeout=20)
    time.sleep(1)
    _xrun(['nmcli', 'networking', 'on'], timeout=20)
    return {'status': 'red reiniciada'}


def flush_dns():
    tool = next((c for c in (['resolvectl', 'flush-caches'], ['systemd-resolve', '--flush-caches'], ['nscd', '-i', 'hosts'])
                 if shutil.which(c[0])), None)
    if not tool:
        raise FileNotFoundError('No encontré resolvectl, systemd-resolve ni nscd')
    _xrun(tool)
    return {'status': 'caché DNS vaciada'}


def firewall_rules():
    tool = next((c for c in (['ufw', 'status', 'numbered'], ['nft', 'list', 'ruleset'], ['iptables', '-S']) if shutil.which(c[0])), None)
    if not tool:
        raise FileNotFoundError('No encontré ufw, nft ni iptables')
    return _xrun(tool, check=False).splitlines()[:120] or ['(vacío o requiere permisos de administrador)']


def network_summary():
    return {'internet': check_internet(), 'gateway': default_gateway(), 'dns': dns_servers(),
            'interfaces': interface_stats(), 'links': link_speed()}


# -------------------------------------------------- quién usa un puerto
def who_uses_port(port):
    port = int(port)
    if not 1 <= port <= 65535:
        raise ValueError('El puerto debe estar entre 1 y 65535')
    out = _xrun(['ss', '-H', '-lntup', f'sport = :{port}'], check=False)
    return {'port': port, 'in_use': bool(out), 'listeners': out.splitlines()}


def port_check_local(port):
    port = int(port)
    return {'port': port, 'listening': _tcp_time('127.0.0.1', port, 1) is not None}


# ====================================================================
# Servidores locales bajo demanda ("levanta un servidor")
# ====================================================================
_REGISTRY = Path.home() / '.cache' / 'llmah' / 'servers.json'


def _load_registry():
    try:
        return json.loads(_REGISTRY.read_text())
    except (OSError, ValueError):
        return []


def _save_registry(items):
    _REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    _REGISTRY.write_text(json.dumps(items, indent=2))


def _alive(pid):
    try:
        os.kill(pid, 0)
        return Path(f'/proc/{pid}/stat').read_text().split(')')[-1].split()[0] != 'Z'
    except (OSError, IndexError):
        return False


def _lan_address():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('192.0.2.1', 9))
            return s.getsockname()[0]
    except OSError:
        return None


def start_http_server(directory='.', port=8000, bind='127.0.0.1', kind='python'):
    """Levanta un servidor de archivos estáticos (python -m http.server o php -S) en segundo plano."""
    port = int(port)
    if not 1 <= port <= 65535:
        raise ValueError('El puerto debe estar entre 1 y 65535')
    if port < 1024 and os.geteuid() != 0:
        raise PermissionError(f'El puerto {port} es privilegiado; usa uno >= 1024 (por ejemplo 8000) o ejecuta como root')
    bind = str(ipaddress.ip_address(bind))
    folder = Path(directory).expanduser().resolve()
    if not folder.is_dir():
        raise FileNotFoundError(f'La carpeta {folder} no existe')
    if _tcp_time('127.0.0.1', port, 0.5) is not None:
        try:
            owner = who_uses_port(port)['listeners'][:1]
        except (FileNotFoundError, RuntimeError):
            owner = 'no pude identificar el proceso (falta ss)'
        raise RuntimeError(f'El puerto {port} ya está en uso: {owner}')
    if kind == 'php':
        if not shutil.which('php'):
            raise FileNotFoundError('PHP no está instalado (sudo apt install php-cli)')
        cmd = [shutil.which('php'), '-S', f'{bind}:{port}', '-t', str(folder)]
    else:
        kind = 'python'
        cmd = [sys.executable, '-m', 'http.server', str(port), '--bind', bind, '--directory', str(folder)]
    _REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    log = _REGISTRY.parent / f'server-{port}.log'
    with open(log, 'ab') as fh:
        proc = subprocess.Popen(cmd, stdout=fh, stderr=fh, stdin=subprocess.DEVNULL, start_new_session=True)
    time.sleep(0.6)
    if proc.poll() is not None:
        raise RuntimeError('El servidor se cerró al arrancar: ' + log.read_text(errors='replace')[-300:])
    items = [i for i in _load_registry() if _alive(i['pid'])]
    items.append({'pid': proc.pid, 'port': port, 'bind': bind, 'directory': str(folder), 'kind': kind,
                  'started': datetime.now().isoformat(timespec='seconds'), 'log': str(log)})
    _save_registry(items)
    host = 'localhost' if bind in {'127.0.0.1', '::1'} else (_lan_address() if bind == '0.0.0.0' else bind)
    result = {'status': 'servidor en marcha', 'url': f'http://{host}:{port}', 'pid': proc.pid, 'directory': str(folder), 'kind': kind}
    if bind == '0.0.0.0':
        result['aviso'] = 'Es accesible desde toda tu red local; páralo cuando termines.'
    return result


def list_local_servers():
    items = [i for i in _load_registry() if _alive(i['pid'])]
    _save_registry(items)
    return items or {'servers': [], 'note': 'No hay servidores HTTP levantados por el asistente'}


def stop_http_server(port=None, pid=None):
    items = [i for i in _load_registry() if _alive(i['pid'])]
    if port is None and pid is None:
        if len(items) != 1:
            raise ValueError('Indica el puerto del servidor a detener' if items else 'No hay servidores levantados por el asistente')
        target = items[0]
    else:
        target = next((i for i in items if (port is not None and i['port'] == int(port)) or (pid is not None and i['pid'] == int(pid))), None)
        if not target:
            raise LookupError('No encontré un servidor levantado por el asistente con ese puerto o PID '
                              '(para servicios del sistema usa "detén nginx").')
    os.killpg(os.getpgid(target['pid']), signal.SIGTERM)
    _save_registry([i for i in items if i['pid'] != target['pid']])
    return {'status': 'servidor detenido', 'port': target['port'], 'pid': target['pid']}


def stop_all_http_servers():
    items = [i for i in _load_registry() if _alive(i['pid'])]
    for i in items:
        os.killpg(os.getpgid(i['pid']), signal.SIGTERM)
    _save_registry([])
    return {'detenidos': [i['port'] for i in items]}


EXTRA_OPERATIONS = {
    'default_gateway': default_gateway, 'dns_servers': dns_servers, 'mac_addresses': mac_addresses, 'link_speed': link_speed,
    'interface_stats': interface_stats, 'arp_table': arp_table, 'hosts_file': hosts_file,
    'network_connections': network_connections, 'connection_summary': connection_summary,
    'network_manager_connections': network_manager_connections, 'dns_lookup': dns_lookup, 'reverse_dns': reverse_dns,
    'latency_check': latency_check, 'check_internet': check_internet, 'bandwidth_now': bandwidth_now,
    'check_site_up': check_site_up, 'http_headers': http_headers, 'ssl_expiry': ssl_expiry, 'wifi_status': wifi_status,
    'wifi_networks': wifi_networks, 'wifi_toggle': wifi_toggle, 'network_restart': network_restart,
    'flush_dns': flush_dns, 'firewall_rules': firewall_rules, 'network_summary': network_summary,
    'who_uses_port': who_uses_port, 'port_check_local': port_check_local, 'start_http_server': start_http_server,
    'list_local_servers': list_local_servers, 'stop_http_server': stop_http_server,
    'stop_all_http_servers': stop_all_http_servers,
}