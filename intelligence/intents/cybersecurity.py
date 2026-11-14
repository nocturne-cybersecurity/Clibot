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

def _op(text, cap, name, args=None, desc='', risk=Risk.READ_ONLY):
    return Plan([Operation(cap, name, args or {}, description=desc or name, risk=risk)], text)


def _ip_from(text):
    m = re.search(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])', text)
    return m.group(0) if m else None


def _block_ip(text, context=None):
    ip = _ip_from(text)
    if not ip:
        return Plan([], text, 'Indica la IP a bloquear (solo contra objetivos autorizados).')
    return _op(text, 'cybersecurity', 'block_ip', {'ip': ip, 'permanent': True},
               f'bloquear la IP {ip} en el firewall', Risk.HIGH)


def _unblock_ip(text, context=None):
    ip = _ip_from(text)
    if not ip:
        return Plan([], text, 'Indica la IP a desbloquear.')
    return _op(text, 'cybersecurity', 'unblock_ip', {'ip': ip},
               f'desbloquear la IP {ip}', Risk.HIGH)


def _collect_evidence(text, context=None):
    args = {}
    m = re.search(r'(?<!\w)(?:/[^\s,;]+|\.\.?/[^\s,;]+)', text)
    if m:
        args['output_dir'] = m.group(0).rstrip('.,;')
    h = re.search(r'(\d+)\s*(?:h|horas?|hours?)\b', text)
    if h:
        args['hours'] = int(h.group(1))
    return _op(text, 'cybersecurity', 'collect_evidence', args,
               'recopilar evidencia del incidente', Risk.MODERATE)


def register(router):
    router.register('rdap_whois',[r'\b(?:whois|informacion de registro)\b'],_whois,priority=135)
    router.register('cyber_dns',[r'\b(?:resuelve|resolver|consulta|consultar|lookup)\s+(?:el\s+)?dns\b',r'\bdns\s+de\s+[a-z0-9.-]+\.[a-z]{2,}'],_dns,priority=90)
    router.register('nmap_status',[r'\b(?:esta|está|is)\s+(?:instalado|installed)\s+nmap\b',r'\bnmap\s+(?:(?:esta|is)\s+)?(?:instalado|installed|disponible|version|versi[oó]n)\b'],_scanner,priority=90)
    router.register('report_observations',[r'\b(?:genera|generar|crea|crear|make|generate)\s+(?:un\s+)?(?:reporte|informe|report)\b'],_report,priority=80)
    # Auditoría y defensa local: prioridad alta para no caer en «buscar → web.search».
    router.register('sec_suid',[r'\b(suid|sgid)\b'],lambda t,c=None:_op(t,'security_audit','find_suid_sgid',{},'buscar archivos SUID/SGID',Risk.HIGH),priority=140)
    router.register('sec_rootkit',[r'\brootkits?\b'],lambda t,c=None:_op(t,'security_audit','check_rootkits',{},'revisar rootkits'),priority=140)
    router.register('sec_secrets',[r'^(?!.*\bgithub\b).*\b(secretos|secrets|scan secrets|credenciales expuestas)\b'],lambda t,c=None:_op(t,'security_audit','scan_secrets',{},'buscar secretos en archivos'),priority=140)
    router.register('sec_ssh_audit',[r'\b(ssh audit|auditoria ssh|auditoría ssh)\b'],lambda t,c=None:_op(t,'security_audit','ssh_audit',{},'auditoría de SSH'),priority=140)
    router.register('sec_sast',[r'\b(sast|analisis estatico|análisis estático|codigo vulnerable|código vulnerable)\b'],lambda t,c=None:_op(t,'security_audit','basic_sast',{},'análisis estático de código'),priority=140)
    router.register('sec_failed_logins',[r'\b(intentos? de acceso fallidos?|accesos fallidos|failed logins?|fuerza bruta|brute force|intentos de intrusi[oó]n)\b'],lambda t,c=None:_op(t,'cybersecurity','failed_logins',{},'revisar intentos de acceso fallidos'),priority=140)
    router.register('sec_firewall',[r'\b(postura del firewall|estado del firewall|firewall status)\b'],lambda t,c=None:_op(t,'cybersecurity','firewall_status',{},'postura del firewall'),priority=140)
    router.register('sec_exposed',[r'\b(servicios expuestos|puertos abiertos|puertos escuchando|exposed services|superficie de ataque)\b'],lambda t,c=None:_op(t,'cybersecurity','exposed_services',{},'servicios y puertos expuestos'),priority=140)
    router.register('sec_updates',[r'\b(actualizaciones pendientes|parches pendientes|updates pendientes|vulnerabilidades sin parchar|paquetes desactualizados)\b'],lambda t,c=None:_op(t,'cybersecurity','pending_updates',{},'actualizaciones pendientes'),priority=140)
    router.register('sec_tools',[r'\b(herramientas de seguridad|herramientas (?:de )?pentest|security tools)\b'],lambda t,c=None:_op(t,'cybersecurity','tools_status',{},'herramientas de seguridad disponibles'),priority=140)
    router.register('sec_pass_policy',[r'\b(politica de contrasenas?|politica de passwords?|password policy)\b'],lambda t,c=None:_op(t,'cybersecurity','password_policy',{},'política de contraseñas'),priority=140)
    router.register('sec_ssh_exposure',[r'\b(exposici[oó]n ssh|ssh expuesto|ssh hardening|hardening ssh)\b'],lambda t,c=None:_op(t,'cybersecurity','ssh_exposure',{},'exposición de SSH'),priority=140)
    router.register('sec_block_ip',[r'\b(bloquea|bloquear|block)\b.*\b(ip|direcci[oó]n|address)\b'],_block_ip,priority=140)
    router.register('sec_unblock_ip',[r'\b(desbloquea|desbloquear|unblock)\b.*\b(ip|direcci[oó]n)\b'],_unblock_ip,priority=140)
    router.register('sec_evidence',[r'\b(recopila|recoger|re[uú]ne|collect)\b.*\b(evidencia|evidencias|logs)\b'],_collect_evidence,priority=140)
    router.register('sec_phishing',[r'\b(phishing|concienciaci[oó]n|entrenamiento|capacitaci[oó]n|awareness)\b'],lambda t,c=None:_op(t,'cybersecurity','phishing_awareness',{},'concienciación anti-phishing'),priority=140)
    router.register('sec_pass_hygiene',[r'\b(higiene de contrasenas?|buenas pr[aá]cticas de contrasenas?|password hygiene)\b'],lambda t,c=None:_op(t,'cybersecurity','password_hygiene',{},'higiene de contraseñas'),priority=140)
    router.register('sec_compliance',[r'\b(cumplimiento|compliance|iso ?27001|nist|auditor[ií]a de cumplimiento)\b'],lambda t,c=None:_op(t,'cybersecurity','compliance_checklist',{},'checklist de cumplimiento'),priority=140)
