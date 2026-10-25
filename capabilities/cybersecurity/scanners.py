"""Nmap availability and strict bounded scan invocation."""
import shutil, subprocess, ipaddress
def availability():return {'available':bool(shutil.which('nmap')),'path':shutil.which('nmap')}
def scan(target,ports='1-1000',timeout=120,authorized=False):
    if not authorized:raise PermissionError('Explicit authorization and target scope are required')
    try:ipaddress.ip_network(target,strict=False)
    except ValueError:
        if not target or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-' for c in target):raise ValueError('Invalid target')
    if not __import__('re').fullmatch(r'\d{1,5}(?:-\d{1,5})?(?:,\d{1,5}(?:-\d{1,5})?)*',ports):raise ValueError('Invalid port specification')
    exe=shutil.which('nmap')
    if not exe:raise FileNotFoundError('nmap is not installed; install it explicitly using your distribution package manager')
    p=subprocess.run([exe,'-sT','-sV','--version-light','-oX','-', '-p',ports,target],capture_output=True,text=True,timeout=timeout)
    if p.returncode:raise RuntimeError(p.stderr.strip())
    return {'xml':p.stdout,'stderr':p.stderr}
