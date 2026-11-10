import json
import os
import subprocess
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import pytest

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


def test_close_application_uses_known_app_operation_and_requires_confirmation():
    parser=Parser()
    operation=parser.parse('cierra chrome').operations[0]
    assert (operation.capability,operation.name)==('browser','close_application')
    assert operation.arguments=={'name':'chrome'}
    assert operation.risk.value=='high'
    assert parser.parse('cierra la aplicación de Spotify').operations[0].name=='close_application'
    assert parser.parse('cierra LibreOffice').operations[0].name=='close_application'
    assert parser.parse('cierra la sesión').operations[0].name=='logout'


def test_beginner_explanation_uses_local_model_before_parser():
    class Model:
        def is_available(self):
            return True

        def generate_response(self, _prompt, **_kwargs):
            return 'Un proceso es un programa que está ejecutándose.'

    assistant=Assistant()
    assistant.llm=Model()
    response=assistant.handle('Explícame qué es un proceso en Linux para principiantes.')
    assert response['message']=='Un proceso es un programa que está ejecutándose.'
    assert response['reasoning']=='local_model'


def test_beginner_explanation_without_model_does_not_search_automatically(monkeypatch):
    assistant=Assistant()
    assistant.llm=None
    monkeypatch.setattr(assistant.executor,'execute',lambda _plan: [])
    response=assistant.handle('Explícame qué es un proceso en Linux para principiantes.')
    assert response['message']
    assert 'modelo de lenguaje activo' in response['message']
    assert assistant.context.last_plan is None


def test_offline_statement_does_not_start_network_diagnostics():
    assistant=Assistant()
    assistant.llm=None
    response=assistant.handle('No tengo Internet.')
    assert 'Sin Internet' in response['message']
    assert 'plan' not in response


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


def test_git_workflows_parse_local_and_remote_actions():
    parser = Parser()
    cases = {
        'crea un repositorio git llamado demo': ('git_init', {'path': 'demo'}),
        'clona https://github.com/owner/project.git en /tmp/project':
            ('git_clone', {'url': 'https://github.com/owner/project.git', 'destination': '/tmp/project'}),
        'clona https://github.com/owner/project.git en "/tmp/my project"':
            ('git_clone', {'url': 'https://github.com/owner/project.git', 'destination': '/tmp/my project'}),
        'git add README.md': ('git_add', {'path': '.', 'files': ['README.md']}),
        'git add': ('git_add', {'path': '.'}),
        'haz un commit con mensaje "corrige inicio"':
            ('git_commit', {'path': '.', 'message': 'corrige inicio'}),
        'git pull origin main': ('git_pull', {'path': '.', 'remote': 'origin', 'branch': 'main'}),
        'git push': ('git_push', {'path': '.'}),
        'git merge feature': ('git_merge', {'path': '.', 'branch': 'feature'}),
        'git rebase main': ('git_rebase', {'path': '.', 'branch': 'main'}),
    }
    for request, (name, arguments) in cases.items():
        plan = parser.parse(request)
        operation = plan.operations[0]
        assert operation.capability == 'development'
        assert operation.name == name
        assert operation.arguments == arguments
        from capabilities import registry
        from core.validator import Validator
        assert Validator(registry).validate(plan)

    assert parser.parse('git commit').clarification.startswith('¿Qué mensaje')
    assert parser.parse('clona el repositorio').clarification.startswith('Indica la URL')


def test_git_init_creates_repository_in_requested_directory(tmp_path):
    from capabilities.development import git_add, git_commit, git_init, git_log

    destination = tmp_path / 'new-project'
    result = git_init(str(destination), initial_branch='main')
    assert result['success']
    assert (destination / '.git').is_dir()
    assert result['branch'] == 'main'
    subprocess.run(['git', '-C', str(destination), 'config', 'user.name', 'CLIBOT test'], check=True)
    subprocess.run(['git', '-C', str(destination), 'config', 'user.email', 'clibot-test@example.invalid'], check=True)
    (destination / 'README.md').write_text('test repository\n')
    assert git_add(str(destination), ['README.md'])['success']
    assert git_commit(str(destination), 'initial commit')['success']
    assert git_log(str(destination))['commits'][0]['message'].endswith('initial commit')


