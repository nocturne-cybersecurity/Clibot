"""Registration of implemented capabilities. Importing registers metadata only."""
from discovery.capability_registry import Capability, registry
from . import filesystem as fs, system, networking, services, development, browser, processes, translation, web_search, package_manager, monitoring, automation
from .cybersecurity import scanners, reconnaissance, reporting

def _add(name, description, operations, schemas, risks=None):
    registry.register(Capability(name,description,operations,schemas,risks or {k:'read_only' for k in operations}))

_add('filesystem','Local files and directories',{
 'list':fs.listing,'metadata':fs.metadata,'read':fs.read_text,'search_names':fs.search_names,'search_text':fs.search_text,
 'mkdir':fs.create_directory,'create':fs.create_file,'write':fs.write,'copy':fs.copy,'move':fs.move,'delete':fs.delete,'hash':fs.digest,
 'disk_usage':fs.disk_usage,'find_large':fs.find_large,'extract':fs.extract,'archive':fs.archive}, {
 'list':{'properties':{'path':'path','all_entries':'boolean'}},'metadata':{'required':['path'],'properties':{'path':'path'}},
 'read':{'required':['path'],'properties':{'path':'path','limit':'integer'}},'search_names':{'required':['path','pattern'],'properties':{'path':'path','pattern':'string'}},
 'search_text':{'required':['path','query'],'properties':{'path':'path','query':'string'}},'mkdir':{'required':['path'],'properties':{'path':'path'}},
 'create':{'required':['path'],'properties':{'path':'path','content':'string'}},'write':{'required':['path'],'properties':{'path':'path','content':'string'}},'copy':{'required':['source','destination'],'properties':{'source':'path','destination':'path'}},
 'move':{'required':['source','destination'],'properties':{'source':'path','destination':'path'}},'delete':{'required':['path'],'properties':{'path':'path'}},
 'hash':{'required':['path'],'properties':{'path':'path','algorithm':'string'}},'disk_usage':{'properties':{'path':'path'}},
 'find_large':{'properties':{'path':'path','minimum_bytes':'integer'}},'extract':{'required':['archive'],'properties':{'archive':'path','destination':'path'}},
 'archive':{'required':['source','destination'],'properties':{'source':'path','destination':'path'}}},
 {'delete':'moderate','move':'moderate','copy':'moderate','mkdir':'low','create':'moderate','write':'moderate','extract':'moderate','archive':'low'})
