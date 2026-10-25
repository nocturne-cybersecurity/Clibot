"""Natural-language intents for safe creation of a new empty file."""
from pathlib import Path
import re
from core.contracts import Operation, Plan, Risk

_CREATE=re.compile(r'\b(?:crea|crear|crees|create|make)\b.*\b(?:archivo|fichero|file)\b',re.I)
def _handler(text,context=None):
    normalized=text
    match=re.search(r'(?i)\b(?:llamado|llamada|llame|named|name)\s+["\']?([^\s"\']+)',text)
    if not match:
        match=re.search(r'(?i)\b(?:archivo|fichero|file)\s+["\']?([\w.-]+\.[\w.-]+)',text)
    if not match:
        if context is not None:
            context.pending={'kind':'create_file_name','directory':_directory(text),'extension':'.txt' if re.search(r'(?i)\b(?:texto|text)\b',text) else ''}
        return Plan([],text,'¿Qué nombre quieres para el archivo? Puedes responder solo con el nombre; por ejemplo, hola.txt.')
    filename=match.group(1).rstrip('.,;')
    if re.search(r'(?i)\b(?:texto|text)\b',text) and '.' not in filename:filename+='.txt'
    if filename in {'.','..'} or '/' in filename or '\\' in filename:return Plan([],text,'Indica solo un nombre de archivo, sin rutas.')
    directory=_directory(text)
    destination=str(Path(directory).expanduser()/filename)
    operation=Operation('filesystem','create',{'path':destination,'content':''},description=f'crear el archivo vacío {destination}',risk=Risk.MODERATE)
    return Plan([operation],text)

def _directory(text):
    directory_match=re.search(r'(?i)\b(?:en|dentro de|inside|in)\s+(?:mi\s+)?(?:carpeta|directorio|folder|directory)\s+(?:actual|current|de trabajo|working directory)\b',text)
    if directory_match:return '.'
    quoted_paths=re.findall(r'["\']([^"\']+)["\']',text)
    path_match=next((item for item in quoted_paths if '/' in item),None)
    if path_match:return path_match
    path_match=re.search(r'(?<!\w)(?:/[^\s,;]+|\.\.?/[^\s,;]+)',text)
    if path_match:return path_match.group(0).rstrip('.,;')
    home_match=re.search(r'(?i)(?<![\w/])home/[\w./-]+',text)
    if home_match:return '/'+home_match.group(0).rstrip('.,;')
    return '.'

def register(router):router.register('create_file',[_CREATE.pattern],_handler,priority=100)
