"""Desktop notifications for long-running operations."""
import subprocess
from pathlib import Path


def send_notification(title: str, message: str, icon: str = None, urgency: str = 'normal'):
    """Send a desktop notification using notify-send."""
    try:
        cmd = ['notify-send']
        if urgency:
            cmd.extend(['-u', urgency])
        if icon:
            cmd.extend(['-i', icon])
        cmd.extend([title, message])
        
        result = subprocess.run(cmd, capture_output=True, timeout=5)
        return {'success': result.returncode == 0}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {'success': False, 'error': 'notify-send not available'}


def notify_completion(operation: str, success: bool = True):
    """Notify when an operation completes."""
    if success:
        send_notification(
            'CLIBOT',
            f'{operation} completado exitosamente',
            urgency='normal'
        )
    else:
        send_notification(
            'CLIBOT',
            f'{operation} falló',
            urgency='critical'
        )


def notify_error(error: str):
    """Notify when an error occurs."""
    send_notification(
        'CLIBOT Error',
        error,
        urgency='critical'
    )


def is_available():
    """Check if desktop notifications are available."""
    try:
        result = subprocess.run(['which', 'notify-send'], capture_output=True, timeout=2)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
