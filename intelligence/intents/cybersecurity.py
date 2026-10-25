"""Intents for defensive reconnaissance and evidence-based reports."""
from pathlib import Path
import re
from core.contracts import Operation, Plan, Risk

def _dns(text,context):
    match=re.search(r'(?i)\b(?:dns\s+(?:de\s+)?|(?:resuelve|resolver|consulta|consultar|lookup)\s+(?:el\s+)?dns\s+(?:de\s+)?)([a-z0-9.-]+\.[a-z]{2,})',text)
    if not match:return Plan([],text,'Indica el nombre de host para consultar DNS, por ejemplo «resuelve DNS example.com».')
    return Plan([Operation('cybersecurity','resolve_dns',{'host':match.group(1)},description='consultar DNS del objetivo',risk=Risk.READ_ONLY)],text)

def _scanner(text,context):
    return Plan([Operation('cybersecurity','scanner_status',{},description='consultar disponibilidad de Nmap',risk=Risk.READ_ONLY)],text)

def _whois(text,context):
    target=re.search(r'(?i)(?<![\w:])(?:\d{1,3}\.){3}\d{1,3}(?![\w:])|(?<![\w.-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}(?![\w.-])',text)
    if not target:return Plan([],text,'Indica una dirección IP o un dominio para consultar su registro público.')
    value=target.group(0)
    return Plan([Operation('cybersecurity','whois_lookup',{'target':value},description=f'consultar información RDAP de {value}',risk=Risk.LOW)],text)

def _report(text,context):
    if not context or not context.last_results or not context.last_plan:return Plan([],text,'Primero ejecuta una comprobación para obtener evidencia que incluir en el informe.')
    quoted=re.findall(r'["\']([^"\']+)["\']',text)
    match=next((item for item in quoted if '/' in item),None)
    if not match:
        m=re.search(r'(?<!\w)(?:/[^\s,;]+|\.\.?/[^\s,;]+)',text)
        match=m.group(0).rstrip('.,;') if m else None
    if not match:return Plan([],text,'¿Dónde guardo el informe? Indica una ruta de salida.')
    evidence=[{'request':context.last_plan.request,'status':result.status.value,'success':result.success,'error':result.error_category,'observed':result.data.get('value')} for result in context.last_results]
    fmt='markdown' if match.casefold().endswith(('.md','.markdown')) else 'json'
    op=Operation('cybersecurity','report',{'title':'Informe de observaciones CLIBOT','scope':context.last_plan.request,'findings':evidence,'output':str(Path(match).expanduser()),'format':fmt},description='escribir un informe con evidencia observada',risk=Risk.MODERATE)
    return Plan([op],text)

def register(router):
    router.register('rdap_whois',[r'\b(?:whois|informacion de registro)\b'],_whois,priority=135)
    router.register('cyber_dns',[r'\b(?:resuelve|resolver|consulta|consultar|lookup)\s+(?:el\s+)?dns\b',r'\bdns\s+de\s+[a-z0-9.-]+\.[a-z]{2,}'],_dns,priority=90)
    router.register('nmap_status',[r'\b(?:esta|está|is)\s+(?:instalado|installed)\s+nmap\b',r'\bnmap\s+(?:(?:esta|is)\s+)?(?:instalado|installed|disponible|version|versi[oó]n)\b'],_scanner,priority=90)
    router.register('report_observations',[r'\b(?:genera|generar|crea|crear|make|generate)\s+(?:un\s+)?(?:reporte|informe|report)\b'],_report,priority=80)
