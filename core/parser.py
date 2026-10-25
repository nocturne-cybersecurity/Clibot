"""Deterministic Spanish and English request interpretation.

El parser es una *tabla de reglas* evaluada en orden (la primera que coincide
gana). Cada regla lleva ejemplos; ``tests/test_parser_rules.py`` comprueba que
todas son alcanzables, así una regla nueva no puede tapar a otra sin avisar.

Las listas grandes (sitios, apps, servicios, typos) viven en ``parser_data.py``.
"""
import re
import unicodedata
import shutil
from difflib import get_close_matches
from collections import namedtuple
from pathlib import Path
from urllib.parse import quote

from core.contracts import Operation, Plan, Risk
from intelligence.intent_registry import intent_registry
from intelligence.intents import load as load_intent_plugins

from .parser_data import (
    WEB_SERVICES, SITE_SEARCH, APP_ALIASES, TERMINAL_TOOLS, SYSTEM_SERVICES, SERVICE_WORDS,
    SERVICE_NAME_MAP, SERVER_DAEMONS, TYPO_TERMS, WORD_FIXES, NUMBER_WORDS)

UNRECOGNIZED = ('No reconocí una tarea compatible todavía. Escribe /help para ver ejemplos '
                'o /capabilities para consultar lo que puedo hacer.')

# Nombres que ya existían en el módulo original (se conservan por compatibilidad):
SITES = WEB_SERVICES                       # sitio → URL
KNOWN_SERVICES = SYSTEM_SERVICES           # demonios de systemd (antes una tupla pisaba al dict de sitios)
APPS = tuple(sorted(APP_ALIASES, key=len, reverse=True))
LOCAL_HOSTS = {'localhost', '127.0.0.1', '::1', '0.0.0.0'}
NAME_STOPWORDS = r'(?:en|de|con|que|para|vacio|nuevo|nueva|llamado|llamada|el|la|un|una|python)'
FILE_EXT = r'[\w.-]+\.(?:txt|md|pdf|py|log|json|yaml|yml|csv)'

# Alias de aplicación que se buscan dentro de frases largas; los genéricos solo valen como frase completa.
_GENERIC_APP_WORDS = {'archivos', 'fuentes', 'contactos', 'reloj', 'relojes', 'ajustes', 'discos', 'llaves', 'builder', 'writer',
                      'micro', 'foot', 'kitty', 'files', 'settings', 'calc', 'impress', 'zed', 'tor', 'ida', 'box', 'cura',
                      'element', 'signal', 'bottles', 'peek', 'albert', 'cursor', 'helix', 'atom', 'caja', 'discover', 'plex',
                      'elementos', 'reloj', 'zap', 'burp', 'cutter', 'ardour', 'kate', 'rofi', 'obs', 'mpv', 'kodi', 'steam'}
_BASE_APPS = {'metasploit', 'msfconsole', 'firefox', 'chromium', 'chrome', 'google chrome', 'visual studio code', 'vscode',
              'code', 'terminal', 'consola', 'navegador', 'browser', 'editor', 'pycharm', 'pycharm community',
              'pycharm professional', 'software', 'gnome software', 'centro de software', 'software center', 'mapa',
              'mapas', 'maps', 'gnome maps', 'calculadora', 'calculator', 'gemini', 'gemini cli', 'gemini-cli'}
APP_ALIASES.setdefault('gemini', 'gemini_cli')
_SENTENCE_APPS = tuple(a for a in APPS if a in _BASE_APPS or (len(a) >= 5 and a not in _GENERIC_APP_WORDS))
_SITE_SENTENCE = tuple(sorted((n for n in WEB_SERVICES if len(n) >= 5), key=len, reverse=True))
_SEARCH_SITES = '|'.join(re.escape(n) for n in sorted(SITE_SEARCH, key=len, reverse=True))
_OPEN_VERBS = r'(?:abrir?|abre|abro|open|launch|ir a|ve a|entra a|entra en|navega a|visita|llevame a|go to)'
_SERVICE_RX = re.compile(r'(?<![\w.@-])(' + '|'.join(re.escape(n) for n in sorted(set(KNOWN_SERVICES), key=len, reverse=True)) + r')(?![\w@-])', re.I)
_SERVICE_CANON = {n.lower(): n for n in KNOWN_SERVICES}
_DAEMON_RX = re.compile(r'(?<![\w.@-])(' + '|'.join(re.escape(n) for n in sorted(set(SERVER_DAEMONS), key=len, reverse=True)) + r')(?![\w@-])', re.I)
_FILE_TLDS = {'txt', 'md', 'pdf', 'py', 'log', 'json', 'yaml', 'yml', 'csv', 'sh', 'conf', 'db', 'zip', 'tar', 'gz', 'png',
              'jpg', 'jpeg', 'gif', 'html', 'css', 'js', 'c', 'cpp', 'h', 'ini', 'cfg', 'xml', 'sql', 'bak', 'tmp', 'pem', 'key'}


def command_exists(cmd):
    """Verifica si un comando existe en el sistema."""
    return shutil.which(cmd) is not None


def find_close_match(input_text, candidates, cutoff=0.8):
    """Encuentra coincidencias cercanas usando fuzzy matching."""
    if not candidates:
        return None
    matches = get_close_matches(input_text, list(candidates), n=1, cutoff=cutoff)
    return matches[0] if matches else None


def suggest_correction(site_name):
    """Sugiere una corrección para un nombre mal escrito (sitio o aplicación)."""
    if len(site_name) < 4 or site_name in WEB_SERVICES or site_name in APP_ALIASES:
        return None, None
    for correct, typos in TYPO_TERMS.items():
        if site_name in typos:
            kind = 'web' if correct in WEB_SERVICES else 'app' if correct in APP_ALIASES else None
            if kind:
                return correct, kind
    web_match = find_close_match(site_name, WEB_SERVICES.keys())
    if web_match:
        return web_match, 'web'
    app_match = find_close_match(site_name, APP_ALIASES.keys())
    if app_match:
        return app_match, 'app'
    return None, None


def suggest_search_correction(query):
    """Sugiere correcciones para consultas de búsqueda de una sola palabra."""
    query_lower = query.lower().strip()
    if ' ' in query_lower or len(query_lower) < 4:
        return None
    for correct_term, typos in TYPO_TERMS.items():
        if query_lower in typos:
            return correct_term
    if query_lower in TYPO_TERMS:
        return None
    return find_close_match(query_lower, TYPO_TERMS.keys(), cutoff=0.84)


def normalize(text):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', text.lower())
                            if not unicodedata.combining(c)).split())


_FILLER_RX = re.compile(
    r'(?i)^\s*(?:(?:oye|hey|hola|ok|okay|bueno|asistente|llmah|por favor|porfa|porfis|please|podrias|podr[ií]as|puedes|puede|'
    r'me puedes|me podr[ií]as|me podrias|quiero que|necesito que|me gustar[ií]a que|quisiera que|ay[uú]dame a|ayudame a|'
    r'dime si puedes|favor de|a ver|entonces|pues|mira|dale|vamos a)\b[\s,.:;!¡-]*)+')


def _strip_fillers(text):
    cleaned = _FILLER_RX.sub('', text, count=1)
    return cleaned if cleaned.strip() else text


def _fix_words(s):
    out = []
    for word in s.split():
        out.append(word if re.search(r'[/.@:~\\]', word) else WORD_FIXES.get(word, word))
    return ' '.join(out)


_NUM_SKIP = {'una', 'uno', 'un'}


def _num_words(s):
    """Sustituye «treinta y cinco» → 35, «ocho mil» → 8000 solo cuando una regla lo pide."""
    tokens, out, i = s.split(), [], 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in NUMBER_WORDS and tok not in _NUM_SKIP:
            total, current = 0, 0
            while i < len(tokens):
                t = tokens[i]
                if t in NUMBER_WORDS and t not in _NUM_SKIP:
                    value = NUMBER_WORDS[t]
                    if value == 1000:
                        total += (current or 1) * 1000
                        current = 0
                    else:
                        current += value
                    i += 1
                elif t == 'y' and i + 1 < len(tokens) and tokens[i + 1] in NUMBER_WORDS and current % 10 == 0 and current:
                    i += 1
                else:
                    break
            out.append(str(total + current))
        else:
            out.append(tok)
            i += 1
    return ' '.join(out)


# --------------------------------------------------------------------------
# Constructores de planes
# --------------------------------------------------------------------------
def _op(cap, name, args=None, risk=Risk.READ_ONLY, desc='', timeout=None):
    operation = Operation(cap, name, args or {}, desc or f'{cap}.{name}', risk=risk)
    if timeout is not None:
        operation.timeout = timeout
    return operation


def _plan(text, *ops):
    return Plan(list(ops), text)


def _ask(text, message):
    return Plan([], text, message)


def _unknown(text):
    return Plan([], text, UNRECOGNIZED, unrecognized=True)


def _simple(cap, name, desc='', risk=Risk.READ_ONLY, args=None, timeout=None):
    return lambda s, text, ctx: _plan(text, _op(cap, name, dict(args or {}), risk, desc, timeout))


# --------------------------------------------------------------------------
# Predicados
# --------------------------------------------------------------------------
def _rx(pattern, flags=0):
    compiled = re.compile(pattern, flags)
    return lambda s, text: bool(compiled.search(s))


def _all(*preds):
    return lambda s, text: all(p(s, text) for p in preds)


def _any(*preds):
    return lambda s, text: any(p(s, text) for p in preds)


def _not(pred):
    return lambda s, text: not pred(s, text)


# --------------------------------------------------------------------------
# Utilidades de extracción
# --------------------------------------------------------------------------
def _path(s, allow_quoted=True):
    """Ruta explícita: entre comillas, ~/..., /absoluta o ./relativa."""
    if allow_quoted:
        m = re.search(r'["\']([^"\']+)["\']', s)
        if m:
            return m.group(1)
    m = re.search(r'(?<![\w.~:/])(?:~/[^\s,;]*|~(?=\s|$)|/[^\s,;]+|\.\.?/[^\s,;]+)', s)
    return m.group(0) if m else None


def _path_or_name(text):
    """Ruta explícita o, si no hay, un nombre de archivo/carpeta suelto («hola.py», «carpeta docs»)."""
    explicit = _path(text)
    if explicit:
        return explicit
    m = re.search(r'\b' + FILE_EXT + r'\b', text, re.I)
    if m:
        return m.group(0)
    m = re.search(r'(?i)\b(?:archivo|fichero|file|carpeta|directorio|folder|directory)\s+(?:vacio\s+)?(?:llamad[ao]\s+)?["\']?(?!' + NAME_STOPWORDS + r'\b)([\w.-]+)', text)
    return m.group(1) if m else None


def _service_name(text):
    m = _SERVICE_RX.search(text)
    if m:
        word = m.group(1).lower()
        return SERVICE_NAME_MAP.get(word, _SERVICE_CANON.get(word, word))
    match = re.search(r'(?i)\bservicio\s+([\w@.-]+)', text)
    return match.group(1) if match else None


def _daemon_name(text):
    m = _DAEMON_RX.search(text)
    if not m:
        return None
    word = m.group(1).lower()
    return SERVICE_NAME_MAP.get(word, _SERVICE_CANON.get(word, word))


