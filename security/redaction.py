"""Best-effort removal of common credential formats from output and logs."""
import re
_PATTERNS=[(re.compile(r'(?i)(password|passwd|token|api[_-]?key|secret)\s*([=:])\s*([^\s,;]+)'),r'\1\2[REDACTED]'),(re.compile(r'(?i)bearer\s+[A-Za-z0-9._~+/=-]+'), 'Bearer [REDACTED]'),(re.compile(r'-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----',re.S),'[PRIVATE KEY REDACTED]')]
def redact(value):
    text=str(value)
    for pattern,replacement in _PATTERNS:text=pattern.sub(replacement,text)
    return text

def redact_data(value):
    """Recursively redact common secret-keyed values and string contents."""
    if isinstance(value,dict):
        return {redact(k):('[REDACTED]' if any(word in k.casefold() for word in ('password','passwd','token','secret','api_key','private_key')) else redact_data(v)) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [redact_data(v) for v in value]
    return redact(value) if isinstance(value,str) else value
