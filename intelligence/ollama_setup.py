"""Ollama and model installation helper for CLIBOT."""
import json
import os
import subprocess
import shutil
import sys
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

from interface.formatter import paint


class OllamaSetup:
    """Manages Ollama installation and Phi-3 Mini model setup."""
    
    CONFIG_DIR = Path.home() / '.config' / 'clibot'
    CONFIG_FILE = CONFIG_DIR / 'llm_setup.json'
    RECOMMENDED_MODEL = 'phi3:mini'
    
    def __init__(self):
        self.config_dir = self.CONFIG_DIR
        self.config_file = self.CONFIG_FILE
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def load_config(self):
        """Load LLM setup configuration."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {'asked': False, 'installed': False, 'model': None}
    
    def save_config(self, config):
        """Save LLM setup configuration."""
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def is_ollama_installed(self):
        """Check if Ollama is installed."""
        return shutil.which('ollama') is not None
    
    def is_ollama_running(self):
        """Check if Ollama daemon is running."""
        try:
            with urlopen('http://127.0.0.1:11434/api/tags', timeout=0.5) as response:
                return True
        except (URLError, TimeoutError):
            return False
    
    def is_model_installed(self, model=None):
        """Check if a model is installed."""
        model = model or self.RECOMMENDED_MODEL
        try:
            with urlopen('http://127.0.0.1:11434/api/tags', timeout=1) as response:
                data = json.loads(response.read().decode())
                models = [m.get('name') for m in data.get('models', [])]
                return model in models
        except (URLError, TimeoutError, json.JSONDecodeError):
            return False
    
    def _status_line(self, ok, label):
        mark = paint('●', 'green' if ok else 'yellow')
        return f"  {mark}  {label}"

    def _offer(self):
        """Draw the first-run model card. Rules stay instant either way."""
        installed = self.is_ollama_installed()
        running = installed and self.is_ollama_running()
        ready = running and self.is_model_installed()
        bar = paint('│', 'cyan')
        print()
        print(paint('╭─', 'cyan') + ' ' + paint('CLIBOT', 'bold') + paint('  ·  modelo local', 'muted'))
        print(bar)
        print(f"{bar}  Las respuestas normales salen al instante.")
        print(f"{bar}  Phi-3 Mini es opcional y solo se consulta")
        print(f"{bar}  cuando una frase no coincide con una regla.")
        print(bar)
        print(f"{bar}  {paint('Phi-3 Mini', 'bold')}{paint('   3.8B · ~2.3 GB · ~1.5 GB RAM', 'muted')}")
        print(f"{bar}  {paint('En CPU una frase del modelo tarda segundos.', 'muted')}")
        print(f"{bar}  {paint('Si tarda más de 4 s, CLIBOT sigue sin esperarlo.', 'muted')}")
        print(bar)
        print(bar + self._status_line(installed, 'Ollama instalado' if installed else 'Ollama no está instalado'))
        print(bar + self._status_line(running, 'Servicio activo' if running else 'Servicio detenido'))
        print(bar + self._status_line(ready, 'phi3:mini listo' if ready else 'phi3:mini todavía no está'))
        print(paint('╰─', 'cyan'))
        print()
        print('  ' + paint('s', 'green') + paint('      instalar Phi-3 Mini', 'muted'))
        print('  ' + paint('enter', 'green') + paint('  seguir sin modelo', 'muted'))
        print()

    def install_ollama(self):
        """Install Ollama using the official install script."""
        print(paint('  Instalando Ollama…', 'cyan'))
        
        try:
            # Detect OS
            if sys.platform == 'linux':
                # Linux install script
                cmd = ['curl', '-fsSL', 'https://ollama.com/install.sh', '|', 'sh']
                print(paint('  curl -fsSL https://ollama.com/install.sh | sh', 'muted'))
                subprocess.run('curl -fsSL https://ollama.com/install.sh | sh', shell=True, check=True)
            elif sys.platform == 'darwin':
                # macOS install
                cmd = ['brew', 'install', 'ollama']
                print(paint('  ' + ' '.join(cmd), 'muted'))
                subprocess.run(cmd, check=True)
            else:
                raise RuntimeError(f"Sistema operativo no soportado: {sys.platform}")
            
            print(paint('  Ollama instalado.', 'green'))
            return True
        except subprocess.CalledProcessError as e:
            print(paint(f'  No pude instalar Ollama: {e}', 'red'))
            return False
        except Exception as e:
            print(paint(f'  No pude instalar Ollama: {e}', 'red'))
            return False
    
    def start_ollama(self):
        """Start Ollama daemon."""
        print(paint('  Arrancando Ollama…', 'cyan'))
        try:
            # Start in background
            subprocess.Popen(['ollama', 'serve'], 
                          stdout=subprocess.DEVNULL, 
                          stderr=subprocess.DEVNULL,
                          start_new_session=True)
            
            # Wait for it to be ready
            import time
            for i in range(10):
                time.sleep(1)
                if self.is_ollama_running():
                    print(paint('  Ollama está activo.', 'green'))
                    return True
            
            print(paint('  Ollama tardó en responder. Sigo de todos modos.', 'yellow'))
            return True
        except Exception as e:
            print(paint(f'  No pude arrancar Ollama: {e}', 'red'))
            return False
    
    def pull_model(self, model=None):
        """Pull a model from Ollama."""
        model = model or self.RECOMMENDED_MODEL
        print(paint(f'  Descargando {model}…', 'cyan'))
        print(paint('  Unos minutos. El archivo pesa ~2.3 GB.', 'muted'))
        
        try:
            process = subprocess.Popen(
                ['ollama', 'pull', model],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            # Show progress
            for line in process.stdout:
                print(f"   {line.strip()}")
            
            process.wait()
            
            if process.returncode == 0:
                print(paint(f'  {model} instalado.', 'green'))
                return True
            else:
                print(paint(f'  La descarga terminó con código {process.returncode}.', 'red'))
                return False
        except Exception as e:
            print(paint(f'  No pude descargar el modelo: {e}', 'red'))
            return False
    
    def setup_complete(self):
        """Check if setup is complete."""
        config = self.load_config()
        return config.get('installed', False) and self.is_model_installed()
    
    def should_ask(self):
        """Check if we should ask the user about LLM setup."""
        config = self.load_config()
        return not config.get('asked', False)
    
    def mark_asked(self):
        """Mark that we've asked the user."""
        config = self.load_config()
        config['asked'] = True
        self.save_config(config)
    
    def mark_installed(self, model=None):
        """Mark that LLM is installed."""
        config = self.load_config()
        config['installed'] = True
        config['model'] = model or self.RECOMMENDED_MODEL
        self.save_config(config)
    
    def interactive_setup(self):
        """Interactive setup process."""
        config = self.load_config()
        
        if config.get('installed', False):
            if self.is_model_installed(config.get('model')):
                return True
            # Model was marked installed but not actually installed
            config['installed'] = False
            self.save_config(config)
        
        self._offer()
        
        while True:
            response = input(paint('  instalar? ', 'cyan') + paint('[s/N] ', 'muted')).strip().lower()
            
            if response in ('n', 'no', '', 'exit'):
                print()
                print(paint('  Listo.', 'green') + ' CLIBOT responde al instante, sin modelo.')
                print(paint('  Más tarde:', 'muted') + ' ollama pull phi3:mini')
                print()
                self.mark_asked()
                return False
            
            if response in ('s', 'si', 'yes', 'y'):
                break
            
            print(paint('  s para instalar, enter para seguir.', 'muted'))
        
        self.mark_asked()
        
        # Check if Ollama is installed
        if not self.is_ollama_installed():
            print()
            print(paint('  Falta Ollama, el programa que ejecuta el modelo.', 'yellow'))
            response = input(paint('  instalar Ollama? ', 'cyan') + paint('[s/N] ', 'muted')).strip().lower()
            
            if response in ('s', 'si', 'yes', 'y'):
                if not self.install_ollama():
                    print(paint('  Sigo sin modelo. Las reglas locales siguen activas.', 'muted'))
                    return False
            else:
                print(paint('  Cuando quieras: https://ollama.com', 'muted'))
                return False
        
        # Check if Ollama is running
        if not self.is_ollama_running():
            if not self.start_ollama():
                print(paint('  No pude arrancar Ollama. Sigo con reglas locales.', 'muted'))
                return False
        
        # Pull the model
        if not self.pull_model():
            return False
        
        self.mark_installed()
        print()
        print(paint('  Phi-3 Mini quedó listo.', 'green'))
        print(paint('  El chat de siempre sigue siendo inmediato.', 'muted'))
        print(paint('  El modelo solo entra si una frase no tiene regla.', 'muted'))
        print()
        return True


def check_and_prompt():
    """Check if we should prompt for LLM setup and do it if needed."""
    setup = OllamaSetup()
    
    if setup.should_ask():
        setup.interactive_setup()
    
    return setup.setup_complete()
