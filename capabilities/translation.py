"""Explicit online translation via Google's public translation endpoint."""
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def translate(text, target_language, source_language='auto', timeout=12):
    """Translate bounded user supplied text; the request is sent to Google."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Escribe el texto que quieres traducir.')
    if len(text) > 5000:
        raise ValueError('Por ahora puedo traducir hasta 5000 caracteres por solicitud.')
    for label, code in (('target_language', target_language), ('source_language', source_language)):
        if not isinstance(code, str) or not code.replace('-', '').isalpha() or len(code) > 8:
            raise ValueError(f'Código de idioma no válido: {label}.')
    query = urlencode({'client': 'gtx', 'sl': source_language, 'tl': target_language, 'dt': 't', 'q': text})
    request = Request(
        f'https://translate.googleapis.com/translate_a/single?{query}',
        headers={'User-Agent': 'LLMAH/0.2 (translation request)'},
    )
    try:
        with urlopen(request, timeout=max(1, min(int(timeout), 20))) as response:
            payload = json.loads(response.read(1_000_001).decode('utf-8'))
    except HTTPError as exc:
        if exc.code != 429:
            raise RuntimeError(f'Google Translate respondió HTTP {exc.code}.') from exc
        return _translate_fallback(text, target_language, source_language, timeout)
    except URLError as exc:
        raise RuntimeError(f'No pude contactar Google Translate: {exc.reason}') from exc
    except (TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError('Google Translate no devolvió una respuesta válida o tardó demasiado.') from exc
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], list):
        raise RuntimeError('La respuesta de Google Translate no tuvo el formato esperado.')
    translated = ''.join(segment[0] for segment in payload[0]
                         if isinstance(segment, list) and segment and isinstance(segment[0], str))
    if not translated:
        raise RuntimeError('Google Translate no devolvió texto traducido.')
    return {
        'translation': translated,
        'source_language': payload[2] if len(payload) > 2 and isinstance(payload[2], str) else source_language,
        'target_language': target_language,
        'provider': 'Google Translate',
    }


def _translate_fallback(text, target_language, source_language, timeout):
    """Try MyMemory when Google's public endpoint rate-limits this client."""
    pair = f"{source_language if source_language != 'auto' else 'autodetect'}|{target_language}"
    query = urlencode({'q': text, 'langpair': pair})
    request = Request(f'https://api.mymemory.translated.net/get?{query}',
                      headers={'User-Agent': 'LLMAH/0.2 translation fallback'})
    try:
        with urlopen(request, timeout=max(1, min(int(timeout), 20))) as response:
            payload = json.loads(response.read(1_000_001).decode('utf-8'))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError('Google Translate limitó la solicitud (HTTP 429) y el servicio alternativo no respondió. Inténtalo más tarde o configura un traductor local.') from exc
    translated = payload.get('responseData', {}).get('translatedText') if isinstance(payload, dict) else None
    if not isinstance(translated, str) or not translated.strip():
        raise RuntimeError('Google Translate limitó la solicitud (HTTP 429) y no se obtuvo una traducción alternativa.')
    return {'translation': translated, 'source_language': source_language,
            'target_language': target_language, 'provider': 'MyMemory (alternativo)'}
