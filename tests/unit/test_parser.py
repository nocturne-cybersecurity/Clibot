from core.parser import Parser

def test_spanish_interfaces():
    plan=Parser().parse('Muéstrame mis interfaces de red')
    assert plan.operations[0].capability=='networking'
    assert plan.operations[0].name=='interfaces'

def test_quoted_file_path():
    plan=Parser().parse('lee "./mi carpeta/nota.txt"')
    assert plan.operations[0].arguments['path']=='./mi carpeta/nota.txt'

def test_asks_for_missing_service():
    assert Parser().parse('muestra el estado del servicio').clarification

def test_unknown_does_not_make_a_command():
    assert Parser().parse('haz algo mágico').clarification

def test_google_and_terminal_are_application_intents():
    assert Parser().parse('abre Google').operations[0].arguments['url']=='https://www.google.com'
    assert Parser().parse('abre una terminal').operations[0].arguments['name']=='terminal'

def test_common_desktop_apps_and_small_typo_are_recognized():
    parser = Parser()
    for request, expected in (
        ('abre PyCharm', 'pycharm'), ('abre pyhcarm', 'pycharm'),
        ('abre Software', 'software'), ('abre mapas', 'maps'),
    ):
        operation = parser.parse(request).operations[0]
        assert (operation.capability, operation.name) == ('browser', 'open_application')
        assert operation.arguments['name'] == expected

def test_gemini_cli_in_new_terminal_is_an_argv_launch():
    parser = Parser()
    for request in ('abre gemini cli en una nueva terminal}',
                    'ejecuta gemini cli en una nueva terminal',
                    'en otra terminal gemini cli', 'abre gemini'):
        operation = parser.parse(request).operations[0]
        assert (operation.capability, operation.name) == ('browser', 'open_application')
        assert operation.arguments == {'name': 'terminal', 'command': 'gemini'}
        assert operation.risk.value == 'high'

def test_explicit_argv_command_is_high_risk():
    from core.contracts import Risk
    op=Parser().parse('ejecuta comando: printf Hola').operations[0]
    assert op.name=='execute_command' and op.arguments['command']=='printf Hola' and op.risk==Risk.HIGH

def test_interface_conversation_is_not_a_network_request():
    assert Parser().parse('tu interfaz es muy fea').clarification

def test_open_site_in_requested_browser_and_metasploit():
    p=Parser()
    site=p.parse('abre github en firefox').operations[0]
    assert site.name=='open_url' and site.arguments=={'url':'https://github.com','browser':'firefox'}
    assert p.parse('abre metasploit').operations[0].arguments['name']=='metasploit'

def test_open_terminal_with_command_is_a_single_application_request():
    op=Parser().parse('abre una terminal y ejecuta msfconsole').operations[0]
    assert op.name=='open_application' and op.arguments=={'name':'terminal','command':'msfconsole'}

def test_local_ip_and_listening_ports_are_distinct_network_intents():
    p=Parser()
    assert p.parse('mi ip').operations[0].name=='local_addresses'
    assert p.parse('qué puertos tengo abiertos').operations[0].name=='listening_ports'

def test_natural_language_create_file_extracts_name_and_folder(tmp_path):
    plan=Parser().parse(f'necesito que crees un archivo que se llame hola.txt y lo pongas en mi carpeta "{tmp_path}"')
    op=plan.operations[0]
    assert op.capability=='filesystem' and op.name=='create'
    assert op.arguments['path']==str(tmp_path/'hola.txt')

def test_plain_text_file_name_gets_txt_extension(tmp_path):
    plan=Parser().parse(f'crea un archivo de texto que se llame hola en "{tmp_path}"')
    assert plan.operations[0].arguments['path']==str(tmp_path/'hola.txt')

def test_firefox_then_github_is_a_single_ordered_browser_launch():
    op=Parser().parse('puedes abrir firefox y luego abrir github por favor?').operations[0]
    assert op.name=='open_url'
    assert op.arguments=={'url':'https://github.com','browser':'firefox'}

def test_cybersecurity_dns_and_nmap_status_have_separate_intents():
    p=Parser()
    dns=p.parse('resuelve el DNS de example.com').operations[0]
    assert dns.name=='resolve_dns' and dns.arguments['host']=='example.com'
    assert p.parse('nmap está instalado?').operations[0].name=='scanner_status'