_add('system','Host and operating system inspection',{'info':system.info,'logs':system.logs,'time':system.current_time,'ram':system.ram,'identity':system.identity,'cwd':system.working_directory,'cpu_info':system.cpu_info,'gpu_info':system.gpu_info,'hardware_info':system.hardware_info},{'info':{'properties':{}},'logs':{'properties':{'lines':'integer'}},'time':{'properties':{'include_date':'boolean'}},'ram':{'properties':{}},'identity':{'properties':{}},'cwd':{'properties':{}},'cpu_info':{'properties':{}},'gpu_info':{'properties':{}},'hardware_info':{'properties':{}}})
_add('processes','Read process list, resource usage, and explicitly targeted signals',{
 'list':processes.listing,'memory_top':processes.memory_top,'inspect':processes.inspect,'terminate':processes.terminate,
 'cpu_top':processes.cpu_top,'io_top':processes.io_top,'process_temperatures':processes.process_temperatures,'detailed_inspect':processes.detailed_inspect,
 'find_by_name':processes.find_by_name,'is_running':processes.is_running,'by_user':processes.by_user,'count':processes.count,
 'zombies':processes.zombies,'stopped':processes.stopped,'children':processes.children,'parents':processes.parents,'tree':processes.tree,
 'cpu_hogs':processes.cpu_hogs,'memory_detail':processes.memory_detail,'top_threads':processes.top_threads,'open_files':processes.open_files,
 'connections_of':processes.connections_of,'limits_of':processes.limits_of,'details':processes.details,'by_port':processes.by_port,
 'send_signal':processes.send_signal,'suspend':processes.suspend,'resume':processes.resume,'renice':processes.renice,
 'terminate_by_name':processes.terminate_by_name},{
 'list':{'properties':{}},'memory_top':{'properties':{'limit':'integer'}},'inspect':{'required':['pid'],'properties':{'pid':'integer'}},
 'terminate':{'required':['pid'],'properties':{'pid':'integer','force':'boolean'}},'cpu_top':{'properties':{'limit':'integer','duration_seconds':'integer'}},
 'io_top':{'properties':{'limit':'integer'}},'process_temperatures':{'properties':{}},'detailed_inspect':{'required':['pid'],'properties':{'pid':'integer'}},
 'find_by_name':{'required':['name'],'properties':{'name':'string','exact':'boolean'}},'is_running':{'required':['name'],'properties':{'name':'string'}},
 'by_user':{'required':['user'],'properties':{'user':'string','limit':'integer'}},'count':{'properties':{}},'zombies':{'properties':{}},'stopped':{'properties':{}},
 'children':{'required':['pid'],'properties':{'pid':'integer'}},'parents':{'required':['pid'],'properties':{'pid':'integer'}},'tree':{'properties':{'limit':'integer'}},
 'cpu_hogs':{'properties':{'limit':'integer','interval':'float'}},'memory_detail':{'required':['pid'],'properties':{'pid':'integer'}},
 'top_threads':{'properties':{'limit':'integer'}},'open_files':{'required':['pid'],'properties':{'pid':'integer','limit':'integer'}},
 'connections_of':{'required':['pid'],'properties':{'pid':'integer'}},'limits_of':{'required':['pid'],'properties':{'pid':'integer'}},
 'details':{'required':['pid'],'properties':{'pid':'integer'}},'by_port':{'required':['port'],'properties':{'port':'integer'}},
 'send_signal':{'required':['pid'],'properties':{'pid':'integer','sig':'string'}},'suspend':{'required':['pid'],'properties':{'pid':'integer'}},
 'resume':{'required':['pid'],'properties':{'pid':'integer'}},'renice':{'required':['pid','nice'],'properties':{'pid':'integer','nice':'integer'}},
 'terminate_by_name':{'required':['name'],'properties':{'name':'string','force':'boolean','exact':'boolean','max_matches':'integer'}}},
 {'terminate':'high','send_signal':'high','suspend':'high','resume':'high','renice':'high','terminate_by_name':'high'})
