"""Structured subprocess pipelines with bounded output and cleanup."""
import subprocess, time, tempfile
from execution.command import Command
class PipelineError(RuntimeError): pass
def run_pipeline(commands,timeout=20,output_limit=1_000_000):
    if not commands: raise ValueError('Pipeline must contain a stage')
    processes=[]; previous=None; started=time.monotonic(); errors=[]; final_output=tempfile.TemporaryFile()
    try:
        for index,command in enumerate(commands):
            if not isinstance(command,Command): raise TypeError('Pipeline stages must be Command objects')
            error_file=tempfile.TemporaryFile(); errors.append(error_file)
            output=final_output if index==len(commands)-1 else subprocess.PIPE
            if index == 0 and command.stdin is not None:
                stdin_stream = subprocess.PIPE
            else:
                stdin_stream = previous.stdout if previous else subprocess.DEVNULL
            proc=subprocess.Popen([command.executable,*command.arguments],stdin=stdin_stream,stdout=output,stderr=error_file,cwd=command.cwd,env={**__import__('os').environ,**command.environment},shell=False)
            if index == 0 and command.stdin is not None and proc.stdin:
                proc.stdin.write(command.stdin.encode('utf-8'))
                proc.stdin.close()
            if previous: previous.stdout.close()
            processes.append(proc); previous=proc
        for proc in processes:proc.wait(timeout=max(.01,timeout-(time.monotonic()-started)))
        final_output.seek(0); output=final_output.read(output_limit+1); codes=[p.returncode for p in processes]
        stderr=[]
        for stream in errors:
            stream.seek(0);stderr.append(stream.read(output_limit).decode(errors='replace'))
        return {'stdout':output[:output_limit].decode(errors='replace'),'stderr':stderr,'exit_codes':codes,'success':all(c==0 for c in codes),'truncated':len(output)>output_limit}
    except Exception:
        for p in processes:
            if p.poll() is None:p.kill()
        for p in processes:p.wait()
        raise
    finally:
        final_output.close()
        for stream in errors:stream.close()
