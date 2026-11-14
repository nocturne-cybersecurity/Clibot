from capabilities import browser

def test_url_launch_reports_destination_not_internal_pid(monkeypatch):
    monkeypatch.setenv('DISPLAY', ':1')
    monkeypatch.setattr(browser.shutil,'which',lambda name:'/usr/bin/firefox' if name=='firefox' else None)
    seen={}
    monkeypatch.setattr(browser.subprocess,'Popen',lambda argv,**kw:seen.update(argv=argv,kwargs=kw))
    response=browser.open_url('https://github.com','firefox')
    assert seen['argv']==['/usr/bin/firefox','https://github.com']
    assert 'github.com' in response and 'PID' not in response

def test_terminal_can_launch_an_explicit_app_without_shell(monkeypatch):
    monkeypatch.setenv('WAYLAND_DISPLAY','wayland-0')
    monkeypatch.setattr(browser.shutil,'which',lambda name:{'x-terminal-emulator':'/usr/bin/x-terminal-emulator','msfconsole':'/usr/bin/msfconsole'}.get(name))
    seen={}
    monkeypatch.setattr(browser.subprocess,'Popen',lambda argv,**kw:seen.update(argv=argv,kwargs=kw))
    message=browser.open_application('terminal','msfconsole')
    assert seen['argv']==['/usr/bin/x-terminal-emulator','-e','/usr/bin/msfconsole']
    assert seen['kwargs'].get('shell') is not True and 'terminal' in message


def test_gemini_cli_starts_in_terminal_as_argument_vector(monkeypatch):
    monkeypatch.setenv('WAYLAND_DISPLAY', 'wayland-0')
    monkeypatch.setattr(browser.shutil, 'which', lambda name: {
        'x-terminal-emulator': '/usr/bin/x-terminal-emulator', 'gemini': '/usr/local/bin/gemini',
    }.get(name))
    seen = {}
    monkeypatch.setattr(browser.subprocess, 'Popen', lambda argv, **kwargs: seen.update(argv=argv, kwargs=kwargs))
    response = browser.open_application('terminal', 'gemini')
    assert seen['argv'] == ['/usr/bin/x-terminal-emulator', '-e', '/usr/local/bin/gemini']
    assert seen['kwargs'].get('shell') is not True
    assert 'gemini' in response


def test_known_apps_launch_by_desktop_entry(monkeypatch, tmp_path):
    desktop = tmp_path / 'example-editor.desktop'
    desktop.write_text('[Desktop Entry]\nType=Application\nName[es]=Editor de pruebas\n'
                       'Name=Test Editor\nExec=/usr/bin/test-editor %F\n')
    monkeypatch.setenv('DISPLAY', ':1')
    monkeypatch.setattr(browser, '_application_roots', lambda: [tmp_path])
    monkeypatch.setattr(browser.shutil, 'which', lambda name: '/usr/bin/gtk-launch' if name == 'gtk-launch' else None)
    seen = {}
    monkeypatch.setattr(browser.subprocess, 'Popen', lambda argv, **kwargs: seen.update(argv=argv, kwargs=kwargs))
    assert browser.open_application('test editor') == 'Envié al escritorio la solicitud para abrir Editor de pruebas.'
    assert seen['argv'] == ['/usr/bin/gtk-launch', 'example-editor']
    assert seen['kwargs']['start_new_session'] is True


def test_open_application_explains_missing_graphical_session(monkeypatch):
    monkeypatch.delenv('DISPLAY', raising=False)
    monkeypatch.delenv('WAYLAND_DISPLAY', raising=False)
    try:
        browser.open_application('pycharm')
    except RuntimeError as exc:
        assert 'sesión gráfica' in str(exc)
    else:
        raise AssertionError('expected a clear graphical-session error')


def test_close_application_targets_only_known_exact_process(monkeypatch):
    seen={}
    monkeypatch.setattr('capabilities.processes.find_by_name',
                        lambda name,exact: {'processes':[{'pid':123}] if name=='chrome' else []})
    monkeypatch.setattr('capabilities.processes.terminate_by_name',
                        lambda name,**kwargs: (seen.update(name=name,kwargs=kwargs) or {'terminated':[123],'failed':[]}))
    assert browser.close_application('Google Chrome')=='Solicité el cierre de Google Chrome (1 proceso(s)).'
    assert seen=={'name':'chrome','kwargs':{'exact':True,'max_matches':50}}


def test_close_application_rejects_unrecognized_process_name():
    import pytest
    with pytest.raises(ValueError,match='No encontré'):
        browser.close_application('systemd')


def test_close_application_resolves_other_installed_desktop_apps(monkeypatch, tmp_path):
    seen={}
    desktop=tmp_path/'libreoffice.desktop'
    entry={'Exec':'/usr/bin/libreoffice --writer %U','StartupWMClass':'libreoffice'}
    monkeypatch.setattr(browser,'_find_desktop_entry',lambda _name:(desktop,'LibreOffice',entry))
    monkeypatch.setattr('capabilities.processes.find_by_name',
                        lambda name,exact:{'processes':[{'pid':321}] if name=='libreoffice' else []})
    monkeypatch.setattr('capabilities.processes.terminate_by_name',
                        lambda name,**kwargs:(seen.update(name=name,kwargs=kwargs) or {'terminated':[321],'failed':[]}))
    assert 'LibreOffice' in browser.close_application('LibreOffice')
    assert seen['name']=='libreoffice'


def test_application_request_reaches_launcher_after_confirmation(monkeypatch):
    from core.assistant import Assistant

    monkeypatch.setenv('DISPLAY', ':1')
    assistant = Assistant(confirm=lambda _prompt: (_ for _ in ()).throw(
        AssertionError('opening a requested app should not require confirmation')))
    launched = []
    monkeypatch.setitem(assistant.registry.get('browser').operations, 'open_application',
                        lambda name, **_: launched.append(name) or f'Abrí {name}.')
    response = assistant.handle('abre PyCharm')
    assert response['results'][0].success
    assert launched == ['pycharm']


def test_close_app_request_is_dispatched_without_confirmation(monkeypatch):
    from core.assistant import Assistant

    prompts=[]
    assistant=Assistant(confirm=lambda prompt: prompts.append(prompt) or 'yes')
    closed=[]
    monkeypatch.setitem(assistant.registry.get('browser').operations,'close_application',
                        lambda name: closed.append(name) or f'Solicité el cierre de {name}.')
    response=assistant.handle('cierra chrome')
    assert response['results'][0].success
    assert closed==['chrome']
    assert prompts==[]