from . import calculator
_add('calculator','Safe arithmetic and common mathematical functions',{'evaluate':calculator.evaluate},{'evaluate':{'required':['expression'],'properties':{'expression':'string'}}})
_add('networking','Read-only network inspection and connectivity',{
 'interfaces':networking.interfaces,'routes':networking.routes,'local_addresses':networking.local_addresses,'listening_ports':networking.listening_ports,
 'dns':networking.dns_config,'resolve':networking.resolve,'tcp_test':networking.tcp_test,'diagnose':networking.diagnose,
 'public_ip':networking.public_ip,'ping':networking.ping,'traceroute':networking.traceroute,'http_request':networking.http_request,
 'speed_test':networking.speed_test,'firewall_status':networking.firewall_status,'vpn_status':networking.vpn_status,
 'default_gateway':networking.default_gateway,'dns_servers':networking.dns_servers,'mac_addresses':networking.mac_addresses,
 'link_speed':networking.link_speed,'interface_stats':networking.interface_stats,'arp_table':networking.arp_table,
 'hosts_file':networking.hosts_file,'network_connections':networking.network_connections,'connection_summary':networking.connection_summary,
 'network_manager_connections':networking.network_manager_connections,'dns_lookup':networking.dns_lookup,'reverse_dns':networking.reverse_dns,
 'latency_check':networking.latency_check,'check_internet':networking.check_internet,'bandwidth_now':networking.bandwidth_now,
 'check_site_up':networking.check_site_up,'http_headers':networking.http_headers,'ssl_expiry':networking.ssl_expiry,
 'wifi_status':networking.wifi_status,'wifi_networks':networking.wifi_networks,'wifi_toggle':networking.wifi_toggle,
 'network_restart':networking.network_restart,'flush_dns':networking.flush_dns,'firewall_rules':networking.firewall_rules,
 'network_summary':networking.network_summary,'who_uses_port':networking.who_uses_port,'port_check_local':networking.port_check_local,
 'start_http_server':networking.start_http_server,'list_local_servers':networking.list_local_servers,'stop_http_server':networking.stop_http_server,
 'stop_all_http_servers':networking.stop_all_http_servers},{
 'interfaces':{'properties':{}},'routes':{'properties':{}},'local_addresses':{'properties':{}},'listening_ports':{'properties':{}},'dns':{'properties':{}},
 'resolve':{'required':['host'],'properties':{'host':'string'}},'tcp_test':{'required':['host','port'],'properties':{'host':'string','port':'integer','timeout':'integer'}},
 'diagnose':{'properties':{}},'public_ip':{'properties':{}},'ping':{'required':['host'],'properties':{'host':'string','count':'integer','timeout':'integer'}},
 'traceroute':{'required':['host'],'properties':{'host':'string','max_hops':'integer'}},'http_request':{'required':['url'],'properties':{'url':'string','method':'string','headers':'string','data':'string','timeout':'integer'}},
 'speed_test':{'properties':{'server':'string'}},'firewall_status':{'properties':{}},'vpn_status':{'properties':{}},'default_gateway':{'properties':{}},
 'dns_servers':{'properties':{}},'mac_addresses':{'properties':{}},'link_speed':{'properties':{}},'interface_stats':{'properties':{}},'arp_table':{'properties':{}},
 'hosts_file':{'properties':{}},'network_connections':{'properties':{'state':'string','limit':'integer'}},'connection_summary':{'properties':{}},
 'network_manager_connections':{'properties':{}},'dns_lookup':{'required':['host'],'properties':{'host':'string','record':'string'}},
 'reverse_dns':{'required':['ip'],'properties':{'ip':'string'}},'latency_check':{'properties':{'hosts':'array'}},'check_internet':{'properties':{}},
 'bandwidth_now':{'properties':{'interval':'float'}},'check_site_up':{'required':['url'],'properties':{'url':'string'}},'http_headers':{'required':['url'],'properties':{'url':'string'}},
 'ssl_expiry':{'required':['host'],'properties':{'host':'string','port':'integer'}},'wifi_status':{'properties':{}},'wifi_networks':{'properties':{'limit':'integer'}},
 'wifi_toggle':{'required':['on'],'properties':{'on':'boolean'}},'network_restart':{'properties':{}},'flush_dns':{'properties':{}},'firewall_rules':{'properties':{}},
 'network_summary':{'properties':{}},'who_uses_port':{'required':['port'],'properties':{'port':'integer'}},'port_check_local':{'required':['port'],'properties':{'port':'integer'}},
 'start_http_server':{'properties':{'directory':'string','port':'integer','bind':'string','kind':'string'}},'list_local_servers':{'properties':{}},
 'stop_http_server':{'properties':{'port':'integer','pid':'integer'}},'stop_all_http_servers':{'properties':{}}},{'start_http_server':'high','stop_http_server':'moderate','stop_all_http_servers':'moderate'})
