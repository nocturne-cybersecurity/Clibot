"""Transparent deterministic task family classification."""
import re
RULES={'networking':r'ip|red|internet|conectividad|dns|ruta','filesystem':r'archivo|carpeta|directorio|file|folder','system':r'sistema|kernel|log|memoria','services':r'servicio|service|nginx|ssh','cybersecurity':r'nmap|scan|escane|metasploit'}
def classify(text):
    s=text.casefold(); found=[name for name,pattern in RULES.items() if re.search(pattern,s)]
    return {'intent':found[0] if len(found)==1 else None,'confidence':0.8 if len(found)==1 else 0.0,'ambiguous':len(found)>1}