def test_time_and_google_search_intents():
    p=Parser()
    assert p.parse('qué hora es').operations[0].name=='time'
    from core.context import Context
    context=Context()
    ask=p.parse('quiero buscar algo en Google',context)
    assert ask.clarification and context.pending=={'kind':'web_search'}
    plan=p.resolve_pending('gatos naranjas',context)
    assert plan.operations[0].arguments['query']=='gatos naranjas'
    second_context=Context();p.parse('puedes buscar cosas en google?',second_context)
    followup=p.resolve_pending('estoy en una CLI, no puedo abrir el navegador, investígalo tú y dime qué encontraste',second_context)
    assert followup.clarification and not followup.operations

def test_file_name_followup_preserves_text_extension_and_path(tmp_path):
    from core.context import Context
    context=Context()
    plan=Parser().parse(f'crea un archivo de texto en "{tmp_path}"',context)
    assert plan.clarification and context.pending['directory']==str(tmp_path)
    followup=Parser().resolve_pending('quiero que hola sea el nombre del archivo',context)
    assert followup.operations[0].arguments['path']==str(tmp_path/'hola.txt')

def test_local_open_ports_take_priority_over_ip_interface_entities():
    p=Parser()
    for request in ('escanea mi localhost','escanea mi IP','no quiero interfaces quiero los puertos de mi IP'):
        plan=p.parse(request)
        assert plan.operations[0].capability=='networking' and plan.operations[0].name=='listening_ports'

def test_file_search_is_local_and_generic_logs_are_system_logs():
    p=Parser()
    op=p.parse('busca un archivo que se llame hola en la computadora').operations[0]
    assert (op.capability,op.name)==('filesystem','search_names')
    assert op.arguments['pattern']=='hola'
    assert op.arguments['path'] != '.'
    logs=p.parse('logs').operations[0]
    assert (logs.capability,logs.name)==('system','logs')

def test_capability_question_can_be_scoped_to_development():
    op=Parser().parse('sobre desarrollo que puedes hacer?').operations[0]
    assert op.capability=='assistant'
    assert op.arguments['category']=='development'

def test_file_creation_accepts_home_path_without_leading_slash():
    from core.context import Context
    context=Context()
    plan=Parser().parse('crea un archivo py en home/nocturne',context)
    assert plan.clarification
    created=Parser().resolve_pending('hola.py',context).operations[0]
    assert created.arguments['path']=='/home/nocturne/hola.py'

def test_ram_identity_date_and_move_intents(tmp_path):
    p=Parser()
    assert p.parse('cuánta RAM tengo').operations[0].name=='ram'
    assert p.parse('quién soy en este sistema').operations[0].name=='identity'
    assert p.parse('qué día es hoy').operations[0].arguments['include_date'] is True
    op=p.parse(f'mueve hola a "{tmp_path}"').operations[0]
    assert op.capability=='filesystem' and op.name=='move'
    assert op.arguments=={'source':'hola','destination':str(tmp_path)}

def test_math_requests_are_structured():
    p=Parser()
    assert p.parse('calcula 2 elevado a 8').operations[0].arguments['expression']=='(2**8)'
    assert p.parse('raíz cuadrada de 81').operations[0].arguments['expression']=='sqrt(81)'

def test_short_cpu_gpu_and_whois_requests_are_specific():
    p=Parser()
    assert p.parse('cpu').operations[0].name=='cpu_info'
    assert p.parse('gpu').operations[0].name=='gpu_info'
    whois=p.parse('ejecuta whois a la ip 157.32.23.1').operations[0]
    assert whois.capability=='cybersecurity' and whois.name=='whois_lookup'
    assert whois.arguments['target']=='157.32.23.1'

def test_process_and_service_intents_are_specific():
    p=Parser()
    assert p.parse('muestra los procesos activos').operations[0].name=='list'
    assert p.parse('qué proceso consume más RAM').operations[0].name=='memory_top'
    assert p.parse('muestra los últimos errores de nginx').operations[0].name=='logs'
    restart=p.parse('reinicia nginx').operations[0]
    assert restart.name=='change' and restart.arguments=={'name':'nginx','action':'restart'}
    assert p.parse('termina el proceso PID 2345').operations[0].arguments['pid']==2345

def test_search_github_user_is_returned_in_terminal_results():
    op=Parser().parse('abre github y busca el usuario nocturne-cybersecurity').operations[0]
    assert op.capability=='web' and op.name=='search'
    assert op.arguments['query']=='site:github.com nocturne-cybersecurity'
