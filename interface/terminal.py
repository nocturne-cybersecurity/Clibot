"""CLIBOT · terminal interactiva de nivel profesional.

Inspirada en Claude Code, Gemini CLI y Codex:
  - Pantalla de bienvenida con logo en degradado y tips.
  - Prompt de dos líneas (ruta + rama git) con modo shell (!) y modo comando (/).
  - Autocompletado con menú y descripciones, sugerencias desde el historial.
  - Historial persistente entre sesiones, edición multilínea (Alt+Enter o "\\").
  - Barra inferior con estado del modelo, rama, modos y atajos.
  - Spinner con tiempo transcurrido, Ctrl+C cancela la solicitud en curso.
  - Respuestas con gutter, revelado progresivo, paginación y footer con duración.
  - Salida JSON / YAML / silenciosa, /export a Markdown, /cd, etc.

Dependencias:  pip install rich prompt_toolkit pyyaml
"""
from __future__ import annotations

import builtins
import contextlib
import difflib
import getpass
import json
import os
import random
import re
import select
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from rich import box
    from rich.console import Console, Group
    from rich.live import Live
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.text import Text
except ImportError:  # rich es obligatorio
    sys.exit('Falta "rich". Instala las dependencias con: pip install rich prompt_toolkit pyyaml')

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.formatted_text import FormattedText
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style
    HAS_PT = True
except ImportError:  # sin prompt_toolkit se usa input() + readline
    HAS_PT = False
    Completer = object

try:
    import yaml
except ImportError:
    yaml = None
try:
    import readline  # edición con flechas e historial en el modo de respaldo
except ImportError:
    readline = None

from core.assistant import Assistant  # noqa: F401  (se conserva por compatibilidad)
from core.contracts import Operation, Plan, Result
from interface.formatter import format_response

APP, VERSION = 'CLIBOT', '2.0'

# Paleta (tonos suaves tipo Catppuccin)
ACCENT, PURPLE = '#7dd3fc', '#c4a7e7'
OK, WARN, ERR, DIM, TEXT = '#a6e3a1', '#f9e2af', '#f38ba8', '#6c7086', '#cdd6f4'

LOGO = [
    ' ██████╗██╗     ██╗██████╗  ██████╗ ████████╗',
    '██╔════╝██║     ██║██╔══██╗██╔═══██╗╚══██╔══╝',
    '██║     ██║     ██║██████╔╝██║   ██║   ██║   ',
    '██║     ██║     ██║██╔══██╗██║   ██║   ██║   ',
    '╚██████╗███████╗██║██████╔╝╚██████╔╝   ██║   ',
    ' ╚═════╝╚══════╝╚═╝╚═════╝  ╚═════╝    ╚═╝   ',
]

COMMANDS = [
    ('/help', '', 'Ayuda, atajos y ejemplos'),
    ('/capabilities', '', 'Ver capacidades disponibles'),
    ('/status', '', 'Estado de la sesión'),
    ('/history', '', 'Historial de la sesión'),
    ('/forget', '', 'Borrar el contexto'),
    ('/reset', '', 'Restablecer preferencias'),
    ('/clear', '', 'Limpiar la pantalla'),
    ('/json', '', 'Alternar salida JSON'),
    ('/yaml', '', 'Alternar salida YAML'),
    ('/silent', '', 'Alternar modo silencioso'),
    ('/verbose', '', 'Alternar modo detallado'),
    ('/paginate', '', 'Alternar paginación'),
    ('/model', '[on|off]', 'Activar o desactivar el modelo'),
    ('/models', '[search <texto>|use|pull]', 'Explorar, buscar, cambiar o descargar modelos Ollama'),
    ('/micro', '[on|off]', 'Activar o desactivar comandos por voz'),
    ('/mic', '[list|use]', 'Listar o cambiar modelo de reconocimiento de voz'),
    ('/voice', '[on|off|list|use]', 'Activar/desactivar respuesta de voz o cambiar voz'),
    ('/keys', '[list|set|clear <servicio>]', 'Gestionar API keys (OpenAI, GitHub, etc.)'),
    ('/token', '[set|status|clear]', 'Configurar token de GitHub sin mostrarlo'),
    ('/run', '<cmd>', 'Ejecutar un comando'),
    ('/cd', '<dir>', 'Cambiar de directorio'),
    ('/export', '[archivo]', 'Guardar la sesión en Markdown'),
    ('/exit', '', 'Salir'),
]

ALIASES = {
    '/quit': '/exit', '/q': '/exit', 'salir': '/exit', 'exit': '/exit', 'quit': '/exit',
    'help': '/help', 'ayuda': '/help', '?': '/help',
    '/caps': '/capabilities', 'capabilities': '/capabilities', '$': '/capabilities',
    'history': '/history', 'historial': '/history',
    'clear': '/clear', 'limpia pantalla': '/clear', 'limpia la pantalla': '/clear',
    'limpiate': '/clear', 'clear screen': '/clear',
}

SHORTCUTS = [
    ('Enter', 'Enviar'),
    ('Alt+Enter  ·  \\ + Enter', 'Nueva línea'),
    ('Tab  ·  →', 'Completar comando / aceptar sugerencia'),
    ('↑ ↓', 'Historial'),
    ('Ctrl+R', 'Buscar en el historial'),
    ('Ctrl+L', 'Limpiar pantalla'),
    ('Ctrl+C', 'Cancelar solicitud (dos veces para salir)'),
    ('Ctrl+D', 'Salir'),
    ('! cmd', 'Ejecutar comando de shell'),
    ('| texto  ·  > archivo', 'Interpretar salida  ·  redirigir a archivo'),
]

EXAMPLES = [
    'muestra información del sistema',
    'lista archivos en .',
    'busca en Google cómo ver el disco',
    'traduce "Good morning" al español',
    'ejecuta printf hola | tr a-z A-Z',
    'abre Firefox y GitHub',
    'muestra los puertos abiertos',
]

TIPS = [
    'Escribe / para ver todos los comandos con su descripción.',
    'Con /micro on puedes dictar comandos; /micro off devuelve el control al teclado.',
    'Empieza una línea con ! para ejecutar un comando de shell directamente.',
    'Alt+Enter inserta una nueva línea sin enviar el mensaje.',
    '/export guarda la sesión completa en un archivo Markdown.',
    '/json y /yaml muestran la respuesta estructurada, ideal para scripts.',
    'Ctrl+R busca en tu historial; el historial se conserva entre sesiones.',
    '/cd cambia de directorio sin salir de CLIBOT.',
]


