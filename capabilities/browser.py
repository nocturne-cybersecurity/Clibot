"""Launch URLs and locally installed desktop applications."""
import configparser
import os
import re
import shlex
import shutil
import subprocess
import unicodedata
from pathlib import Path
from urllib.parse import urlparse


def _normal(value):
    value = ''.join(char for char in unicodedata.normalize('NFKD', value.casefold())
                    if not unicodedata.combining(char))
    return ' '.join(re.sub(r'[^\w]+', ' ', value).split())


def _application_roots():
    data_home = os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))
    data_dirs = os.environ.get('XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(':')
    roots = [Path(data_home) / 'applications']
    roots.extend(Path(item) / 'applications' for item in data_dirs if item)
    roots.append(Path('/var/lib/snapd/desktop/applications'))
    return list(dict.fromkeys(roots))


def _desktop_entries():
    """Yield readable application entries without running their Exec strings."""
    for root in _application_roots():
        if not root.is_dir():
            continue
        for current, directories, files in os.walk(root):
            depth = len(Path(current).relative_to(root).parts)
            if depth >= 3:
                directories[:] = []
            for filename in files:
                if not filename.endswith('.desktop'):
                    continue
                path = Path(current) / filename
                parser = configparser.ConfigParser(interpolation=None, strict=False)
                parser.optionxform = str.lower
                try:
                    parser.read(path, encoding='utf-8')
                    entry = parser['Desktop Entry']
                except (OSError, KeyError, configparser.Error):
                    continue
                if entry.get('Type', 'Application') != 'Application':
                    continue
                if entry.getboolean('Hidden', fallback=False) or entry.getboolean('NoDisplay', fallback=False):
                    continue
                name = entry.get('Name[es]', entry.get('Name', path.stem))
                yield path, name, entry


def _find_desktop_entry(name):
    wanted = _normal(name)
    aliases = {
        'pycharm': {'pycharm', 'pycharm community', 'pycharm professional', 'pycharm ce'},
        'software': {'software', 'gnome software', 'software center', 'centro de software'},
        'maps': {'maps', 'mapas', 'gnome maps'},
        'calculator': {'calculator', 'calculadora', 'gnome calculator'},
        'files': {'files', 'archivos', 'file manager', 'gestor de archivos'},
    }
    accepted = aliases.get(wanted, {wanted})
    for path, display_name, entry in _desktop_entries():
        filename = _normal(path.stem)
        entry_name = _normal(display_name)
        try:
            executable = _normal(shlex.split(entry.get('Exec', ''))[0])
        except (ValueError, IndexError):
            executable = ''
        localized_names = {_normal(value) for key, value in entry.items() if key == 'name' or key.startswith('name[')}
        candidates = {entry_name, filename, executable, Path(executable).name} | localized_names
        if accepted & candidates:
            try_exec = entry.get('TryExec', '').strip()
            if try_exec and not (Path(try_exec).is_file() or shutil.which(try_exec)):
                continue
            return path, display_name, entry
    return None


def _launch_desktop(name):
    found = _find_desktop_entry(name)
    if not found:
        return None
    path, display_name, entry = found
    launcher = shutil.which('gtk-launch')
    if launcher:
        try:
            subprocess.Popen([launcher, path.stem], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        except OSError as exc:
            raise RuntimeError(f'No se pudo solicitar la apertura de {display_name}: {exc}') from exc
        return f'Envié al escritorio la solicitud para abrir {display_name}.'
    else:
        # Desktop Exec is parsed as argv, never as shell source. Field codes
        # that request files or URLs are omitted because this is a plain launch.
        try:
            argv = shlex.split(entry.get('Exec', ''))
        except ValueError as exc:
            raise RuntimeError(f'La entrada de «{display_name}» tiene un comando inválido.') from exc
        argv = [token.replace('%c', display_name).replace('%k', str(path))
                for token in argv if not re.fullmatch(r'%[fFuUdDnNickvm]', token)]
        argv = [token for token in argv if token]
        if not argv:
            raise RuntimeError(f'La entrada de «{display_name}» no define cómo iniciarse.')
        if Path(argv[0]).name in {'sh', 'bash', 'dash', 'zsh'}:
            raise RuntimeError(f'No iniciaré «{display_name}»: su entrada requiere ejecutar una shell.')
        if not (Path(argv[0]).is_file() or shutil.which(argv[0])):
            raise FileNotFoundError(f'No se encontró el ejecutable de «{display_name}»: {argv[0]}')
    subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
    return f'Abrí {display_name}.'


def open_url(url, browser=None):
    if not url.startswith(('https://', 'http://')):
        raise ValueError('Solo se aceptan direcciones http(s).')
    if not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY'):
        raise RuntimeError('No hay una sesión gráfica disponible para abrir el navegador.')
    choices = {'firefox': ['firefox', 'firefox-esr'],
               'chrome': ['google-chrome', 'google-chrome-stable'],
               'chromium': ['chromium', 'chromium-browser']}
    opener = next((shutil.which(item) for item in choices.get((browser or '').casefold(), [])
                   if shutil.which(item)), None) if browser else shutil.which('xdg-open')
    if not opener:
        raise FileNotFoundError(f'No se encontró el navegador solicitado{f" ({browser})" if browser else ""}.')
    subprocess.Popen([opener, url], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
    return f'Solicité al navegador que abriera {url}.'


def open_application(name, command=None):
    """Launch a known command or a matching installed .desktop application."""
    aliases = {
        'navegador': 'browser', 'browser': 'browser', 'firefox': 'firefox', 'chrome': 'chrome',
        'chromium': 'chromium', 'google chrome': 'chrome', 'editor': 'editor', 'code': 'code',
        'visual studio code': 'code', 'terminal': 'terminal', 'consola': 'terminal',
        'metasploit': 'metasploit', 'msfconsole': 'metasploit', 'pycharm community': 'pycharm',
        'pycharm professional': 'pycharm', 'pycharm ce': 'pycharm', 'software center': 'software',
        'centro de software': 'software', 'gnome software': 'software', 'mapa': 'maps',
        'mapas': 'maps', 'gnome maps': 'maps', 'calculadora': 'calculator', 'files': 'files',
        'archivos': 'files', 'gestor de archivos': 'files',
    }
    requested = name.casefold().strip()
    key = aliases.get(requested, requested)
    if not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY'):
        raise RuntimeError('No hay una sesión gráfica disponible. Ejecuta LLMAH desde el escritorio para abrir aplicaciones.')

    if key not in {'browser', 'firefox', 'chrome', 'chromium', 'editor', 'code', 'terminal', 'metasploit'}:
        launched = _launch_desktop(key)
        if launched:
            return launched

    terminal = next((shutil.which(item) for item in
                     ('x-terminal-emulator', 'kgx', 'gnome-terminal', 'konsole', 'xfce4-terminal', 'xterm')
                     if shutil.which(item)), None)
    choices = {
        'browser': ['firefox', 'firefox-esr', 'chromium', 'google-chrome', 'xdg-open'],
        'firefox': ['firefox', 'firefox-esr'],
        'chrome': ['google-chrome', 'google-chrome-stable', 'chromium'],
        'chromium': ['chromium', 'chromium-browser'],
        'editor': ['gedit', 'mousepad', 'kate'],
        'code': ['code'],
        'pycharm': ['pycharm', 'pycharm-community', 'charm'],
        'software': ['gnome-software'],
        'maps': ['gnome-maps'],
        'calculator': ['gnome-calculator', 'qalculate-gtk', 'kcalc'],
        'files': ['nautilus', 'thunar', 'dolphin'],
        'terminal': [terminal] if terminal else [],
        'metasploit': ['msfconsole'],
    }
    if key not in choices:
        raise FileNotFoundError(f'No encontré «{name}» en las aplicaciones instaladas.')
    executable = terminal if key == 'terminal' else next(
        (shutil.which(item) for item in choices[key] if item and shutil.which(item)), None)
    if not executable:
        raise FileNotFoundError(f'No encontré «{name}» instalado. Revisa el nombre en el menú de aplicaciones.')

    if key == 'metasploit':
        if not terminal:
            raise FileNotFoundError('Metasploit está instalado, pero no hay un emulador de terminal gráfico.')
        subprocess.Popen([terminal, '-e', executable], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return 'Abrí Metasploit en una ventana de terminal.'
    if key == 'terminal' and command:
        argv = shlex.split(command)
        if not argv:
            raise ValueError('El comando de inicio está vacío.')
        resolved = shutil.which(argv[0])
        if not resolved:
            raise FileNotFoundError(f'No se encontró el comando solicitado: {argv[0]}')
        argv[0] = resolved
        subprocess.Popen([executable, '-e', *argv], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return f'Se abrió una terminal ejecutando {argv[0]}.'
    subprocess.Popen([executable], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
    return f'Abrí {name}.'


def close_application(name):
    """Request a graceful close only for a recognized desktop application."""
    aliases = {
        'chrome': ('chrome',), 'google chrome': ('chrome',), 'google-chrome': ('chrome',),
        'firefox': ('firefox', 'firefox-esr'), 'firefox-esr': ('firefox-esr', 'firefox'),
        'chromium': ('chromium', 'chromium-browser'), 'chromium-browser': ('chromium-browser', 'chromium'),
        'code': ('code',), 'vscode': ('code',), 'visual studio code': ('code',),
        'spotify': ('spotify',), 'discord': ('Discord', 'discord'),
        'telegram': ('telegram-desktop', 'Telegram'), 'slack': ('slack',),
        'pycharm': ('pycharm', 'pycharm64'), 'pycharm community': ('pycharm', 'pycharm64'),
        'gedit': ('gedit',), 'mousepad': ('mousepad',), 'kate': ('kate',),
        'gimp': ('gimp',), 'vlc': ('vlc',), 'nautilus': ('nautilus',),
        'files': ('nautilus', 'thunar', 'dolphin'), 'archivos': ('nautilus', 'thunar', 'dolphin'),
        'calculadora': ('gnome-calculator', 'kcalc', 'qalculate-gtk'),
        'calculator': ('gnome-calculator', 'kcalc', 'qalculate-gtk'),
    }
    key = _normal(str(name))
    candidates = aliases.get(key)
    if not candidates:
        found = _find_desktop_entry(str(name))
        if not found:
            raise ValueError(f'No encontré «{name}» entre las aplicaciones de escritorio instaladas.')
        path, display_name, entry = found
        candidates = [path.stem, display_name, entry.get('StartupWMClass', '')]
        try:
            argv = shlex.split(entry.get('Exec', ''))
        except ValueError as exc:
            raise ValueError(f'La entrada de «{display_name}» tiene un comando inválido.') from exc
        try_exec = entry.get('TryExec', '').strip()
        if try_exec:
            candidates.append(Path(try_exec).name)
        if argv:
            executable = Path(argv[0]).name
            if executable not in {'sh', 'bash', 'dash', 'zsh', 'env', 'gtk-launch', 'xdg-open'}:
                candidates.append(executable)
        candidates = tuple(dict.fromkeys(candidate for candidate in candidates if candidate))

    from capabilities.processes import find_by_name, terminate_by_name
    for process_name in candidates:
        matches = find_by_name(process_name, exact=True)
        if matches['processes']:
            result = terminate_by_name(process_name, exact=True, max_matches=50)
            terminated = len(result['terminated'])
            failed = len(result['failed'])
            if not terminated:
                details = result['failed'][0]['error'] if result['failed'] else result.get('note', 'sin detalles')
                raise RuntimeError(f'No pude cerrar {name}: {details}')
            message = f'Solicité el cierre de {name} ({terminated} proceso(s)).'
            if failed:
                message += f' No se pudieron cerrar {failed} proceso(s).'
            return message
    raise ProcessLookupError(f'No encontré procesos de {name} en ejecución.')
