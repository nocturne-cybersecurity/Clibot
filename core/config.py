"""Validated project configuration. JSON is used as a strict YAML 1.2 subset."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class ConfigurationError(ValueError):pass
def load_config():
    try:
        settings=json.loads((ROOT/'config/settings.yaml').read_text())
        policies=json.loads((ROOT/'config/policies.yaml').read_text())
        aliases=json.loads((ROOT/'config/aliases.yaml').read_text())
    except (OSError,json.JSONDecodeError) as exc:raise ConfigurationError(f'Invalid configuration: {exc}') from exc
    if settings.get('language') not in {'es','en'}:raise ConfigurationError('language must be es or en')
    for key in ('output_limit_bytes','default_timeout_seconds'):
        if not isinstance(settings.get(key),int) or settings[key]<=0:raise ConfigurationError(f'{key} must be a positive integer')
    if not isinstance(aliases,dict) or not isinstance(policies.get('risk'),dict):raise ConfigurationError('aliases or risk policy have an invalid structure')
    execution=settings.get('execution',{})
    defaults=execution.get('default_yes_operations',[])
    if not isinstance(defaults,list) or any(not isinstance(item,str) or '.' not in item for item in defaults):raise ConfigurationError('execution.default_yes_operations must be a list of capability.operation names')
    if not isinstance(settings.get('terminal',{}).get('animation',True),bool):raise ConfigurationError('terminal.animation must be a boolean')
    research=settings.get('research',{})
    if not isinstance(research.get('automatic_for_general_questions',True),bool):raise ConfigurationError('research.automatic_for_general_questions must be a boolean')
    if research.get('provider','duckduckgo')!='duckduckgo':raise ConfigurationError('research.provider currently supports only duckduckgo')
    return {'settings':settings,'policies':policies,'aliases':aliases}
