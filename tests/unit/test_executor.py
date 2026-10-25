from core.executor import Executor
from core.contracts import Operation, Plan, Risk, Status
from discovery.capability_registry import Capability, CapabilityRegistry
from security.redaction import redact

def test_execution_result_and_secret_redaction():
    reg=CapabilityRegistry();reg.register(Capability('x','test',{'run':lambda:{'token':'abc123'}},{'run':{'properties':{}}},{'run':'read_only'}))
    result=Executor(reg).execute(Plan([Operation('x','run')]))[0]
    assert result.success and 'abc123' not in result.stdout

def test_declined_consequential_action_is_not_called():
    called=[];reg=CapabilityRegistry();reg.register(Capability('x','test',{'run':lambda:called.append(1)},{'run':{'properties':{}}},{'run':'high'}))
    result=Executor(reg,confirm=lambda _: 'n').execute(Plan([Operation('x','run',risk=Risk.HIGH)]))[0]
    assert result.status==Status.DENIED and not called

def test_default_yes_is_scoped_to_configured_operation():
    called=[];prompts=[]
    reg=CapabilityRegistry();reg.register(Capability('browser','test',{'open_url':lambda:called.append(1)},{'open_url':{'properties':{}}},{'open_url':'moderate'}))
    result=Executor(reg,confirm=lambda prompt:(prompts.append(prompt) or ''),default_yes_operations=['browser.open_url']).execute(Plan([Operation('browser','open_url')]))[0]
    assert result.success and called and '[Y/n]' in prompts[0]

def test_high_risk_confirmation_remains_no_by_default():
    called=[];prompts=[]
    reg=CapabilityRegistry();reg.register(Capability('x','test',{'run':lambda:called.append(1)},{'run':{'properties':{}}},{'run':'high'}))
    result=Executor(reg,confirm=lambda prompt:(prompts.append(prompt) or ''),default_yes_operations=['browser.open_url']).execute(Plan([Operation('x','run')]))[0]
    assert not result.success and not called and '[y/N]' in prompts[0]

def test_redacts_bearer_and_password():
    value=redact('password=hunter2 Bearer eyJ.abc')
    assert 'hunter2' not in value and 'eyJ.abc' not in value

def test_explicit_argv_command_runs_after_confirmation():
    from core.assistant import Assistant
    response=Assistant(confirm=lambda _: 'yes').handle('ejecuta comando: printf LLMAH')
    assert response['results'][0].success
    assert response['results'][0].data['value']['stdout']=='LLMAH'

def test_reformat_followup_reuses_previous_observation():
    from core.assistant import Assistant
    assistant=Assistant()
    first=assistant.handle('muestra información del sistema')
    followup=assistant.handle('mejor estructurada')
    assert followup['results'][0] is first['results'][0]

def test_greeting_gets_a_conversational_response():
    from core.assistant import Assistant
    assert '¡Hola!' in Assistant().handle('hola')['message']

def test_terminal_preference_is_session_scoped_and_does_not_approve_commands():
    from core.assistant import Assistant
    assistant=Assistant(confirm=lambda _: 'no')
    assert 'En esta sesión' in assistant.handle('no me preguntes, siempre abre terminales')['message']
    assert assistant._confirm('Confirm abrir una terminal (moderate)? [y/N] ')=='yes'
    assert assistant._confirm('Confirm ejecutar un comando (high)? [y/N] ')=='no'

def test_create_file_intent_creates_a_real_empty_file(tmp_path):
    from core.assistant import Assistant
    from core.contracts import Status
    assistant=Assistant(confirm=lambda _: 'yes')
    response=assistant.handle(f'crea un archivo llamado hola.txt en "{tmp_path}"')
    assert response['results'][0].status==Status.SUCCEEDED
    assert (tmp_path/'hola.txt').is_file() and (tmp_path/'hola.txt').read_text()==''

def test_report_uses_previous_observation_and_writes_json(tmp_path):
    from core.assistant import Assistant
    import json
    assistant=Assistant(confirm=lambda _: 'yes')
    assert assistant.handle('muestra información del sistema')['results'][0].success
    destination=tmp_path/'report.json'
    result=assistant.handle(f'genera un informe en "{destination}"')
    assert result['results'][0].success
    report=json.loads(destination.read_text())
    assert report['findings'][0]['success'] is True

def test_create_file_clarification_keeps_name_context_and_reports_location(tmp_path):
    from core.assistant import Assistant
    assistant=Assistant(confirm=lambda _: 'yes')
    question=assistant.handle(f'crea un archivo de texto en "{tmp_path}"')
    assert 'nombre' in question['clarification']
    created=assistant.handle('quiero que hola sea el nombre del archivo')
    assert created['results'][0].success and (tmp_path/'hola.txt').is_file()
    assert f'{tmp_path}/hola.txt' in assistant.handle('¿dónde lo tienes?')['message']

def test_web_search_followup_keeps_query_for_terminal_search():
    from core.parser import Parser
    from core.context import Context
    parser=Parser(); context=Context()
    first=parser.parse('quiero buscar algo en Google',context)
    assert 'Qué tema' in first.clarification
    second=parser.resolve_pending('kernel Linux 6.12',context)
    assert second.operations[0].capability=='web'
    assert second.operations[0].arguments['query']=='kernel Linux 6.12'

def test_calculator_handles_roots_powers_and_rejects_code():
    from capabilities.calculator import evaluate
    assert evaluate('sqrt(81)')['result']==9
    assert evaluate('(2**8)')['result']==256
    import pytest
    assert evaluate('sin(30)')['result']==pytest.approx(0.5)
    with pytest.raises(ValueError):evaluate("__import__('os').system('id')")
    with pytest.raises(ValueError):evaluate('2**10000')

def test_followup_explains_last_command_error_from_observed_stderr():
    from core.assistant import Assistant
    assistant=Assistant(confirm=lambda _: 'yes')
    result=assistant.handle('ejecuta comando: false')
    assert not result['results'][0].success
    answer=assistant.handle('¿Por qué falló el último comando?')
    assert 'falló' in answer['message'] and 'código' in answer['message']

def test_discount_calculation_asks_then_uses_followup():
    from core.assistant import Assistant
    assistant=Assistant()
    question=assistant.handle('calcula el descuento de la factura')
    assert 'monto total' in question['clarification']
    answer=assistant.handle('1250 y 15%')
    assert 'results' in answer,answer
    assert answer['results'][0].success and answer['results'][0].data['value']['result']==1062.5

def test_move_followup_updates_actual_file_location(tmp_path):
    from core.assistant import Assistant
    assistant=Assistant(confirm=lambda _: 'yes')
    downloads=tmp_path/'Descargas';downloads.mkdir()
    created=assistant.handle(f'crea un archivo llamado hola en "{tmp_path}"')
    assert created['results'][0].success
    moved=assistant.handle(f'mueve "{tmp_path}/hola" a "{downloads}"')
    assert moved['results'][0].success
    assert assistant.handle('¿dónde lo guardaste?')['message']==f'Quedó en {downloads}/hola.'
