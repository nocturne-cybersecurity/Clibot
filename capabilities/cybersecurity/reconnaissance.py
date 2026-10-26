"""Scope parsing and DNS reconnaissance primitives."""
import ipaddress, socket, json, threading
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
def normalize_target(value):
    try:return str(ipaddress.ip_network(value,strict=False) if '/' in value else ipaddress.ip_address(value))
    except ValueError:
        if not value or len(value)>253 or any(not x or len(x)>63 for x in value.rstrip('.').split('.')):raise ValueError('Invalid target syntax')
        return value.rstrip('.').encode('idna').decode('ascii').lower()
def resolve(host, timeout=5):
    """Resolve a host. libc getaddrinfo has no timeout and can stall for minutes."""
    normalized = normalize_target(host)
    box = {}
    def work():
        try: box['value'] = socket.getaddrinfo(normalized, None)
        except Exception as exc: box['error'] = exc
    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    thread.join(max(0.3, min(float(timeout), 8)))
    if thread.is_alive():
        raise TimeoutError(f'La resolución DNS de {normalized} superó {min(float(timeout), 8):g}s.')
    if 'error' in box:
        raise box['error']
    return sorted({item[4][0] for item in box['value']})

def whois_lookup(target, timeout=12):
    """Look up public registration data through RDAP without a whois binary."""
    normalized = normalize_target(target)
    try:
        ipaddress.ip_address(normalized)
        kind = 'ip'
    except ValueError:
        kind = 'domain'
    request = Request(f'https://rdap.org/{kind}/{quote(normalized, safe=".:-")}',
                      headers={'Accept': 'application/rdap+json', 'User-Agent': 'LLMAH/0.2'})
    try:
        with urlopen(request, timeout=max(1, min(int(timeout), 20))) as response:
            data = json.loads(response.read(1_000_001).decode('utf-8'))
    except HTTPError as exc:
        raise RuntimeError(f'El servicio RDAP respondió HTTP {exc.code} para {normalized}.') from exc
    except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError(f'No pude consultar el registro público de {normalized}: {exc}') from exc
    if not isinstance(data, dict):
        raise RuntimeError('La respuesta RDAP no tenía el formato esperado.')
    names = []
    for entity in data.get('entities', []):
        for item in entity.get('vcardArray', [None, []])[1] if isinstance(entity.get('vcardArray'), list) else []:
            if isinstance(item, list) and len(item) > 3 and item[0] == 'fn':
                names.append(item[3])
    return {'target': normalized, 'type': kind,
            'name': data.get('name') or data.get('ldhName') or data.get('handle'),
            'network': data.get('cidr0_cidrs') or data.get('startAddress'),
            'status': data.get('status', []), 'entities': sorted(set(names)),
            'source': 'RDAP', 'disclaimer': 'Datos públicos de registro; no equivalen a geolocalización ni identifican necesariamente al usuario final.'}