def _target(s):
    m = re.search(r'\b(?:a|contra|sobre|target|host)\s+([\w.-]+(?:/\d+)?)', s)
    if m:
        return m.group(1)
    m = re.search(r'\b(?:autorizado|authorized)\s+((?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?|[a-z0-9.-]+\.[a-z]{2,})', s, re.I)
    if m:
        return m.group(1)
    m = re.search(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?', s)
    return m.group(0) if m else None


def _looks_like_host(value):
    return bool(re.fullmatch(r'(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?|[a-z0-9-]+(?:\.[a-z0-9-]+)+', value or '', re.I))


def _is_local(value):
    return value in LOCAL_HOSTS or (value or '').startswith('127.')


def _file_name(text):
    """Nombre de archivo tras «archivo/script/doc…», ignorando palabras de relleno."""
    m = re.search(
        r'(?i)\b(?:archivo|fichero|file|script|programa|doc)\s+(?:de\s+)?(?:python\s+)?'
        r'(?:con\s+el\s+nombre\s+)?(?:llamado|llamada|que\s+se\s+llame)?\s*["\']?'
        r'(?!' + NAME_STOPWORDS + r'\b)([\w.-]+)["\']?', text)
    return m.group(1) if m else None


def _port_from(s):
    s = _num_words(s)
    m = (re.search(r'\b(?:puerto|port)\s*(?:numero\s*)?(\d{1,5})\b', s) or re.search(r':(\d{2,5})\b', s)
         or re.search(r'\ben el\s+(\d{4,5})\b', s))
    if m and 1 <= int(m.group(1)) <= 65535:
        return int(m.group(1))
    return None


def _pid_from(s):
    m = re.search(r'\b(?:pid|proceso(?:\s+numero)?)\s*(\d{1,9})\b', s) or re.search(r'\b(\d{2,9})\b', s)
    return int(m.group(1)) if m else None


def _domain_from(text):
    url = re.search(r'https?://[^\s]+', text)
    if url:
        return url.group(0).rstrip('.,;)')
    for m in re.finditer(r'(?i)(?<![\w@/.-])((?:[a-z0-9-]+\.)+([a-z]{2,}))\b', text):
        if m.group(2).lower() not in _FILE_TLDS:
            return m.group(1)
    return None


def _minutes_from(s):
    s = _num_words(s)
    m = re.search(r'\b(?:en|dentro de)\s+(\d+)\s*(segundos?|seg|minutos?|min|horas?|h)\b', s)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    return max(1, round(n / 60)) if unit.startswith('seg') else n * 60 if unit.startswith('h') else n


# --------------------------------------------------------------------------
# Constructores de reglas
# --------------------------------------------------------------------------
def build_capabilities(s, text, ctx):
    category = None
    for key, pattern in {
        'development': r'\b(desarrollo|programacion|programar|codigo|code|developer)\b',
        'filesystem': r'\b(archivos|archivo|ficheros|carpetas)\b',
        'networking': r'\b(red|redes|networking|internet|servidores)\b',
        'cybersecurity': r'\b(ciberseguridad|seguridad|auditoria|pentest)\b',
        'monitoring': r'\b(monitoreo|monitorizar|monitoring|metricas|rendimiento)\b',
        'processes': r'\b(procesos)\b',
        'services': r'\b(servicios|systemd)\b',
        'system': r'\b(sistema|linux|administracion)\b',
    }.items():
        if re.search(pattern, s):
            category = key
            break
    return _plan(text, Operation('assistant', 'capabilities', {'category': category}))


# ---- servicios y servidores -------------------------------------------------
_RE_SERVICE_NEGATIVE = (r'\b(?:sin|no|sin\s+necesidad\s+de)\b.*\b(?:reiniciar|iniciar|detener|cambiar|modificar)\b|'
                        r'\b(?:como|how)\b.*\b(?:diagnosticar|diagnosticarias|resolverias)\b')


def _service_action(s):
    if re.search(r'\b(?:deshabilita\w*|disable|inhabilita)\b|\bque no (?:inicie|arranque)\b|\bquita\b.*\bdel arranque\b', s):
        return 'disable-now' if re.search(r'\b(?:ahora|ya|tambien|y (?:detenlo|deten|apagalo))\b', s) else 'disable'
    if re.search(r'\b(?:habilita\w*|enable)\b|\bque (?:inicie|arranque) (?:con|al) (?:el )?(?:sistema|arranque|inicio)\b|\bal (?:arrancar|arranque|iniciar|encender)\b', s):
        return 'enable-now' if re.search(r'\b(?:ahora|ya|tambien|y (?:arranca|enciende|inicia|levanta)\w*|now)\b', s) else 'enable'
    if re.search(r'\b(?:reinicia\w*|restart|resetea\w*)\b', s):
        return 'restart'
    if re.search(r'\b(?:recarga\w*|reload|relee)\b', s):
        return 'reload'
    if re.search(r'\b(?:deten\w*|stop|apaga\w*|baja|bajar|desactiva\w*|parar|cierra|cerrar|mata|matar|termina\w*)\b', s):
        return 'stop'
    return 'start'


def build_service_change(s, text, ctx):
    if re.search(_RE_SERVICE_NEGATIVE, s):
        return None
    name = _service_name(s)
    if not name:
        return _ask(text, '¿Qué servicio quieres iniciar, detener, reiniciar, recargar o habilitar?')
    action = _service_action(s)
    return _plan(text, _op('services', 'change', {'name': name, 'action': action}, Risk.HIGH,
                           f'{action} del servicio {name}'))


_START_VERBS = (r'(?:levanta\w*|arranca\w*|enciende|encender|prende\w*|monta\w*|inicia\w*|lanza\w*|activa\w*|despliega\w*|'
                r'pon|ponme|abre|abrir|crea|crear|habilita\w*|start|launch|serve|sirve|servir|run)')
_STRONG_START = r'\b(?:levanta\w*|arranca\w*|enciende|encender|prende\w*|inicia\w*|lanza\w*|activa\w*|start|launch)\b'
_STOP_VERBS = r'\b(?:deten\w*|detener|apaga\w*|baja|bajar|cierra|cerrar|mata|matar|termina\w*|quita|quitar|stop|kill)\b'


def build_server_start(s, text, ctx):
    if re.search(r'\b(?:sin|no)\b\s+(?:levant|inici|arranc)', s):
        return None
    if re.search(r'\b(?:crea|crear|genera\w*)\b', s) and re.search(r'\b(?:archivo|script|programa|doc|fichero)\b', s):
        return None
    daemon = _daemon_name(s)
    generic_word = re.search(r'\b(?:servidor(?:es)?|server|webserver)\b', s)
    if daemon and (generic_word or re.search(_STRONG_START, s)):
        return _plan(text, _op('services', 'change', {'name': daemon, 'action': 'start'}, Risk.HIGH, f'start del servicio {daemon}'))
    if not generic_word:
        return None
    kind = 'php' if re.search(r'\bphp\b', s) else 'python'
    port = _port_from(s) or 8000
    wide = bool(re.search(r'\b(?:toda la red|red local|todas las interfaces|0\.0\.0\.0|publico|lan|desde otros dispositivos|accesible)\b', s))
    folder = _path(text) or '.'
    args = {'directory': folder, 'port': port, 'bind': '0.0.0.0' if wide else '127.0.0.1', 'kind': kind}
    where = 'en toda la red local' if wide else 'solo en este equipo'
    return _plan(text, _op('networking', 'start_http_server', args, Risk.HIGH if wide else Risk.MODERATE,
                           f'levantar un servidor HTTP de {folder} en el puerto {port} ({where})'))


def build_server_stop(s, text, ctx):
    daemon = _daemon_name(s)
    if daemon:
        return _plan(text, _op('services', 'change', {'name': daemon, 'action': 'stop'}, Risk.HIGH, f'stop del servicio {daemon}'))
    if re.search(r'\btodos\b', s):
        return _plan(text, _op('networking', 'stop_all_http_servers', {}, Risk.MODERATE, 'detener todos los servidores HTTP levantados'))
    port = _port_from(s)
    args = {'port': port} if port else {}
    return _plan(text, _op('networking', 'stop_http_server', args, Risk.MODERATE, 'detener el servidor HTTP levantado por el asistente'))


def build_server_list(s, text, ctx):
    return _plan(text, _op('networking', 'list_local_servers', {}, desc='listar servidores HTTP levantados'),
                 _op('networking', 'listening_ports', {}, desc='puertos en escucha'))


def _with_service(cap, name, desc, key='name', extra=None, risk=Risk.READ_ONLY, ask='¿De qué servicio?'):
    def build(s, text, ctx):
        service = _service_name(s)
        if not service:
            return _ask(text, ask)
        args = {key: service}
        args.update(extra or {})
        return _plan(text, _op(cap, name, args, risk, desc))
    return build


def build_service_deps(s, text, ctx):
    service = _service_name(s)
    if not service:
        return _ask(text, '¿De qué servicio quieres ver las dependencias?')
    return _plan(text, _op('services', 'dependencies', {'name': service, 'reverse': bool(re.search(r'\bque depende de\b|\bquien depende\b', s))}))


def build_find_service(s, text, ctx):
    m = re.search(r'\b(?:servicio|service|llame|contengan|tengan)\s+(?:llamado\s+)?([\w.@-]+)\s*$', s)
    if not m:
        return _ask(text, '¿Qué nombre (o parte) del servicio busco?')
    return _plan(text, _op('services', 'find_service', {'pattern': m.group(1)}))


def build_service_logs_since(s, text, ctx):
    service = _service_name(s)
    if not service:
        return _ask(text, '¿De qué servicio quieres los logs?')
    n = re.search(r'ultimas?\s+(\d+)\s*(minutos?|horas?|dias?)', _num_words(s))
    if n:
        since = f"{n.group(1)} {'minutes' if n.group(2).startswith('min') else 'hours' if n.group(2).startswith('hor') else 'days'} ago"
    elif re.search(r'\bayer\b', s):
        since = 'yesterday'
    elif re.search(r'\bhoy\b', s):
        since = 'today'
    else:
        since = '1 hour ago'
    args = {'name': service, 'since': since}
    if re.search(r'\berrores?\b', s):
        args['priority'] = 'err'
    return _plan(text, _op('services', 'logs_since', args, desc=f'logs de {service} desde {since}'))


# ---- abrir ------------------------------------------------------------------
def _terminal_command(value):
    """Convert the app label "Gemini CLI" to its executable, preserving argv otherwise."""
    value = value.strip().rstrip('}.,;!?')
    value = re.sub(r'(?i)^(?:el\s+)?comando\s+', '', value).strip()
    if normalize(value).casefold() in {'gemini cli', 'gemini-cli'}:
        return 'gemini'
    return value


def _site_search(s):
    m = re.search(r'(?:abrir?|abre|busca|buscar|googlea|google|encuentra|search|investiga)\s+(.+?)\s+(?:en|on|in|dentro de)\s+(' + _SEARCH_SITES +
                  r')(?:\s+en\s+(?:firefox|chromium|chrome))?\s*$', s)
    if not m:
        return None
    query, site = m.group(1).strip(), m.group(2)
    query = re.sub(r'^(?:(?:el|la|los|las|un|una|algo de|informacion de|informacion sobre|sobre)\s+)+', '', query).strip()
    return (query, site) if query else None


def _open_known(s, text, name, wants_app, open_url):
    """Resuelve «abre <nombre>»: herramienta de terminal → app conocida → sitio → corrección → conjetura."""
    if name in TERMINAL_TOOLS and not wants_app:
        cmd = TERMINAL_TOOLS[name]
        return _plan(text, _op('browser', 'open_application', {'name': 'terminal', 'command': cmd}, Risk.HIGH,
                               f'abrir {cmd} en una nueva terminal'))
    cmd = APP_ALIASES.get(name, name.replace(' ', '-'))
    if cmd == 'gemini_cli':
        return _plan(text, _op('browser', 'open_application', {'name': 'terminal', 'command': 'gemini'}, Risk.HIGH,
                               'abrir Gemini CLI en una nueva terminal'))
    if name in APP_ALIASES and not (name in WEB_SERVICES and not wants_app and not command_exists(cmd) and cmd not in {
            'terminal', 'browser', 'editor', 'maps', 'calculator', 'software'}):
        desc = 'abrir una terminal' if cmd == 'terminal' else f'abrir {name}'
        return _plan(text, _op('browser', 'open_application', {'name': cmd}, Risk.READ_ONLY, desc))
    if wants_app or command_exists(cmd):
        if command_exists(cmd):
            return _plan(text, _op('browser', 'open_application', {'name': cmd}, Risk.HIGH, f'abrir la aplicación {name}'))
    if name in WEB_SERVICES:
        return open_url(WEB_SERVICES[name], f'abrir {name}')
    correction, kind = suggest_correction(name)
    if correction:
        label = 'la aplicación ' if kind == 'app' else ''
        return _ask(text, f'¿Te refieres a {label}{correction}? (escribe "abre {correction}" para confirmar)')
    if wants_app:
        return _plan(text, _op('browser', 'open_application', {'name': name}, Risk.MODERATE, f'abrir {name}'))
    if ' ' not in name and re.fullmatch(r'[a-z0-9-]+', name):
        return open_url(f'https://www.{name}.com', f'abrir {name}.com')
    return None


def build_open(s, text, ctx):
    terminal_request = re.search(
        r'(?i)^\s*(?:por favor\s+)?(?:abre|abrir|abro|ejecuta|corre|inicia|run)\s+'
        r'(.+?)\s+(?:en|desde)\s+(?:(?:una\s+nueva|otra|nueva|la)\s+)?terminal\W*$', text)
    if terminal_request:
        command = _terminal_command(terminal_request.group(1))
        if command:
            return _plan(text, _op('browser', 'open_application',
                                   {'name': 'terminal', 'command': command}, Risk.HIGH,
                                   f'abrir una nueva terminal y ejecutar {command}'))

    browser = next((n for n in ('firefox', 'chromium', 'chrome') if re.search(r'\b' + n + r'\b', s)), None)

    def open_url(url, desc):
        args = {'url': url}
        if browser:
            args['browser'] = browser
        return _plan(text, _op('browser', 'open_url', args, desc=desc))

    url_match = re.search(r'https?://[^\s]+', text)
    if url_match:
        url = url_match.group(0).rstrip('.,;')
        return open_url(url, f'abrir {url}' + (f' en {browser}' if browser else ''))
    profile = re.search(r'(?:perfil|profile)\s+(?:de\s+)?@?([\w-]+)\s+(?:en\s+)?github', s)
    if profile:
        return open_url(f'https://github.com/{profile.group(1)}', f'abrir perfil de {profile.group(1)} en GitHub')

    found = _site_search(s)
    if found:
        query, site = found
        return open_url(SITE_SEARCH[site] + quote(query), f'buscar «{query}» en {site}')

    site_name_match = re.search(_OPEN_VERBS + r'\s+([a-z0-9\s.-]+?)(?:\s+en\s+el\s+navegador)?$', s, re.I)
    if site_name_match and not re.search(r'\b(busca|buscar|google|archivo|fichero|documento|file)\b', s):
        site_name = re.sub(r'^(?:(?:el|la|los|las|un|una|mi|mis)\s+)+', '', site_name_match.group(1).strip().lower())
        site_name = re.sub(r'\s+(?:en\s+)?(?:firefox|chromium|chrome)$', '', site_name).strip()
        wants_app = bool(re.search(r'\b(aplicacion|programa|app|software)\b', s))
        site_name = re.sub(r'^(?:(?:la|el)\s+)?(?:aplicacion|programa|app)\s+(?:de\s+)?', '', site_name).strip() or site_name
        if site_name:
            result = _open_known(s, text, site_name, wants_app, open_url)
            if result is not None:
                return result

    site = next((n for n in _SITE_SENTENCE if re.search(r'\b' + re.escape(n) + r'\b', s)), None)
    if site and not re.search(r'\b(archivo|fichero|documento|file|carpeta|terminal)\b', s) and not re.search(FILE_EXT, text, re.I):
        return open_url(WEB_SERVICES[site], f'abrir {WEB_SERVICES[site]}' + (f' en {browser}' if browser else ' en el navegador predeterminado'))
    if re.search(r'\b(busca|buscar|google|googlea|search)\b', s):
        query_match = re.search(r'(?:busca|buscar|google|googlea|search)(?:\s+(?:en\s+google|en\s+el\s+buscador)?)?\s+(.+)', s)
        if not query_match:
            return _ask(text, '¿Qué quieres buscar?')
        query = query_match.group(1).strip()
        corrected = suggest_search_correction(query)
        if corrected and corrected != query.lower():
            return _ask(text, f'Te refieres a "{corrected}"? (escribe "busca {corrected}" para confirmar)')
        return open_url(f'https://www.google.com/search?q={quote(query)}', f'buscar «{query}» en Google')
    if re.search(r'\b(archivo|fichero|documento|file)\b', s) or re.search(r'\b' + FILE_EXT + r'\b', text, re.I):
        found_file = _path(text) or re.search(r'\b' + FILE_EXT + r'\b', text, re.I)
        if hasattr(found_file, 'group'):
            found_file = found_file.group(0)
        if not found_file:
            return _ask(text, '¿Qué archivo quieres abrir? Indica su ruta o nombre.')
        return _plan(text, _op('development', 'open_file', {'path': found_file}, Risk.MODERATE, 'abrir el archivo ' + found_file))
    terminal_command = re.search(r'\b(?:ejecuta|run)\s+(.+)$', text, re.I)
    if terminal_command and re.search(r'\b(terminal|consola)\b', s):
        app = 'terminal'
    else:
        app = next((x for x in _SENTENCE_APPS if re.search(r'\b' + re.escape(x) + r'\b', s)), None)
    if not app:
        # Corrige un typo en un nombre de aplicación de una palabra (p. ej. "pyhcarm").
        request = re.sub(r'^.*?\b(?:abrir|abre|abro|open|launch|inicia)\b', '', s, count=1).strip()
        request = re.sub(r'^(?:(?:por favor|el|la|un|una)\s+)+', '', request)
        request = re.sub(r'\s+(?:por favor|ahora)$', '', request).strip()
        if request and len(request.split()) == 1:
            match = get_close_matches(request, APPS, n=1, cutoff=0.76)
            if match:
                app = match[0]
    if not app:
        requested = re.sub(r'^.*?\b(?:abrir|abre|abro|open|launch|inicia)\b', '', s, count=1).strip()
        if requested and len(requested.split()) <= 3:
            return _plan(text, _op('browser', 'open_application', {'name': requested},
                                   Risk.MODERATE, f'abrir {requested}'))
        return _ask(text, '¿Qué aplicación quieres abrir? Dime su nombre tal como aparece en el menú de aplicaciones.')
    app_name = APP_ALIASES.get(app, app)
    if app_name == 'gemini_cli':
        return _plan(text, _op('browser', 'open_application',
                               {'name': 'terminal', 'command': 'gemini'}, Risk.HIGH,
                               'abrir Gemini CLI en una nueva terminal'))
    if app in TERMINAL_TOOLS:
        return _plan(text, _op('browser', 'open_application', {'name': 'terminal', 'command': TERMINAL_TOOLS[app]}, Risk.HIGH,
                               f'abrir {app} en una nueva terminal'))
    args = {'name': app_name}
    if args['name'] == 'terminal' and terminal_command:
        args['command'] = _terminal_command(terminal_command.group(1))
    if args['name'] == 'terminal':
        description = ('abrir una terminal' if 'command' not in args
                       else 'abrir una terminal para ejecutar el comando indicado')
    else:
        description = f'abrir {app}'
    risk = Risk.HIGH if args.get('command') else Risk.READ_ONLY
    return _plan(text, _op('browser', 'open_application', args, risk=risk, desc=description))


def _multi_open(s, text):
    """«abre firefox y vscode» → varias operaciones de apertura."""
    m = re.match(r'^(?:abre|abrir|open|lanza|inicia)\s+(.+)$', s)
    if not m or not re.search(r',|\by\b|\be\b|\+', m.group(1)) or re.search(r'\b(terminal|archivo|busca|buscar|servidor|en)\b', m.group(1)):
        return None
    parts = [re.sub(r'^(?:(?:el|la|los|las|un|una)\s+)+', '', p.strip()) for p in re.split(r'\s*(?:,|\by\b|\be\b|\+)\s*', m.group(1)) if p.strip()]
    if len(parts) < 2 or len(parts) > 6 or not all(p in APP_ALIASES or p in WEB_SERVICES or p in TERMINAL_TOOLS for p in parts):
        return None
    ops = []
    for part in parts:
        plan = build_open(f'abre {part}', f'abre {part}', None)
        if plan is None or not plan.operations:
            return None
        ops.extend(plan.operations)
    return _plan(text, *ops)


# ---- comandos y seguridad ----------------------------------------------------
def build_exec_command(s, text, ctx):
    m = re.search(r'(?i)(?:ejecuta(?:\s+este)?(?:\s+el)?\s+comando|corre(?:\s+el)?\s+comando|run(?: the)? command|command:)\s*[:=]?\s*(.+)', text)
    if not m or not m.group(1).strip():
        return _ask(text, 'Escribe el comando después de «ejecuta comando».')
    return _plan(text, _op('development', 'execute_command', {'command': m.group(1).strip()}, Risk.HIGH,
                           'ejecutar el comando solicitado', timeout=120))


def build_nmap(s, text, ctx):
    target = _target(text)
    if not target:
        return _ask(text, 'Indica el objetivo autorizado (IP o nombre de host).')
    if not re.search(r'\b(autorizado|authorized|mi laboratorio|my lab|tengo permiso)\b', s):
        return _ask(text, 'Confirma que tienes autorización explícita para escanear el objetivo indicado.')
    args = {'target': target, 'authorized': True}
    ports = re.search(r'(?i)(?:puerto|port|ports)\s+([\d,-]+)', s)
    if ports:
        args['ports'] = ports.group(1)
    return _plan(text, _op('cybersecurity', 'scan', args, Risk.HIGH, 'escaneo Nmap de alcance autorizado', timeout=900))


# ---- archivos ----------------------------------------------------------------
def build_delete(s, text, ctx):
    path = _path_or_name(text)
    if not path:
        return _ask(text, '¿Qué archivo o carpeta quieres eliminar? Indica la ruta.')
    return _plan(text, _op('filesystem', 'delete', {'path': path}, Risk.MODERATE, 'eliminar ' + path))


def build_edit(s, text, ctx):
    path = _path_or_name(text)
    content_match = re.search(r'(?i)(?:con|with|contenido|content)\s+["\'](.+)["\']', text)
    if not path:
        return _ask(text, '¿Qué archivo quieres modificar? Indica la ruta.')
    content = content_match.group(1) if content_match else ''
    return _plan(text, _op('filesystem', 'write', {'path': path, 'content': content}, Risk.MODERATE, 'modificar ' + path))


def build_mkdir(s, text, ctx):
    path = _path_or_name(text)
    if not path:
        return _ask(text, '¿Qué carpeta quieres crear? Indica la ruta.')
    return _plan(text, _op('filesystem', 'mkdir', {'path': path}, Risk.MODERATE, 'crear carpeta ' + path))


def build_touch(s, text, ctx):
    path = _path_or_name(text)
    if not path:
        return _ask(text, '¿Qué archivo quieres crear? Indica la ruta.')
    return _plan(text, _op('filesystem', 'create', {'path': path, 'content': ''}, Risk.MODERATE, 'crear archivo vacío ' + path))


def build_find_content(s, text, ctx):
    path = _path(text) or '.'
    query_match = re.search(r'(?i)(?:texto|contenido|content|text)\s+["\'](.+)["\']', text)
    if not query_match:
        return _ask(text, '¿Qué texto quieres buscar dentro de los archivos?')
    query = query_match.group(1)
    return _plan(text, _op('filesystem', 'search_text', {'path': path, 'query': query}, Risk.READ_ONLY,
                           f'buscar «{query}» en archivos de {path}'))


def build_apt_install(s, text, ctx):
    packages = re.findall(r'["\']?([\w\-\.]+)["\']?', text)
    exclude = {'apt', 'apt-get', 'install', 'instala', 'instalar', 'paquete', 'paquetes', 'package', 'packages', 'y', 'yes', 'assume', 'yes'}
    packages = [p for p in packages if p not in exclude and not p.startswith('-')]
    if not packages:
        return _ask(text, '¿Qué paquetes quieres instalar?')
    assume_yes = bool(re.search(r'\b(-y|--yes|--assume-yes)\b', text))
    return _plan(text, _op('package_manager', 'apt_install', {'packages': packages, 'assume_yes': assume_yes}, Risk.HIGH,
                           f'instalar {", ".join(packages)} con apt'))


def build_pip_install(s, text, ctx):
    packages = re.findall(r'["\']?([\w\-\.]+)["\']?', text)
    exclude = {'pip', 'pip3', 'install', 'instala', 'instalar', 'paquete', 'paquetes', 'package', 'packages', 'user', 'u', 'upgrade', 'U', 'help', 'h'}
    packages = [p for p in packages if p not in exclude and not p.startswith('-')]
    if not packages:
        return _ask(text, '¿Qué paquetes quieres instalar?')
    user = bool(re.search(r'\b(--user|-u)\b', text))
    upgrade = bool(re.search(r'\b(--upgrade|-U)\b', text))
    return _plan(text, _op('package_manager', 'pip_install', {'packages': packages, 'user': user, 'upgrade': upgrade}, Risk.HIGH,
                           f'instalar {", ".join(packages)} con pip'))


def build_npm_install(s, text, ctx):
    packages = re.findall(r'["\']?([\w\-\.@/]+)["\']?', text)
    exclude = {'npm', 'install', 'instala', 'instalar', 'paquete', 'paquetes', 'package', 'packages', 'global', 'g', 'save', 'S', 'help', 'h'}
    packages = [p for p in packages if p not in exclude and not p.startswith('-')]
    if not packages:
        return _ask(text, '¿Qué paquetes quieres instalar?')
    global_ = bool(re.search(r'\b(--global|-g)\b', text))
    save = bool(re.search(r'\b(--save|-S)\b', text))
    return _plan(text, _op('package_manager', 'npm_install', {'packages': packages, 'global_': global_, 'save': save}, Risk.MODERATE,
                           f'instalar {", ".join(packages)} con npm'))


def build_move(s, text, ctx):
    quoted = re.findall(r'["\']([^"\']+)["\']', text)
    match = re.search(r'(?i)\b(?:mueve|mover|move|renombra|renombrar|rename)\s+(.+?)\s+(?:a|hacia|to)\s+(.+?)\s*[?.!]*$', text)
    if len(quoted) >= 2:
        source, destination = quoted[0], quoted[1]
    elif match:
        source, destination = match.group(1).strip(' "\''), match.group(2).strip(' "\'')
        if (source.casefold() in {'el archivo', 'ese archivo', 'lo que acabo de crear', 'el que acabo de crear'}
                and ctx and ctx.last_plan and ctx.last_plan.operations):
            previous = ctx.last_plan.operations[0]
            if previous.capability == 'filesystem' and previous.name in {'create', 'move', 'copy'}:
                source = previous.arguments.get('path') or previous.arguments.get('destination', source)
    else:
        return _ask(text, '¿Qué archivo quieres mover y a qué carpeta?')
    return _plan(text, _op('filesystem', 'move', {'source': source, 'destination': destination}, Risk.MODERATE,
                           'mover ' + source + ' a ' + destination))


# ---- procesos ----------------------------------------------------------------
def build_kill(s, text, ctx):
    pid = re.search(r'\b(?:pid\s*)?(\d{1,9})\b', s)
    if not pid:
        return _ask(text, 'Indica el PID exacto. Primero puedo listar procesos para que elijas el correcto.')
    return _plan(text, _op('processes', 'terminate',
                           {'pid': int(pid.group(1)), 'force': bool(re.search(r'\b(forzar|force|kill -9)\b', s))},
                           Risk.HIGH, 'enviar una señal al proceso PID ' + pid.group(1)))


_NOT_PROCESS_NAMES = {'sesion', 'la', 'el', 'pantalla', 'ventana', 'conexion', 'servidor', 'servicio', 'todo', 'todos', 'esto', 'eso',
                      'terminal', 'sistema', 'bluetooth', 'wifi', 'volumen', 'proceso', 'procesos', 'programa', 'aplicacion', 'app'}


def build_kill_by_name(s, text, ctx):
    m = re.search(r'\b(?:mata|matar|killall|pkill|termina|terminar|finaliza|finalizar|cierra|cerrar|fuerza el cierre de)\s+'
                  r'(?:(?:a la fuerza|forzado)\s+)?(?:(?:todos|todas)\s+)?(?:(?:los|las|el|la)\s+)?(?:(?:procesos?|programas?|aplicacion|app)\s+(?:de\s+|llamados?\s+)?)?'
                  r'(?:(?:los|las|el|la)\s+)?([a-z][a-z0-9._-]*)\b', s)
    if not m or re.search(r'\b\d{2,9}\b', s):
        return None
    name = m.group(1)
    if name in _NOT_PROCESS_NAMES or _daemon_name(name):
        return None
    force = bool(re.search(r'\b(?:a la fuerza|forzado|forzar|kill -9|-9|con kill)\b', s))
    return _plan(text, _op('processes', 'terminate_by_name', {'name': name, 'force': force, 'exact': False}, Risk.HIGH,
                           f'terminar los procesos llamados {name}'))


def build_find_process(s, text, ctx):
    for pattern in (r'\b(?:proceso|procesos|pid de|pid del)\s+(?:llamado\s+)?([a-z][\w.-]*)\s*$',
                    r'\bcorriendo\s+(?:el\s+|la\s+)?([a-z][\w.-]*)\s*$', r'\b(?:esta|sigue)\s+(?:abierto\s+|abierta\s+)?(?:el\s+|la\s+)?([a-z][\w.-]*)\s+(?:corriendo|abierto|abierta|ejecutandose|funcionando)\b',
                    r'\bpid de\s+([a-z][\w.-]*)'):
        m = re.search(pattern, s)
        if m and m.group(1) not in _NOT_PROCESS_NAMES:
            return _plan(text, _op('processes', 'find_by_name', {'name': m.group(1)}, desc=f'buscar procesos {m.group(1)}'))
    return None


def _pid_op(name, desc, extra=None):
    def build(s, text, ctx):
        pid = _pid_from(s)
        if not pid:
            return _ask(text, 'Indica el PID del proceso.')
        args = {'pid': pid}
        args.update(extra or {})
        return _plan(text, _op('processes', name, args, desc=desc))
    return build


def build_pid_signal(name, risk=Risk.MODERATE):
    def build(s, text, ctx):
        pid = _pid_from(s)
        if not pid:
            return _ask(text, 'Indica el PID del proceso.')
        return _plan(text, _op('processes', name, {'pid': pid}, risk, f'{name} del proceso {pid}'))
    return build


def build_renice(s, text, ctx):
    s2 = _num_words(s)
    pid = _pid_from(re.sub(r'(?:prioridad|nice)\s*-?\d+', '', s2))
    value = re.search(r'(?:prioridad|nice|a)\s*(-?\d{1,2})\b(?!\s*\d)', s2)
    if not pid or not value:
        return _ask(text, 'Indica el PID y la prioridad (nice, de -20 a 19). Ej: «cambia la prioridad del proceso 1234 a 10».')
    return _plan(text, _op('processes', 'renice', {'pid': pid, 'nice': int(value.group(1))}, Risk.HIGH, f'cambiar la prioridad del PID {pid}'))


def build_by_user(s, text, ctx):
    m = re.search(r'\bprocesos de(?:l)?\s+(?:usuario\s+)?(\w+)', s)
    return _plan(text, _op('processes', 'by_user', {'user': m.group(1) if m else 'root'}))


def build_by_port(s, text, ctx):
    port = _port_from(s)
    if not port:
        return _ask(text, '¿Qué puerto quieres investigar?')
    return _plan(text, _op('processes', 'by_port', {'port': port}, desc=f'qué proceso usa el puerto {port}'))


def build_port_check(s, text, ctx):
    port = _port_from(s)
    if not port:
        return _ask(text, '¿Qué puerto quieres comprobar?')
    return _plan(text, _op('networking', 'port_check_local', {'port': port}))


# ---- sistema, red y monitoreo -------------------------------------------------
def build_service_logs(s, text, ctx):
    name = _service_name(s)
    if not name:
        return _ask(text, '¿De qué servicio quieres consultar los logs?')
    amount = re.search(r'\b(?:ultimos?|ultimas?|last)\s+(\d+)\b', s)
    return _plan(text, _op('services', 'logs', {'name': name, 'lines': int(amount.group(1)) if amount else 50}))


def build_time(s, text, ctx):
    return _plan(text, _op('system', 'time', {'include_date': bool(re.search(r'\b(fecha|dia|date|today)\b', s))}))


def build_network_view(s, text, ctx):
    if re.search(r'\b(ruta|rutas|routes?)\b', s):
        return _plan(text, _op('networking', 'routes'))
    return _plan(text, _op('networking', 'interfaces'))


def build_tcp(s, text, ctx):
    port_match = re.search(r'(?i)(?:puerto|port)\s+(\d{1,5})', s)
    host = _target(text)
    if not host:
        return _ask(text, 'Indica el host/IP para comprobar.')
    if not port_match:
        return _ask(text, 'Indica el puerto TCP que quieres comprobar.')
    port = int(port_match.group(1))
    if not 1 <= port <= 65535:
        return _ask(text, 'El puerto debe estar entre 1 y 65535.')
    return _plan(text, _op('networking', 'tcp_test', {'host': host, 'port': port}))


def build_system_logs(s, text, ctx):
    m = re.search(r'ultimos?\s+(\d+)', s)
    return _plan(text, _op('system', 'logs', {'lines': int(m.group(1)) if m else 100}))


def build_disk_usage(s, text, ctx):
    return _plan(text, _op('filesystem', 'disk_usage', {'path': _path(text) or '.'}))


def build_search_names(s, text, ctx):
    name = re.sub(r'(?i)\b(?:busca|buscar|encuentra|find|search|un|una|el|la|archivo|archivos|fichero|ficheros|file|files|que|se|llame|llamado|llamada|llamados|llamadas|de nombre|con nombre|llamado a|en|computadora|ordenador|todo el sistema)\b', ' ', text)
    name = re.sub(r'[¿?¡!,;:\\"\']', ' ', name)
    name = ' '.join(name.split()).strip()
    if not name:
        return _ask(text, '¿Qué nombre de archivo busco?')
    path = _path(text)
    if not path:
        path = str(Path.home()) if re.search(r'(?i)\b(?:computadora|ordenador|todo el sistema)\b', s) else '.'
    return _plan(text, _op('filesystem', 'search_names', {'path': path, 'pattern': name},
                           desc=f'buscar archivos que contengan «{name}» en {path}'))


def build_list(s, text, ctx):
    return _plan(text, _op('filesystem', 'list', {'path': _path(text) or '.',
                                                  'all_entries': bool(re.search(r'\b(all|todos|ocultos)\b', s))}))


def build_create(s, text, ctx):
    path_match = _path(text)
    name = _file_name(text) or (None if path_match else _path_or_name(text))
    if path_match:
        dest = Path(path_match).expanduser()
        if dest.is_dir():
            dest = dest / (name or 'archivo.txt')
        return _plan(text, _op('filesystem', 'create', {'path': str(dest), 'content': ''}, Risk.MODERATE, f'crear archivo {dest}'))
    if name:
        return _plan(text, _op('filesystem', 'create', {'path': name, 'content': ''}, Risk.MODERATE, f'crear archivo {name}'))
    return _ask(text, '¿Cómo quieres llamar al archivo? Ejemplo: "crea archivo hola.py en /home/usuario/Descargas"')


def build_scan_folder(s, text, ctx):
    path = _path(text) or '.'
    return _plan(text, _op('filesystem', 'list', {'path': path, 'all_entries': True}, desc='escanear carpeta ' + path))


def _with_path(text, message, cap, name, key, extra=None, risk=Risk.READ_ONLY, desc=''):
    path = _path(text)
    if not path:
        return _ask(text, message)
    args = {key: path}
    args.update(extra or {})
    return _plan(text, _op(cap, name, args, risk, desc))


def build_csv_to_json(s, text, ctx):
    path = _path(text)
    if not path:
        return _ask(text, 'Indica el archivo CSV')
    return _plan(text, _op('data_processing', 'csv_to_json', {'csv_path': path, 'json_path': path.rsplit('.', 1)[0] + '.json'}))


def build_json_to_csv(s, text, ctx):
    path = _path(text)
    if not path:
        return _ask(text, 'Indica el archivo JSON')
    return _plan(text, _op('data_processing', 'json_to_csv', {'json_path': path, 'csv_path': path.rsplit('.', 1)[0] + '.csv'}))


def build_chmod(s, text, ctx):
    path = _path(text)
    mode = re.search(r'\b([0-7]{3,4})\b', s)
    if not path or not mode:
        return _ask(text, 'Indica la ruta y el modo (ej: 755)')
    return _plan(text, _op('filesystem', 'change_permissions',
                           {'path': path, 'mode': mode.group(1), 'recursive': bool(re.search(r'\b(recursivo|recursive)\b', s))},
                           Risk.MODERATE, 'cambiar permisos'))


def build_chown(s, text, ctx):
    path = _path(text)
    if not path:
        return _ask(text, 'Indica la ruta del archivo/directorio')
    args = {'path': path}
    user = re.search(r'(?:usuario|user)\s+(\w+)', s)
    if user:
        args['user'] = user.group(1)
    return _plan(text, _op('filesystem', 'change_owner', args, Risk.HIGH, 'cambiar propietario'))


def build_service_status(s, text, ctx):
    name = _service_name(s)
    if not name:
        return _ask(text, '¿De qué servicio quieres consultar el estado?')
    return _plan(text, _op('services', 'status', {'name': name}))


def build_run_python(s, text, ctx):
    path = _path(text)
    if not path:
        return _ask(text, 'Indica la ruta del script Python.')
    return _plan(text, _op('development', 'run_python', {'path': path}, Risk.MODERATE, 'ejecutar el programa Python indicado', timeout=120))


def build_late_scan(s, text, ctx):
    return _ask(text, 'Indica el objetivo autorizado (IP o nombre de host).')


def build_timezone(s, text, ctx):
    tz = re.search(r'(?i)\b(?:a|to)\s+([\w/]+)', text)
    if not tz:
        return _ask(text, '¿A qué zona horaria quieres cambiar? (ej: America/Mexico_City)')
    return _plan(text, _op('system', 'set_timezone', {'timezone': tz.group(1)}, Risk.HIGH, 'cambiar zona horaria'))


def build_power(s, text, ctx):
    if re.search(r'\b(?:sin|no)\b.*\b(?:reiniciar|apagar)\b|\b(?:reiniciar|iniciar|detener)\s+(?:servicio|servicios|nginx|apache|ssh|docker)\b', s):
        return None
    action = 'reboot' if re.search(r'\b(reiniciar|reinicia|reboot|restart)\b', s) else 'shutdown'
    delay = _minutes_from(s)
    if delay:
        return _plan(text, _op('system', 'power_schedule', {'action': action, 'delay_minutes': delay}, Risk.HIGH,
                               f'{action} del sistema en {delay} minutos'))
    return _plan(text, _op('system', 'power_management', {'action': action}, Risk.HIGH, f'{action} del sistema'))


def _level(cap, name, key, label):
    def build(s, text, ctx):
        value = re.search(r'(\d+)', _num_words(s))
        if value:
            return _plan(text, _op(cap, name, {key: int(value.group(1))}, Risk.MODERATE, f'cambiar {label}'))
        return _plan(text, _op(cap, name))
    return build


def _step(cap, name, label, default=10):
    def build(s, text, ctx):
        if re.search(r'\d+', _num_words(s)):
            return None
        up = re.search(r'\b(?:sube|subir|aumenta\w*|mas|arriba|alto|incrementa\w*)\b', s)
        down = re.search(r'\b(?:baja|bajar|reduce|reducir|menos|abajo|bajo|disminuye\w*)\b', s)
        if not (up or down):
            return None
        delta = default if up and not down else -default
        return _plan(text, _op(cap, name, {'delta': delta}, Risk.MODERATE, f'{"subir" if delta > 0 else "bajar"} {label}'))
    return build


def build_mute(s, text, ctx):
    unmute = re.search(r'\b(?:unmute|desmutea|desilencia|activa el sonido|pon el sonido|quita el silencio|reactiva el sonido)\b', s)
    toggle = re.search(r'\balterna\b', s)
    return _plan(text, _op('system', 'audio_mute', {'mute': None if toggle else not unmute}, Risk.MODERATE,
                           'alternar silencio' if toggle else 'activar sonido' if unmute else 'silenciar audio'))


def build_onoff(cap, name, key, label, on_words=r'\b(?:enciende|encender|prende|prender|activa|activar|on|conecta|habilita)\b'):
    def build(s, text, ctx):
        return _plan(text, _op(cap, name, {key: bool(re.search(on_words, s))}, Risk.MODERATE,
                               f'{"encender" if re.search(on_words, s) else "apagar"} {label}'))
    return build


def build_transfer(s, text, ctx):
    src = re.search(r'(?:desde|from|source)\s+([^\s]+)', s)
    dst = re.search(r'(?:a|to|dest|destination)\s+([^\s]+)', s)
    if not src or not dst:
        return _ask(text, 'Indica origen y destino')
    tool = 'rsync' if re.search(r'\brsync\b', s) else 'scp'
    return _plan(text, _op('remote_transfer', tool, {'source': src.group(1), 'destination': dst.group(1)}, Risk.MODERATE, f'transferir con {tool}', timeout=600))


def build_ping(s, text, ctx):
    return _plan(text, _op('networking', 'ping', {'host': _target(text) or '8.8.8.8'}))


def build_traceroute(s, text, ctx):
    host = _target(text)
    if not host:
        return _ask(text, 'Indica el host para traceroute')
    return _plan(text, _op('networking', 'traceroute', {'host': host}, timeout=60))


def build_http(s, text, ctx):
    url = re.search(r'https?://[^\s]+', text)
    if not url:
        return _ask(text, 'Indica la URL')
    return _plan(text, _op('networking', 'http_request', {'url': url.group(0).rstrip('.,;')}))


def _domain_op(name, key='host', **fixed):
    def build(s, text, ctx):
        target = _domain_from(text)
        if not target:
            return None
        value = target if key == 'url' else re.sub(r'^https?://', '', target).split('/')[0]
        if key == 'url' and not target.startswith('http'):
            value = 'https://' + target
        args = {key: value}
        args.update(fixed)
        return _plan(text, _op('networking', name, args, desc=f'{name} {value}'))
    return build


def build_dns_lookup(s, text, ctx):
    target = _domain_from(text)
    if not target:
        return None
    host = re.sub(r'^https?://', '', target).split('/')[0]
    record = next((r.upper() for r in ('mx', 'txt', 'ns', 'aaaa', 'cname', 'soa', 'caa') if re.search(r'\b' + r + r'\b', s)), 'A')
    return _plan(text, _op('networking', 'dns_lookup', {'host': host, 'record': record}, desc=f'consulta DNS {record} de {host}'))


def build_reverse_dns(s, text, ctx):
    ip = re.search(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])', text)
    if not ip:
        return _ask(text, '¿Qué dirección IP quieres resolver?')
    return _plan(text, _op('networking', 'reverse_dns', {'ip': ip.group(0)}))


