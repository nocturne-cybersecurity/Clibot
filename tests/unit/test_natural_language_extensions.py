import json
import os
from urllib.parse import parse_qs, urlparse

from core.parser import Parser
from core.assistant import Assistant
from capabilities import translation
from capabilities.development import execute_command


def test_translation_intent_preserves_text_and_asks_for_missing_target():
    parser = Parser()
    plan = parser.parse('traduce "Good morning" al español')
    operation = plan.operations[0]
    assert (operation.capability, operation.name) == ('translation', 'translate')
    assert operation.arguments == {'text': 'Good morning', 'target_language': 'es'}

    context = type('ContextStub', (), {'pending': None})()
    question = parser.parse('traduce hello', context)
    assert question.clarification.startswith('¿A qué idioma')
    assert context.pending['kind'] == 'translate_target'
    followup = parser.resolve_pending('español', context)
    assert followup.operations[0].arguments['text'] == 'hello'
    assert followup.operations[0].arguments['target_language'] == 'es'


def test_translation_understands_country_as_its_main_language():
    operation=Parser().parse('como se dice hola en rusia').operations[0]
    assert operation.arguments=={'text':'hola','target_language':'ru'}


def test_translation_wins_over_calculator_and_accepts_target_before_text():
    parser = Parser()
    phrase = 'traduce "Buenos días a todos en este día tan maravilloso"'
    missing = parser.parse(phrase)
    assert missing.clarification.startswith('¿A qué idioma')
    assert missing.operations == []
    context = type('ContextStub', (), {'pending': None})()
    parser.parse(phrase, context)
    operation = parser.resolve_pending('alemán', context).operations[0]
    assert operation.arguments == {
        'text': 'Buenos días a todos en este día tan maravilloso',
        'target_language': 'de',
    }

    direct = parser.parse('traduce al alemán hola cómo estás hoy').operations[0]
    assert direct.arguments == {'text': 'hola cómo estás hoy', 'target_language': 'de'}


def test_search_and_plain_command_intents_are_structured():
    parser = Parser()
    search = parser.parse('quiero buscar fotos de gatos en Google')
    query = search.operations[0].arguments['query']
    assert query == 'fotos de gatos'
    direct = parser.parse('busca en Google cómo revisar el disco')
    direct_query = direct.operations[0].arguments['query']
    assert direct_query == 'cómo revisar el disco'
    assert direct.operations[0].capability == 'web'

    question = parser.parse('puedes buscar cosas en google?')
    assert not question.operations and '¿Qué tema' in question.clarification

    command = parser.parse('ejecuta ls -la').operations[0]
    assert command.capability == 'development'
    assert command.name == 'execute_command'
    assert command.arguments['command'] == 'ls -la'
    assert command.risk.value == 'high'


def test_translation_capability_parses_google_response(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, _limit):
            return json.dumps([[['Hola', 'Hello', None, None]], None, 'en']).encode()

    observed = {}

    def fake_urlopen(request, timeout):
        observed['url'] = request.full_url
        observed['timeout'] = timeout
        return Response()

    monkeypatch.setattr(translation, 'urlopen', fake_urlopen)
    result = translation.translate('Hello', 'es')
    assert result['translation'] == 'Hola'
    assert result['source_language'] == 'en'
    assert parse_qs(urlparse(observed['url']).query)['q'] == ['Hello']


def test_translation_falls_back_when_google_rate_limits(monkeypatch):
    from urllib.error import HTTPError
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, _limit):
            return json.dumps({'responseData': {'translatedText': 'Hallo'}}).encode()
    urls=[]
    def fake_urlopen(request, timeout):
        urls.append(request.full_url)
        if len(urls)==1:
            raise HTTPError(request.full_url,429,'limited',{},None)
        return Response()
    monkeypatch.setattr(translation,'urlopen',fake_urlopen)
    result=translation.translate('Hello','de')
    assert result['translation']=='Hallo'
    assert result['provider']=='MyMemory (alternativo)'
    assert 'api.mymemory.translated.net' in urls[1]


def test_web_search_formats_results_without_a_browser(monkeypatch):
    from capabilities import web_search
    class Response:
        def __enter__(self): return self
        def __exit__(self,*_): return False
        def read(self,_limit):
            return b'<a class="result__a" href="https://example.test">Example</a><a class="result__snippet">Useful summary</a>'
    monkeypatch.setattr(web_search,'urlopen',lambda request,timeout:Response())
    result=web_search.search('example query')
    assert result['results'][0]=={'title':'Example','url':'https://example.test','snippet':'Useful summary'}


