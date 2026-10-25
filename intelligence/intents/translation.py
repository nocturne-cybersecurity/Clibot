"""Natural language translation requests using the Google Translate endpoint."""
import re
from core.contracts import Operation, Plan, Risk
from intelligence.rules import normalize

LANGUAGES = {
    'espanol': 'es', 'castellano': 'es', 'spanish': 'es', 'ingles': 'en', 'english': 'en',
    'espanol latinoamericano': 'es', 'frances': 'fr', 'francais': 'fr',
    'aleman': 'de', 'german': 'de', 'deutsch': 'de', 'italiano': 'it', 'italian': 'it',
    'portugues': 'pt', 'portuguese': 'pt', 'portugues brasileno': 'pt', 'japones': 'ja', 'japanese': 'ja',
    'chino': 'zh-CN', 'chinese': 'zh-CN', 'ruso': 'ru', 'russian': 'ru', 'arabe': 'ar', 'arabic': 'ar',
    'coreano': 'ko', 'korean': 'ko', 'neerlandes': 'nl', 'dutch': 'nl', 'holandes': 'nl', 'polaco': 'pl', 'polish': 'pl', 'turco': 'tr', 'turkish': 'tr',
    'rusia': 'ru', 'japon': 'ja', 'china': 'zh-CN', 'alemania': 'de', 'francia': 'fr', 'italia': 'it',
}
_LANG_ALIASES = {
    **{name: name for name in LANGUAGES},
    'español': 'espanol', 'inglés': 'ingles', 'francés': 'frances', 'alemán': 'aleman',
    'portugués': 'portugues', 'japonés': 'japones', 'árabe': 'arabe',
    'neerlandés': 'neerlandes', 'holandés': 'holandes', 'portugués brasileño': 'portugues brasileno',
    'rusia': 'rusia', 'japón': 'japon', 'china': 'china', 'alemania': 'alemania', 'francia': 'francia', 'italia': 'italia',
}
_LANG_PATTERN = '(?:' + '|'.join(sorted((re.escape(item) for item in _LANG_ALIASES), key=len, reverse=True)) + ')'
_TRANSLATE = re.compile(r'\b(?:traduce|traducir|traduceme|como se dice|translate)\b', re.I)


def _language(value):
    key = normalize(value).strip().casefold()
    return LANGUAGES.get(key)


def _handler(text, context=None):
    normalized = normalize(text)
    # Accept both "traduce X al alemán" and "traduce al alemán X".
    target_match = re.search(rf'(?i)\b(?:al?|a|en|to|into)\s+({_LANG_PATTERN})\b', normalized)
    target = _language(target_match.group(1)) if target_match else None
    source_match = re.search(rf'(?i)\b(?:del?|from)\s+({_LANG_PATTERN})\s+(?:al?|to)\s+{_LANG_PATTERN}\b', normalize(text))
    source = _language(source_match.group(1)) if source_match else None

    content = text.strip()
    content = re.sub(r'^.*?\b(?:traduce|traducir|traduceme|translate)\b', '', content, count=1, flags=re.I)
    if content == text.strip():
        content = re.sub(r'^.*?\bcomo se dice\b', '', content, count=1, flags=re.I)
    # Remove target/source phrases from the original string, preserving accents
    # and the text being translated regardless of where the target was written.
    content = re.sub(rf'(?i)\b(?:del?|from)\s+(?:{_LANG_PATTERN})\s+(?:al?|to)\s+(?:{_LANG_PATTERN})\b', ' ', content)
    if target_match:
        content = re.sub(rf'(?i)\b(?:al?|a|en|to|into)\s+(?:{_LANG_PATTERN})\b', ' ', content)
    content = re.sub(r'\b(?:por favor|please|esto|this text)\b', ' ', content, flags=re.I)
    content = content.strip(' \t\n.,;:¿?¡!"\'')

    if not content:
        return Plan([], text, '¿Qué palabra o texto quieres traducir?')
    if not target:
        if context is not None:
            context.pending = {'kind': 'translate_target', 'text': content, 'source_language': source}
        return Plan([], text, '¿A qué idioma lo traduzco? Por ejemplo, español o inglés.')
    args = {'text': content, 'target_language': target}
    if source:
        args['source_language'] = source
    return Plan([Operation('translation', 'translate', args,
                           description=f'traducir texto al idioma {target}', risk=Risk.MODERATE)], text)


def register(router):
    # Must precede calculator's broad mathematical vocabulary rules.
    router.register('translation', [_TRANSLATE.pattern], _handler, priority=140)
