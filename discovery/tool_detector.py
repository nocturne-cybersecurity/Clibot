"""Local executable discovery; inspection never runs a tool."""
import shutil
_cache={}
def detect(name, refresh=False):
    if refresh or name not in _cache: _cache[name]=shutil.which(name)
    return {'name':name,'available':_cache[name] is not None,'path':_cache[name]}
def available(name): return detect(name)['available']
def invalidate(name=None): _cache.clear() if name is None else _cache.pop(name,None)
def inspect(name):
    item=detect(name)
    if item['available']:
        import os
        item['usable']=os.access(item['path'],os.X_OK)
        item['reason']=None if item['usable'] else 'Executable is not accessible'
    else:item['usable']=False;item['reason']='Executable not found in PATH'
    return item
