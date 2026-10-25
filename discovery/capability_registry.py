"""Registry of implemented, inspectable operations."""
from dataclasses import dataclass
from typing import Callable, Any


@dataclass
class Capability:
    name: str
    description: str
    operations: dict[str, Callable[..., Any]]
    schemas: dict[str, dict[str, Any]]
    risks: dict[str, str]
    docs: str = ""


class CapabilityRegistry:
    def __init__(self):
        self._items: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        if capability.name in self._items:
            raise ValueError(f"Capability already registered: {capability.name}")
        if set(capability.operations) != set(capability.schemas):
            raise ValueError("Each operation must have a schema")
        self._items[capability.name] = capability

    def get(self, name: str) -> Capability:
        try:
            return self._items[name]
        except KeyError as exc:
            raise KeyError(f"Unknown capability: {name}") from exc

    def list(self) -> list[Capability]:
        return sorted(self._items.values(), key=lambda c: c.name)

    def invoke(self, capability: str, operation: str, arguments: dict[str, Any]):
        cap = self.get(capability)
        if operation not in cap.operations:
            raise KeyError(f"Unknown operation: {capability}.{operation}")
        schema = cap.schemas[operation]
        missing = [key for key in schema.get("required", []) if key not in arguments]
        extra = set(arguments) - set(schema.get("properties", {}))
        if missing or extra:
            raise ValueError(f"Invalid arguments; missing={missing}, unexpected={sorted(extra)}")
        for key, value in arguments.items():
            expected = schema.get("properties", {}).get(key)
            if expected == "path" and not isinstance(value, (str, __import__('pathlib').Path)):
                raise ValueError(f"{key} must be a path")
            if expected == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
                raise ValueError(f"{key} must be an integer")
            if expected == "string" and not isinstance(value, str):
                raise ValueError(f"{key} must be a string")
        return cap.operations[operation](**arguments)


registry = CapabilityRegistry()

