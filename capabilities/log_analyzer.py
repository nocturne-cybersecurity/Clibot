"""Automatic log error detection and diagnosis."""
import re, subprocess, shutil
from pathlib import Path
from datetime import datetime, timedelta

ERROR_PATTERNS = {
    'oom_killed': re.compile(r'Out of memory|OOM killer|killed process', re.IGNORECASE),
    'disk_full': re.compile(r'No space left on device|disk full', re.IGNORECASE),
    'connection_refused': re.compile(r'Connection refused|ECONNREFUSED', re.IGNORECASE),
    'permission_denied': re.compile(r'Permission denied|EACCES', re.IGNORECASE),
    'segmentation_fault': re.compile(r'Segmentation fault|SIGSEGV', re.IGNORECASE),
    'kernel_panic': re.compile(r'Kernel panic|panic:', re.IGNORECASE),
    'service_crash': re.compile(r'failed to start|exited with status|crashed', re.IGNORECASE),
    'network_unreachable': re.compile(r'Network is unreachable|ENETUNREACH', re.IGNORECASE),
    'timeout': re.compile(r'timeout|timed out', re.IGNORECASE),
    'corruption': re.compile(r'corrupt|checksum|inconsistent', re.IGNORECASE),
}

SERVICE_PATTERNS = {
    'nginx': re.compile(r'nginx', re.IGNORECASE),
    'apache': re.compile(r'apache|httpd', re.IGNORECASE),
    'ssh': re.compile(r'sshd|sshd', re.IGNORECASE),
    'mysql': re.compile(r'mysql|mariadb', re.IGNORECASE),
    'postgresql': re.compile(r'postgresql|postgres', re.IGNORECASE),
    'docker': re.compile(r'docker', re.IGNORECASE),
}

def analyze_journalctl(lines=1000, since=None, unit=None):
    """Analyze journalctl logs for common errors and patterns."""
    if not shutil.which('journalctl'):
        raise FileNotFoundError('journalctl is not available')
    
    cmd = ['journalctl', '-n', str(lines), '--no-pager']
    if since:
        cmd.extend(['--since', since])
    if unit:
        cmd.extend(['-u', unit])
    
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        log_content = p.stdout
    except subprocess.TimeoutExpired:
        raise RuntimeError('journalctl timed out')
    
    findings = []
    errors_by_type = {}
    services_with_errors = set()
    
    for line in log_content.splitlines():
        for error_type, pattern in ERROR_PATTERNS.items():
            if pattern.search(line):
                if error_type not in errors_by_type:
                    errors_by_type[error_type] = []
                errors_by_type[error_type].append(line[:500])
                
                for service_name, service_pattern in SERVICE_PATTERNS.items():
                    if service_pattern.search(line):
                        services_with_errors.add(service_name)
                break
    
    for error_type, occurrences in errors_by_type.items():
        findings.append({
            'type': error_type,
            'count': len(occurrences),
            'sample': occurrences[0] if occurrences else None,
            'severity': _severity_for_error(error_type)
        })
    
    return {
        'total_errors': sum(len(v) for v in errors_by_type.values()),
        'errors': findings,
        'findings': sorted(findings, key=lambda x: x['count'], reverse=True),
        'affected_services': sorted(services_with_errors),
        'recommendations': _generate_recommendations(errors_by_type.keys())
    }

def analyze_syslog(path='/var/log/syslog', lines=1000):
    """Analyze traditional syslog file for errors."""
    log_path = Path(path)
    if not log_path.exists():
        raise FileNotFoundError(f'{path} does not exist')
    
    try:
        content = log_path.read_text(errors='replace')
    except PermissionError:
        raise PermissionError(f'Cannot read {path} without sufficient permissions')
    
    lines_list = content.splitlines()[-lines:]
    
    findings = []
    errors_by_type = {}
    
    for line in lines_list:
        for error_type, pattern in ERROR_PATTERNS.items():
            if pattern.search(line):
                if error_type not in errors_by_type:
                    errors_by_type[error_type] = []
                errors_by_type[error_type].append(line[:500])
                break
    
    for error_type, occurrences in errors_by_type.items():
        findings.append({
            'type': error_type,
            'count': len(occurrences),
            'sample': occurrences[0] if occurrences else None,
            'severity': _severity_for_error(error_type)
        })
    
    return {
        'source': str(path),
        'total_errors': sum(len(v) for v in errors_by_type.values()),
        'findings': sorted(findings, key=lambda x: x['count'], reverse=True),
        'recommendations': _generate_recommendations(errors_by_type.keys())
    }

def diagnose_service(service_name):
    """Diagnose a specific systemd service."""
    if not shutil.which('systemctl'):
        raise FileNotFoundError('systemctl is not available')
    
    result = {
        'service': service_name,
        'status': None,
        'logs': None,
        'errors': []
    }
    
    try:
        p = subprocess.run(['systemctl', 'status', service_name, '--no-pager'], 
                          capture_output=True, text=True, timeout=10)
        result['status'] = p.stdout
    except subprocess.TimeoutExpired:
        result['status'] = 'Command timed out'
    
    try:
        log_result = analyze_journalctl(lines=200, unit=service_name)
        result['logs'] = log_result
        result['errors'] = log_result['findings']
    except Exception as e:
        result['logs'] = {'error': str(e)}
    
    return result

def _severity_for_error(error_type):
    """Map error types to severity levels."""
    severity_map = {
        'kernel_panic': 'critical',
        'oom_killed': 'high',
        'disk_full': 'high',
        'segmentation_fault': 'high',
        'service_crash': 'high',
        'corruption': 'high',
        'connection_refused': 'medium',
        'permission_denied': 'medium',
        'network_unreachable': 'medium',
        'timeout': 'low',
    }
    return severity_map.get(error_type, 'low')

def _generate_recommendations(error_types):
    """Generate actionable recommendations based on error types."""
    recommendations = []
    
    if 'oom_killed' in error_types:
        recommendations.append('Consider increasing swap space or adding more RAM')
        recommendations.append('Check for memory leaks in running processes')
    
    if 'disk_full' in error_types:
        recommendations.append('Clean up old log files and temporary files')
        recommendations.append('Check disk usage with: df -h')
    
    if 'connection_refused' in error_types or 'network_unreachable' in error_types:
        recommendations.append('Verify network connectivity and firewall rules')
        recommendations.append('Check if required services are running')
    
    if 'permission_denied' in error_types:
        recommendations.append('Review file and directory permissions')
        recommendations.append('Check SELinux/AppArmor contexts if applicable')
    
    if 'service_crash' in error_types:
        recommendations.append('Review service logs for crash details')
        recommendations.append('Check service configuration files')
    
    if 'kernel_panic' in error_types:
        recommendations.append('Check hardware (memory, disk) for failures')
        recommendations.append('Review recent kernel updates or driver changes')
    
    return recommendations