def build_ssl(s, text, ctx):
    if _path(text) and not _domain_from(text):
        return None
    target = _domain_from(text)
    if not target:
        return None
    host = re.sub(r'^https?://', '', target).split('/')[0]
    return _plan(text, _op('networking', 'ssl_expiry', {'host': host}, desc=f'caducidad del certificado de {host}'))


def build_secrets(s, text, ctx):
    return _plan(text, _op('security_audit', 'scan_secrets', {'path': _path(text) or '.'}))


def build_certificate(s, text, ctx):
    path = _path(text)
    if not path:
        return _ask(text, 'Indica la ruta del certificado')
    return _plan(text, _op('security_audit', 'certificate_info', {'cert_path': path}))


def build_install(s, text, ctx):
    pkg = re.search(r'(?:paquete|package)\s+([\w.+-]+)', s)
    if not pkg:
        pkg = re.search(r'\b(?:instalar|instala|install)\s+(?:el\s+|the\s+)?(?!(?:paquete|package)\b)([\w.+-]+)', s)
    if not pkg:
        return _ask(text, 'Indica el nombre del paquete')
    return _plan(text, _op('packages', 'install', {'package_names': [pkg.group(1)]}, Risk.HIGH, 'instalar paquete', timeout=900))


def build_update(s, text, ctx):
    if re.search(r'\b(sistema|system|todo|all)\b', s):
        return _plan(text, _op('packages', 'upgrade', {}, Risk.HIGH, 'actualizar sistema', timeout=1800))
    return _plan(text, _op('packages', 'update', {}, Risk.HIGH, 'actualizar lista de paquetes', timeout=600))


