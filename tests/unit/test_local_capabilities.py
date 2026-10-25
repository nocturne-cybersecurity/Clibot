from capabilities import development, processes, system

def test_open_file_uses_desktop_default_without_a_shell(tmp_path,monkeypatch):
    target=tmp_path/'hello.txt';target.write_text('hello')
    calls=[]
    monkeypatch.setenv('DISPLAY',':1')
    monkeypatch.setattr(development.shutil,'which',lambda name:'/usr/bin/xdg-open' if name=='xdg-open' else None)
    monkeypatch.setattr(development.subprocess,'Popen',lambda args,**kw:calls.append((args,kw)))
    result=development.open_file(target)
    assert result['path']==str(target) and result['interactive'] is False
    assert calls[0][0]==['/usr/bin/xdg-open',str(target)]

def test_open_file_uses_only_known_terminal_editors(tmp_path,monkeypatch):
    target=tmp_path/'hello.txt';target.write_text('hello')
    calls=[]
    monkeypatch.delenv('DISPLAY',raising=False);monkeypatch.delenv('WAYLAND_DISPLAY',raising=False)
    monkeypatch.setenv('EDITOR','nano')
    monkeypatch.setattr(development.shutil,'which',lambda name:'/usr/bin/'+name if name in {'nano','xdg-open'} else None)
    monkeypatch.setattr(development.subprocess,'run',lambda args,**kw:calls.append((args,kw)))
    assert development.open_file(target)['opened_with']=='nano'
    assert calls[0][0]==['/usr/bin/nano',str(target)] and calls[0][1]['shell'] is False

def test_terminate_targets_only_the_requested_pid(monkeypatch):
    signals=[]
    monkeypatch.setattr(processes.os,'kill',lambda pid,sig:signals.append((pid,sig)))
    result=processes.terminate(4321)
    assert result['pid']==4321 and signals[0][0]==4321

def test_system_ram_and_time_return_local_observations():
    ram=system.ram();clock=system.current_time()
    assert ram['total_gib']>0 and ram['available_gib']>=0
    assert clock['time'] and clock['date'] and clock['timezone']
