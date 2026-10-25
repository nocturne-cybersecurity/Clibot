from capabilities import services

def test_service_command_uses_controlled_argument_vector(monkeypatch):
    seen={}
    class P:
        returncode=0;stdout='active';stderr=''
    def run(args,**kw):seen['args']=args;return P()
    monkeypatch.setattr(services.shutil,'which',lambda x:'/usr/bin/systemctl')
    monkeypatch.setattr(services.subprocess,'run',run)
    assert services.status('nginx')['stdout']=='active'
    assert seen['args']==['/usr/bin/systemctl','status','nginx','--no-pager']

def test_service_logs_use_bounded_journal_arguments(monkeypatch):
    seen={}
    class P:returncode=0;stdout='started';stderr=''
    monkeypatch.setattr(services.shutil,'which',lambda x:'/usr/bin/journalctl')
    monkeypatch.setattr(services.subprocess,'run',lambda args,**kw:(seen.update(args=args,kw=kw) or P()))
    assert services.logs('nginx',999)=='started'
    assert seen['args']==['/usr/bin/journalctl','-u','nginx','-n','500','--no-pager']
    assert seen['kw']['timeout']==20
