"""Capture file inspection and bounded tcpdump capture."""
import shutil, subprocess
def availability():return {x:shutil.which(x) for x in ('tcpdump','tshark')}
def capture(interface,duration=10,output='/tmp/llmah-capture.pcap'):
    if not 1<=int(duration)<=60:raise ValueError('Capture duration must be between 1 and 60 seconds')
    exe=shutil.which('tcpdump')
    if not exe:raise FileNotFoundError('tcpdump is not installed')
    p=subprocess.run([exe,'-i',interface,'-G',str(duration),'-W','1','-w',output],capture_output=True,text=True,timeout=duration+5)
    if p.returncode:raise RuntimeError(p.stderr.strip())
    return output
def inspect(path):
    exe=shutil.which('tshark')
    if not exe:raise FileNotFoundError('tshark is not installed')
    return subprocess.run([exe,'-r',path,'-q','-z','io,stat,0'],capture_output=True,text=True,timeout=30).stdout
