"""Explicit local development helpers."""
import subprocess, shutil, sys, os, shlex
def python_version():return {'executable':sys.executable,'version':sys.version}
def git_status(path='.'):
    if not shutil.which('git'):raise FileNotFoundError('git is not installed')
    p=subprocess.run(['git','-C',path,'status','--short','--branch'],capture_output=True,text=True,timeout=10)
    if p.returncode:raise RuntimeError(p.stderr.strip())
    return p.stdout
def run_python(path,args=(),timeout=60):
    import shlex
    if isinstance(args,str):args=shlex.split(args)
    p=subprocess.run([sys.executable,path,*args],capture_output=True,text=True,timeout=timeout,shell=False)
    return {'exit_code':p.returncode,'stdout':p.stdout[:100000],'stderr':p.stderr[:100000]}
def clone(url,destination):
    if not shutil.which('git'):raise FileNotFoundError('git is not installed')
    p=subprocess.run(['git','clone','--',url,destination],capture_output=True,text=True,timeout=300)
    if p.returncode:raise RuntimeError(p.stderr.strip())
    return destination

def execute_command(command,timeout=30):
    """Run explicitly requested argv/pipeline; never pass text to a shell."""
    import shlex
    lexer=shlex.shlex(command,posix=True,punctuation_chars='|;&<>')
    lexer.whitespace_split=True
    lexer.commenters=''
    tokens=list(lexer)
    if not tokens:raise ValueError('No se indicó ningún comando')
    if any(token in {';', '&', '&&', '<', '>', '>>', '<<'} for token in tokens):
        raise ValueError('Solo se permiten comandos y tuberías con |; no se admite redirección ni encadenamiento shell.')
    raw_stages=[]
    current=[]
    for token in tokens:
        if token=='|':
            if not current:raise ValueError('La tubería contiene una etapa vacía.')
            raw_stages.append(current);current=[]
        else:current.append(token)
    if not current:raise ValueError('La tubería no puede terminar con |.')
    raw_stages.append(current)
    stages=[]
    for argv in raw_stages:
        resolved=shutil.which(argv[0])
        if not resolved:raise FileNotFoundError(f"No se encontró el ejecutable: {argv[0]}")
        stages.append([resolved,*argv[1:]])
    bounded_timeout=max(1,min(int(timeout),300))

    sudo_pwd = None
    if raw_stages[0][0] == 'sudo':
        check = subprocess.run(['sudo', '-n', 'true'], capture_output=True)
        if check.returncode != 0:
            import getpass
            try:
                sudo_pwd = getpass.getpass('[sudo] Contraseña: ')
            except (EOFError, KeyboardInterrupt):
                sudo_pwd = ''
            if '-S' not in stages[0]:
                stages[0] = [stages[0][0], '-S', *stages[0][1:]]

    if len(stages)==1:
        input_data = (sudo_pwd + '\n') if sudo_pwd is not None else None
        p=subprocess.run(stages[0],input=input_data,capture_output=True,text=True,timeout=bounded_timeout,shell=False)
        stderr_text = p.stderr[:100000]
        if p.returncode == 0 and stderr_text:
            lines = [line for line in stderr_text.splitlines() if not line.startswith('[sudo]')]
            stderr_text = '\n'.join(lines)
        return {'exit_code':p.returncode,'stdout':p.stdout[:100000],'stderr':stderr_text,'argv':raw_stages[0]}

    from core.pipeline import run_pipeline
    from execution.command import Command
    pipeline_cmds = []
    for idx, stage in enumerate(stages):
        cmd_stdin = (sudo_pwd + '\n') if (idx == 0 and sudo_pwd is not None) else None
        pipeline_cmds.append(Command(stage[0], stage[1:], stdin=cmd_stdin))
    result=run_pipeline(pipeline_cmds,timeout=bounded_timeout,output_limit=100000)
    failing_code=next((code for code in result['exit_codes'] if code!=0),0)
    clean_stderr = []
    for item in result['stderr']:
        if item:
            lines = [line for line in item.splitlines() if not line.startswith('[sudo]')]
            if lines:
                clean_stderr.append('\n'.join(lines))
    return {
        'exit_code':failing_code,
        'exit_codes':result['exit_codes'],
        'stdout':result['stdout'],
        'stderr':'\n'.join(clean_stderr)[:100000],
        'success':result['success'],
        'argv':raw_stages,
    }