# ───────────────────────────── utilidades ─────────────────────────────
def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _gradient(line, start=(125, 211, 252), end=(196, 167, 231)):
    out, n = Text(), max(len(line) - 1, 1)
    for i, ch in enumerate(line):
        r, g, b = _lerp(start, end, i / n)
        out.append(ch, style=f'bold #{r:02x}{g:02x}{b:02x}')
    return out


class _OllamaCatalogParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.models=[]
        self.current=None
        self.in_description=False
        self.in_variant=False

    def handle_starttag(self, tag, attrs):
        attributes=dict(attrs)
        if tag=='li':
            self.current={'name':None,'description':[],'spans':[]}
        elif self.current is not None:
            if tag=='a':
                href=attributes.get('href','')
                match=re.fullmatch(r'/library/([a-zA-Z0-9._-]+)',href)
                if match:self.current['name']=match.group(1)
            elif tag=='p' and not self.current['description']:
                self.in_description=True
            elif tag=='span' and 'bg-[#ddf4ff]' in attributes.get('class',''):
                self.in_variant=True

    def handle_endtag(self, tag):
        if tag=='p':self.in_description=False
        elif tag=='span':self.in_variant=False
        elif tag=='li' and self.current is not None:
            name=self.current['name']
            if name:
                description=' '.join(' '.join(self.current['description']).split())
                variants=[]
                for text in self.current['spans']:
                    value=''.join(text.split()).lower()
                    if re.fullmatch(r'\d+(?:\.\d+)?[mb]',value) and value not in variants:
                        variants.append(value)
                self.models.append({'name':name,'description':description,'variants':variants})
            self.current=None
            self.in_description=False
            self.in_variant=False

    def handle_data(self, data):
        if self.current is None:return
        if self.in_description:self.current['description'].append(data)
        if self.in_variant:self.current['spans'].append(data)


class _Spinner:
    """Renderable dinámico: se recalcula en cada refresco de rich.Live."""
    FRAMES = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    VERBS = ('Pensando', 'Analizando', 'Procesando', 'Resolviendo')

    def __init__(self):
        self.t0 = time.monotonic()
        self.verb = random.choice(self.VERBS)

    def __rich__(self):
        e = time.monotonic() - self.t0
        frame = self.FRAMES[int(e * 12) % len(self.FRAMES)]
        return Text.assemble(
            (f'{frame} ', ACCENT), (f'{self.verb}… ', TEXT),
            (f'({e:.0f}s · Ctrl+C para cancelar)', DIM),
        )


class _SlashCompleter(Completer):
    """Autocompleta comandos /, argumentos de /model y directorios de /cd."""

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if '\n' in text:
            return
        low = text.lower()
        if low.startswith('/cd '):
            yield from self._dirs(text[4:])
        elif low.startswith('/model '):
            arg = text[7:]
            for opt in ('on', 'off'):
                if opt.startswith(arg.lower()):
                    yield Completion(opt, start_position=-len(arg))
        elif low.startswith('/models '):
            arg = text[8:]
            for opt in ('list', 'search ', 'use ', 'pull '):
                if opt.startswith(arg.lower()):
                    yield Completion(opt, start_position=-len(arg))
        elif text.startswith('/') and ' ' not in text:
            for name, args, desc in COMMANDS:
                if name.startswith(low):
                    shown = f'{name} {args}'.strip()
                    yield Completion(name, start_position=-len(text), display=shown, display_meta=desc)

    @staticmethod
    def _dirs(partial):
        folder, prefix = os.path.split(os.path.expanduser(partial))
        typed = os.path.basename(partial)
        try:
            entries = sorted(os.scandir(folder or '.'), key=lambda e: e.name.lower())
        except OSError:
            return
        shown = 0
        for entry in entries:
            if not entry.is_dir(follow_symlinks=False):
                continue
            if entry.name.startswith('.') and not prefix.startswith('.'):
                continue
            if entry.name.startswith(prefix):
                yield Completion(entry.name + '/', start_position=-len(typed))
                shown += 1
                if shown >= 50:
                    return