def test_web_search_falls_back_to_bing_when_duckduckgo_has_no_parseable_results(monkeypatch):
    from capabilities import web_search
    class Response:
        def __init__(self, body): self.body=body
        def __enter__(self): return self
        def __exit__(self,*_): return False
        def read(self,_limit): return self.body
    responses=[Response(b'<html>challenge</html>'),Response(
        b'<li class="b_algo"><h2><a href="https://example.test/kernel">Kernel</a></h2>'
        b'<div class="b_caption"><p>Core of an operating system.</p></div></li>')]
    monkeypatch.setattr(web_search,'urlopen',lambda request,timeout:responses.pop(0))
    result=web_search.search('what is a kernel')
    assert result['provider']=='Bing HTML'
    assert result['results'][0]['title']=='Kernel'


def test_web_search_status_question_is_not_sent_to_search_provider():
    response=Assistant().handle('tu buscador funciona?')
    assert 'Puedo buscar desde esta terminal' in response['clarification']
    assert not response.get('results')


def test_translation_does_not_prompt_and_terminal_output_is_concise(monkeypatch):
    from interface.formatter import format_response
    assistant=Assistant(confirm=lambda _: (_ for _ in ()).throw(AssertionError('routine translation prompted')))
    monkeypatch.setitem(assistant.registry.get('translation').operations,'translate',
                        lambda text,target_language,**_: {'translation':'bonjour','target_language':target_language,'source_language':'auto','provider':'test'})
    response=assistant.handle('como se dice hola en frances')
    rendered=format_response(response)
    assert 'bonjour' in rendered
    assert 'Idioma detectado' not in rendered and 'provider' not in rendered


def test_unrelated_message_cancels_pending_translation_instead_of_looping():
    assistant=Assistant(confirm=lambda _: 'yes')
    question=assistant.handle('traduce hola')
    assert question['clarification'].startswith('¿A qué idioma')
    answer=assistant.handle('que puedes hacer por mi')
    assert assistant.context.pending is None
    assert 'desarrollo' in answer.get('message','').lower() or answer.get('results')


def test_web_answer_is_compact_and_omits_sources():
    from interface.formatter import _human_value,format_response
    from core.contracts import Operation,Plan,Result
    value={'query':'Linux','provider':'test','results':[
        {'title':'Fuente uno','url':'https://one.test','snippet':'Linux usa el kernel Linux.'},
        {'title':'Fuente dos','url':'https://two.test','snippet':'Es un sistema de código abierto.'},
        {'title':'Fuente tres','url':'https://three.test','snippet':'Funciona en muchos dispositivos.'},
    ]}
    rendered=_human_value(value)
    assert rendered=='Linux usa el kernel Linux.'
    assert 'https://' not in rendered
    assert 'También coincide' not in rendered
    assert '· test' not in rendered
    operation=Operation('web','search',{'query':'Linux'})
    result=Result(operation.id,True,data={'value':value},duration=0.9)
    terminal=format_response({'plan':Plan([operation]),'results':[result]})
    assert '✓ Listo' not in terminal
    assert 'https://' not in terminal
    assert '0.9s' in terminal


def test_general_research_only_runs_for_factual_queries():
    assert Assistant._is_general_question('¿Qué es fiable?')
    assert Assistant._is_general_question('¿Qué sabes de Linux?')
    assert not Assistant._is_general_question('¿Cuál es el peor consejo para cocinar un huevo?')
    assert not Assistant._is_general_question('¿Cómo aprender a programar?')
    assert not Assistant._is_general_question('Escribe un poema sobre calcetines')
    assert Assistant._is_general_question('¿Cómo se llama la capital de Rusia?')


def test_compound_spoken_math_preserves_precedence_and_square_root():
    from capabilities.calculator import evaluate
    examples = {
        'cuanto es 2 mas 2 por 3 mas la raiz cuadrada de 81': 17,
        'cuanto es 5 mas cinco entre 2': 7.5,
        'cuanto es 5 menos cinco': 0,
        'cuanto es 5 menos cinco entre 2 mas la rainz cuadrada de 81': 11.5,
        'seis mas seis': 12,
    }
    for request, expected in examples.items():
        plan = Parser().parse(request)
        assert plan.operations, request
        expression = plan.operations[0].arguments['expression']
        assert evaluate(expression)['result'] == expected, (request, expression)