def build_cron(s, text, ctx):
    if re.search(r'\b(lista|listar|mostrar)\b', s):
        return _plan(text, _op('packages', 'list_cron_jobs'))
    return _ask(text, 'Usa /run crontab -e para editar tareas cron')


def build_compile(s, text, ctx):
    path = _path(text)
    if not path:
        return _ask(text, 'Indica el archivo fuente')
    name = 'compile_cpp' if re.search(r'\b(c\+\+|cpp)\b', s) else 'compile_c'
    return _plan(text, _op('development', name, {'source': path}, timeout=120))


def _dev_path(name, timeout=None):
    return lambda s, text, ctx: _plan(text, _op('development', name, {'path': _path(text) or '.'}, timeout=timeout))


def build_git_checkout(s, text, ctx):
    branch = re.search(r'(?:a|to)\s+([\w-]+)', s)
    if not branch:
        return _ask(text, 'Indica la rama o commit')
    return _plan(text, _op('development', 'git_checkout', {'branch_or_commit': branch.group(1)}, Risk.MODERATE))


def build_docker_build(s, text, ctx):
    tag = re.search(r'-t\s+([\w:.-]+)', s)
    return _plan(text, _op('development', 'docker_build', {'path': _path(text) or '.', 'tag': tag.group(1) if tag else None}, timeout=1800))


def build_sqlite(s, text, ctx):
    db = _path(text, allow_quoted=False)
    if not db:
        found = re.search(r'["\']?([\w./~-]+\.(?:db|sqlite3?))["\']?', text)
        db = found.group(1) if found else None
    if not db:
        return _ask(text, 'Indica la ruta de la base de datos SQLite')
    if re.search(r'\b(query|consulta)\b', s):
        query = re.search(r'(?i)(?:query|consulta)\s+["\'](.+)["\']', text)
        if not query:
            return _ask(text, 'Indica la consulta SQL')
        return _plan(text, _op('database', 'sqlite_query', {'db_path': db, 'query': query.group(1)}))
    return _plan(text, _op('database', 'sqlite_list_tables', {'db_path': db}))


def build_explicit_exec(s, text, ctx):
    explicit = re.match(r'(?i)^\s*(?:por favor\s+)?(?:ejecuta|corre|run)\s+(.+?)\s*$', text)
    if explicit and explicit.group(1).strip().casefold() not in {'un comando', 'un programa', 'mi programa', 'este comando', 'algo'}:
        command = explicit.group(1).strip()
        return _plan(text, _op('development', 'execute_command', {'command': command}, Risk.HIGH, 'ejecutar explícitamente: ' + command, timeout=120))
    return _unknown(text)


def _remote_scan(s, text):
    if not re.search(r'\b(?:nmap|escanea|escanear|scan)\b', s):
        return False
    target = _target(text)
    return bool(target) and _looks_like_host(target) and not _is_local(target)


# ---- builders nuevos de sistema ---------------------------------------------
def build_env_get(s, text, ctx):
    m = re.search(r'\$([A-Za-z_]\w*)', text) or re.search(r'(?i)\bvariable\s+(?:de entorno\s+)?([A-Za-z_]\w*)', text)
    if not m:
        return None
    return _plan(text, _op('system', 'env_get', {'name': m.group(1)}, desc=f'valor de {m.group(1)}'))


def build_sysctl(s, text, ctx):
    m = re.search(r'\bsysctl\s+([a-z0-9_./-]+)', s)
    if not m:
        return _ask(text, '¿Qué parámetro del kernel quieres leer? Ej: «sysctl vm.swappiness».')
    return _plan(text, _op('system', 'sysctl_get', {'key': m.group(1)}))


def build_screenshot(s, text, ctx):
    path = _path(text)
    return _plan(text, _op('system', 'screenshot', {'path': path} if path else {}, Risk.MODERATE, 'tomar una captura de pantalla'))


def build_notify(s, text, ctx):
    m = re.search(r'(?i)(?:notificame|notificacion|notify)\s*(?:que|de|:)?\s*["\']?(.+?)["\']?$', text)
    if not m or not m.group(1).strip():
        return _ask(text, '¿Qué mensaje quieres en la notificación?')
    return _plan(text, _op('system', 'notify', {'message': m.group(1).strip()}, Risk.MODERATE, 'enviar una notificación de escritorio'))


def build_clipboard_copy(s, text, ctx):
    m = re.search(r'["\'](.+)["\']', text) or re.search(r'(?i)\bcopia(?:r)?\s+(.+?)\s+(?:al|en el)\s+portapapeles', text)
    if not m:
        return _ask(text, '¿Qué texto quieres copiar al portapapeles? Escríbelo entre comillas.')
    return _plan(text, _op('system', 'clipboard_copy', {'text': m.group(1)}, Risk.MODERATE, 'copiar texto al portapapeles'))


def build_set_hostname(s, text, ctx):
    m = re.search(r'\b(?:a|como)\s+["\']?([A-Za-z0-9][A-Za-z0-9-]{0,62})["\']?\s*$', text)
    if not m:
        return _ask(text, '¿Qué nombre quieres para el equipo? (letras, números y guiones)')
    return _plan(text, _op('system', 'set_hostname', {'name': m.group(1)}, Risk.HIGH, f'cambiar el nombre del equipo a {m.group(1)}'))


def build_disk_hogs(s, text, ctx):
    return _plan(text, _op('system', 'disk_hogs', {'path': _path(text) or str(Path.home()), 'limit': 10}, desc='carpetas que más espacio ocupan'))


def build_large_files(s, text, ctx):
    args = {'path': _path(text) or str(Path.home()), 'limit': 10}
    m = re.search(r'(\d+)\s*(mb|gb)', s)
    if m:
        args['min_mb'] = int(m.group(1)) * (1024 if m.group(2) == 'gb' else 1)
    return _plan(text, _op('system', 'large_files', args, desc='archivos más grandes'))


def build_recent_files(s, text, ctx):
    hours = 24
    s2 = _num_words(s)
    m = re.search(r'ultim[ao]s?\s+(\d+)?\s*(hora|horas|dia|dias|semana|semanas)', s2)
    if m:
        n = int(m.group(1) or 1)
        hours = n * (1 if m.group(2).startswith('hora') else 24 if m.group(2).startswith('dia') else 168)
    return _plan(text, _op('system', 'recent_files', {'path': _path(text) or str(Path.home()), 'hours': hours, 'limit': 20}, desc='archivos modificados recientemente'))


_METRICS = (('cpu', r'\b(?:cpu|procesador)\b'), ('memory', r'\b(?:memoria|ram)\b'), ('swap', r'\bswap\b'), ('load', r'\bcarga\b'),
            ('temperature', r'\btemperatura\b'), ('network', r'\b(?:red|internet|ancho de banda)\b'), ('disk_io', r'\b(?:disco|ssd|hdd)\b'))


def build_watch(s, text, ctx):
    metric = next((m for m, pat in _METRICS if re.search(pat, s)), None)
    if not metric:
        return _ask(text, '¿Qué quieres vigilar: cpu, memoria, swap, carga, temperatura, red o disco?')
    s2 = _num_words(s)
    m = re.search(r'(\d+)\s*(segundos?|seg|minutos?|min)\b', s2)
    duration = 10
    if m:
        duration = int(m.group(1)) * (60 if m.group(2).startswith('min') else 1)
    duration = max(2, min(duration, 60))
    return _plan(text, _op('monitoring', 'watch_metric', {'metric': metric, 'duration': duration, 'interval': 1}, desc=f'vigilar {metric} durante {duration} s', timeout=duration + 30))


Rule = namedtuple('Rule', 'name match build examples')


def _R(name, pattern, cap, op, examples, desc='', risk=Risk.READ_ONLY, args=None, timeout=None):
    """Regla simple: patrón → una operación fija. Los ejemplos se etiquetan solos."""
    return Rule(name, _rx(pattern), _simple(cap, op, desc, risk, args, timeout), [(e, f'{cap}.{op}') for e in examples])


def _B(name, match, build, examples):
    return Rule(name, _rx(match) if isinstance(match, str) else match, build, examples)


_SVC = r'\b' + SERVICE_WORDS + r'\b'
_SERVER_WORD = r'\b(?:servidor(?:es)?|server|webserver)\b'
_START_RX = r'\b' + _START_VERBS + r'\b'
_NOT_ENABLE = _not(_rx(r'\bhabilita\w*|\bdeshabilita\w*|\bal (?:arranque|arrancar|iniciar|encender)\b|\bcon el sistema\b'))
_SITE_OPEN_RX = (r'\b(?:ir a|ve a|entra a|entra en|navega a|visita|llevame a|go to)\s+(?:https?|www\.|(?:'
                 + '|'.join(re.escape(n) for n in _SITE_SENTENCE) + r')\b)')

