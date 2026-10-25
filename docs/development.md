# Development

Requires Python 3.11+. Create an isolated environment and install editable package plus pytest with `python -m pip install -e '.[dev]'`. Run the suite with `python -m pytest`. The standard-library runtime has no model or network dependency.

Configuration files use JSON syntax, which is also a strict YAML 1.2 subset; the standard-library JSON parser validates them without runtime dependencies.

## Optional language model

LLMAH needs no model for normal operations. If a local Ollama server and at least one model are already available, it detects them through the loopback API. To select a specific installed model, set `LLMAH_LLM_PROVIDER=ollama` and `LLMAH_LLM_MODEL` to the exact name shown by `ollama list`. No model is downloaded by LLMAH. The provider adapter uses Python's standard library.

OpenAI-compatible services are opt-in through `LLMAH_LLM_PROVIDER=openai` plus `LLM_API_KEY`, or through `LLMAH_LLM_PROVIDER=openai_compatible`, `LLMAH_LLM_BASE_URL`, and `LLM_API_KEY`. Those services receive unrecognized requests and a short redacted recent-context summary. Keep credentials in environment variables rather than tracked project files. Model-generated operations still require the ordinary capability schemas and risk checks.

## Add a natural-language feature

1. Add a focused module under `capabilities/plugins/` with `register(registry)`.
2. Register its callable, argument schema, and risk in that function.
3. Add a small intent plugin under `intelligence/intents/`; `Parser` discovers it automatically.
4. Test entity extraction, validation, and the operation against a temporary resource or mock.

Example plugin:

Capability plugin (`capabilities/plugins/greeting.py`):

```python
from discovery.capability_registry import Capability

def uptime():
    with open("/proc/uptime") as stream:
        return float(stream.read().split()[0])

def register(registry):
    registry.register(Capability(
        name="example", description="Example local facts",
        operations={"uptime": uptime},
        schemas={"uptime": {"properties": {}}}, risks={"uptime": "read_only"},
    ))
```

Intent plugin (`intelligence/intents/example.py`):

```python
from core.contracts import Operation, Plan

def handle(text, context):
    host = text.split()[-1]
    return Plan([Operation("networking", "resolve", {"host": host})], text)

def register(router):
    router.register("resolve_host", [r"\b(resuelve|resolve)\s+dns\b"], handle)
```

Both plugin directories load modules that define `register(...)`; no change to `core/parser.py` or the central capability list is needed. Intent patterns run against accent/case-normalized text, and handlers receive the original text to preserve paths and identifiers. Intent plugins return a structured `Plan` or `None`; normal schema and risk validation still applies. Keep patterns narrow so conversation does not trigger system actions. Keep subprocess arguments separate, bound time and output, and report absent tools clearly. A future local model may suggest a structured plan, but the same validator must approve it and the model must never execute commands directly.