# ───────────────────────────── terminal ─────────────────────────────
class Terminal:
    def __init__(self, assistant):
        self.assistant = assistant
        self.json_mode = False
        self.yaml_mode = False
        self.silent_mode = False
        self.paginate_mode = True
        self.console = Console(highlight=False)
        self._started = time.monotonic()
        self._requests = 0
        self._last_sigint = 0.0
        self._model_cache = None   # (id(llm), t, ok, label)
        self._git_cache = ('', 0.0, '')
        self._session = None
        self._handlers = {
            '/help': self._cmd_help, '/capabilities': self._cmd_caps, '/status': self._cmd_status,
            '/history': self._cmd_history, '/forget': self._cmd_forget, '/reset': self._cmd_reset,
            '/clear': self._cmd_clear, '/json': self._cmd_json, '/yaml': self._cmd_yaml,
            '/silent': self._cmd_silent, '/verbose': self._cmd_verbose, '/paginate': self._cmd_paginate,
            '/model': self._cmd_model, '/models': self._cmd_models, '/micro': self._cmd_micro,
            '/mic': self._cmd_mic, '/voice': self._cmd_voice, '/keys': self._cmd_keys,
            '/token': self._cmd_token,
            '/run': self._cmd_run, '/cd': self._cmd_cd,
            '/export': self._cmd_export, '/exit': lambda _a: 'exit',
        }
        self._micro_enabled = False
        self._voice_input = None
        self._setup_input()
        
        # Initialize TTS and keys managers
        from intelligence.tts_manager import TTSManager
        from intelligence.keys_manager import KeysManager
        from intelligence.voice_setup import VoiceSetup
        self._tts = TTSManager()
        self._keys = KeysManager()
        
        # Auto-enable microphone if voice was installed and marked for auto-enable
        voice_setup = VoiceSetup()
        voice_config = voice_setup.load_config()
        if voice_config.get('auto_enable', False) and voice_config.get('installed', False):
            try:
                from interface.voice import VoiceInput
                voice = VoiceInput()
                voice.prepare()
                self._voice_input = voice
                self._micro_enabled = True
            except Exception:
                pass  # If it fails, just continue without microphone

    # ── entrada ──
    def _setup_input(self):
        interactive = sys.stdin.isatty() and sys.stdout.isatty()
        if HAS_PT and interactive:
            hist_dir = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'clibot'
            try:
                hist_dir.mkdir(parents=True, exist_ok=True)
                history = FileHistory(str(hist_dir / 'history'))
            except OSError:
                history = None
            kb = KeyBindings()

            @kb.add('enter')
            def _enter(event):
                buf = event.current_buffer
                if buf.text.endswith('\\'):          # continuación estilo shell
                    buf.delete_before_cursor(1)
                    buf.insert_text('\n')
                else:
                    buf.validate_and_handle()

            @kb.add('escape', 'enter')
            @kb.add('c-j')
            def _newline(event):
                event.current_buffer.insert_text('\n')

            @kb.add('c-l')
            def _clear(event):
                event.app.renderer.clear()

            style = Style.from_dict({
                'p.path': f'bold {ACCENT}', 'p.git': PURPLE, 'p.arrow': f'bold {ACCENT}',
                'p.shell': f'bold {WARN}', 'p.cmd': f'bold {OK}',
                'auto-suggestion': '#585b70',
                'bottom-toolbar': f'bg:#181825 {DIM}', 'bottom-toolbar.text': f'bg:#181825 {DIM}',
                'tb.ok': f'bg:#181825 {OK}', 'tb.off': f'bg:#181825 {ERR}',
                'tb.git': f'bg:#181825 {PURPLE}', 'tb.path': f'bg:#181825 {ACCENT}',
                'tb.mode': f'bg:#181825 {WARN}', 'tb.sep': 'bg:#181825 #313244',
                'completion-menu': 'bg:#1e1e2e', 'completion-menu.completion': f'bg:#1e1e2e {TEXT}',
                'completion-menu.completion.current': 'bg:#7dd3fc #11111b bold',
                'completion-menu.meta.completion': f'bg:#181825 {DIM}',
                'completion-menu.meta.completion.current': 'bg:#5fb3d9 #11111b',
            })
            self._session = PromptSession(
                message=self._prompt_message,
                history=history,
                auto_suggest=AutoSuggestFromHistory(),
                completer=_SlashCompleter(),
                complete_while_typing=True,
                multiline=True,
                key_bindings=kb,
                prompt_continuation=lambda w, n, soft: FormattedText([('class:p.git', '  … ')]),
                bottom_toolbar=self._toolbar,
                style=style,
                enable_history_search=True,
                mouse_support=False,
            )
        elif readline:
            names = [c[0] for c in COMMANDS]
            readline.set_completer(lambda t, s: ([n for n in names if n.startswith(t)] + [None])[s])
            readline.parse_and_bind('tab: complete')

    def _read(self):
        if self._micro_enabled:
            return self._read_micro()
        if self._session:
            return self._session.prompt()
        line = input(f'{self._get_prompt_path()} ❯ ')
        while line.endswith('\\'):
            line = line[:-1] + '\n' + input('… ')
        return line

    def _read_micro(self):
        from interface.voice import VoiceInputError, voice_command

        try:
            self._voice_input.start()
        except VoiceInputError as exc:
            self._micro_enabled = False
            self.console.print(Text(f'  No se pudo iniciar el micrófono: {exc}', style=ERR))
            return ''
        prompt = f'\n{self._get_prompt_path()}  [MIC] ❯ '
        self.console.print(Text(prompt, style=f'bold {ACCENT}'), end='')
        try:
            while True:
                event = self._voice_input.poll()
                if event:
                    self._voice_input.stop()
                    if event[0] == 'error':
                        self._micro_enabled = False
                        self.console.print(Text(f'\n  Error del micrófono: {event[1]}', style=ERR))
                        return ''
                    transcript = event[1]
                    self.console.print(Text(f'\n  Oí: {transcript}', style=DIM))
                    return voice_command(transcript)
                ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                if ready:
                    line = sys.stdin.readline()
                    self._voice_input.stop()
                    if line == '':
                        raise EOFError
                    return line
        finally:
            self._voice_input.stop()

    # ── estado cacheado (la barra se redibuja con cada tecla) ──
    def _model_info(self):
        llm, now = self.assistant.llm, time.monotonic()
        c = self._model_cache
        if c and c[0] == id(llm) and now - c[1] < 10:
            return c[2], c[3]
        try:
            ok = bool(llm and llm.is_available())
        except Exception:
            ok = False
        label = f'{llm.provider}:{llm.model}' if ok else 'offline · reglas'
        self._model_cache = (id(llm), now, ok, label)
        return ok, label

    def _git_branch(self):
        cwd, t, branch = self._git_cache
        now = time.monotonic()
        if cwd == os.getcwd() and now - t < 5:
            return branch
        try:
            branch = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'], stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, timeout=0.4,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            branch = ''
        self._git_cache = (os.getcwd(), now, branch)
        return branch

    def _get_prompt_path(self):
        cwd, home = Path.cwd(), Path.home()
        try:
            rel = cwd.relative_to(home)
            return '~' if str(rel) == '.' else f'~/{rel}'
        except ValueError:
            return str(cwd)

    def _prompt_message(self):
        buf = self._session.default_buffer.text if self._session else ''
        if buf.startswith('!'):
            mode, cls = '$', 'class:p.shell'
        elif buf.startswith('/'):
            mode, cls = '/', 'class:p.cmd'
        else:
            mode, cls = '❯', 'class:p.arrow'
        branch = self._git_branch()
        return FormattedText([
            ('', '\n'), ('class:p.path', self._get_prompt_path()),
            ('class:p.git', f'  ⎇ {branch}' if branch else ''), ('', '\n'), (cls, f'{mode} '),
        ])

    def _toolbar(self):
        ok, label = self._model_info()
        sep = ('class:tb.sep', ' │ ')
        parts = [('class:tb.path', f' {self._get_prompt_path()}')]
        branch = self._git_branch()
        if branch:
            parts += [sep, ('class:tb.git', f'⎇ {branch}')]
        parts += [sep, ('class:tb.ok' if ok else 'class:tb.off', f'● {label}')]
        modes = [m for m, on in (('JSON', self.json_mode), ('YAML', self.yaml_mode),
                                 ('silencioso', self.silent_mode)) if on]
        if modes:
            parts += [sep, ('class:tb.mode', ' · '.join(modes))]
        parts += [sep, ('', 'Alt+Enter nueva línea · / comandos · Ctrl+D salir ')]
        return FormattedText(parts)

    # ── bucle principal ──
    def run(self):
        self._banner()
        while True:
            try:
                line = self._read()
            except EOFError:
                self._bye()
                break
            except KeyboardInterrupt:
                if self._micro_enabled:
                    self._micro_enabled = False
                    if self._voice_input:
                        self._voice_input.stop()
                    self.console.print(Text('\n  Micrófono desactivado.', style=WARN))
                now = time.monotonic()
                if now - self._last_sigint < 2:
                    self._bye()
                    break
                self._last_sigint = now
                self.console.print(Text('  Presiona Ctrl+C otra vez para salir', style=DIM))
                continue
            self._last_sigint = 0.0
            line = line.strip()
            if line and self._dispatch(line) == 'exit':
                self._bye()
                break

    def _dispatch(self, line):
        key = line.casefold()
        name, arg = ALIASES.get(key), ''
        if not name:
            head, _, rest = line.partition(' ')
            head_l = head.casefold()
            name, arg = ALIASES.get(head_l, head_l), rest.strip()
        if name in self._handlers:
            return self._handlers[name](arg)
        if line.startswith('/'):
            near = difflib.get_close_matches(name, [c[0] for c in COMMANDS], n=1)
            hint = f' ¿Quisiste decir {near[0]}?' if near else ' Escribe /help.'
            self.console.print(Text(f'  Comando desconocido: {name}.{hint}', style=WARN))
            return None
        if line.startswith('!'):
            line = 'ejecuta comando: ' + line[1:].strip()
        elif line.startswith('|'):
            line = 'interpreta salida: ' + line[1:].strip()
        elif line.startswith('>'):
            line = 'redirige a archivo: ' + line[1:].strip()
        self._ask(line)
        return None

    # ── solicitud al asistente ──
    @contextlib.contextmanager
    def _thinking(self):
        """Spinner mientras el asistente trabaja; se pausa si pide confirmación con input()."""
        if not self.console.is_terminal:
            yield
            return
        live = Live(_Spinner(), console=self.console, transient=True, refresh_per_second=15)
        real_input = builtins.input

        def guarded_input(prompt=''):
            live.stop()
            try:
                return real_input(prompt)
            finally:
                live.start()

        builtins.input = guarded_input
        live.start()
        try:
            yield
        finally:
            builtins.input = real_input
            live.stop()

    def _ask(self, line):
        t0 = time.monotonic()
        try:
            with self._thinking():
                response = self.assistant.handle(line)
        except KeyboardInterrupt:
            self.console.print(Text('  ⎋ Solicitud interrumpida', style=WARN))
            return
        except Exception as exc:  # no tumbar la sesión por un error del asistente
            self._error(exc)
            return
        self._requests += 1
        self._show(response, time.monotonic() - t0)

    def _error(self, exc):
        self.console.print(Panel(Text(f'{type(exc).__name__}: {exc}', style=ERR), title='Error',
                                 title_align='left', border_style=ERR, box=box.ROUNDED))
        if os.environ.get('CLIBOT_DEBUG'):
            self.console.print_exception()

    # ── salida ──
    def _show(self, response, elapsed):
        if self.json_mode:
            self.console.print_json(json.dumps(self._serialize_response(response),
                                               ensure_ascii=False, default=str))
        elif self.yaml_mode:
            if yaml is None:
                self.console.print(Text('PyYAML no está instalado: pip install pyyaml', style=ERR))
            else:
                data = yaml.safe_dump(self._serialize_response(response), allow_unicode=True,
                                      default_flow_style=False, sort_keys=False)
                self.console.print(Syntax(data, 'yaml', theme='ansi_dark', background_color='default'))
        elif self.silent_mode:
            if isinstance(response, dict) and response.get('error'):
                self.console.print(Text.assemble(('Error: ', ERR), str(response['error'])))
        else:
            formatted = format_response(response)
            self._emit(formatted)
            self.console.print(Text(f'  ✓ {elapsed:.1f}s', style=DIM))
            
            # Speak response if TTS is enabled
            if self._tts.is_available():
                tts_config = self._tts.load_config()
                if tts_config.get('enabled', False):
                    text_to_speak = self._extract_text_for_speech(response)
                    if text_to_speak:
                        self._tts.speak(text_to_speak)

    def _extract_text_for_speech(self, response):
        """Extract readable text from response for TTS."""
        if isinstance(response, dict):
            # Extract message or summary
            if 'message' in response:
                return str(response['message'])
            if 'summary' in response:
                return str(response['summary'])
            if 'results' in response:
                results = response['results']
                if results and len(results) > 0:
                    first_result = results[0]
                    if hasattr(first_result, 'stdout') and first_result.stdout:
                        return str(first_result.stdout)[:500]  # Limit length
            return str(response)
        return str(response)[:500]  # Limit length for TTS

    def _gutter(self, text, bullet='●'):
        grid = Table.grid(padding=(0, 1), expand=True)
        grid.add_column(width=1, no_wrap=True)
        grid.add_column(ratio=1)
        grid.add_row(Text(bullet, style=ACCENT), Text.from_ansi(text))
        return grid

    @property
    def _animate(self):
        if not sys.stdout.isatty() or self.json_mode or self.yaml_mode or self.silent_mode:
            return False
        try:
            return bool(self.assistant.config['settings'].get('terminal', {}).get('animation', True))
        except Exception:
            return True

    def _emit(self, text):
        text = text.rstrip('\n')
        if not text:
            return
        lines = text.split('\n')
        if self.paginate_mode and self.console.is_terminal and len(lines) >= self.console.height - 4:
            if self._pager(text):
                return
        if self._animate and len(lines) <= 40:
            delay = min(0.03, 0.6 / len(lines))
            with Live(console=self.console, refresh_per_second=60, vertical_overflow='visible') as live:
                for i in range(1, len(lines) + 1):
                    live.update(self._gutter('\n'.join(lines[:i])))
                    time.sleep(delay)
        else:
            self.console.print(self._gutter(text))

    @staticmethod
    def _pager(text):
        try:
            proc = subprocess.Popen(['less', '-R', '-F', '-X'], stdin=subprocess.PIPE)
            proc.communicate(text.encode())
            return True
        except (OSError, KeyboardInterrupt):
            return False

    def _serialize_response(self, response):
        """Convierte Plan, Operation y Result a estructuras serializables."""
        s = self._serialize_response
        if isinstance(response, dict):
            return {k: s(v) for k, v in response.items()}
        if isinstance(response, (list, tuple)):
            return [s(i) for i in response]
        if isinstance(response, Plan):
            return {'operations': [s(o) for o in response.operations], 'request': response.request,
                    'clarification': response.clarification, 'message': response.message,
                    'unrecognized': response.unrecognized, 'reformat_last': response.reformat_last}
        if isinstance(response, Operation):
            return {'capability': response.capability, 'name': response.name,
                    'arguments': response.arguments, 'description': response.description,
                    'dependencies': response.dependencies, 'risk': response.risk.value,
                    'requires_privilege': response.requires_privilege, 'timeout': response.timeout,
                    'id': response.id}
        if isinstance(response, Result):
            return {'operation_id': response.operation_id, 'success': response.success,
                    'stdout': response.stdout, 'stderr': response.stderr,
                    'exit_code': response.exit_code, 'started_at': response.started_at,
                    'ended_at': response.ended_at, 'duration': response.duration,
                    'data': response.data, 'error_category': response.error_category,
                    'verified': response.verified, 'status': response.status.value}
        return response

    # ── vistas ──
    def _banner(self):
        ok, label = self._model_info()
        info = Table.grid(padding=(0, 2))
        info.add_column(style=DIM)
        info.add_column()
        info.add_row('Modelo', Text(f'● {label}', style=OK if ok else ERR))
        info.add_row('Directorio', Text(self._get_prompt_path(), style=ACCENT))
        try:
            info.add_row('Capacidades', Text(f'{len(self.assistant.capabilities())} grupos', style=TEXT))
        except Exception:
            pass
        info.add_row('Ayuda', Text.assemble(('/help', f'bold {OK}'), ('  ·  ', DIM),
                                            ('/models', f'bold {ACCENT}'), ('  ·  ', DIM),
                                            ('/exit', f'bold {PURPLE}')))
        body = Group(*[_gradient(l) for l in LOGO], Text(''),
                     Text('Asistente Linux local · escribe en lenguaje natural', style=DIM),
                     Text(''), info)
        self.console.print(Panel(
            body, box=box.ROUNDED, border_style='#45475a', padding=(1, 3),
            title=Text.assemble((f' {APP} ', f'bold {ACCENT}'), (f'v{VERSION} ', DIM)),
            title_align='left', expand=False,
        ))
        self.console.print(Text.assemble(('  Tip  ', f'bold {WARN}'), (random.choice(TIPS), DIM)))

    @staticmethod
    def _table(title):
        return Table(box=box.ROUNDED, border_style='#45475a', show_header=False, padding=(0, 1),
                     title=Text(title, style=f'bold {ACCENT}'), title_justify='left')

    def _cmd_help(self, _a):
        cmds = self._table('Comandos')
        for name, args, desc in COMMANDS:
            cmds.add_row(Text(name, style=f'bold {OK}'), Text(args, style=DIM), desc)
        keys = self._table('Atajos')
        for k, d in SHORTCUTS:
            keys.add_row(Text(k, style=f'bold {ACCENT}'), d)
        ex = self._table('Ejemplos')
        for e in EXAMPLES:
            ex.add_row(Text('›', style=PURPLE), e)
        self.console.print(cmds)
        self.console.print(keys)
        self.console.print(ex)
        self.console.print(Text('  /keys gestiona API keys (OpenAI, GitHub, Stack Exchange, etc.).', style=DIM))
        self.console.print(Text('  /voice on activa respuesta de voz; /voice list muestra perfiles disponibles.', style=DIM))
        self.console.print(Text('  /mic list muestra modelos de reconocimiento de voz disponibles.', style=DIM))
        self.console.print(Text('  /micro on activa dictado local en español; di «micro off» o escribe /micro off para detenerlo.', style=DIM))
        self.console.print(Text('  Las acciones se ejecutan directamente; solo se pide la contraseña de sudo cuando un comando la necesita.', style=DIM))

    def _cmd_caps(self, _a):
        caps = self.assistant.capabilities()
        t = Table(box=box.ROUNDED, border_style='#45475a', title=Text('Capacidades', style=f'bold {ACCENT}'),
                  title_justify='left', header_style=f'bold {DIM}')
        t.add_column('Grupo', style=ACCENT, no_wrap=True)
        t.add_column('Operaciones', style=DIM)
        for item in caps:
            t.add_row(item['name'], ', '.join(item['operations']))
        t.caption = f'{len(caps)} grupos'
        self.console.print(t)

    def _flag(self, on):
        return Text('● activado', style=OK) if on else Text('○ desactivado', style=DIM)

    def _cmd_status(self, _a):
        ok, label = self._model_info()
        t = self._table('Estado')
        t.add_row('Modelo', Text(f'● {label}', style=OK if ok else ERR))
        t.add_row('Micrófono', self._flag(self._micro_enabled))
        tts_status = self._tts.get_status()
        t.add_row('Respuesta voz', self._flag(tts_status['enabled']))
        t.add_row('Capacidades', f'{len(self.assistant.capabilities())} grupos')
        t.add_row('JSON', self._flag(self.json_mode))
        t.add_row('YAML', self._flag(self.yaml_mode))
        t.add_row('Silencioso', self._flag(self.silent_mode))
        t.add_row('Paginación', self._flag(self.paginate_mode))
        t.add_row('Solicitudes', str(self._requests))
        t.add_row('Sesión', f'{int((time.monotonic() - self._started) // 60)} min')
        self.console.print(t)

    def _cmd_micro(self, arg):
        action = arg.strip().casefold()
        if action in {'on', 'encender', 'activar'}:
            if not sys.stdin.isatty():
                self.console.print(Text('  El modo de micrófono requiere una terminal interactiva.', style=WARN))
                return
            from interface.voice import VoiceInput, VoiceInputError

            try:
                voice = VoiceInput()
                voice.prepare()
            except VoiceInputError as exc:
                self.console.print(Text(f'  No se pudo activar el micrófono: {exc}', style=ERR))
                return
            self._voice_input = voice
            self._micro_enabled = True
            self.console.print(Text(
                '  Micrófono activado. Habla una instrucción o escribe /micro off para volver al teclado; '
                'Ctrl+C también lo desactiva.', style=OK))
            return
        if action in {'off', 'apagar', 'desactivar'}:
            self._micro_enabled = False
            if self._voice_input:
                self._voice_input.stop()
            self.console.print(Text('  Micrófono desactivado.', style=DIM))
            return
        if action in {'status', 'estado'}:
            self.console.print(Text(
                f'  Micrófono {"activado" if self._micro_enabled else "desactivado"}.', style=DIM))
            return
        self.console.print(Text('  Uso: /micro on | /micro off | /micro status', style=DIM))

    def _cmd_mic(self, arg):
        """Manage voice recognition models (similar to /models)."""
        action = arg.strip().casefold()
        
        if action == 'list':
            # List available Vosk models
            self.console.print(Text('  Modelos de reconocimiento de voz disponibles:', style=ACCENT))
            self.console.print(Text('  - vosk-model-small-es-0.42 (español, ~50 MB)', style=DIM))
            self.console.print(Text('  Para descargar otros modelos, visita: https://alphacephei.com/vosk/models', style=DIM))
            return
        
        if action.startswith('use '):
            model = action[4:].strip()
            if not model:
                self.console.print(Text('  Uso: /mic use <modelo>', style=DIM))
                return
            
            # Set model via environment variable
            import os
            os.environ['CLIBOT_VOSK_MODEL'] = model
            self.console.print(Text(f'  Modelo de voz cambiado a: {model}', style=OK))
            self.console.print(Text('  Reinicia /micro on para aplicar el cambio.', style=DIM))
            return
        
        self.console.print(Text('  Uso: /mic list | /mic use <modelo>', style=DIM))

    def _cmd_voice(self, arg):
        """Manage text-to-speech."""
        action = arg.strip().casefold()
        
        if action in {'on', 'encender', 'activar'}:
            if not self._tts.is_available():
                self.console.print(Text('  TTS no disponible. Instala con: pip install -e ".[tts]"', style=ERR))
                return
            self._tts.set_enabled(True)
            self.console.print(Text('  Respuesta de voz activada.', style=OK))
            return
        
        if action in {'off', 'apagar', 'desactivar'}:
            self._tts.set_enabled(False)
            self.console.print(Text('  Respuesta de voz desactivada.', style=DIM))
            return
        
        if action == 'list':
            voices = self._tts.list_voices()
            self.console.print(Text('  Perfiles de voz disponibles:', style=ACCENT))
            for profile, desc in voices.items():
                self.console.print(Text(f'  - {profile}: {desc}', style=DIM))
            return
        
        if action.startswith('use '):
            profile = action[4:].strip()
            success, msg = self._tts.set_voice_profile(profile)
            if success:
                self.console.print(Text(f'  {msg}', style=OK))
            else:
                self.console.print(Text(f'  {msg}', style=ERR))
            return
        
        if action == 'status':
            status = self._tts.get_status()
            self.console.print(Text('  Estado de respuesta de voz:', style=ACCENT))
            self.console.print(Text(f'  Disponible: {"Sí" if status["available"] else "No"}', style=DIM))
            self.console.print(Text(f'  Activado: {"Sí" if status["enabled"] else "No"}', style=DIM))
            self.console.print(Text(f'  Voz actual: {status["voice_name"]}', style=DIM))
            self.console.print(Text(f'  Velocidad: {status["rate"]} palabras/min', style=DIM))
            self.console.print(Text(f'  Volumen: {status["volume"]}', style=DIM))
            return
        
        self.console.print(Text('  Uso: /voice on | /voice off | /voice list | /voice use <perfil> | /voice status', style=DIM))

    def _cmd_keys(self, arg):
        """Manage API keys."""
        parts = arg.strip().split()
        if not parts:
            self._keys.interactive_list()
            return
        
        action = parts[0].casefold()
        
        if action == 'list':
            self._keys.interactive_list()
            return
        
        if action == 'set':
            if len(parts) < 2:
                self.console.print(Text('  Uso: /keys set <servicio>', style=DIM))
                self.console.print(Text('  Servicios: ' + ', '.join(self._keys.SUPPORTED_KEYS.keys()), style=DIM))
                return
            service = parts[1].casefold()
            success, msg = self._keys.interactive_set(service)
            if success:
                self.console.print(Text(f'  {msg}', style=OK))
            else:
                self.console.print(Text(f'  {msg}', style=ERR))
            return
        
        if action == 'clear':
            if len(parts) < 2:
                self.console.print(Text('  Uso: /keys clear <servicio>', style=DIM))
                return
            service = parts[1].casefold()
            success, msg = self._keys.interactive_clear(service)
            if success:
                self.console.print(Text(f'  {msg}', style=OK))
            else:
                self.console.print(Text(f'  {msg}', style=ERR))
            return
        
        self.console.print(Text('  Uso: /keys list | /keys set <servicio> | /keys clear <servicio>', style=DIM))
        self.console.print(Text('  Servicios: ' + ', '.join(self._keys.SUPPORTED_KEYS.keys()), style=DIM))

    def _cmd_history(self, _a):
        events = getattr(self.assistant.context, 'events', [])
        if not events:
            self.console.print(Text('  Aún no hay solicitudes en esta sesión.', style=DIM))
            return
        t = Table(box=box.ROUNDED, border_style='#45475a', title=Text('Historial', style=f'bold {ACCENT}'),
                  title_justify='left', header_style=f'bold {DIM}')
        t.add_column('#', style=ACCENT, justify='right')
        t.add_column('Solicitud', overflow='fold')
        t.add_column('Operaciones', style=DIM, overflow='fold')
        t.add_column('Estado', overflow='fold')
        for i, ev in enumerate(events, 1):
            ops = ', '.join(f"{o['capability']}.{o['name']}" for o in ev.get('operations') or [])
            status = Text()
            for r in ev.get('results') or []:
                good = r.get('success')
                status.append('✓ ' if good else '✗ ', style=OK if good else ERR)
                extra = ' · '.join(x for x in (r.get('error_category'), (r.get('detail') or '')[:60]) if x)
                status.append(extra + '\n' if extra else '\n', style=DIM)
            status.rstrip()
            if not status.plain:
                status = Text(ev.get('message') or 'conversación', style=DIM)
            t.add_row(str(i), (ev.get('request') or '')[:80], ops, status)
        self.console.print(t)

    def _cmd_forget(self, _a):
        self.assistant.context.clear()
        self.console.print(Text('  Contexto borrado.', style=DIM))

    def _cmd_reset(self, _a):
        self.assistant.auto_open_terminal = False
        self.json_mode = self.yaml_mode = self.silent_mode = False
        self.paginate_mode = True
        self.console.print(Text('  Preferencias restablecidas.', style=DIM))

    def _cmd_clear(self, _a):
        self.console.clear()
        self._banner()

    def _toggle(self, attr, label, exclusive=None):
        value = not getattr(self, attr)
        setattr(self, attr, value)
        if value and exclusive:
            setattr(self, exclusive, False)
        self.console.print(Text(f'  {label} {"activado" if value else "desactivado"}.', style=DIM))

    def _cmd_json(self, _a):
        self._toggle('json_mode', 'JSON', 'yaml_mode')

    def _cmd_yaml(self, _a):
        if yaml is None:
            self.console.print(Text('  PyYAML no está instalado: pip install pyyaml', style=ERR))
        else:
            self._toggle('yaml_mode', 'YAML', 'json_mode')

    def _cmd_silent(self, _a):
        self._toggle('silent_mode', 'Modo silencioso')

    def _cmd_verbose(self, _a):
        self.silent_mode = not self.silent_mode
        self.console.print(Text(f'  Modo detallado {"desactivado" if self.silent_mode else "activado"}.', style=DIM))

    def _cmd_paginate(self, _a):
        self._toggle('paginate_mode', 'Paginación')

    def _cmd_model(self, arg):
        arg = arg.lower()
        if not arg:
            ok, label = self._model_info()
            msg = f'  ● Modelo activo: {label}' if ok else '  ○ Modelo desactivado (respuestas por reglas)'
            self.console.print(Text(msg, style=OK if ok else DIM))
        elif arg in {'on', 'enable', 'activar', 'true', '1'}:
            from intelligence.llm_integration import LLMIntegration
            self.assistant.llm = LLMIntegration()
            self._model_cache = None
            ok, label = self._model_info()
            if ok:
                self.console.print(Text(f'  ● Modelo activado: {label}', style=OK))
            else:
                self.assistant.llm = None
                self._model_cache = None
                self.console.print(Text('  No se pudo activar el modelo. ¿Está corriendo Ollama?', style=ERR))
        elif arg in {'off', 'disable', 'desactivar', 'false', '0'}:
            self.assistant.llm = None
            self._model_cache = None
            self.console.print(Text('  Modelo desactivado (respuestas por reglas).', style=OK))
        else:
            self.console.print(Text('  Uso: /model [on|off]', style=DIM))

    @staticmethod
    def _llm_config_path():
        configured = os.environ.get('CLIBOT_LLM_CONFIG')
        if configured:
            return Path(configured).expanduser()
        config_home = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
        return config_home / 'clibot' / 'llm.json'

    def _ollama_url(self):
        llm = self.assistant.llm
        base_url = getattr(llm, 'base_url', None) if getattr(llm, 'provider', None) == 'ollama' else None
        return (base_url or os.environ.get('CLIBOT_OLLAMA_URL', 'http://127.0.0.1:11434')).rstrip('/')

    def _ollama_models(self):
        try:
            with urlopen(self._ollama_url() + '/api/tags', timeout=2) as response:
                data = json.loads(response.read(256_000).decode('utf-8'))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError) as exc:
            raise RuntimeError(f'No se pudo consultar Ollama ({self._ollama_url()}): {exc}') from exc
        models = data.get('models') if isinstance(data, dict) else None
        if not isinstance(models, list):
            raise RuntimeError('Ollama devolvió una lista de modelos no válida.')
        return [model for model in models if isinstance(model, dict) and isinstance(model.get('name'), str)]

    def _ollama_catalog(self, query=''):
        params={'sort':'popular'}
        if query:params['q']=query
        url='https://ollama.com/library?'+urlencode(params)
        request=Request(url,headers={
            'User-Agent':'CLIBOT model browser',
            'HX-Request':'true',
            'HX-Target':'repo',
        })
        try:
            with urlopen(request,timeout=5) as response:
                body=response.read(2_000_000).decode('utf-8')
        except (HTTPError,URLError,TimeoutError,OSError,UnicodeDecodeError) as exc:
            raise RuntimeError(f'No se pudo consultar el catálogo de Ollama: {exc}') from exc
        parser=_OllamaCatalogParser()
        parser.feed(body)
        if not parser.models and '<div' not in body:
            raise RuntimeError('Ollama devolvió una respuesta de catálogo no válida.')
        return parser.models

    def _save_ollama_model(self, model):
        path = self._llm_config_path()
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(path.parent, 0o700)
        fd, temporary = tempfile.mkstemp(prefix='.llm-', dir=path.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump({'provider': 'ollama', 'model': model, 'base_url': self._ollama_url()}, stream)
                stream.write('\n')
            os.replace(temporary, path)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
        from intelligence.llm_integration import LLMIntegration
        self.assistant.llm = LLMIntegration(config_path=str(path))
        self._model_cache = None
        if not self.assistant.llm.is_available():
            raise RuntimeError(f'Ollama no confirmó el modelo {model!r} como disponible.')

    def _cmd_models(self, arg):
        action, _, model = arg.strip().partition(' ')
        action = action.casefold() if action else 'list'
        model = model.strip()
        if action in {'list', 'ls'} and not model:
            self._show_models_catalog()
            return
        if action in {'search','buscar'} and model:
            self._show_models_catalog(model)
            return
        if action == 'use' and model:
            try:
                installed = {item['name'] for item in self._ollama_models()}
                if model not in installed:
                    self.console.print(Text(f'  {model} no está descargado. Usa /models pull {model}.', style=WARN))
                    return
                self._save_ollama_model(model)
            except (RuntimeError, OSError, ValueError) as exc:
                self.console.print(Text(f'  No se pudo activar el modelo: {exc}', style=ERR))
                return
            self.console.print(Text(f'  Modelo Ollama seleccionado: {model}', style=OK))
            return
        if action == 'pull' and model and len(model) <= 128 and all(
                char.isalnum() or char in '._:/-' for char in model):
            self._pull_ollama_model(model)
            return
        self.console.print(Text('  Uso: /models [search <texto> | use <modelo> | pull <modelo>]', style=DIM))

    def _show_models_catalog(self, query=''):
        current=getattr(self.assistant.llm,'model',None)
        try:
            installed=self._ollama_models()
        except RuntimeError as exc:
            installed=[]
            self.console.print(Text(f'  Modelos instalados: no se pudo consultar Ollama ({exc}).',style=WARN))
        if installed:
            table=self._table('Modelos instalados')
            for item in installed:
                name=item['name']
                size=item.get('size')
                size_text=f'{size/1_000_000_000:.1f} GB' if isinstance(size,(int,float)) else ''
                table.add_row(Text('●' if name==current else ' ',style=OK),
                              Text(name,style=OK if name==current else TEXT),Text(size_text,style=DIM))
            self.console.print(table)
        else:
            self.console.print(Text('  Aún no hay modelos locales instalados.',style=DIM))
        try:
            catalog=self._ollama_catalog(query)
        except RuntimeError as exc:
            self.console.print(Text(f'  {exc} · puedes verlos en https://ollama.com/library',style=WARN))
            return
        title='Catálogo Ollama' + (f' · búsqueda: {query}' if query else ' · populares')
        table=self._table(title)
        for index,item in enumerate(catalog,1):
            variants=', '.join(item['variants']) or 'latest'
            desc=item['description']
            if len(desc)>88:desc=desc[:85].rstrip()+'…'
            table.add_row(Text(str(index),style=f'bold {PURPLE}'),
                          Text(item['name'],style=ACCENT),
                          Text(variants,style=DIM),
                          Text(desc,style=TEXT))
        if catalog:self.console.print(table)
        else:self.console.print(Text('  No se encontraron modelos con esa búsqueda.',style=DIM))
        self.console.print(Text('  Busca en el catálogo: /models search <texto>',style=DIM))
        if not catalog:return
        if not sys.stdin.isatty():
            self.console.print(Text('  Descarga: /models pull <modelo[:variante]> · selecciona: /models use <modelo>',style=DIM))
            return
        by_name={item['name']:item for item in catalog}
        while True:
            try:
                choice=input('  Número/modelo para descargar, «buscar <texto>» o Enter para salir: ').strip()
            except (EOFError,KeyboardInterrupt):
                self.console.print(Text('\n  Selector de modelos cerrado.',style=DIM))
                return
            if not choice:return
            if choice.casefold().startswith(('buscar ','search ')):
                query=choice.split(' ',1)[1].strip()
                if query:
                    self._show_models_catalog(query)
                return
            if choice.isdigit() and 1<=int(choice)<=len(catalog):
                item=catalog[int(choice)-1]
                selected=item['name']
                variants=item['variants']
                if variants:
                    self.console.print(Text('  Variantes: '+', '.join(
                        f'{index}. {variant}' for index,variant in enumerate(variants,1)),style=DIM))
                    try:
                        variant=input('  Número o etiqueta de variante (Enter para latest): ').strip().lower()
                    except (EOFError,KeyboardInterrupt):
                        self.console.print(Text('\n  Descarga cancelada.',style=WARN))
                        return
                    if variant:
                        if variant.isdigit() and 1<=int(variant)<=len(variants):
                            variant=variants[int(variant)-1]
                        if variant not in variants:
                            self.console.print(Text('  Variante no válida; usa una de las etiquetas mostradas.',style=WARN))
                            continue
                        selected=f'{selected}:{variant}'
            else:
                selected=choice
                base=selected.split(':',1)[0]
                if base not in by_name:
                    self.console.print(Text('  Elige un número de la lista o un nombre que aparezca en ella.',style=WARN))
                    continue
            self._pull_ollama_model(selected)
            return

    def _pull_ollama_model(self, model):
        request = Request(self._ollama_url() + '/api/pull',
                          data=json.dumps({'name': model, 'stream': True}).encode('utf-8'),
                          headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urlopen(request, timeout=600) as response:
                for raw_line in response:
                    if not raw_line.strip():
                        continue
                    update = json.loads(raw_line.decode('utf-8'))
                    if update.get('error'):
                        raise RuntimeError(str(update['error']))
                    status = update.get('status', 'Descargando')
                    total, complete = update.get('total'), update.get('completed')
                    progress = f' {complete * 100 // total}%' if isinstance(total, int) and total > 0 and isinstance(complete, int) else ''
                    self.console.print(Text(f'  {status}{progress}', style=DIM), end='\r')
                    if status == 'success':
                        self.console.print()
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError, RuntimeError) as exc:
            self.console.print(Text(f'\n  No se pudo descargar {model}: {exc}', style=ERR))
            return
        try:
            self._save_ollama_model(model)
        except (RuntimeError, OSError, ValueError) as exc:
            self.console.print(Text(f'\n  Descargado, pero no se pudo seleccionar {model}: {exc}', style=WARN))
            return
        self.console.print(Text(f'\n  Modelo descargado y seleccionado: {model}', style=OK))

    def _cmd_token(self, arg):
        from capabilities.github import (
            clear_github_token, configure_github_token, github_token_path,
        )
        action = arg.strip().casefold() or 'status'
        path = github_token_path()
        environment_token = bool(os.environ.get('GITHUB_TOKEN'))
        if action in {'status', 'estado'}:
            configured = environment_token or path.is_file()
            source = 'GITHUB_TOKEN del entorno' if environment_token else (str(path) if path.is_file() else None)
            message = f'  Token de GitHub configurado ({source}).' if configured else '  No hay un token de GitHub configurado.'
            self.console.print(Text(message, style=OK if configured else DIM))
            self.console.print(Text('  Usa /token set para guardarlo sin mostrarlo o /token clear para borrarlo.', style=DIM))
            return
        if action in {'set', 'configurar'}:
            if not sys.stdin.isatty():
                self.console.print(Text('  Para ocultar el token, ejecuta /token set desde una terminal interactiva.', style=ERR))
                return
            self.console.print(Text('  El token se solicitará sin mostrarlo ni guardarlo en el historial.', style=DIM))
            try:
                token = getpass.getpass('  GitHub token: ')
                path = configure_github_token(token)
            except (EOFError, KeyboardInterrupt):
                self.console.print(Text('\n  Configuración cancelada.', style=WARN))
                return
            except (OSError, ValueError) as exc:
                self.console.print(Text(f'  No se pudo guardar el token: {exc}', style=ERR))
                return
            self.console.print(Text(f'  Token guardado de forma privada en {path}. No se muestra su valor.', style=OK))
            return
        if action in {'clear', 'borrar', 'eliminar'}:
            try:
                clear_github_token()
            except OSError as exc:
                self.console.print(Text(f'  No se pudo borrar el token: {exc}', style=ERR))
                return
            message = '  Token guardado eliminado.'
            if environment_token:
                message += ' GITHUB_TOKEN sigue disponible desde el entorno.'
            self.console.print(Text(message, style=OK))
            return
        self.console.print(Text('  Uso: /token [status | set | clear]', style=DIM))

    def _cmd_run(self, arg):
        if not arg:
            self.console.print(Text('  Uso: /run <comando>', style=DIM))
        else:
            self._ask('ejecuta comando: ' + arg)

    def _cmd_cd(self, arg):
        target = Path(arg).expanduser() if arg else Path.home()
        try:
            os.chdir(target)
            self._git_cache = ('', 0.0, '')
            self.console.print(Text(f'  {self._get_prompt_path()}', style=DIM))
        except OSError as exc:
            self.console.print(Text(f'  No se pudo cambiar de directorio: {exc.strerror or exc}', style=ERR))

    def _cmd_export(self, arg):
        events = getattr(self.assistant.context, 'events', [])
        if not events:
            self.console.print(Text('  No hay nada que exportar todavía.', style=DIM))
            return
        path = Path(arg).expanduser() if arg else Path.cwd() / f'clibot-sesion-{datetime.now():%Y%m%d-%H%M%S}.md'
        out = [f'# Sesión {APP} · {datetime.now():%Y-%m-%d %H:%M}', '']
        for i, ev in enumerate(events, 1):
            out += [f'## {i}. {ev.get("request", "")}', '']
            ops = ', '.join(f"`{o['capability']}.{o['name']}`" for o in ev.get('operations') or [])
            if ops:
                out += [f'Operaciones: {ops}', '']
            for r in ev.get('results') or []:
                out.append(f'- {"✓" if r.get("success") else "✗"} {r.get("detail") or r.get("error_category") or ""}'.rstrip())
            if ev.get('message'):
                out += ['', ev['message']]
            out.append('')
        try:
            path.write_text('\n'.join(out), encoding='utf-8')
            self.console.print(Text(f'  Sesión guardada en {path}', style=OK))
        except OSError as exc:
            self.console.print(Text(f'  No se pudo guardar: {exc.strerror or exc}', style=ERR))

    def _bye(self):
        mins = int((time.monotonic() - self._started) // 60)
        self.console.print(Text(f'\n  Hasta luego · {self._requests} solicitudes · {mins} min', style=DIM))