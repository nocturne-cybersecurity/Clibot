"""Browser opening and terminal web-search intents."""
import re
from core.contracts import Operation, Plan, Risk

_VERB = r'(?:quiero\s+)?(?:busc\w*|busqu\w*|googlea\w*|encuentr\w*|investig\w*|search(?:\s+for)?)'
_SEARCH = re.compile(r'\b' + _VERB + r'\b', re.I)


def _handler(text, context=None):
    normalized = text.strip()
    # A request to find a local file belongs to the filesystem capability, not
    # to the web-search intent. Returning None lets the main parser handle it.
    if (re.search(r'(?i)\b(?:archivo|archivos|fichero|ficheros|file|files|carpeta|directorio)\b', normalized)
            and re.search(r'(?i)\b(?:busc\w*|encuentr\w*|find)\b', normalized)):
        return None
    # Questions about whether search is available should not turn into a query
    # for the words following "buscador".
    if (re.search(r'(?i)\b(?:buscador|busqueda|busquedas)\b', normalized)
            and re.search(r'(?i)\b(?:funciona|sirve|disponible|estado|status)\b', normalized)):
        return Plan([], text, 'Puedo buscar desde esta terminal. Si un proveedor bloquea la petición, probaré otro; necesito conexión a Internet.')
    # A capability question is conversation, not a search for the word "cosas".
    if re.search(r'(?i)\b(?:puedes|puede|sabes)\b', normalized) and re.search(r'(?i)\b(?:buscar|buscas|google)\b', normalized):
        if context is not None:
            context.pending = {'kind': 'web_search'}
        return Plan([], text, 'Sí. Puedo buscar en la web y mostrarte resultados aquí mismo. ¿Qué tema quieres investigar?')

    match = re.search(r'(?i)\b' + _VERB + r'\s+(.+?)[?.!]*$', normalized)
    query = match.group(1).strip(' "\'?.!') if match else ''
    query = re.sub(r'(?i)^(?:en\s+)?(?:google|la\s+web|internet)\s+', '', query).strip()
    query = re.sub(r'(?i)\s+(?:en\s+)?(?:google|la\s+web|internet)\s*$', '', query).strip()
    github = bool(re.search(r'(?i)\bgithub\b', text))
    query = re.sub(r'(?i)\b(?:abre|abrir|github)\b', ' ', query)
    query = re.sub(r'(?i)^el\s+usuario\s+', '', query).strip()
    if github and query:
        query = 'site:github.com ' + query
    if query.casefold() in {'algo', 'cosas', 'alguna cosa', 'something', 'algo en google'}:
        query = ''
    if not query:
        if context is not None:
            context.pending = {'kind': 'web_search'}
        return Plan([], text, '¿Qué tema o frase quieres que busque? Te mostraré los resultados en esta terminal.')

    return Plan([Operation('web', 'search', {'query': query}, description=f'buscar «{query}» en la web', risk=Risk.LOW)], text)


def register(router):
    router.register('web_search', [_SEARCH.pattern], _handler, priority=125)