def test_git_clone_uses_argv_and_rejects_embedded_credentials(monkeypatch, tmp_path):
    from capabilities import development

    calls = []
    monkeypatch.setattr(development.subprocess, 'run', lambda args, **kwargs:
                        calls.append((args, kwargs)) or subprocess.CompletedProcess(args, 0, 'cloned', ''))
    destination = tmp_path / 'clone'
    result = development.clone('https://github.com/owner/project.git', str(destination))
    assert result['path'] == str(destination.resolve())
    assert calls[0][0] == ['git', 'clone', '--', 'https://github.com/owner/project.git', str(destination.resolve())]
    assert 'shell' not in calls[0][1]

    monkeypatch.chdir(tmp_path)
    ssh_result = development.clone('git@github.com:owner/ssh-project.git')
    assert ssh_result['path'] == str((tmp_path / 'ssh-project').resolve())
    assert calls[1][0][-1] == str((tmp_path / 'ssh-project').resolve())

    with pytest.raises(ValueError, match='No incluyas credenciales'):
        development.clone('https://user:token@example.com/repo.git', str(tmp_path / 'private'))


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
    assert not Assistant._is_general_question('averigua eso que conversamos sobre el reloj')


def test_local_model_is_auto_detected_unless_explicitly_disabled(monkeypatch):
    import core.assistant as assistant_module
    available=object()
    monkeypatch.delenv('CLIBOT_USE_LLM',raising=False)
    monkeypatch.setattr(assistant_module,'LLMIntegration',lambda:available)
    assert Assistant().llm is available
    monkeypatch.setenv('CLIBOT_USE_LLM','false')
    assert Assistant().llm is None


def test_hypothetical_storage_math_does_not_inspect_the_real_disk():
    for request in ('Si tengo 10 GB libres y un archivo ocupa 3 GB, ¿cuánto espacio me queda?',
                    '¿Cuánto espacio me queda si tengo 10 GB libres y un archivo ocupa 3 GB?'):
        response=Assistant().handle(request)
        assert response['message']=='Te quedarían 7 GB.'
        assert not response.get('results')
        parsed=Parser().parse(request)
        assert not parsed.operations


def test_offline_capabilities_question_does_not_run_network_diagnostics():
    response=Assistant().handle('No tengo conexión a Internet. ¿Qué puedes seguir haciendo por mí?')
    assert 'archivos locales' in response['message']
    assert not response.get('plan') and not response.get('results')


def test_advice_about_temp_files_does_not_request_a_deletion_target():
    response=Assistant().handle('Quiero borrar archivos temporales para liberar espacio. ¿Qué debería comprobar primero?')
    assert 'No borres a ciegas' in response['message']
    assert 'clarification' not in response


def test_disk_hog_request_uses_read_only_folder_scan(monkeypatch):
    from pathlib import Path
    assistant=Assistant()
    observed={}
    monkeypatch.setitem(assistant.registry.get('system').operations,'disk_hogs',
                        lambda path,limit: observed.update(path=path,limit=limit) or [{'ruta':'~/Videos','mib':2048}])
    response=assistant.handle('Necesito saber qué está ocupando espacio en mi equipo. ¿Cómo lo resolverías?')
    assert response['results'][0].success
    assert observed=={'path':str(Path.home()),'limit':10}
    assert response['results'][0].data['value'][0]['ruta']=='~/Videos'


def test_project_folder_statement_is_remembered_in_session_context():
    assistant=Assistant()
    response=assistant.handle('Mi carpeta de proyectos se llama Fenrir')
    assert response['message']=='Entendido, carpeta de proyectos es Fenrir. Lo recordaré durante esta sesión.'
    assert assistant.context.get_entity('carpeta de proyectos')=='Fenrir'


