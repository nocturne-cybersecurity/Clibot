# Development

Requires Python 3.11+. Create an isolated environment and install editable package plus pytest with `python -m pip install -e '.[dev]'`. Run the suite with `python -m pytest`. The standard-library runtime has no model or network dependency.

Configuration files use JSON syntax, which is also a strict YAML 1.2 subset; the standard-library JSON parser validates them without runtime dependencies.

## Optional language model

LLMAH needs no model for local system operations. If a local Ollama server and at least one model are available, it detects them through the loopback API and uses them for open-ended answers and ambiguous requests. To select a specific installed model, set `CLIBOT_LLM_PROVIDER=ollama` and `CLIBOT_LLM_MODEL` to the exact name shown by `ollama list`. `CLIBOT_USE_LLM=false` disables model use for a session. No model is downloaded implicitly. The provider adapter uses Python's standard library. Ollama requests use a 10-second socket timeout; this is not a strict end-to-end response deadline. Smaller models such as Qwen2.5 1.5B or 0.5B have fewer parameters than Phi-3 mini, but actual latency and answer quality depend on the machine, quantization, and prompt. These are candidates to benchmark locally, not guaranteed speed recommendations.

In the interactive CLI, `/models` lists installed models and opens Ollama's online catalog. Choose a result and variant to download it; type `buscar <texto>` to filter the catalog. `/models search <texto>` displays matching results, `/models pull <name[:tag]>` downloads directly, and `/models use <name>` switches to an installed model. The online catalog requires Internet; when unavailable, installed-model management and direct pulls still work if the local Ollama server is reachable.

Requests to create or explain code are routed to the configured model when available; the assistant does not silently substitute a built-in code template. Explicit requests to find existing examples on Stack Overflow or GitHub use their respective integrations and retain attribution. A plain request for an example does not trigger an external search unless a source is named.

OpenAI-compatible services are opt-in through `CLIBOT_LLM_PROVIDER=openai` plus `LLM_API_KEY`, or through `CLIBOT_LLM_PROVIDER=openai_compatible`, `CLIBOT_LLM_BASE_URL`, and `LLM_API_KEY`. Those services receive unrecognized requests and a short redacted recent-context summary. Keep credentials in environment variables rather than tracked project files. Model-generated operations still require the ordinary capability schemas and risk checks.

Stack Overflow code examples are fetched from the public Stack Exchange API and rendered with answer attribution and links. GitHub code search uses the authenticated code-search API and requires `GITHUB_TOKEN`; without it, the assistant reports that requirement instead of falling back to an unrelated search.

## Git

Git requests support local repository initialization, cloning HTTP(S)/SSH remotes, staging files, commits, status/branches/diff/log, stash, checkout, pull, push, merge, and rebase. For example, create a repository in a named directory, clone a repository URL, stage files with `git add`, then commit with a message. Commit records already-staged changes. Pull, push, checkout, merge, and rebase require confirmation; init, clone, add, and commit follow the normal configured risk policy. Git errors are returned instead of being reported as successful operations.

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
