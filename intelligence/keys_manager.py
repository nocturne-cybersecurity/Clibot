"""API keys manager for CLIBOT."""
import json
import os
import getpass
from pathlib import Path


class KeysManager:
    """Manages API keys for various services."""
    
    CONFIG_DIR = Path.home() / '.config' / 'clibot'
    CONFIG_FILE = CONFIG_DIR / 'api_keys.json'
    
    # Supported services
    SUPPORTED_KEYS = {
        'openai': 'OpenAI API Key (para modelos GPT)',
        'github': 'GitHub Personal Access Token (para búsqueda de código)',
        'stack_exchange': 'Stack Exchange API Key (opcional, mayor límite de tasa)',
        'anthropic': 'Anthropic API Key (para modelos Claude)',
        'google': 'Google API Key (para servicios de Google)',
    }
    
    def __init__(self):
        self.config_dir = self.CONFIG_DIR
        self.config_file = self.CONFIG_FILE
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def load_keys(self):
        """Load all API keys."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}
    
    def save_keys(self, keys):
        """Save API keys with restricted permissions."""
        with open(self.config_file, 'w') as f:
            json.dump(keys, f, indent=2)
        # Set restrictive permissions (read/write only for owner)
        os.chmod(self.config_file, 0o600)
    
    def get_key(self, service):
        """Get API key for a service."""
        keys = self.load_keys()
        return keys.get(service)
    
    def set_key(self, service, key):
        """Set API key for a service."""
        keys = self.load_keys()
        keys[service] = key
        self.save_keys(keys)
    
    def clear_key(self, service):
        """Clear API key for a service."""
        keys = self.load_keys()
        if service in keys:
            del keys[service]
            self.save_keys(keys)
    
    def list_keys(self):
        """List all configured keys (without showing values)."""
        keys = self.load_keys()
        return list(keys.keys())
    
    def interactive_set(self, service):
        """Interactively set a key."""
        if service not in self.SUPPORTED_KEYS:
            return False, f"Servicio '{service}' no soportado. Servicios: {', '.join(self.SUPPORTED_KEYS.keys())}"
        
        description = self.SUPPORTED_KEYS[service]
        print(f"  Configurando: {description}")
        key = getpass.getpass(f"  Ingresa la clave para {service} (no se mostrará): ")
        
        if not key:
            return False, "Clave vacía. No se guardó."
        
        self.set_key(service, key)
        return True, f"Clave para {service} guardada."
    
    def interactive_list(self):
        """List all keys with their descriptions."""
        keys = self.load_keys()
        if not keys:
            print("  No hay claves configuradas.")
            return
        
        print("  Claves configuradas:")
        for service in keys:
            desc = self.SUPPORTED_KEYS.get(service, 'Desconocido')
            print(f"    - {service}: {desc}")
    
    def interactive_clear(self, service):
        """Interactively clear a key."""
        if service not in self.load_keys():
            return False, f"No hay clave configurada para {service}."
        
        self.clear_key(service)
        return True, f"Clave para {service} eliminada."