def test_code_example_requests_use_search_source_and_return_code(monkeypatch):
    parser=Parser()
    operation=parser.parse('busca un ejemplo de código Python para leer JSON en Stack Overflow').operations[0]
    assert (operation.capability,operation.name)==('stack_exchange','search_code_examples')
    assert operation.arguments['query']=='python read json'
    github=parser.parse('busca un ejemplo de código Python en GitHub').operations[0]
    assert (github.capability,github.name)==('github','search_code')
    assert github.arguments['query']=='python'

    from interface.formatter import _human_value
    rendered=_human_value({
        'kind':'code_examples','query':'python json','source':'Stack Overflow','results':[{
            'title':'Read JSON','answer_author':'Contributor','answer_url':'https://stackoverflow.com/a/1',
            'code':['import json\njson.loads("{}")'],
        }],
    })
    assert 'import json' in rendered and 'Contributor' in rendered and 'stackoverflow.com/a/1' in rendered


def test_code_generation_returns_complete_model_answer_without_search():
    searches=[]
    assistant=Assistant()
    class Model:
        def is_available(self):return True
        def generate_response(self,prompt,**kwargs):
            assert 'código' in prompt
            assert kwargs['max_tokens']==320
            return '```python\nimport json\nwith open(\"data.json\", encoding=\"utf-8\") as file:\n    data = json.load(file)\nprint(data)\n```\nGuárdalo como `leer_json.py` y ejecútalo con `python leer_json.py`.'
    assistant.llm=Model()
    assistant.registry.get('web').operations['search']=lambda *args,**kwargs:searches.append(args) or {}
    response=assistant.handle('Dame un ejemplo de código Python completo para leer JSON')
    assert response['reasoning']=='local_model_code'
    assert 'json.load(file)' in response['message']
    assert 'Fuentes' not in response['message']
    assert searches==[]


def test_code_search_only_runs_when_a_source_is_explicitly_requested():
    assistant=Assistant()
    assistant.llm=None
    response=assistant.handle('Busca un ejemplo de código Python en GitHub')
    assert response['plan'].operations[0].capability=='github'
    assert response['plan'].operations[0].name=='search_code'


def test_plain_code_example_request_does_not_make_parser_search_stackoverflow():
    plan=Parser().parse('necesito un ejemplo de código Python para leer JSON')
    assert not plan.operations


def test_troubleshooting_uses_model_and_does_not_trigger_web_search():
    assistant=Assistant()
    searches=[]
    assistant.registry.get('web').operations['search']=lambda *args,**kwargs:searches.append(args) or {}
    class Model:
        def is_available(self):return True
        def generate_response(self,prompt,**kwargs):
            assert 'no busques en la web' in prompt.lower()
            return 'Comprueba la ruta con `ls -l archivo`, revisa permisos con `stat archivo` y pega el error completo para identificar la causa.'
    assistant.llm=Model()
    response=assistant.handle('Mi script Python falla al abrir un archivo, ¿cómo lo arreglo?')
    assert response['reasoning']=='local_model_troubleshooting'
    assert '`stat archivo`' in response['message']
    assert searches==[]


def test_troubleshooting_without_model_asks_for_useful_diagnostic_context():
    assistant=Assistant()
    assistant.llm=None
    response=assistant.handle('Mi programa no funciona, ¿cómo lo soluciono?')
    assert 'mensaje de error completo' in response['message']
    assert 'No hice una búsqueda web' in response['message']


def test_factual_questions_use_local_model_without_automatic_web_search(monkeypatch):
    assistant=Assistant()
    searches=[]
    monkeypatch.setitem(assistant.registry.get('web').operations,'search',lambda query,**_:
                        searches.append(query) or {'query':query,'results':[{
                            'title':'Capital de Francia','url':'https://example.test/paris',
                            'snippet':'París es la capital de Francia.',
                        }]})
    class Model:
        def is_available(self):return True
        def generate_response(self,prompt,**kwargs):return 'La capital de Francia es París.'
    assistant.llm=Model()
    response=assistant.handle('¿Cómo se llama la capital de Francia?')
    assert response['message']=='La capital de Francia es París.'
    assert response['reasoning']=='local_model'
    assert searches==[]


