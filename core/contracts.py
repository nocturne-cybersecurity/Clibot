"""Shared contracts for plans, operations, and results."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid


class Risk(str, Enum):
    READ_ONLY = "read_only"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    DESTRUCTIVE = "destructive"


class Status(str, Enum):
    PLANNED = "planned"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    UNVERIFIED = "unverified"


@dataclass
class Operation:
    capability: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    dependencies: list[str] = field(default_factory=list)
    risk: Risk = Risk.READ_ONLY
    requires_privilege: bool = False
    timeout: float = 20.0  # segundos; <= 0 desactiva el límite
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


@dataclass
class Plan:
    """Resultado de interpretar una petición.

    Los tres primeros campos conservan el orden original para no romper
    llamadas posicionales como ``Plan([], texto, 'pregunta')``.
    """
    operations: list[Operation]
    request: str = ""
    clarification: str | None = None
    message: str | None = None        # respuesta directa sin operaciones
    unrecognized: bool = False        # el parser no entendió la petición
    reformat_last: bool = False       # volver a presentar el último resultado


@dataclass
class Result:
    operation_id: str
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ended_at: str = ""
    duration: float = 0.0
    data: dict[str, Any] = field(default_factory=dict)
    error_category: str | None = None
    verified: bool | None = None
    status: Status = Status.SUCCEEDED