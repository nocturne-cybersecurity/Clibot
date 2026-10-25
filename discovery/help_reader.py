"""Bounded local tool help inspection; output is treated as data."""
import shutil, subprocess
def read_help(name,limit=12000,timeout=3):
    exe=shutil.which(name)
    if not exe:raise FileNotFoundError(f'{name} is not installed')
    try:p=subprocess.run([exe,'--help'],capture_output=True,text=True,timeout=timeout)
    except subprocess.TimeoutExpired as e:raise TimeoutError(f'{name} help timed out') from e
    return (p.stdout or p.stderr)[:limit]
