"""Small bounded HTML search for showing web results inside the terminal."""
from html.parser import HTMLParser
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse, parse_qs
from urllib.request import Request, urlopen


class _Results(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self._title = None
        self._snippet = None
        self._text_target = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get('class', '').split()
        if tag == 'a' and 'result__a' in classes:
            self._title = {'title': '', 'url': attrs.get('href', '')}
            self._text_target = self._title
        elif tag in {'a', 'div'} and 'result__snippet' in classes and self.rows:
            self._snippet = {'snippet': ''}
            self._text_target = self._snippet

    def handle_data(self, data):
        if self._text_target is not None:
            key = 'title' if 'title' in self._text_target else 'snippet'
            self._text_target[key] += data

    def handle_endtag(self, tag):
        if self._title is not None and tag == 'a':
            title = self._title['title'].strip()
            if title and self._title['url']:
                self.rows.append({**self._title, 'snippet': ''})
            self._title = None
            self._text_target = None
        elif self._snippet is not None and tag in {'a', 'div'}:
            if self.rows:
                self.rows[-1]['snippet'] = self._snippet['snippet'].strip()
            self._snippet = None
            self._text_target = None


class _BingResults(HTMLParser):
    """Read result cards from Bing's lightweight HTML page."""
    def __init__(self):
        super().__init__()
        self.rows = []
        self.card_depth = 0
        self.in_card = False
        self.in_heading = False
        self.in_caption = False
        self.target = None
        self.row = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get('class', '').split()
        if tag == 'li' and 'b_algo' in classes:
            self.in_card = True
            self.card_depth = 1
            self.row = {'title': '', 'url': '', 'snippet': ''}
            return
        if not self.in_card:
            return
        if tag == 'li': self.card_depth += 1
        if tag == 'h2': self.in_heading = True
        if tag == 'div' and 'b_caption' in classes: self.in_caption = True
        if tag == 'a' and self.in_heading:
            self.row['url'] = attrs.get('href', '')
            self.target = 'title'
        elif tag == 'p' and self.in_caption:
            self.target = 'snippet'

    def handle_data(self, data):
        if self.in_card and self.target:
            self.row[self.target] += data

    def handle_endtag(self, tag):
        if not self.in_card: return
        if tag == 'a' and self.target == 'title': self.target = None
        elif tag == 'p' and self.target == 'snippet': self.target = None
        elif tag == 'h2': self.in_heading = False
        elif tag == 'div' and self.in_caption: self.in_caption = False
        elif tag == 'li':
            self.card_depth -= 1
            if self.card_depth <= 0:
                if self.row.get('title') and self.row.get('url'):
                    self.rows.append(self.row)
                self.row = None
                self.in_card = False


def _clean(value, limit):
    """Strip terminal control characters from untrusted remote result text."""
    value = ''.join(char for char in value if unicodedata.category(char) not in {'Cc', 'Cf'} or char in '\t\n')
    return ' '.join(value.split())[:limit]
def search(query, limit=5, timeout=5):
    """Return public search results as title/url/snippet rows, without a GUI.

    Tries two lightweight HTML providers sequentially. A provider can return
    JavaScript/challenge markup, so an empty parse triggers the next provider.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError('Escribe el tema que quieres buscar.')
    if len(query) > 500:
        raise ValueError('La búsqueda admite hasta 500 caracteres.')
    count = max(1, min(int(limit), 10))
    providers = (
        ('DuckDuckGo HTML', 'https://html.duckduckgo.com/html/?' + urlencode({'q': query}), _Results, 'https://duckduckgo.com'),
        ('Bing HTML', 'https://www.bing.com/search?' + urlencode({'q': query}), _BingResults, 'https://www.bing.com'),
    )
    failures = []
    for provider, url, parser_type, base_url in providers:
        request = Request(url, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36'})
        try:
            with urlopen(request, timeout=max(1, min(int(timeout), 10))) as response:
                html = response.read(2_000_001)
            if len(html) > 2_000_000:
                failures.append(f'{provider}: respuesta mayor de 2 MB')
                continue
            parser = parser_type()
            parser.feed(html.decode('utf-8', errors='replace'))
            rows = []
            for row in parser.rows:
                result_url = row['url']
                if result_url.startswith('//') or result_url.startswith('/'):
                    result_url = urljoin(base_url, result_url)
                    parsed = urlparse(result_url)
                    redirect = parse_qs(parsed.query).get('uddg', [])
                    if redirect and parsed.hostname and parsed.hostname.endswith('duckduckgo.com'):
                        result_url = redirect[0]
                if not result_url.startswith(('https://', 'http://')):
                    continue
                parsed_result=urlparse(result_url)
                query_params=parse_qs(parsed_result.query)
                if ((parsed_result.hostname or '').endswith('duckduckgo.com') and
                    (parsed_result.path in {'/y.js','/ac/'} or any(key.startswith('ad_') for key in query_params))):
                    continue
                if (parsed_result.hostname or '').endswith('bing.com') and parsed_result.path.startswith('/aclick'):
                    continue
                rows.append({'title': _clean(row['title'], 300), 'url': _clean(result_url, 1000),
                             'snippet': _clean(row['snippet'], 1200)})
                if len(rows) >= count: break
            if rows:
                return {'query': query, 'provider': provider, 'results': rows}
            failures.append(f'{provider}: no devolvió resultados legibles')
        except HTTPError as exc:
            failures.append(f'{provider}: HTTP {exc.code}')
        except URLError as exc:
            failures.append(f'{provider}: {exc.reason}')
        except TimeoutError:
            failures.append(f'{provider}: tiempo de espera agotado')
    detail = '; '.join(failures)
    raise RuntimeError(f'No pude obtener resultados de los buscadores ({detail}).')
