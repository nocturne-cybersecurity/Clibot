"""Read-only block device and mount inspection."""
import shutil, subprocess
def _read(args):
    exe=shutil.which(args[0])
    if not exe:raise FileNotFoundError(f'{args[0]} is unavailable')
    p=subprocess.run([exe,*args[1:]],capture_output=True,text=True,timeout=10)
    if p.returncode:raise RuntimeError(p.stderr.strip())
    return p.stdout
def devices():return _read(['lsblk','-J','-o','NAME,SIZE,FSTYPE,MOUNTPOINTS,UUID,TYPE'])
def mounts():return _read(['findmnt','-J'])
def space():return _read(['df','-hT'])
