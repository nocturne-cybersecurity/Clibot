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