def test_factual_question_does_not_search_web_even_when_local_model_is_available(monkeypatch):
    assistant=Assistant()
    class Model:
        def is_available(self):return True
        def generate_response(self,prompt,**kwargs):return 'París es la capital de Francia.'
    assistant.llm=Model()
    def unavailable(*_args,**_kwargs):
        raise AssertionError('no automatic search')
    monkeypatch.setitem(assistant.registry.get('web').operations,'search',unavailable)
    response=assistant.handle('¿Cuál es la capital de Francia?')
    assert response['reasoning']=='local_model'
    assert 'París' in response['message']


def test_beginner_explanation_without_model_does_not_search_automatically(monkeypatch):
    assistant=Assistant()
    assistant.llm=None
    searches=[]
    monkeypatch.setitem(assistant.registry.get('web').operations,'search',
                        lambda query,**_:searches.append(query) or {'query':query,'results':[]})
    response=assistant.handle('Explícame qué es un proceso en Linux como si estuviera empezando')
    assert 'modelo de lenguaje activo' in response['message']
    assert searches==[]


def test_stackoverflow_code_search_extracts_small_attributed_code_blocks():
    from capabilities.stack_exchange import StackExchangeIntegration
    client=StackExchangeIntegration()
    client.search_questions=lambda *args,**kwargs:{'results':[{
        'question_id':1,'title':'Read JSON','url':'https://stackoverflow.com/q/1','owner':'Question author',
    }]}
    client.get_answers=lambda *args,**kwargs:{'results':[{
        'answer_id':2,'owner':'Answer author','score':4,'is_accepted':True,
        'body':'<p>Use this:</p><pre><code>import json\njson.loads("{}")</code></pre>',
    }]}
    result=client.search_code_examples('python json')
    assert result['results'][0]['answer_author']=='Answer author'
    assert result['results'][0]['code']==['import json\njson.loads("{}")']
    assert result['results'][0]['answer_url']=='https://stackoverflow.com/a/2'


def test_github_code_search_requires_token_and_returns_source_links(monkeypatch):
    from capabilities.github import GitHubIntegration
    import pytest

    client=GitHubIntegration()
    with pytest.raises(RuntimeError,match='GITHUB_TOKEN'):
        client.search_code('python json')
    client=GitHubIntegration('test-token')
    observed={}
    def fake_request(endpoint,params,headers):
        observed.update(endpoint=endpoint,params=params,headers=headers)
        return {'total_count':1,'items':[{'repository':{'full_name':'owner/project'},'path':'src/main.py',
                 'html_url':'https://github.com/owner/project/blob/main/src/main.py',
                 'text_matches':[{'fragment':'json.loads(data)'}]}]}
    monkeypatch.setattr(client,'_request',fake_request)
    result=client.search_code('python json')
    assert result['results'][0]['code']==['json.loads(data)']
    assert observed['endpoint']=='/search/code'
    assert 'text-match' in observed['headers']['Accept']


def test_github_token_command_saves_private_credential(monkeypatch, tmp_path):
    import stat
    import capabilities.github as github
    import interface.terminal as terminal_module
    from interface.terminal import Terminal

    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    monkeypatch.delenv('GITHUB_TOKEN', raising=False)
    monkeypatch.setattr(terminal_module.getpass, 'getpass', lambda _prompt: 'ghp_private-test-token')
    monkeypatch.setattr(terminal_module.sys, 'stdin', type('TTY', (), {'isatty': lambda _self: True})())
    Terminal(Assistant())._cmd_token('set')
    assert github.GitHubIntegration().token == 'ghp_private-test-token'
    assert stat.S_IMODE(github.github_token_path().stat().st_mode) == 0o600


def test_help_lists_token_and_model_commands():
    from interface.terminal import COMMANDS
    names={name for name, _args, _description in COMMANDS}
    assert {'/help','/token','/models'} <= names


