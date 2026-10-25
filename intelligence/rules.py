"""Normalization and configurable alias loading."""
import unicodedata
def normalize(text):return ' '.join(''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c)).split())
def load_aliases(path):
    # Alias configuration is deliberately simple key/value YAML; PyYAML is optional.
    try:
        import yaml
        with open(path) as stream:return yaml.safe_load(stream) or {}
    except ImportError: return {}
