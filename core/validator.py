"""Validate the complete structured plan before execution."""
import ipaddress
import re
from pathlib import Path

from core.contracts import Risk


class ValidationError(ValueError):
    pass


ROOT = Path('/')
# Rutas donde nunca se escribe. Ajusta con ``extra_protected`` si hace falta.
PROTECTED_PATHS = ('/etc', '/usr', '/bin', '/sbin', '/lib', '/lib64', '/boot',
                   '/dev', '/proc', '/sys', '/root', '/var/lib')
# Carpetas sensibles dentro del HOME del usuario.
SENSITIVE_HOME = ('.ssh', '.gnupg', '.aws')
# Operaciones que modifican el sistema de archivos (por nombre).
WRITE_OPS = frozenset({
    'delete', 'move', 'copy', 'create', 'mkdir', 'extract', 'archive', 'report',
    'write', 'append', 'truncate', 'rename', 'symlink',
    'change_permissions', 'change_owner', 'rsync', 'scp', 'format_python',
})
SCAN_TARGET_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:/-]*$')
PORTS_RE = re.compile(r'^[0-9,\-]+$')


class Validator:
    def __init__(self, registry, allowed_targets=(), require_allowlist=False, extra_protected=()):
        self.registry = registry
        self.require_allowlist = bool(require_allowlist)
        self.protected = tuple(Path(p) for p in (*PROTECTED_PATHS, *extra_protected))
        self.allowed_networks = []
        self.allowed_hosts = []
        for item in allowed_targets or ():
            item = str(item).strip().lower()
            if not item:
                continue
            try:
                self.allowed_networks.append(ipaddress.ip_network(item, strict=False))
            except ValueError:
                self.allowed_hosts.append(item)

    # ------------------------------------------------------------------ plan
    def validate(self, plan):
        seen = {x.id for x in plan.operations}
        for op in plan.operations:
            if any(d not in seen for d in op.dependencies):
                raise ValidationError(f'{op.id} depends on a missing operation')
            if op.capability == 'assistant' and op.name == 'capabilities':
                continue
            cap = self.registry.get(op.capability)
            if op.name not in cap.operations:
                raise ValidationError(f'Unsupported operation {op.capability}.{op.name}')
            schema = cap.schemas[op.name]
            props = schema.get('properties', {})
            missing = set(schema.get('required', ())) - set(op.arguments)
            extra = set(op.arguments) - set(props)
            if missing or extra:
                raise ValidationError(
                    f'Invalid arguments for {op.name}: missing {sorted(missing)}, unexpected {sorted(extra)}')
            writes = op.name in WRITE_OPS or bool(schema.get('writes'))
            for key, value in op.arguments.items():
                self._check_type(key, props[key], value)
                if props[key] == 'path' and writes and self._is_protected(value):
                    raise ValidationError(f'Protected system path: {value}')
            if op.capability == 'remote_transfer':
                self._check_remote_transfer(op)
            if op.capability == 'cybersecurity' and op.name == 'scan':
                self._check_scan(op)
        from core.planner import Planner
        Planner().ordered(plan)
        return True

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _check_type(key, kind, value):
        if kind == 'path' and not isinstance(value, str):
            raise ValidationError(f'{key} must be a path (text)')
        if kind == 'integer' and (not isinstance(value, int) or isinstance(value, bool)):
            raise ValidationError(f'{key} must be an integer')
        if kind == 'string' and not isinstance(value, str):
            raise ValidationError(f'{key} must be text')
        if kind == 'boolean' and not isinstance(value, bool):
            raise ValidationError(f'{key} must be a boolean')
        if kind == 'array' and not isinstance(value, list):
            raise ValidationError(f'{key} must be a list')

    def _is_protected(self, value):
        try:
            resolved = Path(value).expanduser().resolve()
        except (OSError, ValueError, RuntimeError) as exc:
            raise ValidationError(f'Invalid path: {exc}') from exc
        if resolved == ROOT:
            return True
        home = Path.home()
        roots = (*self.protected, *(home / name for name in SENSITIVE_HOME))
        return any(resolved == root or root in resolved.parents for root in roots)

    def _check_remote_transfer(self, op):
        """Solo el extremo local de rsync/scp puede caer en una ruta protegida."""
        value = op.arguments.get('destination')
        if isinstance(value, str) and re.match(r'^(?:/|~)', value) and '@' not in value and ':' not in value:
            if self._is_protected(value):
                raise ValidationError(f'Protected system path: {value}')

    def _check_scan(self, op):
        if op.arguments.get('authorized') is not True:
            raise ValidationError('Explicit target authorization is required')
        target = str(op.arguments.get('target', '')).strip()
        if not target or not SCAN_TARGET_RE.match(target):
            raise ValidationError('Invalid scan target')
        ports = op.arguments.get('ports')
        if ports is not None and not PORTS_RE.match(str(ports)):
            raise ValidationError('Invalid port specification')
        if self.require_allowlist and not (self.allowed_networks or self.allowed_hosts):
            raise ValidationError('No hay objetivos de escaneo autorizados en la configuración')
        if (self.allowed_networks or self.allowed_hosts) and not self._target_allowed(target):
            raise ValidationError(f'El objetivo {target} no está en la lista de objetivos autorizados')

    def _target_allowed(self, target):
        target = target.lower()
        try:
            network = ipaddress.ip_network(target, strict=False)
        except ValueError:
            return any(target == host or target.endswith('.' + host) for host in self.allowed_hosts)
        return any(network.version == allowed.version and network.subnet_of(allowed)
                   for allowed in self.allowed_networks)