def test_web_search_answer_is_not_cut_by_formatter_and_wraps_to_terminal_width(monkeypatch):
    import shutil
    from interface.formatter import _human_value, format_response
    from core.contracts import Operation, Plan, Result

    long_excerpt = 'Berlin is the capital of Germany. ' + ('Additional useful context. ' * 12)
    value = {'query': 'capital de Alemania', 'provider': 'test', 'results': [
        {'title': 'Germany', 'url': 'https://example.test', 'snippet': long_excerpt},
    ]}
    monkeypatch.setattr(shutil, 'get_terminal_size', lambda *_: os.terminal_size((52, 24)))
    rendered = _human_value(value)
    assert rendered == long_excerpt.strip()
    assert '…' not in rendered

    operation = Operation('web', 'search', {'query': value['query']})
    result = Result(operation.id, True, data={'value': value})
    terminal = format_response({'plan': Plan([operation]), 'results': [result]})
    assert 'Berlin is the capital of Germany.' in terminal
    assert all(len(line) <= 44 for line in terminal.splitlines())


def test_search_followup_can_repeat_the_full_available_excerpt(monkeypatch):
    assistant = Assistant()
    excerpt = 'Berlin is the capital of Germany. This complete search excerpt includes useful context.'
    monkeypatch.setitem(assistant.registry.get('web').operations, 'search',
                        lambda query, **_: {'query': query, 'provider': 'test', 'results': [
                            {'title': 'Germany', 'url': 'https://example.test', 'snippet': excerpt},
                        ]})
    first = assistant.handle('investiga cual es la capital de alemania')
    assert first['results']
    detail = assistant.handle('eso que')
    assert detail['message'] == excerpt
    repeated = assistant.handle('muestra la respuesta completa, no la acortes')
    assert repeated['message'] == excerpt


def test_failed_calculation_followup_explains_the_actual_cause():
    assistant=Assistant()
    failed=assistant.handle('cuanto es 1 dividido entre 0')
    assert not failed['results'][0].success
    explanation=assistant.handle('por que no pudiste hacer el calculo?')
    assert '1 / 0' in explanation['message']
    assert 'division by zero' in explanation['message']


def test_repeat_and_search_detail_followups_use_recent_context(monkeypatch):
    assistant=Assistant()
    queries=[]
    def fake_search(query,**_):
        queries.append(query)
        return {'query':query,'provider':'test','results':[{'title':'Resultado','url':'https://example.test','snippet':'Rusia fue parte de tres estados históricos.'}]}
    monkeypatch.setitem(assistant.registry.get('web').operations,'search',fake_search)
    assistant.handle('¿Cuál es la capital de Rusia?')
    assistant.handle('una de las 3 que?')
    assert len(queries)==2 and 'una de las 3 que' in queries[-1]
    repeated=assistant.handle('repítelo')
    assert repeated['results'][0].success


def test_creative_requests_are_not_misrouted_to_web_or_system_tools():
    assistant=Assistant()
    for request in ('Inventa un deporte nuevo en la Luna','Explícame la física cuántica como si tuviera 5 años y amara los dinosaurios',
                    'Escribe un poema épico sobre un calcetín perdido','Imagina que eres un pirata en internet'):
        response=assistant.handle(request)
        assert response.get('message','').startswith('Para inventar')
        assert not response.get('results')


def test_numbered_creative_prompts_are_not_misrouted():
    prompts=(
        '¿Cuál es el peor consejo que alguien me podría dar para aprender a cocinar un huevo?',
        'Explícame la física cuántica como si yo tuviera 5 años y estuviera muy interesado en los dinosaurios.',
        'Inventa un deporte nuevo que se juegue en la luna con solo tres reglas sencillas.',
        'Si los gatos pudieran hablar, ¿cuál crees que sería su mayor queja sobre los humanos?',
        'Hazme un resumen de mi día ideal si yo fuera un mapache viviendo en el centro de una gran ciudad.',
        'Escribe un poema épico de cuatro estrofas sobre la odisea de buscar un calcetín perdido en la lavadora.',
        '¿Es un hot dog un sándwich? Dame argumentos fuertes para ambos lados.',
        'Imagina que eres un pirata del siglo XVIII que acaba de descubrir internet. Escríbeme un reporte de tu primer día navegando en la red.',
        '¿Qué tres objetos llevarías a una isla desierta si pudieras elegir cosas completamente absurdas pero inútiles?',
        'Hazme una lista de 5 preguntas difíciles que yo debería hacerte a ti para ponerte a prueba.',
    )
    assert all(Assistant._is_open_ended_request(prompt) for prompt in prompts)