def open_file(path):
    """Open an existing file with the desktop default or a local terminal editor."""
    from pathlib import Path
    target=Path(path).expanduser()
    if not target.is_file():raise FileNotFoundError(f'No existe un archivo regular en {target}')
    graphical=bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'))
    opener=shutil.which('xdg-open') if graphical else None
    if opener:
        subprocess.Popen([opener,str(target)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        return {'path':str(target),'opened_with':'aplicación predeterminada','interactive':False}
    configured=os.environ.get('VISUAL') or os.environ.get('EDITOR')
    candidates=[]
    if configured:
        requested=Path(shlex.split(configured)[0]).name if shlex.split(configured) else ''
        if requested in {'nano','vi','vim','nvim','micro','emacs'}:candidates.append([requested])
    candidates.extend([['nano'],['vi']])
    editor=next((shutil.which(item[0]) for item in candidates if item and shutil.which(item[0])),None)
    if not editor:raise FileNotFoundError('No hay sesión gráfica ni editor de terminal instalado (nano/vi).')
    command=next(item for item in candidates if item and shutil.which(item[0])==editor)
    subprocess.run([editor,*command[1:],str(target)],check=True,shell=False)
    return {'path':str(target),'opened_with':Path(editor).name,'interactive':True}

def compile_c(source, output=None, optimization='O2'):
    """Compile C code using gcc or clang."""
    from pathlib import Path
    src = Path(source).expanduser()
    if not src.exists():
        raise FileNotFoundError(f'Source file not found: {src}')
    
    compiler = shutil.which('gcc') or shutil.which('clang')
    if not compiler:
        raise FileNotFoundError('gcc or clang is not installed')
    
    if output is None:
        output = src.with_suffix('')
    
    cmd = [compiler, f'-{optimization}', str(src), '-o', str(output)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    
    return {
        'source': str(src),
        'output': str(output),
        'compiler': Path(compiler).name,
        'exit_code': result.returncode,
        'stdout': result.stdout,
        'stderr': result.stderr,
        'success': result.returncode == 0
    }

def compile_cpp(source, output=None, optimization='O2'):
    """Compile C++ code using g++ or clang++."""
    from pathlib import Path
    src = Path(source).expanduser()
    if not src.exists():
        raise FileNotFoundError(f'Source file not found: {src}')
    
    compiler = shutil.which('g++') or shutil.which('clang++')
    if not compiler:
        raise FileNotFoundError('g++ or clang++ is not installed')
    
    if output is None:
        output = src.with_suffix('')
    
    cmd = [compiler, f'-{optimization}', str(src), '-o', str(output)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    
    return {
        'source': str(src),
        'output': str(output),
        'compiler': Path(compiler).name,
        'exit_code': result.returncode,
        'stdout': result.stdout,
        'stderr': result.stderr,
        'success': result.returncode == 0
    }

def lint_python(path):
    """Lint Python code using pylint if available."""
    if not shutil.which('pylint'):
        raise FileNotFoundError('pylint is not installed. Install with: pip install pylint')
    
    from pathlib import Path
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f'Path not found: {p}')
    
    cmd = ['pylint', str(p)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    
    return {
        'path': str(p),
        'exit_code': result.returncode,
        'output': result.stdout,
        'stderr': result.stderr
    }

def format_python(path):
    """Format Python code using black if available."""
    if not shutil.which('black'):
        raise FileNotFoundError('black is not installed. Install with: pip install black')
    
    from pathlib import Path
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f'Path not found: {p}')
    
    cmd = ['black', str(p)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    
    return {
        'path': str(p),
        'exit_code': result.returncode,
        'output': result.stdout,
        'stderr': result.stderr,
        'reformatted': 'reformatted' in result.stdout.lower()
    }

def git_branch(path='.'):
    """Show current and all git branches."""
    if not shutil.which('git'):
        raise FileNotFoundError('git is not installed')
    
    result = subprocess.run(['git', '-C', path, 'branch', '-a'], 
                          capture_output=True, text=True, timeout=10)
    
    branches = []
    current = None
    for line in result.stdout.splitlines():
        if line.startswith('*'):
            current = line[1:].strip()
            branches.append({'name': current, 'current': True})
        else:
            branches.append({'name': line.strip(), 'current': False})
    
    return {'current': current, 'branches': branches}

def git_diff(path='.', file=None):
    """Show git diff."""
    if not shutil.which('git'):
        raise FileNotFoundError('git is not installed')
    
    cmd = ['git', '-C', path, 'diff']
    if file:
        cmd.append(file)
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    
    return {'path': path, 'file': file, 'diff': result.stdout}

def git_log(path='.', limit=10):
    """Show git commit history."""
    if not shutil.which('git'):
        raise FileNotFoundError('git is not installed')
    
    cmd = ['git', '-C', path, 'log', f'-{limit}', '--oneline', '--decorate']
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    
    commits = []
    for line in result.stdout.splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) >= 2:
            commits.append({'hash': parts[0], 'message': parts[1]})
    
    return {'path': path, 'commits': commits}

def git_stash(path='.'):
    """Stash current changes."""
    if not shutil.which('git'):
        raise FileNotFoundError('git is not installed')
    
    result = subprocess.run(['git', '-C', path, 'stash'], 
                          capture_output=True, text=True, timeout=10)
    
    return {'path': path, 'output': result.stdout, 'success': result.returncode == 0}

def git_checkout(path, branch_or_commit):
    """Checkout a branch or commit."""
    if not shutil.which('git'):
        raise FileNotFoundError('git is not installed')
    
    result = subprocess.run(['git', '-C', path, 'checkout', branch_or_commit], 
                          capture_output=True, text=True, timeout=10)
    
    return {
        'path': path,
        'target': branch_or_commit,
        'exit_code': result.returncode,
        'output': result.stdout,
        'error': result.stderr
    }

def run_tests(path='.', test_framework='pytest'):
    """Run tests using pytest or unittest."""
    from pathlib import Path
    p = Path(path).expanduser()
    
    if test_framework == 'pytest':
        if not shutil.which('pytest'):
            raise FileNotFoundError('pytest is not installed. Install with: pip install pytest')
        cmd = ['pytest', str(p), '-v']
    elif test_framework == 'unittest':
        cmd = [sys.executable, '-m', 'unittest', 'discover', str(p)]
    else:
        raise ValueError(f'Unsupported test framework: {test_framework}')
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    
    return {
        'path': str(p),
        'framework': test_framework,
        'exit_code': result.returncode,
        'output': result.stdout,
        'stderr': result.stderr
    }

def docker_build(path='.', tag=None):
    """Build a Docker image."""
    if not shutil.which('docker'):
        raise FileNotFoundError('docker is not installed')
    
    from pathlib import Path
    p = Path(path).expanduser()
    if not (p / 'Dockerfile').exists():
        raise FileNotFoundError('Dockerfile not found in the specified path')
    
    cmd = ['docker', 'build', str(p)]
    if tag:
        cmd.extend(['-t', tag])
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    
    return {
        'path': str(p),
        'tag': tag,
        'exit_code': result.returncode,
        'output': result.stdout,
        'stderr': result.stderr
    }

def ci_check(path='.'):
    """Check for CI/CD configuration files."""
    from pathlib import Path
    p = Path(path).expanduser()
    
    ci_files = {
        'github': ['.github/workflows/*.yml', '.github/workflows/*.yaml'],
        'gitlab': ['.gitlab-ci.yml'],
        'travis': ['.travis.yml'],
        'circle': ['.circleci/config.yml'],
        'jenkins': ['Jenkinsfile']
    }
    
    found = {}
    for ci_type, patterns in ci_files.items():
        for pattern in patterns:
            matches = list(p.glob(pattern))
            if matches:
                found[ci_type] = [str(m) for m in matches]
                break
    
    return {'path': str(p), 'ci_configs': found}


def git_add(path, files=None):
    """Stage files for commit."""
    if not shutil.which('git'):
        raise FileNotFoundError('git is not installed')
    
    cmd = ['git', '-C', path, 'add']
    if files:
        if isinstance(files, str):
            files = [files]
        cmd.extend(files)
    else:
        cmd.append('.')
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    
    return {'path': path, 'files': files, 'success': result.returncode == 0}


def git_commit(path, message):
    """Commit staged changes."""
    if not shutil.which('git'):
        raise FileNotFoundError('git is not installed')
    
    result = subprocess.run(['git', '-C', path, 'commit', '-m', message],
                          capture_output=True, text=True, timeout=10)
    
    return {
        'path': path,
        'message': message,
        'exit_code': result.returncode,
        'output': result.stdout,
        'success': result.returncode == 0
    }


def git_push(path, remote='origin', branch=None):
    """Push commits to remote repository."""
    if not shutil.which('git'):
        raise FileNotFoundError('git is not installed')
    
    cmd = ['git', '-C', path, 'push', remote]
    if branch:
        cmd.append(branch)
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    
    return {
        'path': path,
        'remote': remote,
        'branch': branch,
        'exit_code': result.returncode,
        'output': result.stdout,
        'error': result.stderr
    }


def git_pull(path, remote='origin', branch=None):
    """Pull changes from remote repository."""
    if not shutil.which('git'):
        raise FileNotFoundError('git is not installed')
    
    cmd = ['git', '-C', path, 'pull', remote]
    if branch:
        cmd.append(branch)
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    
    return {
        'path': path,
        'remote': remote,
        'branch': branch,
        'exit_code': result.returncode,
        'output': result.stdout,
        'error': result.stderr
    }


def git_merge(path, branch):
    """Merge a branch into current branch."""
    if not shutil.which('git'):
        raise FileNotFoundError('git is not installed')
    
    result = subprocess.run(['git', '-C', path, 'merge', branch],
                          capture_output=True, text=True, timeout=30)
    
    return {
        'path': path,
        'branch': branch,
        'exit_code': result.returncode,
        'output': result.stdout,
        'error': result.stderr,
        'success': result.returncode == 0
    }


def git_rebase(path, branch):
    """Rebase current branch onto another branch."""
    if not shutil.which('git'):
        raise FileNotFoundError('git is not installed')
    
    result = subprocess.run(['git', '-C', path, 'rebase', branch],
                          capture_output=True, text=True, timeout=60)
    
    return {
        'path': path,
        'branch': branch,
        'exit_code': result.returncode,
        'output': result.stdout,
        'error': result.stderr,
        'success': result.returncode == 0
    }


def git_list_conflicts(path='.'):
    """List files with merge conflicts."""
    if not shutil.which('git'):
        raise FileNotFoundError('git is not installed')
    
    result = subprocess.run(['git', '-C', path, 'diff', '--name-only', '--diff-filter=U'],
                          capture_output=True, text=True, timeout=10)
    
    conflicts = [f for f in result.stdout.splitlines() if f.strip()]
    
    return {'path': path, 'conflicts': conflicts}


def git_abort_merge(path='.'):
    """Abort an ongoing merge or rebase."""
    if not shutil.which('git'):
        raise FileNotFoundError('git is not installed')
    
    result = subprocess.run(['git', '-C', path, 'merge', '--abort'],
                          capture_output=True, text=True, timeout=10)
    
    return {'path': path, 'success': result.returncode == 0}
