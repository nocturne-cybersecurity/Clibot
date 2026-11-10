"""Voice model setup helper for CLIBOT."""
import json
import os
import subprocess
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

from interface.formatter import paint


class VoiceSetup:
    """Manages Vosk voice model installation."""
    
    CONFIG_DIR = Path.home() / '.config' / 'clibot'
    CONFIG_FILE = CONFIG_DIR / 'voice_setup.json'
    MODEL_DIR = Path.home() / '.cache' / 'clibot'
    MODEL_NAME = 'vosk-model-small-es-0.42'
    MODEL_URL = 'https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip'
    
    def __init__(self):
        self.config_dir = self.CONFIG_DIR
        self.config_file = self.CONFIG_FILE
        self.model_dir = self.MODEL_DIR
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.model_dir.mkdir(parents=True, exist_ok=True)
    
    def load_config(self):
        """Load voice setup configuration."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {'asked': False, 'installed': False}
    
    def save_config(self, config):
        """Save voice setup configuration."""
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def is_model_downloaded(self):
        """Check if the voice model is downloaded."""
        model_path = self.model_dir / self.MODEL_NAME
        return model_path.is_dir() and (model_path / 'model').exists()
    
    def is_vosk_installed(self):
        """Check if Vosk is installed."""
        try:
            import vosk
            return True
        except ImportError:
            return False
    
    def _status_line(self, ok, label):
        mark = paint('●', 'green' if ok else 'yellow')
        return f"  {mark}  {label}"
    
    def _offer(self):
        """Draw the first-run voice model card."""
        installed = self.is_vosk_installed()
        downloaded = self.is_model_downloaded()
        ready = installed and downloaded
        bar = paint('│', 'cyan')
        print()
        print(paint('╭─', 'cyan') + ' ' + paint('CLIBOT', 'bold') + paint('  ·  reconocimiento de voz', 'muted'))
        print(bar)
        print(f"{bar}  Dicta comandos en español directamente al micrófono.")
        print(f"{bar}  El modelo Vosk funciona 100% offline y local.")
        print(bar)
        print(f"{bar}  {paint('Modelo español pequeño', 'bold')}{paint('   ~50 MB · CPU ligera', 'muted')}")
        print(f"{bar}  {paint('Ideal para comandos simples como "abre chrome"', 'muted')}")
        print(bar)
        print(bar + self._status_line(installed, 'Vosk instalado' if installed else 'Vosk no está instalado'))
        print(bar + self._status_line(downloaded, 'Modelo descargado' if downloaded else 'Modelo todavía no está'))
        print(paint('╰─', 'cyan'))
        print()
        print('  ' + paint('s', 'green') + paint('      instalar modelo de voz', 'muted'))
        print('  ' + paint('enter', 'green') + paint('  seguir sin voz', 'muted'))
        print()
    
    def install_vosk(self):
        """Install Vosk package."""
        print(paint('  Instalando Vosk…', 'cyan'))
        
        try:
            # Detectar si estamos en un entorno virtual
            if sys.prefix != sys.base_prefix:
                pip = [sys.executable, '-m', 'pip', 'install', 'vosk>=0.3.45']
            else:
                pip = ['pip', 'install', 'vosk>=0.3.45']
            
            subprocess.run(pip, check=True)
            print(paint('  Vosk instalado.', 'green'))
            return True
        except subprocess.CalledProcessError as e:
            print(paint(f'  No pude instalar Vosk: {e}', 'red'))
            print(paint('  Instálalo manualmente: pip install vosk>=0.3.45', 'muted'))
            return False
    
    def download_model(self):
        """Download the Spanish voice model."""
        model_path = self.model_dir / self.MODEL_NAME
        zip_path = self.model_dir / f'{self.MODEL_NAME}.zip'
        
        print(paint(f'  Descargando modelo de voz español…', 'cyan'))
        print(paint('  Tamaño: ~50 MB', 'muted'))
        
        try:
            # Descargar con barra de progreso
            def reporthook(count, block_size, total_size):
                percent = int(count * block_size * 100 / total_size) if total_size > 0 else 0
                sys.stdout.write(f'\r  Progreso: {percent}%')
                sys.stdout.flush()
            
            urllib.request.urlretrieve(self.MODEL_URL, zip_path, reporthook)
            print()  # Nueva línea después del progreso
            
            # Extraer
            print(paint('  Extrayendo modelo…', 'cyan'))
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.model_dir)
            
            # Limpiar zip
            zip_path.unlink()
            
            print(paint(f'  Modelo descargado en {model_path}', 'green'))
            return True
            
        except Exception as e:
            print(paint(f'  No pude descargar el modelo: {e}', 'red'))
            print(paint('  Descárgalo manualmente:', 'muted'))
            print(paint(f'  cd {self.model_dir}', 'muted'))
            print(paint(f'  wget {self.MODEL_URL}', 'muted'))
            print(paint(f'  unzip {self.MODEL_NAME}.zip', 'muted'))
            print(paint(f'  rm {self.MODEL_NAME}.zip', 'muted'))
            # Limpiar si se descargó parcialmente
            if zip_path.exists():
                zip_path.unlink()
            return False
    
    def check_alsa(self):
        """Check if ALSA (arecord) is installed."""
        return shutil.which('arecord') is not None
    
    def should_ask(self):
        """Check if we should ask the user about voice setup."""
        config = self.load_config()
        return not config.get('asked', False)
    
    def mark_asked(self):
        """Mark that we've asked the user."""
        config = self.load_config()
        config['asked'] = True
        self.save_config(config)
    
    def mark_installed(self):
        """Mark that voice is installed."""
        config = self.load_config()
        config['installed'] = True
        config['auto_enable'] = True  # Auto-enable /micro on first run
        self.save_config(config)
    
    def interactive_setup(self):
        """Interactive setup process."""
        config = self.load_config()
        
        if config.get('installed', False) and self.is_model_downloaded():
            return True
        
        self._offer()
        
        while True:
            response = input(paint('  instalar? ', 'cyan') + paint('[s/N] ', 'muted')).strip().lower()
            
            if response in ('n', 'no', '', 'exit'):
                print()
                print(paint('  Listo.', 'green') + ' CLIBOT funcionará sin reconocimiento de voz.')
                print(paint('  Más tarde:', 'muted') + ' /micro on para configurar la voz.')
                print()
                self.mark_asked()
                return False
            
            if response in ('s', 'si', 'yes', 'y'):
                break
            
            print(paint('  s para instalar, enter para seguir.', 'muted'))
        
        self.mark_asked()
        
        # Check if Vosk is installed
        if not self.is_vosk_installed():
            print()
            print(paint('  Falta Vosk, la librería de reconocimiento de voz.', 'yellow'))
            response = input(paint('  instalar Vosk? ', 'cyan') + paint('[s/N] ', 'muted')).strip().lower()
            
            if response in ('s', 'si', 'yes', 'y'):
                if not self.install_vosk():
                    print(paint('  Sigo sin voz. El resto de CLIBOT sigue funcionando.', 'muted'))
                    return False
            else:
                print(paint('  Instálalo manualmente: pip install vosk>=0.3.45', 'muted'))
                return False
        
        # Check if ALSA is installed (Linux only)
        if sys.platform == 'linux' and not self.check_alsa():
            print()
            print(paint('  Falta arecord (ALSA) para capturar audio del micrófono.', 'yellow'))
            response = input(paint('  instalar alsa-utils? ', 'cyan') + paint('[s/N] ', 'muted')).strip().lower()
            
            if response in ('s', 'si', 'yes', 'y'):
                try:
                    subprocess.run(['sudo', 'apt', 'install', '-y', 'alsa-utils'], check=True)
                    print(paint('  alsa-utils instalado.', 'green'))
                except subprocess.CalledProcessError:
                    print(paint('  No pude instalar alsa-utils.', 'red'))
                    print(paint('  Instálalo manualmente: sudo apt install alsa-utils', 'muted'))
                    return False
            else:
                print(paint('  Instálalo manualmente: sudo apt install alsa-utils', 'muted'))
                return False
        
        # Download the model
        if not self.download_model():
            return False
        
        self.mark_installed()
        print()
        print(paint('  Modelo de voz listo.', 'green'))
        print(paint('  Usa /micro on para activar el reconocimiento de voz.', 'muted'))
        print()
        return True


def check_and_prompt():
    """Check if we should prompt for voice setup and do it if needed."""
    setup = VoiceSetup()
    
    if setup.should_ask():
        setup.interactive_setup()
    
    return setup.is_model_downloaded()