GUARDS = [
    Rule('chat_guard',
         _rx(r'^(?:estoy|me siento|me gusta|me encanta|tengo (?:hambre|sueno|frio|calor|sed|miedo|una duda|una pregunta|un problema))\b'),
         lambda s, t, c: _unknown(t),
         [('estoy cansado de esto', 'unrecognized'), ('me gusta el sistema', 'unrecognized')]),
    Rule('howto_guard',
         _rx(r'^(?:como|de que forma|how)\b.*\b(?:cre\w+|hac\w+|borr\w+|elimin\w+|copi\w+|mov\w+|renombr\w+|instal\w+|actualiz\w+|ejecut\w+|corr\w+|sal\w+|cerr\w+|ver|consult\w+|apag\w+|reinici\w+|aprend\w+|empiez\w+|levant\w+|arranc\w+|habilit\w+|deshabilit\w+|recarg\w+|monit\w+|bloque\w+|conect\w+|abr\w+|inici\w+|detener|deten\w*|learn|do|create|delete|install)\b'),
         lambda s, t, c: _unknown(t),
         [('como reinicio nginx', 'unrecognized'), ('como creo un archivo', 'unrecognized'), ('como levanto un servidor', 'unrecognized')]),
    Rule('explain_guard',
         _rx(r'^(?:para que sirve|que es|que son|que significa|que quiere decir|que hace|cual es la diferencia|diferencia entre|como funciona|que permisos tienes)\b'),
         lambda s, t, c: _unknown(t),
         [('para que sirve chmod', 'unrecognized'), ('que permisos tienes', 'unrecognized')]),
    Rule('capabilities_question', _rx(r'\b(que puedes hacer|que sabes hacer|en que me ayudas|cual es tu proposito|what can you do)\b'),
         build_capabilities, [('que puedes hacer', 'assistant.capabilities'), ('que puedes hacer en redes', 'assistant.capabilities')]),
    Rule('reformat', _rx(r'\b(mejor estructurada|mas claro|mas limpia|ordena la salida|no me lo compartas asi|formatea(?:lo)?|dimelo mejor|explicalo mejor)\b'),
         lambda s, t, c: Plan([], t, reformat_last=True), [('dimelo mejor', 'reformat')]),
]

# Reglas que deben ir antes de «service_change» y «open» porque comparten verbos (inicia, abre, apaga, reinicia…).
EARLY_RULES = [
    _B('server_list', r'\bservidores?\s+(?:activos?|levantados?|corriendo|abiertos?)\b|\b(?:que|cuales|lista\w*|muestra\w*|ver)\b.*\bservidores\b.*\b(?:corriendo|activos|levantados|tengo|hay)\b',
       build_server_list, [('que servidores tengo corriendo', 'networking.list_local_servers'), ('lista los servidores activos', 'networking.list_local_servers')]),
    _B('server_stop', _all(_rx(_STOP_VERBS), _rx(_SERVER_WORD)), build_server_stop,
       [('apaga el servidor nginx', 'services.change'), ('deten el servidor del puerto 8000', 'networking.stop_http_server'),
        ('baja el servidor', 'networking.stop_http_server'), ('cierra todos los servidores', 'networking.stop_all_http_servers')]),
    _B('server_start',
       lambda s, t: bool(re.search(_START_RX, s)) and _NOT_ENABLE(s, t) and (bool(re.search(_SERVER_WORD, s)) or (bool(_daemon_name(s)) and bool(re.search(_STRONG_START, s)))),
       build_server_start,
       [('levanta un servidor', 'networking.start_http_server'), ('levanta apache', 'services.change'), ('abre un servidor nginx', 'services.change'),
        ('levanta un servidor en el puerto 9000', 'networking.start_http_server'), ('arranca mysql', 'services.change'),
        ('crea un servidor web en ~/proyecto', 'networking.start_http_server'), ('levanta un servidor php', 'networking.start_http_server'),
        ('inicia el servicio redis', 'services.change'), ('levanta un servidor en la red local', 'networking.start_http_server')]),
    _R('restart_failed_services', r'\b(?:reinicia\w*|arregla\w*|repara\w*|levanta\w*)\b.*\bservicios (?:fallidos|caidos|que fallaron)\b',
       'services', 'restart_failed', ['reinicia los servicios fallidos'], 'reiniciar servicios fallidos', Risk.HIGH),
    _R('network_restart', r'\b(?:reinicia\w*|resetea\w*)\b.*\b(?:la red|el internet|el wifi|networking|la conexion)\b',
       'networking', 'network_restart', ['reinicia la red'], 'reiniciar la red', Risk.HIGH),
    _B('wifi_toggle', r'\b(?:enciende|encender|prende|apaga\w*|activa\w*|desactiva\w*|conecta|desconecta)\b.*\bwifi\b',
       build_onoff('networking', 'wifi_toggle', 'on', 'el Wi-Fi', r'\b(?:enciende|encender|prende|activa\w*|conecta)\b'),
       [('apaga el wifi', 'networking.wifi_toggle'), ('enciende el wifi', 'networking.wifi_toggle')]),
    _B('bluetooth_power', r'\b(?:enciende|encender|prende|apaga\w*|activa\w*|desactiva\w*)\b.*\bbluetooth\b',
       build_onoff('system', 'bluetooth_power', 'on', 'el Bluetooth', r'\b(?:enciende|encender|prende|activa\w*)\b'),
       [('apaga el bluetooth', 'system.bluetooth_power'), ('enciende el bluetooth', 'system.bluetooth_power')]),
    _B('service_active_q', _all(_rx(_SVC), _rx(r'\b(?:esta|sigue|anda|corre|funciona)\b.*\b(?:activo|activa|corriendo|encendido|funcionando|levantado|arriba|ejecutandose|vivo)\b|\b(?:activo|corriendo|funcionando)\?')),
       _with_service('services', 'is_active', 'comprobar si el servicio está activo'),
       [('esta activo nginx', 'services.is_active'), ('esta corriendo docker', 'services.is_active'), ('esta nginx corriendo', 'services.is_active')]),
    _B('service_enabled_q', _all(_rx(_SVC), _rx(r'\b(?:esta habilitado|arranca con el sistema|inicia con el sistema|inicia solo|se inicia al arrancar|esta en el arranque|arranca solo)\b')),
       _with_service('services', 'is_enabled', 'comprobar si el servicio arranca con el sistema'),
       [('esta habilitado ssh', 'services.is_enabled'), ('nginx arranca con el sistema', 'services.is_enabled')]),
    _B('service_deps', _all(_rx(_SVC), _rx(r'\b(?:dependencias de|de que depende|que depende de|dependencias)\b')), build_service_deps,
       [('dependencias de docker', 'services.dependencies')]),
    _B('service_unit_file', _all(_rx(_SVC), _rx(r'\b(?:archivo de unidad|unit file|configuracion del servicio|systemctl cat|como esta configurado)\b')),
       _with_service('services', 'unit_file', 'ver el archivo de unidad'), [('archivo de unidad de nginx', 'services.unit_file')]),
    _B('service_resources', _all(_rx(_SVC), _rx(r'\b(?:cuanta (?:memoria|ram|cpu)|consumo de|recursos de|uso de recursos|cuanto consume)\b')),
       _with_service('services', 'resource_usage', 'recursos que usa el servicio'),
       [('cuanta memoria usa nginx', 'services.resource_usage'), ('recursos de docker', 'services.resource_usage')]),
    _B('service_summary', _all(_rx(_SVC), _rx(r'\b(?:resumen de|como va|como esta|que tal|que onda con)\b')),
       _with_service('services', 'summary', 'resumen del servicio'), [('como esta nginx', 'services.summary')]),
    _B('service_ensure', _all(_rx(_SVC), _rx(r'\b(?:asegurate de que|asegura que|verifica que|checa que)\b')),
       _with_service('services', 'ensure_running', 'asegurar que el servicio esté activo', risk=Risk.HIGH),
       [('asegurate de que nginx este corriendo', 'services.ensure_running')]),
    _B('service_logs_since', _all(_rx(r'\b(?:logs?|registros?|errores)\b'), _rx(_SVC), _rx(r'\b(?:ultima hora|ultimas? \w+ (?:minutos?|horas?|dias?)|hoy|ayer|desde)\b')),
       build_service_logs_since, [('logs de nginx de la ultima hora', 'services.logs_since'), ('errores de docker de ayer', 'services.logs_since')]),
    _B('set_hostname', r'\b(?:cambia\w*|pon|renombra\w*|establece)\b.*\bnombre del (?:equipo|host|pc|ordenador|computadora)\b', build_set_hostname,
       [('cambia el nombre del equipo a rodnet-pc', 'system.set_hostname')]),
    Rule('service_change',
         _all(_rx(r'\b(reinicia\w*|restart|resetea|inicia\w*|start|deten\w*|stop|levanta\w*|arranca\w*|enciende|prende|apaga\w*|recarga\w*|reload|habilita\w*|deshabilita\w*|enable|disable|desactiva\w*|activa\w*)\b'),
              _rx(_SVC + r'|\bservicio\b')),
         build_service_change, [('reinicia nginx', 'services.change'), ('inicia el servicio redis', 'services.change'),
                                ('recarga la configuracion de nginx', 'services.change'), ('habilita ssh al arranque', 'services.change'),
                                ('deshabilita docker', 'services.change'), ('apaga mysql', 'services.change')]),
    Rule('run_in_terminal', _all(_rx(r'\b(?:ejecuta|corre|run)\b'), _rx(r'\bterminal\b')),
         build_open, [('ejecuta gemini cli en una nueva terminal', 'browser.open_application')]),
    Rule('open',
         _rx(r'\b(?:abrir|abre|abro|open|launch|inicia)\b|' + _SITE_OPEN_RX),
         build_open,
         [('abre firefox', 'browser.open_application'), ('abre github', 'browser.open_url'),
          ('abre https://github.com/user/repo', 'browser.open_url'), ('abre el archivo notas.txt', 'development.open_file'),
          ('abre una terminal y ejecuta el comando ls', 'browser.open_application'), ('abre', 'ask'),
          ('abre mercado libre', 'browser.open_url'), ('ve a hackthebox', 'browser.open_url'), ('abre htop', 'browser.open_application'),
          ('abre spotify en el navegador', 'browser.open_url'), ('abre gimp', 'browser.open_application'),
          ('abre gatos en youtube', 'browser.open_url'), ('abre firefox y vscode', 'browser.open_application'),
          ('abre yutube', 'ask')]),
    Rule('site_search', _rx(r'^(?:busca|buscar|googlea|google|encuentra|search|investiga)\s+.+\s+(?:en|on|in)\s+(?:' + _SEARCH_SITES + r')\s*$'),
         build_open, [('busca gatos en youtube', 'browser.open_url'), ('busca nginx en github', 'browser.open_url')]),
    Rule('exec_command', _rx(r'\b(ejecuta(?:\s+este)?(?:\s+el)?\s+comando|corre(?:\s+el)?\s+comando|run(?: the)? command|command:)'),
         build_exec_command, [('ejecuta el comando uptime', 'development.execute_command')]),
]


