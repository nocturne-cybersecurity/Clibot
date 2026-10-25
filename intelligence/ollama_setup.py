"""Ollama and model installation helper for CLIBOT."""
import json
import os
import subprocess
import shutil
import sys
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError


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
    
    def install_ollama(self):
        """Install Ollama using the official install script."""
        print("📦 Instalando Ollama...")
        
        try:
            # Detect OS
            if sys.platform == 'linux':
                # Linux install script
                cmd = ['curl', '-fsSL', 'https://ollama.com/install.sh', '|', 'sh']
                print("   Ejecutando: curl -fsSL https://ollama.com/install.sh | sh")
                subprocess.run('curl -fsSL https://ollama.com/install.sh | sh', shell=True, check=True)
            elif sys.platform == 'darwin':
                # macOS install
                cmd = ['brew', 'install', 'ollama']
                print(f"   Ejecutando: {' '.join(cmd)}")
                subprocess.run(cmd, check=True)
            else:
                raise RuntimeError(f"Sistema operativo no soportado: {sys.platform}")
            
            print("✅ Ollama instalado correctamente")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Error instalando Ollama: {e}")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def start_ollama(self):
        """Start Ollama daemon."""
        print("🚀 Iniciando Ollama...")
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
                    print("✅ Ollama iniciado correctamente")
                    return True
            
            print("⚠️  Ollama tardó en iniciar, pero debería estar corriendo")
            return True
        except Exception as e:
            print(f"❌ Error iniciando Ollama: {e}")
            return False
    
    def pull_model(self, model=None):
        """Pull a model from Ollama."""
        model = model or self.RECOMMENDED_MODEL
        print(f"📥 Descargando modelo {model}...")
        print(f"   Esto puede tomar unos minutos (el modelo pesa ~2.3GB)")
        
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
                print(f"✅ Modelo {model} instalado correctamente")
                return True
            else:
                print(f"❌ Error descargando modelo: código {process.returncode}")
                return False
        except Exception as e:
            print(f"❌ Error: {e}")
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
        
        print("\n" + "="*60)
        print("🤖 CONFIGURACIÓN DE MODELO DE LENGUAJE LOCAL")
        print("="*60)
        print("\nCLIBOT puede usar un modelo de lenguaje local (Phi-3 Mini)")
        print("para respuestas más naturales y fluidas.")
        print("\nDetalles:")
        print("  • Modelo: Phi-3 Mini (3.8B parámetros)")
        print("  • Tamaño: ~2.3GB en disco")
        print("  • RAM: ~1.5GB")
        print("  • Velocidad: 30-80ms por respuesta")
        print("  • Uso: Solo para chat casual, NO para comandos del sistema")
        print("\nEs completamente opcional. CLIBOT funcionará perfectamente sin él.")
        print("="*60 + "\n")
        
        while True:
            response = input("¿Quieres instalar Phi-3 Mini ahora? [s/N]: ").strip().lower()
            
            if response in ('n', 'no', '', 'exit'):
                print("\n👍 Entendido. CLIBOT funcionará con respuestas predefinidas.")
                print("   Puedes instalarlo más tarde ejecutando:")
                print("   ollama pull phi3:mini")
                self.mark_asked()
                return False
            
            if response in ('s', 'si', 'yes', 'y'):
                break
            
            print("Por favor responde 's' para sí o 'n' para no.")
        
        self.mark_asked()
        
        # Check if Ollama is installed
        if not self.is_ollama_installed():
            print("\n📦 Ollama no está instalado.")
            response = input("¿Quieres instalar Ollama ahora? [s/N]: ").strip().lower()
            
            if response in ('s', 'si', 'yes', 'y'):
                if not self.install_ollama():
                    print("\n❌ No se pudo instalar Ollama.")
                    return False
            else:
                print("\n❌ Necesitas Ollama para usar el modelo.")
                print("   Instálalo manualmente desde: https://ollama.com")
                return False
        
        # Check if Ollama is running
        if not self.is_ollama_running():
            if not self.start_ollama():
                print("\n❌ No se pudo iniciar Ollama.")
                return False
        
        # Pull the model
        if not self.pull_model():
            return False
        
        self.mark_installed()
        print("\n✅ ¡Configuración completada!")
        print("   CLIBOT ahora usará Phi-3 Mini para respuestas más naturales.")
        return True


def check_and_prompt():
    """Check if we should prompt for LLM setup and do it if needed."""
    setup = OllamaSetup()
    
    if setup.should_ask():
        setup.interactive_setup()
    
    return setup.setup_complete()
