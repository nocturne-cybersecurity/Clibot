"""Structured subprocess invocation, shell disabled by default."""
from dataclasses import dataclass, field
from typing import Mapping
@dataclass
class Command:
    executable: str
    arguments: list[str] = field(default_factory=list)
    cwd: str | None = None
    environment: Mapping[str,str] = field(default_factory=dict)
    timeout: float = 20.0
    stdin: str | None = None
    output_limit: int = 1_000_000
