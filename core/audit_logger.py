"""Command audit logging for security and accountability."""
import json
import os
from pathlib import Path
from datetime import datetime
from core.contracts import Plan, Operation, Result


class AuditLogger:
    """Log all commands executed through CLIBOT."""

    def __init__(self, log_dir=None):
        """Initialize audit logger."""
        if log_dir is None:
            log_dir = Path.home() / '.clibot' / 'logs'
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_log_file = self._get_current_log_file()

    def _serialize_for_log(self, obj):
        """Convert Plan, Operation, and Result objects to dicts for JSON serialization."""
        if isinstance(obj, dict):
            return {k: self._serialize_for_log(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_for_log(item) for item in obj]
        elif isinstance(obj, Plan):
            return {
                'operations': [self._serialize_for_log(op) for op in obj.operations],
                'request': obj.request,
                'clarification': obj.clarification,
                'message': obj.message,
                'unrecognized': obj.unrecognized,
                'reformat_last': obj.reformat_last,
            }
        elif isinstance(obj, Operation):
            return {
                'capability': obj.capability,
                'name': obj.name,
                'arguments': obj.arguments,
                'description': obj.description,
                'dependencies': obj.dependencies,
                'risk': obj.risk.value,
                'requires_privilege': obj.requires_privilege,
                'timeout': obj.timeout,
                'id': obj.id,
            }
        elif isinstance(obj, Result):
            return {
                'operation_id': obj.operation_id,
                'success': obj.success,
                'stdout': obj.stdout,
                'stderr': obj.stderr,
                'exit_code': obj.exit_code,
                'started_at': obj.started_at,
                'ended_at': obj.ended_at,
                'duration': obj.duration,
                'data': obj.data,
                'error_category': obj.error_category,
                'verified': obj.verified,
                'status': obj.status.value,
            }
        else:
            return obj

    def _get_current_log_file(self):
        """Get the log file for the current date."""
        date_str = datetime.now().strftime('%Y-%m-%d')
        return self.log_dir / f'audit_{date_str}.jsonl'

    def log_command(self, request, response, operations=None):
        """Log a command execution."""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'request': request,
            'response': self._serialize_for_log(response),
            'operations': operations or [],
            'success': not response.get('error')
        }

        # Write to current log file
        with open(self.current_log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

    def get_logs(self, date=None, limit=100):
        """Get logs for a specific date or current date."""
        if date:
            log_file = self.log_dir / f'audit_{date}.jsonl'
        else:
            log_file = self.current_log_file
        
        if not log_file.exists():
            return []
        
        logs = []
        with open(log_file, 'r') as f:
            for line in f:
                if line.strip():
                    logs.append(json.loads(line))
        
        return logs[-limit:] if limit else logs

    def search_logs(self, query, date=None):
        """Search logs for a query."""
        logs = self.get_logs(date)
        results = []
        
        for log in logs:
            if query.lower() in log.get('request', '').lower():
                results.append(log)
        
        return results

    def get_stats(self, date=None):
        """Get statistics for logs."""
        logs = self.get_logs(date)
        
        total = len(logs)
        successful = sum(1 for log in logs if log.get('success'))
        failed = total - successful
        
        # Count operations
        operation_counts = {}
        for log in logs:
            for op in log.get('operations', []):
                op_name = f"{op.get('capability')}.{op.get('name')}"
                operation_counts[op_name] = operation_counts.get(op_name, 0) + 1
        
        return {
            'total': total,
            'successful': successful,
            'failed': failed,
            'operations': operation_counts
        }

    def clear_old_logs(self, days=30):
        """Clear logs older than specified days."""
        cutoff = datetime.now().timestamp() - (days * 86400)
        
        for log_file in self.log_dir.glob('audit_*.jsonl'):
            if log_file.stat().st_mtime < cutoff:
                log_file.unlink()
        
        return {'cleared': True, 'days': days}
