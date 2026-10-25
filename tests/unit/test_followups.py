from core.assistant import Assistant
from core.contracts import Operation, Plan, Result, Status


def _remember(assistant, operation, result, request='previous request'):
    assistant.context.record_exchange(request, {
        'plan': Plan([operation], request),
        'results': [result],
    })


def test_are_you_sure_followup_is_honest_about_launch_evidence():
    assistant = Assistant()
    operation = Operation('browser', 'open_application', {'name': 'pycharm'},
                          description='abrir PyCharm')
    result = Result(operation.id, True, stdout='Abrí PyCharm.', duration=5.5,
                    status=Status.SUCCEEDED)
    _remember(assistant, operation, result, 'abre PyCharm')
    response = assistant.handle('¿Seguro?')
    assert 'solicitud terminó bien' in response['message']
    assert 'no puedo verificar' in response['message']


def test_networks_followup_expands_previous_capability_overview():
    assistant = Assistant()
    assistant.context.last_answer = 'Con Linux, archivos, redes, desarrollo, cálculos y búsquedas web.'
    response = assistant.handle('redes?')
    assert 'interfaces' in response['message']
    assert 'puertos locales' in response['message']


def test_latency_followup_explains_remote_gemini_503():
    assistant = Assistant()
    operation = Operation('development', 'execute_command', {'command': 'gemini'},
                          description='ejecutar Gemini CLI')
    detail = 'Gemini CLI: HTTP 503 service unavailable, model experiencing high demand; retrying.'
    result = Result(operation.id, False, stderr=detail, error_category='process_failure',
                    duration=24.8, status=Status.FAILED)
    _remember(assistant, operation, result, 'ejecuta gemini')
    response = assistant.handle('¿Por qué tardaste tanto?')
    assert '24.8 segundos' in response['message']
    assert 'HTTP 503' in response['message']


def test_gemini_503_trace_is_summarized_in_terminal_output():
    from interface.formatter import _compact_error
    trace = 'Error 503: service unavailable; high demand\n' + '\n'.join(f'frame {n}' for n in range(30))
    summary = _compact_error(trace)
    assert summary.startswith('El servicio de Gemini respondió HTTP 503')
    assert 'frame 29' not in summary
