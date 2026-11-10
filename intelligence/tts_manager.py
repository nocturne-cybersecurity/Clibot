"""Text-to-Speech manager for CLIBOT."""
import json
import os
from pathlib import Path


class TTSManager:
    """Manages text-to-speech configuration and playback."""
    
    CONFIG_DIR = Path.home() / '.config' / 'clibot'
    CONFIG_FILE = CONFIG_DIR / 'tts_config.json'
    
    # Available voices (pyttsx3 voice IDs will be mapped at runtime)
    VOICE_PROFILES = {
        'default': 'Mujer joven (predeterminado)',
        'female_young': 'Mujer joven',
        'female_adult': 'Mujer adulta',
        'male_young': 'Hombre joven',
        'male_adult': 'Hombre adulto',
    }
    
    def __init__(self):
        self.config_dir = self.CONFIG_DIR
        self.config_file = self.CONFIG_FILE
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._engine = None
        self._voice_map = {}
    
    def load_config(self):
        """Load TTS configuration."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {
            'enabled': False,
            'voice_profile': 'default',
            'rate': 150,  # Words per minute
            'volume': 0.9,
        }
    
    def save_config(self, config):
        """Save TTS configuration."""
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def is_available(self):
        """Check if TTS is available."""
        try:
            import pyttsx3
            return True
        except ImportError:
            return False
    
    def _get_engine(self):
        """Get or create TTS engine."""
        if self._engine is None:
            try:
                import pyttsx3
                self._engine = pyttsx3.init()
                
                # Build voice map
                voices = self._engine.getProperty('voices')
                self._voice_map = {}
                
                # Try to map available voices to profiles
                for i, voice in enumerate(voices):
                    voice_id = voice.id
                    name = voice.name.lower()
                    
                    # Map based on common patterns
                    if 'female' in name or 'woman' in name or 'zira' in name or 'hazel' in name:
                        if 'young' in name or 'samantha' in name:
                            self._voice_map['female_young'] = voice_id
                        else:
                            self._voice_map['female_adult'] = voice_id
                    elif 'male' in name or 'man' in name or 'david' in name or 'mark' in name:
                        if 'young' in name or 'daniel' in name:
                            self._voice_map['male_young'] = voice_id
                        else:
                            self._voice_map['male_adult'] = voice_id
                    
                    # Always map first available female voice to default
                    if 'default' not in self._voice_map and ('female' in name or 'woman' in name):
                        self._voice_map['default'] = voice_id
                
                # Fallback: use first available voice for default
                if 'default' not in self._voice_map and voices:
                    self._voice_map['default'] = voices[0].id
                    
            except ImportError:
                return None
        return self._engine
    
    def speak(self, text):
        """Speak text using TTS."""
        if not self.is_available():
            return False
        
        config = self.load_config()
        if not config.get('enabled'):
            return False
        
        engine = self._get_engine()
        if engine is None:
            return False
        
        try:
            # Set voice
            profile = config.get('voice_profile', 'default')
            voice_id = self._voice_map.get(profile, self._voice_map.get('default'))
            
            if voice_id:
                voices = engine.getProperty('voices')
                for voice in voices:
                    if voice.id == voice_id:
                        engine.setProperty('voice', voice.id)
                        break
            
            # Set rate and volume
            engine.setProperty('rate', config.get('rate', 150))
            engine.setProperty('volume', config.get('volume', 0.9))
            
            # Speak
            engine.say(text)
            engine.runAndWait()
            return True
        except Exception:
            return False
    
    def set_enabled(self, enabled):
        """Enable or disable TTS."""
        config = self.load_config()
        config['enabled'] = enabled
        self.save_config(config)
    
    def set_voice_profile(self, profile):
        """Set voice profile."""
        if profile not in self.VOICE_PROFILES:
            return False, f"Perfil '{profile}' no válido. Opciones: {', '.join(self.VOICE_PROFILES.keys())}"
        
        config = self.load_config()
        config['voice_profile'] = profile
        self.save_config(config)
        return True, f"Perfil de voz cambiado a: {self.VOICE_PROFILES[profile]}"
    
    def set_rate(self, rate):
        """Set speech rate (words per minute)."""
        config = self.load_config()
        config['rate'] = max(50, min(300, rate))  # Clamp between 50 and 300
        self.save_config(config)
    
    def set_volume(self, volume):
        """Set volume (0.0 to 1.0)."""
        config = self.load_config()
        config['volume'] = max(0.0, min(1.0, volume))  # Clamp between 0.0 and 1.0
        self.save_config(config)
    
    def get_status(self):
        """Get current TTS status."""
        config = self.load_config()
        enabled = config.get('enabled', False)
        profile = config.get('voice_profile', 'default')
        return {
            'available': self.is_available(),
            'enabled': enabled,
            'voice_profile': profile,
            'voice_name': self.VOICE_PROFILES.get(profile, 'Desconocido'),
            'rate': config.get('rate', 150),
            'volume': config.get('volume', 0.9),
        }
    
    def list_voices(self):
        """List available voice profiles."""
        return self.VOICE_PROFILES
    
    def list_available_voices(self):
        """List actual system voices available."""
        if not self.is_available():
            return []
        
        engine = self._get_engine()
        if engine is None:
            return []
        
        try:
            voices = engine.getProperty('voices')
            return [(v.id, v.name) for v in voices]
        except Exception:
            return []
