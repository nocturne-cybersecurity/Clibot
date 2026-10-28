# CLIBOT v2.0 - Intelligent Terminal Assistant Architecture

## Overview

CLIBOT v2.0 is an intelligent terminal assistant that combines deterministic rule-based execution with optional LLM-powered reasoning. It can understand natural language, reason about tasks, use real tools, consult documentation, and produce professional technical solutions.

## Architecture Components

### 1. Agent Cycle (`core/agent_cycle.py`)

Implements the reasoning cycle: **Interpret → Plan → Execute → Verify → Respond**

- **Intent Classification**: Classifies user requests into semantic categories (conversation, explanation, calculation, system info, processes, files, network, development, debugging, Git, GitHub, Stack Overflow, etc.)
- **Plan Generation**: Creates execution plans based on intent, selecting appropriate tools
- **Tool Execution**: Executes tools with safety checks (iteration limits, time limits, output size limits)
- **Response Synthesis**: Formats results into human-readable responses with source attribution

### 2. System Prompt (`intelligence/system_prompt.py`)

Centralized, versioned system prompt that defines:
- Fundamental principles (interpret by meaning, not keywords)
- Tool usage guidelines (when to use tools vs. model knowledge)
- Security and privacy rules (never expose secrets, treat web content as untrusted)
- Communication style (direct, professional, honest)
- Context management (maintain session context, distinguish temporary vs. persistent data)
- Offline mode behavior (use local tools, explain limitations honestly)
- Source citation requirements (show source, title, URL, relevance, limitations)

### 3. Model Provider Layer (`intelligence/llm_integration.py`)

Abstraction layer supporting multiple LLM providers:
- **Ollama**: Local models with auto-detection
- **OpenAI-compatible**: Any API following OpenAI's interface
- **Configuration**: Via environment variables or config file
- **Fallback**: Graceful degradation when model unavailable

### 4. Context Management (`core/context.py`)

Enhanced conversation context with:
- **Session history**: Recent requests and responses
- **Entities**: User-provided facts (e.g., "My project folder is Fenrir")
- **Preferences**: User settings for the session
- **Task context**: Context specific to current task
- **Summary**: Method to get context overview

### 5. Tool Registry (`discovery/capability_registry.py`)

Registry of all available tools with:
- **Capability metadata**: Name, description, operations
- **Schema validation**: Type checking for arguments
- **Risk classification**: read_only, low, moderate, high, destructive
- **Permission policies**: Confirmation requirements based on risk

### 6. External API Integrations

#### GitHub (`capabilities/github.py`)
- Search repositories by query, language, stars
- Search issues and pull requests
- Get repository details and README
- Get file content from repositories
- Rate limit status checking
- Optional authentication via GITHUB_TOKEN

#### Stack Exchange (`capabilities/stack_exchange.py`)
- Search questions on Stack Overflow and other Stack Exchange sites
- Get detailed question information
- Get answers for questions
- Search similar questions
- Rate limit status checking
- Optional authentication via STACK_EXCHANGE_KEY

### 7. Existing Capabilities (Preserved)

All existing CLIBOT capabilities remain functional:
- **Filesystem**: List, read, write, search, copy, move, delete, hash, etc.
- **System**: Info, logs, time, RAM, CPU, GPU, hardware
- **Processes**: List, inspect, terminate, signal, tree view
- **Networking**: Interfaces, routes, DNS, ping, traceroute, HTTP requests
- **Services**: systemd service status, logs, start/stop/restart
- **Development**: Python execution, Git operations, command execution
- **Calculator**: Safe arithmetic evaluation
- **Browser**: Open URLs and applications
- **Translation**: Google Translate integration
- **Web Search**: DuckDuckGo integration
- **Package Management**: apt, pip, npm
- **Monitoring**: Real-time system metrics
- **Automation**: Scripts, cron jobs, systemd timers
- **Cybersecurity**: Authorized scanning, reconnaissance, reporting

## Configuration

### Environment Variables

```bash
# LLM Provider
CLIBOT_LLM_PROVIDER=ollama|openai|openai_compatible
CLIBOT_LLM_MODEL=llama3.2|gpt-4o-mini
CLIBOT_OLLAMA_URL=http://127.0.0.1:11434
CLIBOT_LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your_api_key_here

# External APIs (optional)
GITHUB_TOKEN=your_github_token
STACK_EXCHANGE_KEY=your_stack_exchange_key

# Legacy (still supported)
CLIBOT_USE_LLM=true
```

### Configuration Files

- `config/settings.yaml`: General settings (language, timeouts, research behavior)
- `config/policies.yaml`: Risk policies and confirmation requirements
- `config/aliases.yaml`: Command aliases

## Modes of Operation

### 1. Rule-Based Mode (Default)
- Uses deterministic parser with 1700+ rules
- No LLM required
- Fast, predictable, offline-capable