# ---------------------------------------------------------------------------
# Reglas nuevas: sistema, monitoreo, red y procesos (van antes de las genéricas)
# ---------------------------------------------------------------------------
NEW_RULES = [
    # --- control de procesos por PID (antes de suspender/bloquear el equipo)
    _B('process_pause', r'\b(?:pausa\w*|congela\w*|suspende\w*)\b.*\b(?:proceso|pid)\s*\d+', build_pid_signal('suspend'), [('pausa el proceso 1234', 'processes.suspend')]),
    _B('process_resume', r'\b(?:reanuda\w*|continua\w*|descongela\w*)\b.*\b(?:proceso|pid)\s*\d+', build_pid_signal('resume'), [('reanuda el proceso 1234', 'processes.resume')]),
    _B('process_renice', r'\b(?:prioridad|renice|nice)\b.*\b(?:proceso|pid)\s*\d+|\b(?:proceso|pid)\s*\d+\b.*\b(?:prioridad|nice)\b', build_renice,
       [('cambia la prioridad del proceso 1234 a 10', 'processes.renice')]),
    _B('process_details', r'\b(?:info\w*|detalles?|ficha|datos)\s+(?:del?|sobre)\s+(?:el\s+)?(?:proceso|pid)\s*\d+', _pid_op('details', 'ficha del proceso'),
       [('detalles del proceso 1234', 'processes.details')]),
    _B('process_open_files', r'\barchivos abiertos (?:por|de)l?\s+(?:el\s+)?(?:proceso|pid)\s*\d+', _pid_op('open_files', 'archivos abiertos del proceso'),
       [('archivos abiertos por el proceso 1234', 'processes.open_files')]),
    _B('process_connections', r'\bconexiones (?:del?|de el)\s+(?:proceso|pid)\s*\d+', _pid_op('connections_of', 'conexiones del proceso'),
       [('conexiones del proceso 1234', 'processes.connections_of')]),
    _B('process_memory', r'\b(?:memoria|ram) (?:del?|de el)\s+(?:proceso|pid)\s*\d+', _pid_op('memory_detail', 'memoria del proceso'),
       [('memoria del proceso 1234', 'processes.memory_detail')]),
    _B('process_children', r'\bhijos (?:del?|de el)\s+(?:proceso|pid)\s*\d+', _pid_op('children', 'procesos hijo'), [('hijos del proceso 1', 'processes.children')]),
    _B('process_by_port', r'\b(?:que (?:proceso|programa|app|aplicacion)|quien)\b.*\b(?:usa|esta usando|ocupa|escucha en|tiene)\b.*\bpuerto\s*\d+', build_by_port,
       [('que proceso usa el puerto 8080', 'processes.by_port'), ('quien ocupa el puerto 80', 'processes.by_port')]),
    _B('port_check', r'\b(?:esta (?:abierto|ocupado|libre|en uso) el puerto\s*\d+|puerto\s*\d+\s+(?:abierto|ocupado|libre|en uso))\b', build_port_check,
       [('esta ocupado el puerto 3000', 'networking.port_check_local')]),
    _B('process_by_user', r'\bprocesos de(?:l)?\s+(?:usuario\s+\w+|root)\b', build_by_user, [('procesos del usuario root', 'processes.by_user')]),
    _R('process_tree', r'\b(?:arbol de procesos|pstree|jerarquia de procesos|procesos en arbol)\b', 'processes', 'tree', ['muestra el arbol de procesos']),
    _R('process_zombies', r'\b(?:zombis?|zombies?)\b', 'processes', 'zombies', ['hay procesos zombie']),
    _R('process_count', r'\bcuantos procesos\b', 'processes', 'count', ['cuantos procesos hay']),
    _R('cpu_hogs', r'\b(?:procesos? (?:que )?(?:mas )?(?:consum\w+|usan|gastan) (?:mas )?(?:de )?cpu|que (?:consume|gasta|usa) mas (?:cpu|procesador)|top (?:de )?cpu|quien consume mas cpu|procesos? (?:que )?mas cpu|mas cpu (?:consum\w+|usan)|procesos pesados|que me esta gastando el procesador)\b',
       'processes', 'cpu_hogs', ['que proceso consume mas cpu', 'top de cpu'], args={'limit': 10}),
    _B('find_process', r'\b(?:busca\w*|encuentra|hay)\s+(?:el\s+|un\s+|algun\s+)?proceso\b|\bpid de\b|\b(?:esta|sigue)\b.*\b(?:corriendo|ejecutandose)\b|\bcorriendo\s+\w+$',
       build_find_process, [('busca el proceso firefox', 'processes.find_by_name'), ('esta corriendo firefox', 'processes.find_by_name'), ('pid de spotify', 'processes.find_by_name')]),
    # --- monitoreo
    _R('health_check', r'\b(?:estado de salud|salud del (?:sistema|equipo|pc|servidor)|health check|chequeo del sistema|revision general|como esta (?:mi|el) (?:sistema|pc|equipo|servidor)|diagnostico del sistema|esta todo bien)\b',
       'monitoring', 'health_check', ['como esta mi sistema', 'chequeo del sistema'], 'diagnóstico global de salud'),
    _R('snapshot', r'\b(?:instantanea|snapshot|panorama del sistema|dashboard|panel del sistema|monitor en vivo|estadisticas del sistema|metricas del sistema)\b',
       'monitoring', 'snapshot', ['dame una instantanea del sistema'], 'instantánea del sistema'),
    _R('thresholds', r'\b(?:alertas?|algo anormal|algun problema|hay (?:algun )?problema|sobrecarga|umbrales)\b', 'monitoring', 'check_thresholds', ['hay alguna alerta', 'tengo algun problema']),
    _R('disk_io', r'\b(?:velocidad (?:del )?(?:disco|ssd|hdd)|lectura y escritura|e/s de disco|disk io|iops|actividad del disco)\b', 'monitoring', 'get_disk_io', ['actividad del disco']),
    _R('net_throughput', r'\b(?:cuanto (?:estoy )?(?:descargando|subiendo)|velocidad de (?:red|descarga|subida) (?:actual|ahora)|trafico de red|ancho de banda (?:actual|ahora|en uso)|consumo de red|bandwidth)\b',
       'monitoring', 'get_network_throughput', ['cuanto estoy descargando', 'trafico de red']),
    _B('watch_metric', r'^(?:vigila\w*|monitorea\w*|monitorizar)\s*$|\b(?:vigila\w*|monitorea\w*|monitorizar|observa\w*|sigue)\b.*\b(?:cpu|procesador|memoria|ram|swap|carga|temperatura|red|internet|disco|ssd)\b', build_watch,
       [('vigila la cpu', 'monitoring.watch_metric'), ('monitorea la memoria 30 segundos', 'monitoring.watch_metric'), ('vigila', 'ask')]),
    _R('oom_events', r'\b(?:oom|out of memory|se quedo sin memoria|memoria agotada)\b', 'monitoring', 'get_oom_events', ['hubo eventos oom']),
    _R('pressure', r'\b(?:presion de (?:memoria|cpu|io)|pressure stall|psi del sistema)\b', 'monitoring', 'get_pressure', ['presion de memoria']),
    _R('file_descriptors', r'\b(?:descriptores de archivo|file descriptors)\b', 'monitoring', 'get_file_descriptors', ['descriptores de archivo']),
    _R('swap_by_process', r'\bque procesos usan (?:el )?swap\b', 'monitoring', 'get_swap_by_process', ['que procesos usan swap']),
    _R('mem_by_user', r'\b(?:memoria|ram) por usuario\b', 'monitoring', 'get_memory_by_user', ['ram por usuario']),
    _R('recent_errors', r'\b(?:errores recientes|ultimos errores|errores del sistema|errores en el log|log de errores)\b', 'monitoring', 'get_recent_errors', ['errores recientes']),
    # --- servicios (listas)
    _R('services_failed', r'\b(?:servicios fallidos|unidades fallidas|servicios caidos|servicios que fallaron|que servicios fallaron|failed services)\b', 'services', 'list_failed', ['servicios fallidos']),
    _R('services_enabled', r'\b(?:servicios habilitados|servicios (?:al|en el) arranque|enabled services|que arranca con el sistema)\b', 'services', 'list_enabled', ['servicios habilitados']),
    _R('services_running', r'\b(?:servicios (?:activos|corriendo|en ejecucion|funcionando)|lista de servicios|que servicios (?:hay|estan)|list services)\b', 'services', 'list_running', ['servicios activos', 'lista de servicios']),
    _R('services_timers', r'\b(?:temporizadores|systemd timers|timers del sistema|tareas programadas del sistema|list timers)\b', 'services', 'list_timers', ['timers del sistema']),
    _R('services_boot_blame', r'\b(?:que (?:tarda|demora) (?:mas )?en arrancar|arranque lento|tiempo de arranque|boot blame|analiza el arranque)\b', 'services', 'boot_blame', ['que tarda mas en arrancar']),
    _B('services_find', r'\b(?:existe el servicio|hay un servicio|busca\w* (?:el )?servicio|servicios que (?:contengan|tengan))\b', build_find_service, [('busca el servicio docker', 'services.find_service')]),
    # --- sesión y energía
    _R('lock_screen', r'\b(?:bloquea|bloquear|lock)\b.*\b(?:pantalla|equipo|pc|sesion|screen)\b|\block screen\b', 'system', 'lock_screen', ['bloquea la pantalla'], 'bloquear la pantalla', Risk.MODERATE),
    _R('logout', r'\b(?:cierra|cerrar|termina)\s+(?:la\s+)?sesion\b|\blogout\b|\bsign out\b', 'system', 'logout', ['cierra la sesion'], 'cerrar la sesión', Risk.HIGH),
    _R('suspend', r'\b(?:suspende\w*|suspender|duerme el equipo|poner en reposo|suspension)\b', 'system', 'suspend', ['suspende el equipo'], 'suspender el equipo', Risk.HIGH),
    _R('hibernate', r'\bhibern\w+', 'system', 'hibernate', ['hiberna el equipo'], 'hibernar el equipo', Risk.HIGH),
    _R('cancel_shutdown', r'\b(?:cancela\w*|aborta\w*)\b.*\b(?:apagado|reinicio|shutdown)\b', 'system', 'cancel_shutdown', ['cancela el apagado'], 'cancelar apagado programado', Risk.HIGH),
    _R('reboot_required', r'\b(?:necesito reiniciar|hace falta reiniciar|reinicio pendiente|reboot required|pide reiniciar)\b', 'system', 'reboot_required', ['necesito reiniciar']),
    _B('screenshot', r'\b(?:captura de pantalla|screenshot|toma\w* una captura|haz una captura|saca\w* una captura|captura la pantalla|tomar captura)\b', build_screenshot,
       [('toma una captura de pantalla', 'system.screenshot')]),
    _B('notify', r'\b(?:notificame|enviame una notificacion|manda una notificacion|notify)\b', build_notify, [('notificame que ya termino', 'system.notify')]),
    _B('clipboard_copy', r'\bcopia(?:r)?\b.*\bportapapeles\b', build_clipboard_copy, [('copia "hola" al portapapeles', 'system.clipboard_copy')]),
    _R('clipboard_paste', r'\b(?:que hay en el portapapeles|muestra el portapapeles|contenido del portapapeles|pega el portapapeles)\b', 'system', 'clipboard_paste', ['que hay en el portapapeles']),
    _B('audio_mute', r'\b(?:silencia\w*|mutea\w*|mute|unmute|desmutea\w*|desilencia\w*|quita el sonido|pon el sonido|activa el sonido|alterna el sonido)\b', build_mute,
       [('silencia el audio', 'system.audio_mute'), ('activa el sonido', 'system.audio_mute')]),
    _B('volume_step', r'\b(?:volumen|sonido|audio)\b', _step('system', 'audio_step', 'el volumen'), [('sube el volumen', 'system.audio_step'), ('baja el volumen', 'system.audio_step')]),
    _B('brightness_step', r'\b(?:brillo|brightness)\b', _step('system', 'brightness_step', 'el brillo'), [('sube el brillo', 'system.brightness_step'), ('menos brillo', 'system.brightness_step')]),
    Rule('volume', _rx(r'\b(volumen|volumen de audio|audio volume)\b'), _level('system', 'audio_volume', 'volume', 'volumen de audio'),
         [('volumen 30', 'system.audio_volume'), ('pon el volumen al cincuenta', 'system.audio_volume'), ('cambia el volumen a 40', 'system.audio_volume')]),
    Rule('brightness', _rx(r'\b(brillo|brightness)\b'), _level('system', 'screen_brightness', 'brightness', 'brillo de pantalla'),
         [('brillo 50', 'system.screen_brightness'), ('brillo al setenta', 'system.screen_brightness')]),
    Rule('timezone', _rx(r'\b(?:cambia\w*|pon|establece)\b.*\b(?:zona horaria|timezone)\b|\bcambiar hora\b|^zona horaria$'), build_timezone,
         [('cambia la zona horaria a America/Mexico_City', 'system.set_timezone'), ('zona horaria', 'ask')]),
    _B('power_schedule', r'\b(?:apaga\w*|reinicia\w*|shutdown|reboot)\b.*\b(?:en|dentro de)\s+\w+\s*(?:segundos?|minutos?|min|horas?)\b', build_power,
       [('apaga el equipo en 10 minutos', 'system.power_schedule'), ('reinicia en dos horas', 'system.power_schedule')]),
    # --- información del sistema
    _R('os_release', r'\b(?:que (?:distro|distribucion|sistema operativo)|version del? (?:sistema|linux|ubuntu|debian|fedora|arch)|os release|distro|distribucion de linux|que version de (?:linux|ubuntu|debian))\b',
       'system', 'os_release', ['que distro uso', 'que sistema operativo tengo']),
    _R('kernel_version', r'\b(?:version del? kernel|kernel version|uname|que kernel)\b', 'system', 'kernel_version', ['version del kernel']),
    _R('uptime', r'\b(?:uptime|cuanto tiempo lleva (?:encendid\w+|prendid\w+)|tiempo encendid\w+|desde cuando esta encendid\w+|cuanto llevo encendid\w+|tiempo de actividad)\b',
       'system', 'uptime', ['uptime', 'cuanto tiempo lleva encendido']),
    _R('boot_time', r'\b(?:cuando (?:arranco|inicio|se encendio|prendi)|ultimo arranque|hora de arranque|last boot|boot time)\b', 'system', 'boot_time', ['cuando arranco el equipo']),
    _R('load_average', r'\b(?:carga del sistema|load average|carga promedio|carga media)\b', 'system', 'load_average', ['carga del sistema']),
    _R('cpu_usage', r'\b(?:uso del procesador|porcentaje de cpu|cuanto cpu (?:estoy )?us\w+|cpu usage|que tan ocupado (?:esta )?(?:el )?(?:procesador|cpu))\b', 'system', 'cpu_usage', ['porcentaje de cpu', 'uso del procesador']),
    _R('cpu_frequency', r'\b(?:frecuencia (?:del|de la) (?:procesador|cpu)|cpu mhz|velocidad (?:del|de la) (?:procesador|cpu)|ghz)\b', 'system', 'cpu_frequency', ['frecuencia del procesador']),
    _R('memory_summary', r'\b(?:resumen|detalle|desglose) de (?:la )?(?:ram|memoria)\b', 'system', 'memory_summary', ['resumen de la memoria']),
    _R('swap_info', r'\b(?:swap|memoria virtual|memoria de intercambio)\b', 'system', 'swap_info', ['cuanto swap tengo']),
    _R('battery', r'\b(?:bateria|battery|cuanta carga|nivel de carga|estoy cargando|esta cargando)\b', 'system', 'battery', ['cuanta bateria me queda']),
    _R('temperatures', r'\b(?:temperaturas?|que tan caliente|esta caliente|sobrecalent\w+|cuantos grados|ventiladores?)\b', 'system', 'temperatures', ['temperatura del cpu', 'esta caliente mi pc']),
    _R('gpu_usage', r'\b(?:uso de (?:la )?gpu|gpu usage|nvidia smi|nvidia-smi|estado de la (?:gpu|tarjeta grafica)|cuanta vram|vram)\b', 'system', 'gpu_usage', ['uso de la gpu']),
    _R('list_users', r'\b(?:lista\w* (?:los )?usuarios|usuarios del sistema|que usuarios (?:hay|existen|tiene)|list users|cuentas de usuario)\b', 'system', 'list_users', ['lista los usuarios']),
    _R('logged_users', r'\b(?:usuarios conectados|sesiones activas|quienes estan (?:conectados|dentro)|quien esta conectado|who is logged)\b', 'system', 'logged_users', ['usuarios conectados']),
    _R('last_logins', r'\b(?:ultimos? (?:accesos|inicios de sesion|logins)|last logins?|historial de (?:accesos|logins|sesiones))\b', 'system', 'last_logins', ['ultimos accesos']),
    _R('my_groups', r'\b(?:a que grupos pertenezco|mis grupos|en que grupos estoy|my groups)\b', 'system', 'my_groups', ['a que grupos pertenezco']),
    _R('sudo_check', r'\b(?:tengo sudo|puedo usar sudo|soy sudoer|soy root|am i root)\b', 'system', 'sudo_check', ['tengo sudo']),
    _R('usb_devices', r'\b(?:dispositivos usb|lsusb|que usb|usb conectados?|puertos usb)\b', 'system', 'usb_devices', ['dispositivos usb']),
    _R('pci_devices', r'\b(?:dispositivos pci|lspci|tarjetas pci)\b', 'system', 'pci_devices', ['dispositivos pci']),
    _R('mounts', r'\b(?:puntos de montaje|que esta montado|particiones montadas|mount points?|dispositivos montados)\b', 'system', 'mounts', ['puntos de montaje']),
    _R('block_devices', r'\b(?:lsblk|particiones|dispositivos de bloque|unidades de disco|discos y particiones|que discos tengo)\b', 'system', 'block_devices', ['que discos tengo', 'lsblk']),
    _R('disk_inodes', r'\b(?:inodos?|inodes?)\b', 'system', 'disk_inodes', ['uso de inodos']),
    _R('kernel_modules', r'\b(?:modulos del kernel|lsmod|modulos cargados|kernel modules)\b', 'system', 'kernel_modules', ['modulos del kernel']),
    _R('hostname_info', r'\b(?:nombre del (?:equipo|host|pc|ordenador)|hostnamectl|como se llama (?:mi|el) (?:pc|equipo|computadora|ordenador)|nombre de host)\b', 'system', 'hostname_info', ['como se llama mi pc']),
    _R('locale_info', r'\b(?:idioma del sistema|configuracion regional|system locale)\b', 'system', 'locale_info', ['idioma del sistema']),
    _R('keyboard_layout', r'\b(?:distribucion del teclado|layout del teclado|idioma del teclado|disposicion del teclado|keyboard layout)\b', 'system', 'keyboard_layout', ['layout del teclado']),
    _R('display_info', r'\b(?:resolucion de (?:la )?pantalla|resolucion actual|monitores conectados|cuantos monitores|xrandr|screen resolution)\b', 'system', 'display_info', ['resolucion de pantalla']),
    _R('session_info', r'\b(?:wayland o x11|x11 o wayland|servidor grafico|tipo de sesion|session type|que escritorio uso|entorno de escritorio)\b', 'system', 'session_info', ['uso wayland o x11']),
    _R('security_status', r'\b(?:estado de (?:apparmor|selinux)|postura de seguridad|seguridad del sistema|aslr|secure boot|hardening)\b', 'system', 'security_status', ['seguridad del sistema', 'estado de apparmor']),
    _R('dmesg_errors', r'\b(?:dmesg|errores del kernel|errores de kernel|kernel errors)\b', 'system', 'dmesg_errors', ['errores del kernel']),
    _R('boot_errors', r'\b(?:errores (?:del|de este|de) arranque|errores de boot|boot errors|errores graves)\b', 'system', 'boot_errors', ['errores del arranque']),
    _R('ntp_status', r'\b(?:sincronizacion de (?:la )?hora|reloj sincronizado|ntp|esta sincronizada la hora)\b', 'system', 'ntp_status', ['sincronizacion de la hora']),
    _R('timezone_info', r'\b(?:que zona horaria|zona horaria actual|mi zona horaria|en que zona horaria)\b', 'system', 'timezone_info', ['que zona horaria tengo']),
    _R('calendar_text', r'\b(?:muestra|ver|dame)\b.*\bcalendario\b', 'system', 'calendar_text', ['muestra el calendario']),
    _R('ulimits', r'\b(?:ulimit|limites del usuario|limite de archivos abiertos|limites de recursos)\b', 'system', 'ulimits', ['limites del usuario']),
    _B('sysctl', r'\bsysctl\b', build_sysctl, [('sysctl vm.swappiness', 'system.sysctl_get'), ('sysctl', 'ask')]),
    _B('env_get', r'\becho\s+\$\w+|\b(?:que vale|valor de|cuanto vale)\b.*\$\w+|\bvariable\s+\w+\s+(?:vale|contiene)\b|\bque (?:vale|contiene) (?:la )?variable\s+\w+', build_env_get,
       [('echo $HOME', 'system.env_get'), ('que vale $USER', 'system.env_get')]),
    _R('path_dirs', r'\b(?:mi path|variable path|directorios del path|que hay en el path)\b', 'system', 'path_dirs', ['mi path']),
    _R('shell_info', r'\b(?:que shell (?:uso|tengo|estoy usando)|shell actual|mi shell|shells disponibles)\b', 'system', 'shell_info', ['que shell uso']),
    _R('summary', r'\b(?:resumen de(?:l| mi)? (?:sistema|equipo|pc|computadora)|neofetch|especificaciones|specs|ficha tecnica|informe del equipo|sobre mi (?:pc|equipo|computadora))\b', 'system', 'summary', ['especificaciones de mi pc', 'resumen del equipo']),
    _R('pkg_count', r'\b(?:cuantos paquetes|paquetes instalados)\b', 'system', 'installed_packages_count', ['cuantos paquetes tengo instalados']),
    _R('pkg_upgradable', r'\b(?:actualizaciones disponibles|paquetes actualizables|hay actualizaciones|que se puede actualizar|upgradable)\b', 'system', 'upgradable_packages', ['hay actualizaciones'], timeout=90),
    _R('empty_trash', r'\b(?:vacia|vaciar)\b.*\bpapelera\b', 'system', 'empty_trash', ['vacia la papelera'], 'vaciar la papelera', Risk.HIGH),
    _B('disk_hogs', r'\b(?:que (?:carpetas?|directorios?) (?:ocupan|pesan|usan) mas|carpetas mas (?:grandes|pesadas)|que ocupa mas espacio|que esta llenando el disco|du top|que ocupa espacio)\b', build_disk_hogs,
       [('que carpetas ocupan mas espacio', 'system.disk_hogs')]),
    _B('large_files', r'\b(?:archivos (?:mas )?(?:grandes|pesados|gigantes)|los mas pesados|archivos que mas pesan)\b', build_large_files, [('archivos mas grandes', 'system.large_files')]),
    _B('recent_files', r'\b(?:archivos (?:recientes|modificados (?:hoy|recientemente|ultimamente)|nuevos)|que archivos cambiaron|ultimos archivos modificados)\b', build_recent_files,
       [('archivos modificados hoy', 'system.recent_files')]),
    # --- red
    _R('default_gateway', r'\b(?:puerta de enlace|gateway|router predeterminado|ip del router|cual es mi router)\b', 'networking', 'default_gateway', ['ip del router']),
    _R('dns_servers', r'\b(?:servidores dns|mi dns|dns actual|que dns uso|dns configurad\w+)\b', 'networking', 'dns_servers', ['que dns uso']),
    _R('mac_addresses', r'\b(?:direccion mac|mac address|mi mac|macs)\b', 'networking', 'mac_addresses', ['mi mac']),
    _R('link_speed', r'\b(?:velocidad del enlace|velocidad de la tarjeta de red|link speed)\b', 'networking', 'link_speed', ['velocidad del enlace']),
    _R('arp_table', r'\b(?:tabla arp|dispositivos en (?:mi )?red|quien esta en mi red|que dispositivos hay en la red|vecinos de red|que hay en mi red|quienes estan en mi red)\b', 'networking', 'arp_table', ['quien esta en mi red']),
    _R('hosts_file', r'\b(?:archivo hosts|etc hosts|mi hosts)\b', 'networking', 'hosts_file', ['archivo hosts']),
    _R('net_summary_conn', r'\b(?:resumen de conexiones|estadisticas de sockets)\b', 'networking', 'connection_summary', ['resumen de conexiones']),
    _R('net_connections', r'\b(?:conexiones (?:activas|establecidas|abiertas)|a donde se conecta mi (?:pc|equipo))\b', 'networking', 'network_connections', ['conexiones activas']),
    _R('nm_connections', r'\b(?:conexiones guardadas|perfiles de red|redes guardadas)\b', 'networking', 'network_manager_connections', ['redes guardadas']),
    _B('dns_lookup', r'\b(?:resuelve\w*|dns de|dig|nslookup|a que ip apunta|ip de|que ip tiene|consulta dns|registros? (?:mx|txt|ns|aaaa|cname))\b', build_dns_lookup,
       [('a que ip apunta google.com', 'networking.dns_lookup'), ('registros mx de gmail.com', 'networking.dns_lookup')]),
    _B('reverse_dns', r'\b(?:dns inverso|reverse dns|a quien pertenece la ip|nombre de la ip)\b', build_reverse_dns, [('dns inverso de 8.8.8.8', 'networking.reverse_dns')]),
    _B('ssl_expiry', r'\b(?:certificado ssl|expira el certificado|cuando vence el certificado|caducidad del certificado|ssl de|tls de|certificado de)\b', build_ssl,
       [('cuando vence el certificado de github.com', 'networking.ssl_expiry')]),
    _B('http_headers', r'\b(?:cabeceras|headers)\b', _domain_op('http_headers', key='url'), [('cabeceras de https://example.com', 'networking.http_headers')]),
    _B('site_up', r'\b(?:esta (?:caido|arriba|disponible|en linea|up)|is it down)\b|\bfunciona\b', _domain_op('check_site_up', key='url'),
       [('esta caido google.com', 'networking.check_site_up')]),
    _R('check_internet', r'(?<!no )(?<!sin )\b(?:tengo|hay)\s+internet\b|\bsalida a internet\b', 'networking', 'check_internet', ['tengo internet']),
    _R('latency', r'\b(?:latencia|tiempo de respuesta de la red|lag de red)\b', 'networking', 'latency_check', ['latencia de mi red']),
    _R('wifi_networks', r'\bwifi\b.*\b(?:redes|disponibles|cerca)\b|\bredes (?:wifi|inalambricas)\b', 'networking', 'wifi_networks', ['redes wifi disponibles']),
    _R('wifi_status', r'\bwifi\b', 'networking', 'wifi_status', ['estado del wifi']),
    _R('bluetooth_status', r'\bbluetooth\b', 'system', 'bluetooth_status', ['estado del bluetooth']),
    _R('firewall_rules', r'\b(?:reglas del firewall|reglas de iptables|reglas de ufw|ufw status|iptables -l)\b', 'networking', 'firewall_rules', ['reglas del firewall']),
    _R('flush_dns', r'\b(?:limpia|vacia|flush|borra)\b.*\bcache dns\b|\bflush dns\b', 'networking', 'flush_dns', ['limpia la cache dns'], 'vaciar la caché DNS', Risk.MODERATE),
    _R('net_summary', r'\b(?:resumen de (?:la )?red|estado de (?:la )?red|panorama de red|como esta mi red)\b', 'networking', 'network_summary', ['resumen de la red']),
]


