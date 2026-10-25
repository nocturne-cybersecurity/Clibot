"""Readable terminal formatting using portable ANSI colors and aligned tables."""
import os, sys, shutil, textwrap
import re

try:
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name, guess_lexer
    from pygments.formatters import TerminalFormatter
    from pygments.util import ClassNotFound
    PYGMENTS_AVAILABLE = True
except ImportError:
    PYGMENTS_AVAILABLE = False

_COLOR = sys.stdout.isatty() and 'NO_COLOR' not in os.environ and os.environ.get('TERM') != 'dumb'
_CODES={'cyan':'36','blue':'34','green':'32','yellow':'33','red':'31','muted':'2','bold':'1','magenta':'35'}
def paint(value,color):
    text=str(value)
    return f"\033[{_CODES[color]}m{text}\033[0m" if _COLOR and color in _CODES else text


def highlight_code(text, language=None):
    """Apply syntax highlighting to code blocks."""
    if not PYGMENTS_AVAILABLE or not _COLOR:
        return text
    
    try:
        if language:
            lexer = get_lexer_by_name(language)
        else:
            lexer = guess_lexer(text)
        return highlight(text, lexer, TerminalFormatter(style='monokai'))
    except (ClassNotFound, Exception):
        return text


def _compact_error(value, limit=20):
    """Keep subprocess failures useful without flooding the interactive terminal."""
    text=str(value or '').strip()
    if re.search(r'\b503\b',text) and re.search(r'high demand|service unavailable|unavailable',text,re.I):
        return 'El servicio de Gemini respondió HTTP 503 por alta demanda. El CLI reintentó la petición; prueba más tarde.'
    lines=text.splitlines()
    if len(lines)>limit:
        return '\n'.join(lines[:limit])+'\n… se omitieron '+str(len(lines)-limit)+' líneas de detalle.'
    return text

def _table(rows):
    if not rows:return '(sin resultados)'
    keys=[]
    for row in rows:
        for key in row:
            if key not in keys:keys.append(key)
    values=[[str(row.get(k,'')) for k in keys] for row in rows]
    available=max(32,shutil.get_terminal_size((88,24)).columns-4)
    widths=[min(32,max(len(str(k)),*(len(r[i]) for r in values))) for i,k in enumerate(keys)]
    while sum(widths)+2*(len(widths)-1)>available:
        widest=max(range(len(widths)),key=widths.__getitem__)
        if widths[widest]<=8:break
        widths[widest]-=1
    head='  '.join(paint(str(k).ljust(widths[i]),'muted') for i,k in enumerate(keys))
    bar='  '.join('─'*w for w in widths)
    body=['  '.join((v[i][:widths[i]-1]+'…' if len(v[i])>widths[i] and widths[i]>1 else v[i][:widths[i]]).ljust(widths[i]) for i in range(len(keys))) for v in values]
    return '\n'.join([head,bar,*body])

def _human_value(value, capability=None):
    if isinstance(value,dict):
        if 'query' in value and 'results' in value:
            rows=value['results']
            if not rows:return f"No encontré resultados para «{value['query']}»."
            
            # Presentación mejorada de resultados de búsqueda
            query = value['query']
            num_results = len(rows)
            
            # Mostrar resumen del mejor resultado
            primary=next((row for row in rows if row.get('snippet')),rows[0])
            snippet = primary.get('snippet') or primary.get('title') or ''
            
            # Construir respuesta con contexto
            lines = []
            lines.append(f"Encontré {num_results} resultado{'s' if num_results > 1 else ''} para «{query}»:")
            lines.append("")
            
            # Mostrar el mejor resultado destacado
            if snippet:
                lines.append(paint('📌 Mejor resultado:', 'yellow'))
                lines.append(f"  {snippet[:300]}{'...' if len(snippet) > 300 else ''}")
                if primary.get('url'):
                    lines.append(f"  {paint(primary['url'], 'cyan')}")
                lines.append("")
            
            # Mostrar otros resultados relevantes
            if num_results > 1:
                lines.append(paint('📚 Otras fuentes:', 'yellow'))
                for i, row in enumerate(rows[1:4], 1):  # Máximo 3 adicionales
                    title = row.get('title', 'Sin título')
                    url = row.get('url', '')
                    lines.append(f"  {i}. {title[:60]}{'...' if len(title) > 60 else ''}")
                    if url:
                        lines.append(f"     {paint(url, 'cyan')}")
            
            return '\n'.join(lines)
        if 'exit_code' in value and ('stdout' in value or 'stderr' in value):
            output=value.get('stdout','').rstrip()
            error=value.get('stderr','').rstrip()
            if output and error:return output+'\n'+paint(_compact_error(error),'red')
            if output:return output
            if error:return paint(_compact_error(error),'red')
            return f"Comando completado (código {value['exit_code']})."
        if 'time' in value and 'timezone' in value:
            return f"Son las {value['time']} ({value['timezone']})."
        if 'result' in value and 'expression' in value:
            return f"{value['expression']} = {value['result']}"
        if 'translation' in value:
            return str(value['translation'])
        if value.get('source') == 'RDAP' and 'target' in value:
            rows=[('Objetivo',value['target']),('Tipo',value.get('type','')),('Registro',value.get('name') or 'sin dato'),('Red',value.get('network') or 'sin dato'),('Estados',', '.join(value.get('status',[])) or 'sin dato'),('Organizaciones',', '.join(value.get('entities',[])) or 'sin dato')]
            return '\n'.join(f"  {paint(k+':','muted')} {v}" for k,v in rows)+f"\n  {paint(value.get('disclaimer',''),'muted')}"
        if 'total_gib' in value and 'available_gib' in value:
            return f"RAM: {value['total_gib']} GiB total; {value['available_gib']} GiB disponible y {value['used_gib']} GiB usada."
        if 'user' in value and 'is_root' in value:
            privilege='root' if value['is_root'] else 'usuario normal (sin root)'
            return f"Usuario {value['user']} (UID {value['uid']}), grupo {value['primary_group']}; {privilege}. Carpeta actual: {value['working_directory']}"
        if {'hostname','os','kernel','architecture','python'} <= value.keys():
            os_name=str(value['os']).split('-')[0]
            memory=value.get('memory') or {}
            ram=''
            if memory.get('MemTotal'):
                total=int(memory['MemTotal'].split()[0])/(1024*1024)
                available=int(memory.get('MemAvailable','0').split()[0])/(1024*1024)
                ram=f" · RAM {available:.1f}/{total:.1f} GiB libre"
            return f"{value['hostname']} · {os_name} · kernel {value['kernel']}\n{value['architecture']} · Python {value['python']}{ram}"
        if 'memory' in value:
            value=dict(value)
            mem=value.pop('memory',{})
            # system details contain a large procfs dictionary; surface only useful totals.
            if mem:value['memoria']=f"{mem.get('MemAvailable','?')} disponible de {mem.get('MemTotal','?')}"
        def compact(item):
            if isinstance(item,(list,tuple)):
                return ', '.join(map(str,item))
            return str(item)
        return '\n'.join(f"  {paint(k.replace('_',' ').capitalize()+':','muted')} {compact(v)}" for k,v in value.items())
    if isinstance(value,list):
        if value and all(isinstance(row,dict) for row in value):return _table(value)
        return '\n'.join(f'  • {item}' for item in value) if value else '(sin resultados)'
    return str(value)