_add('services','systemd service operations',{'status':services.status,'list':services.list_services,'logs':services.logs,'change':services.change},{'status':{'required':['name'],'properties':{'name':'string'}},'list':{'properties':{}},'logs':{'required':['name'],'properties':{'name':'string','lines':'integer'}},'change':{'required':['name','action'],'properties':{'name':'string','action':'string'}}},{'change':'high'})
_add('development','Local Python and Git operations',{
 'python_version':development.python_version,'run_python':development.run_python,'git_status':development.git_status,'execute_command':development.execute_command,'open_file':development.open_file,
 'git_branch':development.git_branch,'git_diff':development.git_diff,'git_log':development.git_log,'git_stash':development.git_stash,'git_checkout':development.git_checkout,
 'git_add':development.git_add,'git_commit':development.git_commit,'git_push':development.git_push,'git_pull':development.git_pull,'git_merge':development.git_merge,'git_rebase':development.git_rebase,'git_list_conflicts':development.git_list_conflicts,'git_abort_merge':development.git_abort_merge},{
 'python_version':{'properties':{}},'run_python':{'required':['path'],'properties':{'path':'path','args':'string','timeout':'integer'}},'git_status':{'properties':{'path':'path'}},'execute_command':{'required':['command'],'properties':{'command':'string','timeout':'integer'}},'open_file':{'required':['path'],'properties':{'path':'path'}},
 'git_branch':{'properties':{'path':'path'}},'git_diff':{'properties':{'path':'path','file':'string'}},'git_log':{'properties':{'path':'path','limit':'integer'}},'git_stash':{'properties':{'path':'path'}},'git_checkout':{'required':['path','branch_or_commit'],'properties':{'path':'path','branch_or_commit':'string'}},
 'git_add':{'required':['path'],'properties':{'path':'path','files':'array'}},'git_commit':{'required':['path','message'],'properties':{'path':'path','message':'string'}},'git_push':{'required':['path'],'properties':{'path':'path','remote':'string','branch':'string'}},'git_pull':{'required':['path'],'properties':{'path':'path','remote':'string','branch':'string'}},'git_merge':{'required':['path','branch'],'properties':{'path':'path','branch':'string'}},'git_rebase':{'required':['path','branch'],'properties':{'path':'path','branch':'string'}},'git_list_conflicts':{'properties':{'path':'path'}},'git_abort_merge':{'properties':{'path':'path'}}},
 {'run_python':'high','execute_command':'high','open_file':'moderate','git_commit':'moderate','git_push':'moderate','git_pull':'moderate','git_merge':'high','git_rebase':'high'})
_add('cybersecurity','Authorized security inspection and reporting',{
 'scan':scanners.scan,'resolve_dns':reconnaissance.resolve,'whois_lookup':reconnaissance.whois_lookup,'scanner_status':scanners.availability,'report':reporting.report},
 {'scan':{'required':['target','authorized'],'properties':{'target':'string','ports':'string','timeout':'integer','authorized':'boolean'}},
  'resolve_dns':{'required':['host'],'properties':{'host':'string'}},'whois_lookup':{'required':['target'],'properties':{'target':'string','timeout':'integer'}},'scanner_status':{'properties':{}},
  'report':{'required':['title','scope','findings','output'],'properties':{'title':'string','scope':'string','findings':'array','output':'path','format':'string'}}},
 {'scan':'high','resolve_dns':'low','report':'moderate'})
