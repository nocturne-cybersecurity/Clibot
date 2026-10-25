from capabilities.networking import tcp_test

def test_tcp_test_reports_closed_port_without_throwing():
    result=tcp_test('127.0.0.1',1,timeout=1)
    assert result['reachable'] is False and result['port']==1

def test_procfs_interface_and_route_fallbacks_work_without_netlink(monkeypatch):
    from capabilities import networking
    def denied(*args,**kwargs):raise RuntimeError('netlink unavailable')
    monkeypatch.setattr(networking,'_run',denied)
    interfaces=networking.interfaces()
    assert interfaces and any(row['interface']=='lo' for row in interfaces)
    assert isinstance(networking.routes(),list)
    assert isinstance(networking.listening_ports(),list)