### 2. Hybrid Mode (LLM Available)
- LLM classifies intent semantically
- LLM generates direct answers for conversation/explanation
- Tools used for data retrieval and actions
- Fallback to rules if LLM fails

### 3. Offline Mode
- All local tools available
- LLM local model if configured
- No external API calls
- Honest limitation reporting

## Security Model

### Risk Classification
- **read_only**: No confirmation required (e.g., list files, show info)
- **low**: No confirmation required (e.g., create empty file)
- **moderate**: Configurable confirmation (e.g., modify files)
- **high**: Confirmation required (e.g., delete files, install packages)
- **destructive**: Confirmation required (e.g., system-wide changes)

### Permission Policies
- Operations respect risk classification
- Protected paths require special authorization (`/`, `/etc`, `/usr`, `/boot`, `/dev`)
- Cybersecurity operations require explicit authorization scope
- No arbitrary command execution via shell=True
- Path traversal protection
- Timeout and output size limits

### Content Safety
- Web content treated as untrusted data
- No execution of instructions from web pages without explicit authorization
- Secrets redaction in logs and responses
- No sending of private data to remote providers without explicit action

## Testing

### Test Suite
Run the comprehensive test suite:
```bash
pytest tests/test_agent_requirements.py -v
```

### Test Coverage
- Calculation reasoning (hypothetical vs. actual storage)
- Contextual assertions (not converted to web searches)
- Offline capability descriptions
- LLM-based explanations
- Network distinction (interface vs. connectivity)
- Safety recommendations
- GitHub integration
- Stack Exchange integration
- Error handling (timeouts, HTTP errors)
- Tool validation (invalid tools/arguments)
- Malicious content handling
- Destructive operation confirmations
- Graceful degradation without credentials
- Agent cycle intent classification
- System prompt versioning

## Usage Examples

### Interactive Mode
```bash
clibot
```

### Direct Command Mode
```bash
clibot --command "muestra los procesos activos"
clibot --command "busca en GitHub proyectos Python para análisis de logs"
clibot --command "busca solución para error en Stack Overflow"
```

### Example Interactions

```
❯ Tengo 10 GB libres y utilizo 3 GB. ¿Cuánto queda?
Resultado: 7 GB

❯ Mi carpeta de proyectos se llama Fenrir.
Entendido. He guardado que tu carpeta de proyectos es Fenrir.

❯ ¿Y cómo veo los procesos?
Puedo listar los procesos con el comando 'ps aux' o usar la capability processes.list.

❯ Explícame qué es un proceso en Linux para principiantes.
[LLM generates explanation]

❯ Busca en GitHub proyectos Python para análisis de logs
Se encontraron 15 repositorios:
- loguru: Python logging made easier
- python-logstash: Logstash handler...
[with links and descriptions]

❯ Busca solución para error "Connection refused" en Stack Overflow
Se encontraron 20 preguntas:
- How to fix Connection refused...
- Python socket.error: Connection refused...
[with accepted answers marked]
```

## Integration Points

### Adding New Tools

1. Implement tool function in `capabilities/your_tool.py`
2. Register in `capabilities/__init__.py` using `_add()`
3. Define schema and risk level
4. Add parser rules in `core/parser.py` if needed
5. Add intent classification in `core/agent_cycle.py` if needed

### Adding New External APIs

1. Create client class in `capabilities/your_api.py`
2. Implement error handling, rate limiting, authentication
3. Register operations in capability registry
4. Add intent classification for API-specific queries
5. Add tests with mocks

## Limitations and Future Work

### Current Limitations
- LLM timeout is conservative (150ms) to prevent blocking
- No persistent memory across sessions (optional feature)
- Limited streaming support for LLM responses
- No multi-agent coordination
- No vector database for RAG

### Planned Enhancements
- Persistent memory with user control
- Streaming LLM responses
- Enhanced code generation with verification
- More sophisticated tool selection
- Better context summarization for long sessions
- Additional API integrations (documentation sites, etc.)

## Migration from v1.0

### Breaking Changes
None. All existing functionality is preserved.

### New Features
- Agent cycle with semantic intent classification
- GitHub and Stack Exchange integrations
- Enhanced context management
- Centralized system prompt
- Improved offline mode

### Configuration Changes
- New environment variables for LLM provider selection
- Optional GITHUB_TOKEN and STACK_EXCHANGE_KEY
- Existing CLIBOT_USE_LLM still supported

## Performance Considerations

- Rule-based parsing: <10ms per request
- LLM classification: 150-500ms (with timeout)
- Tool execution: varies by operation
- External API calls: network-dependent with 10s timeout
- Memory usage: ~50-100MB base, plus LLM model if local

## License

MIT License - See LICENSE file for details.