def test_banner_help_points_to_models_browser(capsys,monkeypatch):
    from interface.terminal import Terminal
    terminal=Terminal(Assistant())
    monkeypatch.setattr(terminal,'_model_info',lambda:(False,'offline · reglas'))
    monkeypatch.setattr(terminal.assistant,'capabilities',lambda:[])
    terminal._banner()
    rendered=capsys.readouterr().out
    assert '/help' in rendered and '/models' in rendered and '/exit' in rendered


def test_models_browser_lists_installed_and_live_catalog(monkeypatch,capsys):
    from interface.terminal import Terminal
    terminal=Terminal(Assistant())
    monkeypatch.setattr(terminal,'_ollama_models',lambda:[{'name':'phi3:mini','size':2_200_000_000}])
    monkeypatch.setattr(terminal,'_ollama_catalog',lambda query='':[
        {'name':'qwen2.5','description':'Multilingual model','variants':['0.5b','1.5b']},
    ])
    monkeypatch.setattr('interface.terminal.sys.stdin',type('NonTTY',(),{'isatty':lambda _self:False})())
    terminal._cmd_models('')
    rendered=capsys.readouterr().out
    assert 'phi3:mini' in rendered
    assert 'qwen2.5' in rendered
    assert '0.5b, 1.5b' in rendered
    assert '/models pull <modelo[:variante]>' in rendered


def test_models_catalog_query_and_interactive_selection_downloads_model(monkeypatch):
    from interface.terminal import Terminal
    terminal=Terminal(Assistant())
    queries=[]
    downloaded=[]
    monkeypatch.setattr(terminal,'_ollama_models',lambda:[])
    monkeypatch.setattr(terminal,'_ollama_catalog',lambda query='':
                        queries.append(query) or [{'name':'qwen2.5','description':'Qwen','variants':['0.5b','1.5b']}])
    monkeypatch.setattr(terminal,'_pull_ollama_model',downloaded.append)
    monkeypatch.setattr('interface.terminal.sys.stdin',type('TTY',(),{'isatty':lambda _self:True})())
    selections=iter(['1','2'])
    monkeypatch.setattr('builtins.input',lambda _prompt:next(selections))
    terminal._cmd_models('search qwen')
    assert queries==['qwen']
    assert downloaded==['qwen2.5:1.5b']


def test_ollama_catalog_parser_extracts_names_descriptions_and_size_tags():
    from interface.terminal import _OllamaCatalogParser
    parser=_OllamaCatalogParser()
    parser.feed('''<li><a href="/library/qwen2.5"><span>qwen2.5</span><p>Multilingual model</p>
        <span>tools</span><span class="bg-[#ddf4ff]">0.5b</span><span class="bg-[#ddf4ff]">1.5b</span>
        <span>45.3M</span></a></li>''')
    assert parser.models==[{'name':'qwen2.5','description':'Multilingual model','variants':['0.5b','1.5b']}]


def test_models_command_selects_only_installed_model(monkeypatch):
    from interface.terminal import Terminal

    terminal=Terminal(Assistant())
    selected=[]
    monkeypatch.setattr(terminal, '_ollama_models', lambda: [{'name':'llama3.2'}])
    monkeypatch.setattr(terminal, '_save_ollama_model', selected.append)
    terminal._cmd_models('use llama3.2')
    assert selected == ['llama3.2']
    terminal._cmd_models('use missing')
    assert selected == ['llama3.2']


def test_models_pull_stream_selects_downloaded_model(monkeypatch):
    import io
    from interface.terminal import Terminal

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    terminal=Terminal(Assistant())
    selected=[]
    monkeypatch.setattr('interface.terminal.urlopen', lambda request, timeout: (
        selected.append((json.loads(request.data), timeout)) or
        Response(b'{"status":"pulling","total":10,"completed":5}\n{"status":"success"}\n')
    ))
    monkeypatch.setattr(terminal, '_save_ollama_model', selected.append)
    terminal._cmd_models('pull llama3.2')
    assert selected[0][0] == {'name':'llama3.2','stream':True}
    assert selected[1] == 'llama3.2'