_add('browser','Desktop browser and application launch',{'open_url':browser.open_url,'open_application':browser.open_application},{'open_url':{'required':['url'],'properties':{'url':'string','browser':'string'}},'open_application':{'required':['name'],'properties':{'name':'string','command':'string'}}},{'open_url':'moderate','open_application':'low'})
_add('translation','Translate explicitly supplied text using Google Translate',{'translate':translation.translate},{'translate':{'required':['text','target_language'],'properties':{'text':'string','target_language':'string','source_language':'string','timeout':'integer'}}},{'translate':'moderate'})
_add('web','Search the web and show results in the terminal',{'search':web_search.search},{'search':{'required':['query'],'properties':{'query':'string','limit':'integer','timeout':'integer'}}},{'search':'low'})
_add('package_manager','Package management for apt, pip, and npm',{
 'apt_search':package_manager.apt_search,'apt_install':package_manager.apt_install,'apt_remove':package_manager.apt_remove,
 'apt_update':package_manager.apt_update,'apt_upgrade':package_manager.apt_upgrade,
 'pip_search':package_manager.pip_search,'pip_install':package_manager.pip_install,'pip_uninstall':package_manager.pip_uninstall,'pip_list':package_manager.pip_list,
 'npm_search':package_manager.npm_search,'npm_install':package_manager.npm_install,'npm_uninstall':package_manager.npm_uninstall,'npm_list':package_manager.npm_list},{
 'apt_search':{'required':['query'],'properties':{'query':'string'}},'apt_install':{'required':['packages'],'properties':{'packages':'array','assume_yes':'boolean'}},'apt_remove':{'required':['packages'],'properties':{'packages':'array','assume_yes':'boolean'}},
 'apt_update':{'properties':{}},'apt_upgrade':{'properties':{'assume_yes':'boolean'}},
 'pip_search':{'required':['query'],'properties':{'query':'string'}},'pip_install':{'required':['packages'],'properties':{'packages':'array','user':'boolean','upgrade':'boolean'}},'pip_uninstall':{'required':['packages'],'properties':{'packages':'array','assume_yes':'boolean'}},'pip_list':{'properties':{'outdated':'boolean'}},
 'npm_search':{'required':['query'],'properties':{'query':'string'}},'npm_install':{'required':['packages'],'properties':{'packages':'array','global_':'boolean','save':'boolean'}},'npm_uninstall':{'required':['packages'],'properties':{'packages':'array','global_':'boolean'}},'npm_list':{'properties':{'global_':'boolean'}}},
 {'apt_install':'high','apt_remove':'high','apt_upgrade':'high','pip_install':'high','pip_uninstall':'high','npm_install':'moderate','npm_uninstall':'moderate'})