def format_response(response):
    if response.get('message'):return _wrap(paint('LLMAH','magenta')+'  '+response['message'])
    if response.get('clarification'):return _wrap(paint('LLMAH','magenta')+'  '+response['clarification'])
    if response.get('error'):return _wrap(paint('Validación fallida:','red')+f" {response['error']}")
    lines=[]
    for result in response.get('results',[]):
        if result.success:
            operation=response.get('plan').operations[0] if response.get('plan') and response['plan'].operations else None
            if not (operation and operation.capability=='web' and operation.name=='search'):
                lines.append(paint('✓','green')+' '+paint('Listo','green'))
            value=result.data.get('value') if isinstance(result.data,dict) else None
            if result.data.get('capabilities'):
                summaries={'system':'hora/fecha, RAM, CPU/GPU, identidad, carpeta actual, información y logs','filesystem':'listar, leer, buscar, crear, mover, copiar, comprimir y calcular hashes','networking':'interfaces, rutas, DNS, pruebas TCP y puertos locales en escucha','services':'consultar servicios y cambiar su estado con confirmación','browser':'abrir aplicaciones y páginas en un escritorio disponible','web':'buscar en la web y mostrar una respuesta breve','translation':'traducir texto con Google y alternativa si hay limitación (requiere internet)','development':'Python, Git y comandos explícitos confirmados','cybersecurity':'DNS, RDAP/WHOIS, disponibilidad de Nmap, escaneos autorizados e informes','calculator':'aritmética, raíces, potencias y funciones comunes'}
                for cap in result.data['capabilities']:
                    description=summaries.get(cap['name'])
                    if description:lines.append(f"  {paint(cap['name'],'cyan')}  {description}")
            elif value is not None:
                if operation and operation.capability=='system' and operation.name=='time' and operation.arguments.get('include_date'):
                    lines.append(f"Hoy es {value['date']}. Son las {value['time']} ({value['timezone']}).")
                elif operation and operation.capability=='system' and operation.name=='gpu_info' and not value:
                    lines.append('No pude detectar una GPU. Puede faltar lspci o el controlador no expone el dispositivo.')
                else:lines.append(_human_value(value,operation.capability if operation else None))
            elif result.stdout:lines.append(result.stdout.rstrip())
            if result.duration>0.4:lines.append(paint(f'  {result.duration:.1f}s','muted'))
        else:
            category=(result.error_category or result.status.value).replace('_',' ')
            lines.append(paint('✗ '+category.capitalize(),'red'))
            if result.stderr:lines.append('  '+_compact_error(result.stderr))
            if result.error_category=='missing_dependency':lines.append(paint('  Instala la herramienta con el gestor de paquetes de tu distribución.','muted'))
    return _wrap('\n'.join(lines) if lines else paint('No se ejecutó ninguna operación.','muted'))


def _wrap(message):
    """Keep prose in a calm, readable column instead of stretching across wide terminals."""
    width=max(50,min(100,shutil.get_terminal_size((80,24)).columns-8))
    output=[]
    for line in message.splitlines():
        if not line:
            output.append('')
        elif len(line)<=width:
            output.append(line)
        else:
            output.extend(textwrap.wrap(line,width=width,subsequent_indent='  ',break_long_words=True,break_on_hyphens=False))
    return '\n'.join(output)
