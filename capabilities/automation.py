"""Automation capabilities for scripts, cron jobs, and systemd timers."""
import subprocess
import os
from pathlib import Path


def create_script(path, content, executable=True):
    """Create a shell script."""
    script_path = Path(path).expanduser()
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(content)
    if executable:
        script_path.chmod(0o755)
    return {'path': str(script_path), 'executable': executable}


def list_cron_jobs(user=None):
    """List cron jobs for a user."""
    try:
        cmd = ['crontab', '-l']
        if user:
            cmd.extend(['-u', user])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return {'jobs': result.stdout.split('\n'), 'user': user or 'current'}
        return {'jobs': [], 'user': user or 'current', 'message': 'No cron jobs found'}
    except Exception as e:
        return {'error': str(e)}


def add_cron_job(cron_expression, command, user=None):
    """Add a cron job."""
    try:
        existing = list_cron_jobs(user)
        jobs = existing.get('jobs', [])
        if jobs == ['No cron jobs found']:
            jobs = []
        jobs.append(f'{cron_expression} {command}')
        
        cron_content = '\n'.join(jobs)
        
        if user:
            cmd = ['crontab', '-u', user]
        else:
            cmd = ['crontab']
        
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate(cron_content.encode())
        
        if process.returncode == 0:
            return {'success': True, 'cron_expression': cron_expression, 'command': command}
        return {'error': stderr.decode()}
    except Exception as e:
        return {'error': str(e)}


def remove_cron_job(cron_expression, command, user=None):
    """Remove a cron job."""
    try:
        existing = list_cron_jobs(user)
        jobs = existing.get('jobs', [])
        if jobs == ['No cron jobs found']:
            return {'message': 'No cron jobs to remove'}
        
        target = f'{cron_expression} {command}'
        new_jobs = [j for j in jobs if target not in j]
        
        cron_content = '\n'.join(new_jobs)
        
        if user:
            cmd = ['crontab', '-u', user]
        else:
            cmd = ['crontab']
        
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate(cron_content.encode())
        
        if process.returncode == 0:
            return {'success': True, 'removed': target}
        return {'error': stderr.decode()}
    except Exception as e:
        return {'error': str(e)}


def list_systemd_timers():
    """List systemd timers."""
    try:
        result = subprocess.run(['systemctl', 'list-timers', '--all'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            timers = []
            for line in lines[1:]:
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 5:
                    timers.append({
                        'unit': parts[0],
                        'next': parts[1],
                        'left': parts[2],
                        'last': parts[3],
                        'passed': parts[4]
                    })
            return {'timers': timers}
        return {'timers': [], 'message': 'No timers found'}
    except Exception as e:
        return {'error': str(e)}


def create_systemd_timer(name, command, schedule, description=''):
    """Create a systemd timer unit."""
    try:
        timer_content = f"""[Unit]
Description={description or f'Timer for {name}'}

[Timer]
OnCalendar={schedule}
Persistent=true

[Install]
WantedBy=timers.target
"""
        
        service_content = f"""[Unit]
Description={description or f'Service for {name}'}

[Service]
ExecStart={command}
Type=oneshot
"""
        
        systemd_dir = Path.home() / '.config' / 'systemd' / 'user'
        systemd_dir.mkdir(parents=True, exist_ok=True)
        
        timer_path = systemd_dir / f'{name}.timer'
        service_path = systemd_dir / f'{name}.service'
        
        timer_path.write_text(timer_content)
        service_path.write_text(service_content)
        
        return {'timer': str(timer_path), 'service': str(service_path), 'name': name}
    except Exception as e:
        return {'error': str(e)}


def enable_systemd_timer(name):
    """Enable and start a systemd timer."""
    try:
        subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True, timeout=5)
        subprocess.run(['systemctl', '--user', 'enable', f'{name}.timer'], check=True, timeout=5)
        subprocess.run(['systemctl', '--user', 'start', f'{name}.timer'], check=True, timeout=5)
        return {'success': True, 'timer': name}
    except Exception as e:
        return {'error': str(e)}


def disable_systemd_timer(name):
    """Disable and stop a systemd timer."""
    try:
        subprocess.run(['systemctl', '--user', 'stop', f'{name}.timer'], check=True, timeout=5)
        subprocess.run(['systemctl', '--user', 'disable', f'{name}.timer'], check=True, timeout=5)
        return {'success': True, 'timer': name}
    except Exception as e:
        return {'error': str(e)}