# ---------------------------------------------------------------------------
# Reglas originales (con sinónimos añadidos y varias reordenadas: «cambia…» ya no las roba «edit»)
# ---------------------------------------------------------------------------
ORIGINAL_RULES = [
    Rule('nmap', lambda s, t: (bool(re.search(r'\bnmap\b', s)) or _remote_scan(s, t)) and not re.search(r'\b(?:instala\w*|install)\b', s), build_nmap,
         [('escanea puertos de 10.0.0.5 autorizado', 'cybersecurity.scan'), ('nmap a 10.0.0.5', 'ask'), ('nmap', 'ask')]),
    Rule('listening_ports',
         lambda s, t: (bool(re.search(r'\bpuertos?\b', s)) and (bool(re.search(r'\b(abiertos?|listening|escanea|escanear|scan|quiero|muestra|mostrar|ver|dame)\b', s))
                                                                 or bool(re.search(r'\b(mi ip|localhost|127\.0\.0\.1|locales?)\b', s))))
                      or (bool(re.search(r'\b(escanea|escanear|scan)\b', s)) and bool(re.search(r'\b(mi ip|localhost|127\.0\.0\.1|loopback)\b', s))),
         _simple('networking', 'listening_ports', 'consultar los puertos que escuchan localmente'),
         [('muestra mis puertos abiertos', 'networking.listening_ports'), ('escanea localhost', 'networking.listening_ports')]),
    Rule('chmod', lambda s, t: bool(re.search(r'\b(chmod)\b', s)) or (bool(re.search(r'\b(permisos|permissions)\b', s)) and bool(re.search(r'\b[0-7]{3,4}\b', s))),
         build_chmod, [('cambia permisos 755 de /tmp/x', 'filesystem.change_permissions'), ('chmod', 'ask')]),
    Rule('chown', _rx(r'\b(propietario|owner|chown)\b'), build_chown, [('cambia el propietario de /tmp/x usuario juan', 'filesystem.change_owner')]),
    Rule('delete', _rx(r'\b(elimina|eliminar|borra|borrar|delete|remove)\b'), build_delete,
         [('elimina /tmp/archivo.txt', 'filesystem.delete'), ('borra el archivo hola.py', 'filesystem.delete'), ('eliminar', 'ask')]),
    Rule('edit', _rx(r'\b(modifica|modificar|edit|edita|editar|cambia|cambiar|escribe|write)\b'), build_edit,
         [('modifica /tmp/archivo.txt', 'filesystem.write'), ('edita el archivo notas.py', 'filesystem.write'), ('modificar', 'ask')]),
    Rule('move', _rx(r'\b(mueve|mover|move|renombra|renombrar|rename)\b'), build_move,
         [('mueve a.txt a /tmp', 'filesystem.move'), ('mover', 'ask')]),
    Rule('kill', _all(_rx(r'\b(mata|matar|termina|terminar|kill)\b'), _rx(r'\b(proceso|pid|kill|programa)\b|\b\d{2,9}\b')), build_kill,
         [('mata el proceso 1234', 'processes.terminate'), ('kill proceso', 'ask')]),
    _B('kill_by_name', r'\b(?:mata|matar|killall|pkill|termina|terminar|finaliza|finalizar|cierra|cerrar|fuerza el cierre de)\s+\w', build_kill_by_name,
       [('mata firefox', 'processes.terminate_by_name'), ('cierra spotify', 'processes.terminate_by_name'), ('killall chrome', 'processes.terminate_by_name')]),
    Rule('memory_top', _all(_rx(r'\b(ram|memoria)\b'), _rx(r'\b(proceso|procesos|consume|consumen|usar|usando)\b')),
         _simple('processes', 'memory_top', args={'limit': 10}), [('que procesos consumen mas ram', 'processes.memory_top')]),
    Rule('process_list', _all(_rx(r'\b(procesos?|process(?:es)?)\b'), _rx(r'\b(lista|listar|muestra|mostrar|ver|activos?|running)\b')),
         _simple('processes', 'list'), [('lista los procesos activos', 'processes.list')]),
    Rule('service_logs', _all(_rx(r'\b(logs?|registros?|errores?)\b'), _rx(_SVC + r'|\bservicio\b')), build_service_logs,
         [('logs de nginx ultimos 20', 'services.logs')]),
    Rule('time', _rx(r'\b(que hora|hora es|hora tienes|what time|fecha de hoy|que dia es|que fecha|hoy es que dia|la hora|hora actual|fecha actual|dia de hoy|a cuanto estamos)\b'), build_time,
         [('que hora es', 'system.time'), ('que dia es hoy', 'system.time'), ('dime la hora', 'system.time')]),
    Rule('ram', _all(_rx(r'\b(cuanta|ram|memory)\b|memoria ram'), _rx(r'\b(ram|memoria|memory)\b')), _simple('system', 'ram'),
         [('cuanta ram libre tengo', 'system.ram')]),
    Rule('identity', _rx(r'\b(quien soy|quien esta logueado|usuario actual|que permisos tengo|permisos de mi usuario|whoami|con que usuario|como me llamo en el sistema)\b'),
         _simple('system', 'identity'), [('quien soy', 'system.identity'), ('whoami', 'system.identity')]),
    Rule('cwd', _rx(r'\b(donde estoy|carpeta actual|directorio actual|working directory|pwd|en que carpeta estoy|en que directorio estoy|ruta actual)\b'), _simple('system', 'cwd'),
         [('carpeta actual', 'system.cwd'), ('en que carpeta estoy', 'system.cwd')]),
    Rule('public_ip', _rx(r'\b(ip publica|public ip|ip externa|ip de internet)\b'), _simple('networking', 'public_ip'), [('cual es mi ip publica', 'networking.public_ip'), ('mi ip externa', 'networking.public_ip')]),
    Rule('local_addresses', _rx(r'\b(mi ip|my ip|mi direccion ip|ip local|local ip|ip privada|ip de mi red)\b'), _simple('networking', 'local_addresses'),
         [('cual es mi ip', 'networking.local_addresses'), ('mi ip privada', 'networking.local_addresses')]),
    Rule('network_view',
         _all(_rx(r'\b(interfaz|interfaces|ip address|direccion(?:es)? ip|rutas?|route table)\b'), _not(_rx(r'\b(tu interfaz|interfaz es|interface is)\b'))),
         build_network_view, [('muestra las rutas', 'networking.routes'), ('ver interfaces', 'networking.interfaces')]),
    Rule('network_diagnose',
         lambda s, t: bool(re.search(r'\b(conectividad|diagnostica|diagnosticar|diagnostico de red|troubleshoot network)\b', s))
                      or bool(re.search(r'\b(?:no tengo|no hay|no funciona|se cayo|perdi)\b.{0,30}\binternet\b|\binternet\b.{0,20}\b(?:no funciona|esta caido|fallo)\b', s)),
         _simple('networking', 'diagnose'), [('no tengo internet', 'networking.diagnose')]),
    Rule('tcp_test', _rx(r'\b(tcp|conectar|conexion|connection)\b'), build_tcp,
         [('conectar a 10.0.0.5 puerto 22', 'networking.tcp_test'), ('prueba tcp', 'ask')]),
    Rule('cpu_top', _rx(r'\b(cpu top|uso de cpu)\b'), _simple('processes', 'cpu_top'), [('uso de cpu', 'processes.cpu_top')]),
    Rule('io_top', _rx(r'\b(io top|uso de io)\b'), _simple('processes', 'io_top'), [('io top', 'processes.io_top')]),
    Rule('search_names', _all(_rx(r'\b(busca|buscar|encuentra|find|search)\b'), _rx(r'\b(archivo|archivos|fichero|ficheros|file|files|nombre)\b')),
         build_search_names, [('busca el archivo informe', 'filesystem.search_names'), ('busca archivo update.log', 'filesystem.search_names')]),
    Rule('system_logs', _all(_rx(r'\b(logs?|registros?)\b'), _not(_rx(r'\bgit\b'))), build_system_logs, [('muestra los logs ultimos 30', 'system.logs')]),
    Rule('disk_usage', _rx(r'\b(disk usage|espacio (?:libre )?en disco|uso de disco|cuanto espacio libre|cuanto espacio (?:me )?queda|espacio disponible|disco lleno)\b'), build_disk_usage,
         [('cuanto espacio libre tengo', 'filesystem.disk_usage'), ('uso de disco del sistema', 'filesystem.disk_usage'), ('cuanto espacio me queda', 'filesystem.disk_usage')]),
    Rule('system_info',
         _all(_rx(r'\b(sistema|hostname|kernel|memoria|cpu|informacion del equipo|info(?:rmacion)? (?:de mi|del) sistema|system info)\b'),
              _not(_rx(r'\b(actualiza\w*|update|upgrade|apag\w+|reinicia\w*|reboot|shutdown|restart)\b'))),
         _simple('system', 'info'), [('info de mi sistema', 'system.info')]),
    Rule('list_dir',
         lambda s, t: (bool(re.search(r'\b(list|lista|listar|muestra|mostrar|contents|contenido)\b', s))
                       and bool(re.search(r'\b(files?|archivos?|directorio|carpeta|directory|folder)\b', s)))
                      or bool(re.search(r'\b(?:que archivos hay|que archivos tiene|que contiene esta carpeta|que hay en esta carpeta|what files are)\b', s))
                      or bool(re.search(r'\b(?:lee|leer|read)\s+(?:esta|este|la|el|this|the)\s+(?:carpeta|directorio|folder|directory)\b', s))
                      or (bool(re.search(r'^(?:lista|listar|ls)\b', s)) and bool(_path(t))),
         build_list, [('lista los archivos de /tmp', 'filesystem.list'), ('lista ~/Descargas', 'filesystem.list')]),
    Rule('create_file', _all(_rx(r'\b(crea|crear|create|nuevo|new|genera|generar)\b'), _rx(r'\b(archivo|fichero|file|script|programa|doc)\b')),
         build_create, [('crea un archivo llamado notas.txt', 'filesystem.create'), ('crea un archivo en /nonexistent_dir_x', 'filesystem.create'), ('crea archivo', 'ask')]),
    Rule('mkdir', _all(_rx(r'\b(crea|crear|create)\b'), _rx(r'\b(carpeta|directorio|folder|directory)\b')),
         build_mkdir, [('crea carpeta /tmp/nueva', 'filesystem.mkdir'), ('crear directorio docs', 'filesystem.mkdir'), ('crear carpeta', 'ask')]),
    Rule('touch', _rx(r'\b(touch|archivo vacio|empty file)\b'), build_touch,
         [('touch /tmp/archivo.txt', 'filesystem.create'), ('crea archivo vacio hola.txt', 'filesystem.create')]),
    Rule('find_content', _all(_rx(r'\b(busca|buscar|find|search)\b'), _rx(r'\b(texto|contenido|content)\b')),
         build_find_content, [('busca texto "hola" en /tmp', 'filesystem.search_text'), ('buscar texto "error" en .', 'filesystem.search_text')]),
    Rule('apt_install', _all(_rx(r'\b(apt|apt-get)\b'), _rx(r'\b(install|instala|instalar)\b')),
         build_apt_install, [('apt install vim', 'package_manager.apt_install'), ('instala curl con apt', 'package_manager.apt_install')]),
    Rule('pip_install', _all(_rx(r'\b(pip|pip3)\b'), _rx(r'\b(install|instala|instalar)\b')),
         build_pip_install, [('pip install requests', 'package_manager.pip_install'), ('instala numpy con pip', 'package_manager.pip_install')]),
    Rule('npm_install', _all(_rx(r'\b(npm)\b'), _rx(r'\b(install|instala|instalar)\b')),
         build_npm_install, [('npm install lodash', 'package_manager.npm_install'), ('instala express con npm', 'package_manager.npm_install')]),
    Rule('scan_folder', _all(_rx(r'\b(escanea|escanear|scan)\b'), _rx(r'\b(carpeta|directorio|folder|directory)\b')), build_scan_folder,
         [('escanea la carpeta /tmp', 'filesystem.list')]),
    Rule('csv_to_json', _rx(r'\b(csv a json|csv to json)\b'), build_csv_to_json, [('convierte csv a json /tmp/a.csv', 'data_processing.csv_to_json')]),
    Rule('json_to_csv', _rx(r'\b(json a csv|json to csv)\b'), build_json_to_csv, [('convierte json a csv /tmp/a.json', 'data_processing.json_to_csv')]),
    Rule('read_csv', _rx(r'\b(csv|leer csv)\b'), lambda s, t, c: _with_path(t, 'Indica la ruta del archivo CSV', 'data_processing', 'read_csv', 'file_path'),
         [('lee el csv /tmp/a.csv', 'data_processing.read_csv')]),
    Rule('read_json', _rx(r'\b(json|leer json)\b'), lambda s, t, c: _with_path(t, 'Indica la ruta del archivo JSON', 'data_processing', 'read_json', 'file_path'),
         [('lee el json /tmp/a.json', 'data_processing.read_json')]),
    Rule('read_file', _rx(r'\b(read|lee|leer|contenido de|cat)\b'),
         lambda s, t, c: _with_path(t, '¿Qué archivo quieres leer?', 'filesystem', 'read', 'path'),
         [('lee /tmp/notas.txt', 'filesystem.read'), ('lee', 'ask')]),
    Rule('certificate', _rx(r'\b(certificado|certificate)\b'), build_certificate, [('info del certificado /tmp/c.pem', 'security_audit.certificate_info')]),
    Rule('metadata', _all(_rx(r'\b(info|metadata|metadatos|permisos)\b'), lambda s, t: bool(_path(t))),
         lambda s, t, c: _with_path(t, '', 'filesystem', 'metadata', 'path'), [('permisos de /tmp/x', 'filesystem.metadata')]),
    Rule('hash', _rx(r'\b(hash|sha256|checksum|resumen criptografico)\b'),
         lambda s, t, c: _with_path(t, 'Indica la ruta del archivo para calcular su hash.', 'filesystem', 'hash', 'path'),
         [('sha256 de /tmp/x', 'filesystem.hash')]),
    Rule('service_status', _all(_rx(r'\b(status|estado)\b'), _rx(r'\b(service|servicio)\b|' + _SVC)), build_service_status,
         [('estado de nginx', 'services.status'), ('estado de docker', 'services.status')]),
    Rule('run_python', _all(_rx(r'\b(ejecuta|run|corre)\b'), _rx(r'\b(python|programa|script)\b')), build_run_python,
         [('ejecuta el script python /tmp/a.py', 'development.run_python'), ('corre el script', 'ask')]),
    Rule('capabilities_generic', _rx(r'^(?:capacidades|capabilities|ayuda|help)$'), _simple('assistant', 'capabilities'),
         [('capacidades', 'assistant.capabilities')]),
    Rule('late_scan', _rx(r'\b(scan|escanea|escanear)\b'), build_late_scan, [('escanea', 'ask')]),
    Rule('env_vars', _rx(r'\b(variables de entorno|environment variables|env)\b'), _simple('system', 'environment_variables'),
         [('variables de entorno', 'system.environment_variables')]),
    Rule('hardware', _rx(r'\b(hardware|cpu|gpu|discos|temperaturas)\b'), _simple('system', 'hardware_info'),
         [('muestra el hardware', 'system.hardware_info')]),
    Rule('power', _rx(r'\b(apagar|apaga|shutdown|reiniciar|reinicia|reboot|restart)\b'), build_power,
         [('apaga la computadora', 'system.power_management'), ('actualiza el sistema', 'packages.upgrade')]),
    Rule('transfer', _rx(r'\b(rsync|scp|transferencia remota)\b'), build_transfer, [('rsync desde /tmp/a a user@host:/tmp', 'remote_transfer.rsync')]),
    Rule('ping', _rx(r'\b(ping)\b'), build_ping, [('ping a 8.8.8.8', 'networking.ping')]),
    Rule('traceroute', _rx(r'\b(traceroute|tracert)\b'), build_traceroute, [('traceroute a example.com', 'networking.traceroute'), ('traceroute', 'ask')]),
    Rule('http_request', _rx(r'\b(http request|solicitud http)\b'), build_http, [('http request https://example.com', 'networking.http_request')]),
    Rule('speed_test', _rx(r'\b(speed test|velocidad|test de velocidad)\b'), _simple('networking', 'speed_test', timeout=120),
         [('test de velocidad', 'networking.speed_test')]),
    Rule('firewall', _rx(r'\b(firewall|cortafuegos)\b'), _simple('networking', 'firewall_status'), [('estado del firewall', 'networking.firewall_status')]),
    Rule('vpn', _rx(r'\b(vpn)\b'), _simple('networking', 'vpn_status'), [('estado de la vpn', 'networking.vpn_status')]),
    Rule('process_temps', _rx(r'\b(temperature)\b'), _simple('processes', 'process_temperatures'), [('process temperature', 'processes.process_temperatures')]),
    Rule('ssh_audit', _rx(r'\b(ssh audit|auditoria ssh)\b'), _simple('security_audit', 'ssh_audit'), [('auditoria ssh', 'security_audit.ssh_audit')]),
    Rule('secrets', _rx(r'\b(secretos|secrets|scan secrets)\b'), build_secrets, [('busca secretos en /tmp', 'security_audit.scan_secrets')]),
    Rule('suid', _rx(r'\b(suid|sgid)\b'), _simple('security_audit', 'find_suid_sgid', 'buscar archivos SUID/SGID', Risk.HIGH), [('buscar suid', 'security_audit.find_suid_sgid')]),
    Rule('rootkit', _rx(r'\b(rootkits?)\b'), _simple('security_audit', 'check_rootkits'), [('revisa rootkits', 'security_audit.check_rootkits')]),
    Rule('install', _rx(r'\b(instalar|instala|install|paquete|package)\b'), build_install,
         [('instala el paquete htop', 'packages.install'), ('instalar nmap', 'packages.install'), ('instalar', 'ask')]),
    Rule('update', _rx(r'\b(actualizar|actualiza|update|upgrade)\b'), build_update,
         [('actualiza el sistema', 'packages.upgrade'), ('actualizar paquetes', 'packages.update')]),
    Rule('cron', _rx(r'\b(cron|tarea programada)\b'), build_cron, [('lista las tareas cron', 'packages.list_cron_jobs')]),
    Rule('compile', _rx(r'\b(compilar|compile)\b'), build_compile, [('compilar /tmp/a.c', 'development.compile_c'), ('compilar c++ /tmp/a.cpp', 'development.compile_cpp')]),
    Rule('lint', _rx(r'\b(lint|pylint)\b'), _dev_path('lint_python'), [('lint ./src', 'development.lint_python')]),
    Rule('format', _rx(r'\b(format|black)\b'), _dev_path('format_python'), [('black ./src', 'development.format_python')]),
    Rule('git_branch', _rx(r'\b(git branch|ramas git)\b'), _simple('development', 'git_branch'), [('git branch', 'development.git_branch')]),
    Rule('git_diff', _rx(r'\b(git diff)\b'), _simple('development', 'git_diff'), [('git diff', 'development.git_diff')]),
    Rule('git_log', _rx(r'\b(git log|historial git)\b'), _simple('development', 'git_log'), [('git log', 'development.git_log')]),
    Rule('git_stash', _rx(r'\b(git stash)\b'), _simple('development', 'git_stash'), [('git stash', 'development.git_stash')]),
    Rule('git_checkout', _rx(r'\b(git checkout)\b'), build_git_checkout, [('git checkout a main', 'development.git_checkout'), ('git checkout', 'ask')]),
    Rule('tests', _rx(r'\b(test|pytest|unittest)\b'), _dev_path('run_tests', timeout=600), [('corre pytest ./tests', 'development.run_tests')]),
    Rule('docker_build', _rx(r'\b(docker build)\b'), build_docker_build, [('docker build ./app -t app:1', 'development.docker_build')]),
    Rule('ci_check', _rx(r'\b(ci check|ci/cd)\b'), _dev_path('ci_check'), [('ci check', 'development.ci_check')]),
    Rule('sqlite', _rx(r'\b(sqlite|base de datos sqlite)\b'), build_sqlite,
         [("sqlite /tmp/a.db consulta 'select 1'", 'database.sqlite_query'), ('sqlite /tmp/a.db', 'database.sqlite_list_tables'), ('sqlite', 'ask')]),
    Rule('explicit_exec_or_unknown', lambda s, t: True, build_explicit_exec,
         [('ejecuta ls -la', 'development.execute_command'), ('blablabla xyz', 'unrecognized')]),
]