def test_safe_system_summary_command_needs_no_confirmation(monkeypatch):
    from capabilities.development import _clean_terminal_output
    assert _clean_terminal_output('\x1b[31minfo\x1b[0m\x1b[1G')=='info'
    assistant=Assistant(confirm=lambda _: (_ for _ in ()).throw(AssertionError('fastfetch is read-only')))
    monkeypatch.setitem(assistant.registry.get('development').operations,'execute_command',
                        lambda command,**_: {'exit_code':0,'stdout':'system summary','stderr':''})
    response=assistant.handle('ejecuta fastfetch')
    assert response['results'][0].success
    assert response['results'][0].data['value']['stdout']=='system summary'
    assert Parser().parse('ejecuta fastfetch para mostrar información de mi sistema').operations[0].arguments['command']=='fastfetch'


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


def test_spoken_multiply_after_square_roots_is_parsed_correctly():
    response=Assistant().handle('Calcula la raiz cuadrada de 144 y multiplicalo por la raiz cuadrada de 81')
    assert response['results'][0].success
    assert response['results'][0].data['value']['result']==108


def test_greeting_about_today_does_not_turn_into_date_search_or_model_call():
    assistant=Assistant()
    class Model:
        def is_available(self):return True
        def generate_response(self,*_args,**_kwargs):
            raise AssertionError('greeting should use conversational handling')
    assistant.llm=Model()
    response=assistant.handle('Hola, como te encuentras el dia de hoy?')
    assert response['message'].startswith('¡Hola!')
    assert not response.get('plan') and not response.get('results')


def test_week_number_is_answered_locally_without_model():
    assistant=Assistant()
    assistant.llm=None
    response=assistant.handle('En que semana estamos')
    expected=datetime.now().date().isocalendar()
    assert response['message']==f'Estamos en la semana {expected.week} del año {expected.year} (semana ISO).'


def test_calculator_code_request_without_model_does_not_invent_static_code():
    assistant=Assistant()
    assistant.llm=None
    response=assistant.handle('Dame el codigo para una calculadora en python')
    assert 'modelo de lenguaje activo' in response['message']
    assert not response.get('plan') and not response.get('results')


def test_calculator_code_request_uses_model_not_a_prebuilt_template():
    assistant=Assistant()
    class Model:
        def is_available(self):return True
        def generate_response(self,prompt,**kwargs):
            assert 'calculadora' in prompt
            assert 'PETICIÓN:' in prompt
            return '```python\nprint("Código generado para la calculadora")\n```'
    assistant.llm=Model()
    response=assistant.handle('Dame el codigo para una calculadora en python')
    assert response['reasoning']=='local_model_code'
    assert 'Código generado para la calculadora' in response['message']


def test_vague_code_request_asks_what_to_build_instead_of_generic_chitchat():
    response=Assistant().handle('Genera codigo')
    assert response['clarification']=='¿Qué debe hacer el código y en qué lenguaje?'


def test_explicit_stackoverflow_code_search_uses_attributed_source():
    assistant=Assistant()
    assistant.llm=None
    response=assistant.handle('Busca un ejemplo de código Python para una calculadora en Stack Overflow')
    operation=response['plan'].operations[0]
    assert (operation.capability,operation.name)==('stack_exchange','search_code_examples')
    assert 'python' in operation.arguments['query']
    assert 'calculadora' in operation.arguments['query']


def test_model_recommendation_uses_hardware_aware_quick_local_guidance():
    response=Assistant().handle('Me recomiendas otro modelo?')
    assert 'qwen2.5:1.5b' in response['message']
    assert 'qwen2.5:0.5b' in response['message']
    assert '/models pull qwen2.5:1.5b' in response['message']


def test_open_url_followup_explains_whether_launch_succeeded(monkeypatch):
    assistant=Assistant()
    monkeypatch.setitem(assistant.registry.get('browser').operations,'open_url',
                        lambda **_kwargs:{'url':'https://www.facebook.com','message':'browser requested'})
    opened=assistant.handle('Abre facebook')
    assert opened['results'][0].success
    followup=assistant.handle('Si se abrio')
    assert 'terminó bien' in followup['message']
    assert 'no puedo confirmar' in followup['message']