def test_file_listing_and_file_search_do_not_become_web_queries():
    parser=Parser()
    for request in ('¿Qué archivos hay en esta carpeta?', 'lee esta carpeta', 'busca un archivo que se llame hola en la computadora'):
        plan=parser.parse(request)
        assert plan.operations
        assert all(op.capability=='filesystem' for op in plan.operations)


def test_open_ended_response_uses_configured_model_without_proposing_tools(monkeypatch):
    assistant=Assistant()
    monkeypatch.setattr(assistant.llm,'is_available',lambda:True)
    monkeypatch.setattr(assistant.llm,'generate_response',lambda prompt:'Una respuesta creativa breve.')
    response=assistant.handle('Inventa un deporte nuevo en la Luna')
    assert response['message']=='Una respuesta creativa breve.'
    assert response['reasoning']=='local_model'
    assert not response.get('results')


def test_folder_content_requests_use_local_filesystem_not_web():
    parser=Parser()
    for request in ('lee esta carpeta','qué archivos hay en esta carpeta','lista los archivos de esta carpeta'):
        operation=parser.parse(request).operations[0]
        assert operation.capability=='filesystem' and operation.name=='list'


def test_network_word_in_creative_text_does_not_trigger_connectivity_diagnostics():
    plan=Parser().parse('Imagina un pirata que acaba de descubrir internet')
    assert plan.clarification
    assert not plan.operations


def test_file_creation_runs_without_routine_confirmation_and_remembers_location(tmp_path):
    assistant=Assistant(confirm=lambda _: (_ for _ in ()).throw(AssertionError('routine file creation prompted')))
    created=assistant.handle(f'crea un archivo llamado hola.py en "{tmp_path}"')
    assert created['results'][0].success
    assert (tmp_path/'hola.py').is_file()
    location=assistant.handle('dime dónde está el archivo hola.py')
    assert str(tmp_path/'hola.py') in location['message']


def test_followup_summarizes_last_operation_without_dumping_raw_system_data():
    assistant=Assistant(confirm=lambda _: 'yes')
    completed=assistant.handle('dame la info del sistema')
    assert completed['results'][0].success
    followup=assistant.handle('qué pasó?')
    assert 'consultar la información del sistema' in followup['message']
    assert 'hostname' not in followup['message']


def test_general_fact_questions_search_web_and_followups_use_session_memory(monkeypatch):
    assistant=Assistant(confirm=lambda _: 'yes')
    searches=[]
    def fake_search(query,**_):
        searches.append(query)
        return {'query':query,'provider':'test','results':[{'title':'Capital de Perú','url':'https://example.test/peru','snippet':'La capital de Perú es Lima.'}]}
    monkeypatch.setitem(assistant.registry.get('web').operations,'search',fake_search)

    found=assistant.handle('Cuál es la capital de Perú')
    assert found['results'][0].success
    assert found['plan'].operations[0].capability=='web'
    assert searches==['Cuál es la capital de Perú']

    repeated=assistant.handle('pues búscalo')
    assert repeated['results'][0].success
    assert searches[-1]=='Cuál es la capital de Perú'
    explanation=assistant.handle('eso qué')
    assert 'La capital de Perú es Lima.' in explanation['message']
    assert 'https://' not in explanation['message']
    continued=assistant.handle('No quiero que abras el navegador, quiero que lo busques e investigues, parece que no puedes hacer nada')
    assert continued['results'][0].success
    assert searches[-1]=='Cuál es la capital de Perú'


def test_plain_history_word_is_a_terminal_command(monkeypatch,capsys):
    from interface.terminal import Terminal
    assistant=Assistant(confirm=lambda _: 'yes')
    assistant.context.record_exchange('hola',{'message':'¡Hola!'})
    inputs=iter(['history','/exit'])
    monkeypatch.setattr('builtins.input',lambda _='':next(inputs))
    Terminal(assistant).run()
    assert 'hola' in capsys.readouterr().out


