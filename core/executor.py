"""Validated operation execution with explicit confirmation and result capture."""
import json
import queue
import threading
import time
from datetime import datetime, timezone

from core.contracts import Result, Status
from core.planner import Planner
from core.verifier import Verifier
from security.redaction import redact, redact_data

RISK_ORDER = {'read_only': 0, 'low': 1, 'moderate': 2, 'high': 3, 'destructive': 4}


class Executor:
    def __init__(self, registry, confirm=input, default_yes_operations=(),
                 confirmation_policy=None, auto_approve=None):
        """``auto_approve(op) -> bool`` solo puede saltarse la confirmación de
        operaciones *moderate*; high y destructive siempre se preguntan."""
        self.registry = registry
        self.confirm = confirm
        self.auto_approve = auto_approve
        self.verifier = Verifier()
        self.default_yes_operations = set(default_yes_operations)
        if confirmation_policy and any(isinstance(v, dict) for v in confirmation_policy.values()):
            confirmation_policy = {
                key: bool(value.get('confirmation_required', True)) if isinstance(value, dict) else bool(value)
                for key, value in confirmation_policy.items()}
        self.confirmation_policy = confirmation_policy or {
            'read_only': False, 'low': False, 'moderate': True, 'high': True, 'destructive': True}

    # --------------------------------------------------------------- public
    def execute(self, plan):
        results = {}
        out = []
        for op in Planner().ordered(plan):
            if any(not results[d].success for d in op.dependencies):
                r = Result(op.id, False, status=Status.SKIPPED, error_category='dependency_failed',
                           stderr='A prerequisite operation failed')
            else:
                r = self._execute_one(op)
            results[op.id] = r
            out.append(r)
        return out

    # ------------------------------------------------------------- internals
    def _risk(self, op):
        if op.capability == 'assistant':
            return op.risk.value
        registered = self.registry.get(op.capability).risks.get(op.name, op.risk.value)
        return max((op.risk.value, registered), key=lambda value: RISK_ORDER.get(value, 0))

    def _execute_one(self, op):
        risk = self._risk(op)
        needs_confirmation = risk in ('moderate', 'high', 'destructive') and self.confirmation_policy.get(risk, True)
        if needs_confirmation and risk == 'moderate' and self.auto_approve and self.auto_approve(op):
            needs_confirmation = False
        if not needs_confirmation:
            return self._run(op)
        default_yes = f'{op.capability}.{op.name}' in self.default_yes_operations
        try:
            answer = self.confirm(self._prompt(op, risk, default_yes)).strip().lower()
            approved = answer in ('y', 'yes', 'si', 'sí') or (not answer and default_yes)
        except (EOFError, KeyboardInterrupt):
            approved = False
        if not approved:
            return Result(op.id, False, status=Status.DENIED, error_category='confirmation_declined',
                          stderr='Confirmation declined')
        return self._run(op)

    @staticmethod
    def _prompt(op, risk, default_yes):
        """Muestra lo que *realmente* se va a ejecutar, no solo la descripción
        (que puede venir de un modelo y no es de fiar)."""
        args = redact(json.dumps(op.arguments, ensure_ascii=False, default=str))
        if len(args) > 200:
            args = args[:197] + '...'
        description = (op.description or '').replace('\n', ' ')[:120]
        suffix = '[Y/n] ' if default_yes else '[y/N] '
        return f'Confirm {op.capability}.{op.name} {args} — {description} ({risk})? {suffix}'

    def _invoke(self, op):
        """Invoca la capacidad con un límite de tiempo.

        Si se agota, se devuelve el control al asistente; el hilo (daemon) puede
        seguir un rato en segundo plano, así que las capacidades que lanzan
        subprocesos deben seguir aplicando su propio timeout.
        """
        if not op.timeout or op.timeout <= 0:
            return self.registry.invoke(op.capability, op.name, op.arguments)
        box = queue.Queue(maxsize=1)

        def worker():
            try:
                box.put((True, self.registry.invoke(op.capability, op.name, op.arguments)))
            except BaseException as exc:  # noqa: BLE001 - se reenvía al hilo principal
                box.put((False, exc))

        threading.Thread(target=worker, daemon=True).start()
        try:
            ok, value = box.get(timeout=op.timeout)
        except queue.Empty:
            raise TimeoutError(f'{op.capability}.{op.name} superó el límite de {op.timeout:g}s') from None
        if ok:
            return value
        raise value

    def _run(self, op):
        start = time.monotonic()
        result = Result(op.id, False)
        try:
            value = redact_data(self._invoke(op))
            result.data = {'value': value}
            result.stdout = redact(str(value))[:1_000_000]
            if isinstance(value, dict) and value.get('available') is False and op.name != 'scanner_status':
                result.status = Status.FAILED
                result.exit_code = 1
                result.error_category = 'permission_denied'
                result.stderr = redact(value.get('reason', 'This information is unavailable'))
            elif isinstance(value, dict) and isinstance(value.get('exit_code'), int) and value['exit_code'] != 0:
                result.status = Status.FAILED
                result.exit_code = value['exit_code']
                result.error_category = 'process_failure'
                result.stderr = redact(value.get('stderr') or value.get('stdout')
                                       or f"Command exited {value['exit_code']}")
            else:
                result.success = True
                result.status = Status.SUCCEEDED
                result.exit_code = 0
                result.verified = True
        except FileNotFoundError as e:
            result.error_category = 'missing_dependency'
            result.stderr = redact(str(e))
        except PermissionError as e:
            result.error_category = 'permission_denied'
            result.stderr = redact(str(e))
        except (TimeoutError, __import__('subprocess').TimeoutExpired) as e:
            result.error_category = 'timeout'
            result.stderr = redact(str(e))
        except Exception as e:  # noqa: BLE001
            result.error_category = 'operation_failed'
            result.stderr = redact(str(e))
            result.exit_code = 1
        if result.success and op.capability == 'filesystem' and not self.verifier.verify(op, result):
            # La operación dijo "ok" pero el resultado no se observa en disco.
            result.success = False
            result.verified = False
            result.status = Status.UNVERIFIED
            result.error_category = 'unverified'
            result.stderr = 'No pude comprobar que el cambio se aplicara en el sistema de archivos.'
        elif not result.success:
            result.status = Status.FAILED
        result.duration = time.monotonic() - start
        result.ended_at = datetime.now(timezone.utc).isoformat()
        return result