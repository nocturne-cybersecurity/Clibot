"""Child process environment helpers."""
import os, shutil
def environment(overrides=None): return {**os.environ,**(overrides or {}),'LC_ALL':(overrides or {}).get('LC_ALL',os.environ.get('LC_ALL','C.UTF-8'))}
def resolve(executable): return shutil.which(executable)