RULES = GUARDS + EARLY_RULES + NEW_RULES + ORIGINAL_RULES


class Parser:
    def __init__(self):
        self.intent_registry = load_intent_plugins(intent_registry)

    def parse(self, text, context=None):
        clean = _strip_fillers(text)               # «oye, por favor, ¿puedes abrir firefox?» → «abrir firefox?»
        s = _fix_words(normalize(clean))           # sin acentos, minúsculas y typos de verbos corregidos
        terminal_followup = re.fullmatch(
            r'(?:en|desde|in)\s+(?:(?:una\s+nueva|otra|nueva|la|another|a\s+new)\s+)?terminal\s+(.+)', s)
        if terminal_followup:
            command = _terminal_command(terminal_followup.group(1))
            if command:
                return _plan(text, _op('browser', 'open_application',
                                       {'name': 'terminal', 'command': command}, Risk.HIGH,
                                       f'abrir una nueva terminal y ejecutar {command}'))
        # Consultas cortas de hardware: devolver solo el componente pedido.
        if re.fullmatch(r'(?:mi\s+)?gpu(?:\s+(?:info|informacion|datos))?[?.!]*', s):
            return _plan(text, _op('system', 'gpu_info', desc='consultar la GPU'))
        if re.fullmatch(r'(?:mi\s+)?cpu(?:\s+(?:info|informacion|datos))?[?.!]*', s):
            return _plan(text, _op('system', 'cpu_info', desc='consultar la CPU'))
        # Comandos cortos para componentes del sistema
        if re.fullmatch(r'cpu[?.!]*', s):
            return _plan(text, _op('system', 'cpu_info', desc='consultar información del procesador'))
        if re.fullmatch(r'(?:disco|disk)[?.!]*', s):
            return _plan(text, _op('filesystem', 'disk_usage', {'path': '.'}, desc='consultar uso de disco'))
        if re.fullmatch(r'(?:temperatura|temperature|temp)[?.!]*', s):
            return _plan(text, _op('monitoring', 'get_temperatures', desc='consultar temperaturas del sistema'))
        if re.fullmatch(r'(?:puertos|ports)[?.!]*', s):
            return _plan(text, _op('networking', 'listening_ports', desc='consultar puertos en escucha'))
        if re.fullmatch(r'(?:mis\s+)?puertos[?.!]*', s):
            return _plan(text, _op('networking', 'listening_ports', desc='consultar puertos en escucha'))
        if re.fullmatch(r'(?:ip)[?.!]*', s):
            return _plan(text, _op('networking', 'local_addresses', desc='consultar direcciones IP locales'))
        if re.fullmatch(r'(?:memoria|ram|memory)[?.!]*', s):
            return _plan(text, _op('system', 'ram', desc='consultar memoria RAM'))
        if re.fullmatch(r'(?:interfaz|interfaces?)[?.!]*', s):
            return _plan(text, _op('networking', 'interfaces', desc='consultar interfaces de red'))
        extension = self.intent_registry.match(text, context)
        if extension is not None:
            return extension
        multi = _multi_open(s, clean)
        if multi is not None:
            return multi
        for rule in RULES:
            if rule.match(s, clean):
                res = rule.build(s, clean, context)
                if res is not None:
                    return res
        return _unknown(text)


    def resolve_pending(self, text, context):
        """Turn a concise clarification reply into the pending structured operation."""
        pending = getattr(context, 'pending', None)
        if not pending:
            return None
        s = normalize(text).strip(' .!?¿¡"\'')
        kind = pending['kind']
        if kind == 'create_file_name':
            match = re.search(r'(?i)\b(?:quiero\s+que\s+)?([\w.-]+)\s+sea\s+(?:el\s+)?nombre\s+del\s+archivo$', s)
            if match:
                filename = match.group(1)
            else:
                match = re.fullmatch(r'[\w.-]+', s)
                filename = match.group(0) if match else ''
            filename = filename.removesuffix('.').strip()
            if not filename or filename in {'.', '..'} or '/' in filename or '\\' in filename:
                return _ask(text, 'Dime un nombre sencillo para el archivo, por ejemplo hola.')
            if '.' not in filename:
                filename += pending.get('extension', '')
            destination = str(Path(pending.get('directory', '.')).expanduser() / filename)
            return _plan(text, _op('filesystem', 'create', {'path': destination, 'content': ''}, Risk.MODERATE,
                                   f'crear el archivo vacío {destination}'))
        if kind == 'google_search':
            query = re.sub(r'(?i)^(?:quiero\s+)?(?:buscar|busca|googlea|search(?:\s+for)?)\s*', '', text.strip()).strip(' .!?¿¡"\'')
            if not query or query in {'algo', 'alguna cosa', 'something'}:
                return _ask(text, '¿Qué tema o frase quieres buscar?')
            return _plan(text, _op('web', 'search', {'query': query}, Risk.LOW, f'buscar «{query}» y mostrar resultados en la terminal'))
        if kind == 'web_search':
            query = text.strip(' .!?¿¡"\'')
            query = re.sub(r'(?i)^(?:quiero\s+)?(?:buscar|busca|googlea|investiga|search(?:\s+for)?)\s*', '', query).strip()
            generic_text = ' '.join(re.sub(r'[,;]+', ' ', s).split())
            generic_followup = bool(re.fullmatch(
                r'(?:estoy en una cli\s*)?(?:no puedo abrir el navegador\s*)?'
                r'(?:investigalo tu(?: y dime que encontraste)?|buscalo tu(?: y dime que encontraste)?|dime que encontraste)',
                generic_text))
            if not query or query.casefold() in {'algo', 'cosas'} or generic_followup:
                return _ask(text, 'Dime el tema concreto que quieres investigar.')
            return _plan(text, _op('web', 'search', {'query': query}, Risk.LOW, f'buscar «{query}» en la web'))
        if kind == 'math_discount':
            numbers = re.findall(r'(?<!\w)\d+(?:[.,]\d+)?%?', text)
            if len(numbers) < 2:
                return _ask(text, 'Dime el monto y el porcentaje, por ejemplo «1250 y 15%».')
            amount = float(numbers[0].replace(',', '.').rstrip('%'))
            percent = float(numbers[1].replace(',', '.').rstrip('%'))
            if not 0 <= percent <= 100:
                return _ask(text, 'El porcentaje debe estar entre 0 y 100%.')
            return _plan(text, _op('calculator', 'evaluate', {'expression': f'{amount}*(1-{percent}/100)'},
                                   desc='calcular precio con descuento'))
        if kind == 'translate_target':
            from intelligence.intents.translation import LANGUAGES
            language_text = re.sub(r'^(?:al?|en|to|into)\s+', '', s.casefold()).strip()
            language = LANGUAGES.get(language_text)
            if language is None:
                for alias, code in sorted(LANGUAGES.items(), key=lambda item: len(item[0]), reverse=True):
                    if re.search(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', language_text):
                        language = code
                        break
            if not language:
                return _ask(text, 'Dime el idioma de destino, por ejemplo español o inglés.')
            args = {'text': pending['text'], 'target_language': language}
            if pending.get('source_language'):
                args['source_language'] = pending['source_language']
            return _plan(text, _op('translation', 'translate', args, Risk.MODERATE, f'traducir texto al idioma {language}'))
        return None