_add('monitoring','Real-time system monitoring',{
 'process_stats':monitoring.get_process_stats,'memory_stats':monitoring.get_memory_stats,'cpu_stats':monitoring.get_cpu_stats,
 'disk_stats':monitoring.get_disk_stats,'network_stats':monitoring.get_network_stats,'system_load':monitoring.get_system_load,
 'get_cpu_usage':monitoring.get_cpu_usage,'get_iowait':monitoring.get_iowait,'get_load_vs_cores':monitoring.get_load_vs_cores,
 'get_context_switches':monitoring.get_context_switches,'get_pressure':monitoring.get_pressure,'get_memory_usage':monitoring.get_memory_usage,
 'get_vmstat':monitoring.get_vmstat,'get_memory_by_user':monitoring.get_memory_by_user,'get_swap_by_process':monitoring.get_swap_by_process,
 'get_oom_events':monitoring.get_oom_events,'get_top_cpu':monitoring.get_top_cpu,'get_top_memory':monitoring.get_top_memory,
 'get_process_states':monitoring.get_process_states,'get_zombies':monitoring.get_zombies,'get_file_descriptors':monitoring.get_file_descriptors,
 'get_disk_io':monitoring.get_disk_io,'get_inode_usage':monitoring.get_inode_usage,'get_disk_smart_hint':monitoring.get_disk_smart_hint,
 'get_network_throughput':monitoring.get_network_throughput,'get_network_errors':monitoring.get_network_errors,
 'get_connection_summary':monitoring.get_connection_summary,'get_established_connections':monitoring.get_established_connections,
 'get_temperatures':monitoring.get_temperatures,'get_fans':monitoring.get_fans,'get_battery':monitoring.get_battery,
 'get_gpu_stats':monitoring.get_gpu_stats,'get_uptime':monitoring.get_uptime,'get_entropy':monitoring.get_entropy,
 'get_logged_in_count':monitoring.get_logged_in_count,'get_failed_services_count':monitoring.get_failed_services_count,
 'get_recent_errors':monitoring.get_recent_errors,'watch_metric':monitoring.watch_metric,'check_thresholds':monitoring.check_thresholds,
 'health_check':monitoring.health_check,'snapshot':monitoring.snapshot},{
 'process_stats':{'properties':{'limit':'integer'}},'memory_stats':{'properties':{}},'cpu_stats':{'properties':{}},'disk_stats':{'properties':{}},'network_stats':{'properties':{}},'system_load':{'properties':{}},
 'get_cpu_usage':{'properties':{'interval':'float'}},'get_iowait':{'properties':{'interval':'float'}},'get_load_vs_cores':{'properties':{}},'get_context_switches':{'properties':{'interval':'float'}},'get_pressure':{'properties':{}},'get_memory_usage':{'properties':{}},'get_vmstat':{'properties':{}},'get_memory_by_user':{'properties':{'limit':'integer'}},'get_swap_by_process':{'properties':{'limit':'integer'}},'get_oom_events':{'properties':{'limit':'integer'}},'get_top_cpu':{'properties':{'limit':'integer'}},'get_top_memory':{'properties':{'limit':'integer'}},'get_process_states':{'properties':{}},'get_zombies':{'properties':{}},'get_file_descriptors':{'properties':{}},'get_disk_io':{'properties':{'interval':'float'}},'get_inode_usage':{'properties':{}},'get_disk_smart_hint':{'properties':{}},'get_network_throughput':{'properties':{'interval':'float'}},'get_network_errors':{'properties':{}},'get_connection_summary':{'properties':{}},'get_established_connections':{'properties':{'limit':'integer'}},'get_temperatures':{'properties':{}},'get_fans':{'properties':{}},'get_battery':{'properties':{}},'get_gpu_stats':{'properties':{}},'get_uptime':{'properties':{}},'get_entropy':{'properties':{}},'get_logged_in_count':{'properties':{}},'get_failed_services_count':{'properties':{}},'get_recent_errors':{'properties':{'lines':'integer'}},'watch_metric':{'properties':{'metric':'string','duration':'integer','interval':'float'}},'check_thresholds':{'properties':{'cpu':'integer','memory':'integer','disk':'integer','load_per_core':'float','temp':'integer','swap':'integer'}},'health_check':{'properties':{}},'snapshot':{'properties':{}}},{})
_add('automation','Automation for scripts, cron jobs, and systemd timers',{
 'create_script':automation.create_script,'list_cron_jobs':automation.list_cron_jobs,'add_cron_job':automation.add_cron_job,
 'remove_cron_job':automation.remove_cron_job,'list_systemd_timers':automation.list_systemd_timers,'create_systemd_timer':automation.create_systemd_timer,
 'enable_systemd_timer':automation.enable_systemd_timer,'disable_systemd_timer':automation.disable_systemd_timer},{
 'create_script':{'required':['path','content'],'properties':{'path':'path','content':'string','executable':'boolean'}},'list_cron_jobs':{'properties':{'user':'string'}},'add_cron_job':{'required':['cron_expression','command'],'properties':{'cron_expression':'string','command':'string','user':'string'}},'remove_cron_job':{'required':['cron_expression','command'],'properties':{'cron_expression':'string','command':'string','user':'string'}},'list_systemd_timers':{'properties':{}},'create_systemd_timer':{'required':['name','command','schedule'],'properties':{'name':'string','command':'string','schedule':'string','description':'string'}},'enable_systemd_timer':{'required':['name'],'properties':{'name':'string'}},'disable_systemd_timer':{'required':['name'],'properties':{'name':'string'}}},
 {'create_script':'moderate','add_cron_job':'high','remove_cron_job':'high','create_systemd_timer':'moderate','enable_systemd_timer':'moderate','disable_systemd_timer':'moderate'})

# Optional capabilities can be added as focused modules under capabilities/plugins/.
from .plugins import load as _load_plugins
_load_plugins(registry)