def test_open_question_prompt_includes_recent_conversation_context():
    assistant=Assistant()
    assistant.context.record_exchange('Estoy aprendiendo Python',{'message':'¡Perfecto! Puedo ayudarte con ejemplos.'})
    class Model:
        def is_available(self):return True
        def generate_response(self,prompt,**_kwargs):
            assert 'Estoy aprendiendo Python' in prompt
            assert 'PREGUNTA: ¿Por qué Python usa indentación?' in prompt
            return 'Python usa indentación para delimitar bloques de código.'
    assistant.llm=Model()
    response=assistant.handle('¿Por qué Python usa indentación?')
    assert response['message'].startswith('Python usa indentación')


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
    assistant.llm=None
    queries=[]
    def fake_search(query,**_):
        queries.append(query)
        return {'query':query,'provider':'test','results':[{'title':'Resultado','url':'https://example.test','snippet':'Rusia fue parte de tres estados históricos.'}]}
    monkeypatch.setitem(assistant.registry.get('web').operations,'search',fake_search)
    assistant.handle('Busca en la web cuál es la capital de Rusia')
    assistant.handle('una de las 3 que?')
    assert len(queries)==2 and 'una de las 3 que' in queries[-1]
    repeated=assistant.handle('repítelo')
    assert repeated['results'][0].success


def test_creative_requests_are_not_misrouted_to_web_or_system_tools():
    assistant=Assistant()
    assistant.llm=None
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


def test_open_ended_response_uses_configured_model_without_proposing_tools():
    assistant=Assistant()
    class Model:
        def is_available(self):return True
        def generate_response(self,prompt):return 'Una respuesta creativa breve.'
    assistant.llm=Model()
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


def test_explicit_web_search_and_followups_use_session_memory(monkeypatch):
    assistant=Assistant(confirm=lambda _: 'yes')
    assistant.llm=None
    searches=[]
    def fake_search(query,**_):
        searches.append(query)
        return {'query':query,'provider':'test','results':[{'title':'Capital de Perú','url':'https://example.test/peru','snippet':'La capital de Perú es Lima.'}]}
    monkeypatch.setitem(assistant.registry.get('web').operations,'search',fake_search)

    found=assistant.handle('Busca en la web cuál es la capital de Perú')
    assert found['results'][0].success
    assert found['plan'].operations[0].capability=='web'
    assert searches==['cuál es la capital de Perú']

    repeated=assistant.handle('pues búscalo')
    assert repeated['results'][0].success
    assert searches[-1]=='cuál es la capital de Perú'
    explanation=assistant.handle('eso qué')
    assert 'La capital de Perú es Lima.' in explanation['message']
    assert 'https://' not in explanation['message']
    continued=assistant.handle('No quiero que abras el navegador, quiero que lo busques e investigues, parece que no puedes hacer nada')
    assert continued['results'][0].success
    assert searches[-1]=='cuál es la capital de Perú'


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

    output=TTY()
    pauses=[]
    monkeypatch.setattr('interface.terminal.sys.stdout',output)
    monkeypatch.setattr('interface.terminal.time.sleep',lambda seconds:pauses.append(seconds))
    terminal=Terminal(Assistant())
    terminal.paginate_mode=False
    terminal._emit('primera línea\nsegunda línea')
    assert 0<len(pauses)<=2
    assert all(0<=delay<=0.03 for delay in pauses)


def test_animation_is_disabled_for_silent_and_json_output(monkeypatch):
    import io
    from interface.terminal import Terminal

    class TTY(io.StringIO):
        def isatty(self):
            return True

    output=TTY()
    monkeypatch.setattr('interface.terminal.sys.stdout',output)
    monkeypatch.setattr('interface.terminal.time.sleep',lambda *_:(_ for _ in ()).throw(AssertionError('animation should be off')))
    terminal=Terminal(Assistant())
    terminal.paginate_mode=False
    terminal.silent_mode=True
    terminal._emit('quiet')
    terminal.silent_mode=False
    terminal.json_mode=True
    terminal._emit('{"ok": true}')


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
