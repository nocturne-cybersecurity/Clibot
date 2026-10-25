"""Clean, keyboard-first interactive terminal inspired by modern coding CLIs."""
import sys, time, json, os, subprocess
from pathlib import Path
from core.contracts import Plan, Operation, Result
try:
    import yaml
except ImportError:
    yaml = None
try:
    import readline  # Enables left/right editing and arrow-key input history in Python's input().
except ImportError:
    readline=None
from interface.formatter import format_response, paint
from core.assistant import Assistant

class Terminal:
    def __init__(self,assistant):
        self.assistant=assistant
        self.json_mode=False
        self.yaml_mode=False
        self.silent_mode=False
        self.paginate_mode=True
        self._setup_completer()

    def _serialize_response(self, response):
        """Convert Plan, Operation, and Result objects to dicts for JSON serialization."""
        if isinstance(response, dict):
            return {k: self._serialize_response(v) for k, v in response.items()}
        elif isinstance(response, list):
            return [self._serialize_response(item) for item in response]
        elif isinstance(response, Plan):
            return {
                'operations': [self._serialize_response(op) for op in response.operations],
                'request': response.request,
                'clarification': response.clarification,
                'message': response.message,
                'unrecognized': response.unrecognized,
                'reformat_last': response.reformat_last,
            }
        elif isinstance(response, Operation):
            return {
                'capability': response.capability,
                'name': response.name,
                'arguments': response.arguments,
                'description': response.description,
                'dependencies': response.dependencies,
                'risk': response.risk.value,
                'requires_privilege': response.requires_privilege,
                'timeout': response.timeout,
                'id': response.id,
            }
        elif isinstance(response, Result):
            return {
                'operation_id': response.operation_id,
                'success': response.success,
                'stdout': response.stdout,
                'stderr': response.stderr,
                'exit_code': response.exit_code,
                'started_at': response.started_at,
                'ended_at': response.ended_at,
                'duration': response.duration,
                'data': response.data,
                'error_category': response.error_category,
                'verified': response.verified,
                'status': response.status.value,
            }
        else:
            return response

    def _paginate(self, text):
        """Paginate long output using less if available."""
        if not self.paginate_mode or not sys.stdout.isatty():
            return text
        
        lines = text.split('\n')
        if len(lines) < 30:  # Only paginate if output is long
            return text
        
        try:
            process = subprocess.Popen(['less', '-R', '-F', '-X'], stdin=subprocess.PIPE, stdout=sys.stdout)
            process.communicate(text.encode())
            return ''
        except (FileNotFoundError, OSError):
            return text

    def _get_prompt_path(self):
        """Get shortened current directory path for prompt."""
        cwd = Path.cwd()
        home = Path.home()
        try:
            rel = cwd.relative_to(home)
            return f'~/{rel}'
        except ValueError:
            return str(cwd)

    def _banner(self):
        model=self.assistant.llm
        mode='offline' if not model.is_available() or model.provider=='ollama' else model.provider
        print(paint('╭─','muted')+' '+paint('CLIBOT','bold')+paint(' · CLI Bot · '+mode,'muted'))
        print(paint('╰─','muted')+' '+paint('/help para ayuda · /exit para salir','muted'))

    def _setup_completer(self):
        """Setup tab completion for commands."""
        if readline:
            commands = ['/help', '/capabilities', '/status', '/history', 'history', 'historial', '/forget', '/reset', '/clear', '/exit', '/json', '/silent', '/verbose']
            readline.set_completer(lambda text, state: self._completer_func(text, state, commands))
            readline.parse_and_bind('tab: complete')
    
    def _completer_func(self, text, state, commands):
        """Tab completion callback."""
        options = [cmd for cmd in commands if cmd.startswith(text)]
        if state < len(options):
            return options[state]
        return None

    def _help(self):
        print(paint('COMANDOS','cyan'))
        for key,description in [('/help','Ayuda y ejemplos'),('/capabilities','Ver capacidades'),('/status','Estado de CLIBOT'),('/history','Historial'),('/forget','Borrar contexto'),('/reset','Restablecer preferencias'),('/clear','Limpiar pantalla'),('/json','Alternar JSON'),('/silent','Alternar modo silencioso'),('/exit','Salir'),('/run <cmd>','Ejecutar comando explícito')]:
            print(f'  {paint(key,"green"):24} {description}')
        print(paint('\nPRUEBA','cyan'))
        for example in ('muestra información del sistema','lista archivos en .','busca en Google cómo ver el disco','traduce "Good morning" al español','ejecuta printf hola | tr a-z A-Z','abre Firefox y GitHub','muestra los puertos abiertos'):
            print('  '+paint('›','muted')+' '+example)
        print(paint('\nLas acciones importantes piden confirmación.','muted'))

    def _print_message(self, message):
        """Reveal a response with a brief typewriter effect on interactive TTYs."""
        animation = (
            sys.stdout.isatty()
            and not self.json_mode
            and not self.silent_mode
            and self.assistant.config['settings'].get('terminal', {}).get('animation', True)
        )
        if not animation:
            print(message)
            return

        # Keep short replies smooth and cap long logs/tables to about 0.9 seconds.
        step = max(1, (len(message) + 179) // 180)
        for index in range(0, len(message), step):
            sys.stdout.write(message[index:index + step])
            sys.stdout.flush()
            time.sleep(0.005)
        print()

    def _multiline_input(self, prompt):
        """Multi-line input editor for long commands."""
        lines = []
        while True:
            try:
                line = input(prompt)
            except (EOFError, KeyboardInterrupt):
                return None
            if line == '' and lines:
                break
            lines.append(line)
            prompt = '... '
        return '\n'.join(lines)

    def run(self):
        self._banner()
        while True:
            try:
                line = input(paint(f'{self._get_prompt_path()} ❯','cyan')+' ').strip()
                if line.endswith('\\'):
                    line = line[:-1]
                    continuation = self._multiline_input('... ')
                    if continuation is None:
                        print('\n'+paint('Cancelado.','muted'))
                        continue
                    line = line + '\n' + continuation
            except (EOFError,KeyboardInterrupt):print('\n'+paint('Hasta luego.','muted'));break
            if not line:continue
            command=line.casefold()
            if command in {'/exit','/quit','/q','salir','exit','quit'}:print(paint('Hasta luego.','muted'));break
            if command in {'/help','help','ayuda'}:self._help();continue
            if command in {'/capabilities','/caps','capabilities','$'}:
                for item in self.assistant.capabilities():print(f"  {paint(item['name'],'cyan')}  {paint(', '.join(item['operations']),'muted')}")
                continue
            if command=='/status':
                json_status=' · JSON' if self.json_mode else ''
                silent_status=' · silent' if self.silent_mode else ''
                model=self.assistant.llm
                model_status=f" · modelo {model.provider}:{model.model}" if model.is_available() else ' · respuestas locales por reglas'
                print(f"  {paint('●','green')} LLMAH listo · {len(self.assistant.capabilities())} grupos{model_status}{json_status}{silent_status}");continue
            if command in {'/history','history','historial'}:
                if not self.assistant.context.events:print(paint('  Aún no hay solicitudes en esta sesión.','muted'))
                else:
                    for i,event in enumerate(self.assistant.context.events,1):
                        request=event['request']
                        operations=', '.join(f"{op['capability']}.{op['name']}" for op in event['operations'])
                        outcomes=event['results']
                        if outcomes:
                            status='; '.join(('correcto' if row['success'] else row['status'].upper())+(f": {row['error_category']}" if row['error_category'] else '')+(f" — {row['detail'][:120]}" if row['detail'] else '') for row in outcomes)
                        else:status=event['message'] or 'conversación'
                        summary=f' · {operations}' if operations else ''
                        print(f'  {paint(str(i).rjust(2),"muted")}  {request}{summary} · {status}')
                continue
            if command=='/forget':self.assistant.context.clear();print(paint('  Contexto borrado.','muted'));continue
            if command=='/reset':self.assistant.auto_open_terminal=False;self.json_mode=False;self.yaml_mode=False;self.silent_mode=False;self.paginate_mode=True;print(paint('  Preferencias restablecidas.','muted'));continue
            if command=='/paginate':self.paginate_mode=not self.paginate_mode;print(paint(f'  Paginación {"activada" if self.paginate_mode else "desactivada"}.','muted'));continue
            if command=='/json':self.json_mode=not self.json_mode;self.yaml_mode=False;print(paint(f'  JSON {"activado" if self.json_mode else "desactivado"}.','muted'));continue
            if command=='/yaml':
                if yaml is None:
                    print(paint('  Error: PyYAML no está instalado. Instálalo con: pip install pyyaml','red'))
                else:
                    self.yaml_mode=not self.yaml_mode;self.json_mode=False
                    print(paint(f'  YAML {"activado" if self.yaml_mode else "desactivado"}.','muted'))
                continue
            if command=='/silent':self.silent_mode=not self.silent_mode;print(paint(f'  Modo silencioso {"activado" if self.silent_mode else "desactivado"}.','muted'));continue
            if command=='/verbose':self.silent_mode=not self.silent_mode;print(paint(f'  Modo detallado {"desactivado" if self.silent_mode else "activado"}.','muted'));continue
            if command in {'/clear','clear','limpia pantalla','limpia la pantalla','limpiate','clear screen'}:
                if sys.stdout.isatty():print('\033[2J\033[H',end='')
                else:print('\n'*3)
                self._banner();continue
            if command.startswith('/run '):line='ejecuta comando: '+line[5:].strip()
            if line.startswith('!'):line='ejecuta comando: '+line[1:].strip()
            if line.startswith('|'):
                line='interpreta salida: '+line[1:].strip()
            if line.startswith('>'):
                line='redirige a archivo: '+line[1:].strip()
            response=self.assistant.handle(line)
            if self.json_mode:
                print(json.dumps(self._serialize_response(response), indent=2, default=str))
            elif self.yaml_mode:
                if yaml is None:
                    print(paint('Error: PyYAML no está instalado. Instálalo con: pip install pyyaml','red'))
                else:
                    print(yaml.dump(response, default_flow_style=False, allow_unicode=True))
            elif self.silent_mode:
                if response.get('error'):
                    print(paint('Error:','red'), response['error'])
            else:
                self._print_message(format_response(response))
                print()