def test_interactive_terminal_reveals_messages_with_a_short_animation(monkeypatch):
    import io
    from interface.terminal import Terminal

    class TTY(io.StringIO):
        def isatty(self):
            return True

    assistant=Assistant()
    terminal=Terminal(assistant)
    output=TTY()
    pauses=[]
    monkeypatch.setattr('interface.terminal.sys.stdout',output)
    monkeypatch.setattr('interface.terminal.time.sleep',lambda seconds:pauses.append(seconds))
    terminal._print_message('LLMAH  ¡Hola!')
    assert output.getvalue()=='LLMAH  ¡Hola!\n'
    assert pauses and sum(pauses)<=0.9


def test_animation_is_disabled_for_silent_and_json_output(monkeypatch):
    import io
    from interface.terminal import Terminal

    class TTY(io.StringIO):
        def isatty(self):
            return True

    terminal=Terminal(Assistant())
    output=TTY()
    monkeypatch.setattr('interface.terminal.sys.stdout',output)
    monkeypatch.setattr('interface.terminal.time.sleep',lambda *_:(_ for _ in ()).throw(AssertionError('animation should be off')))
    terminal.silent_mode=True
    terminal._print_message('quiet')
    terminal.silent_mode=False
    terminal.json_mode=True
    terminal._print_message('{"ok": true}')
    assert output.getvalue()=='quiet\n{"ok": true}\n'


def test_terminal_table_respects_narrow_width(monkeypatch):
    import shutil
    from interface.formatter import _table
    monkeypatch.setattr(shutil,'get_terminal_size',lambda fallback:shutil.os.terminal_size((40,24)))
    rendered=_table([{'interface':'wlp3s0','state':'UP','addresses':['192.168.100.24/24','2001:db8::1/64']}])
    assert max(map(len,rendered.splitlines()))<=40
    assert '…' in rendered


def test_system_info_terminal_summary_is_compact():
    from interface.formatter import _human_value
    rendered=_human_value({'hostname':'debian','os':'Linux-6.12-x86_64','kernel':'6.12','architecture':'x86_64','python':'3.13',
                           'user':'nocturne','uptime_seconds':12345,'load_average':[1,2,3],
                           'memory':{'MemTotal':'14230928 kB','MemAvailable':'5791144 kB'}})
    assert 'RAM 5.5/13.6 GiB libre' in rendered
    assert 'uptime_seconds' not in rendered and 'load_average' not in rendered and len(rendered.splitlines())==2


def test_optional_model_operations_still_pass_through_validation():
    class Model:
        def is_available(self):
            return True

        def interpret_request(self, request, capabilities, context):
            assert any(item['name'] == 'system' for item in capabilities)
            return {'kind': 'operations', 'operations': [{
                'capability': 'system', 'operation': 'time', 'arguments': {},
                'description': 'consultar la hora', 'depends_on': [],
            }]}

    assistant = Assistant()
    assistant.llm = Model()
    response = assistant.handle('averigua eso que conversamos sobre el reloj')
    assert response['results'][0].success
    assert response['plan'].operations[0].capability == 'system'

    class InvalidModel(Model):
        def interpret_request(self, request, capabilities, context):
            return {'kind': 'operations', 'operations': [{
                'capability': 'unknown', 'operation': 'delete_everything', 'arguments': {},
            }]}

    assistant.llm = InvalidModel()
    rejected = assistant.handle('haz algo que no tenga sentido')
    assert 'results' not in rejected


def test_explicit_command_supports_a_real_safe_pipeline_and_rejects_shell_operators(tmp_path):
    result = execute_command('printf hola | tr a-z A-Z')
    assert result['success'] is True
    assert result['stdout'] == 'HOLA'
    try:
        execute_command(f'printf hola > {tmp_path / "output.txt"}')
    except ValueError as exc:
        assert 'redirección' in str(exc)
    else:
        raise AssertionError('redirection must not be evaluated as shell syntax')


def test_web_fallback_and_interface_improvements():
    from core.assistant import Assistant
    from interface.formatter import format_response

    assistant = Assistant()
    
    # 1. Single word 'web' exact match
    resp_web = assistant.handle('web')
    assert resp_web.get('message') == 'No entendí. ¿Qué necesitas exactamente?'

    # 2. General factual question fallback to web search
    assert Assistant._is_general_question('¿Cuál es la capital de Francia?')
    assert Assistant._is_general_question('¿Qué es Debian Linux?')

    # 3. Formatting clarification uses LLMAH prefix
    rendered = format_response({'clarification': 'No entendí.'})
    assert 'LLMAH' in rendered
    assert 'No entendí.' in rendered

