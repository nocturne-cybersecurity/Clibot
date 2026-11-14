"""Text-to-Speech manager for CLIBOT."""
import json
import os
import shutil
from pathlib import Path


class TTSManager:
    """Manages text-to-speech configuration and playback."""
    
    CONFIG_DIR = Path.home() / '.config' / 'clibot'
    CONFIG_FILE = CONFIG_DIR / 'tts_config.json'
    PIPER_DIR = Path.home() / '.cache' / 'clibot' / 'piper'
    # Voces neuronales Piper (mucho más naturales que espeak-ng).
    # valor: (etiqueta, speaker_id). sharvard tiene 2 hablantes: 0=H, 1=M.
    PIPER_VOICES = {
        'es_ES-sharvard-medium': ('Español (España, mujer)', 1),
        'es_ES-davefx-medium': ('Español (España, hombre)', 0),
        'es_MX-ald-medium': ('Español (México, hombre)', 0),
        'es_MX-claude-high': ('Español (México, hombre, alta calidad)', 0),
    }
    # Perfiles con nombre propio. (modelo, speaker_id, length_scale propio o None)
    _PROFILE_TO_PIPER = {
        'carla': ('es_ES-sharvard-medium', 1, 0.85),
        'elena': ('es_ES-sharvard-medium', 1, 1.0),
        'ramiro': ('es_ES-davefx-medium', 0, 0.9),
        'diego': ('es_MX-ald-medium', 0, 0.9),
    }
    # Aliases antiguos -> nombre propio
    VOICE_ALIASES = {
        'default': 'carla',
        'female_young': 'carla',
        'female_adult': 'elena',
        'male_young': 'ramiro',
        'male_adult': 'diego',
    }
    VOICE_PROFILES = {
        'carla': 'Carla — mujer joven, España (rápida)',
        'elena': 'Elena — mujer adulta, España (pausada)',
        'ramiro': 'Ramiro — hombre, España',
        'diego': 'Diego — hombre, México',
    }
    # Preferencias de id de voz por perfil (se busca por subcadena, en orden).
    _PROFILE_HINTS = {
        'default': ('roa/es', '/es', 'es-419', 'es'),
        'female_young': ('roa/es-419', 'es-419', 'roa/es', '/es'),
        'male_young': ('gmw/en-us', 'en-us', '/en'),
        'female_adult': ('roa/es', '/es', 'es'),
        'male_adult': ('gmw/en-gb', 'en-gb', 'gmw/en', '/en'),
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
            'rate': 200,  # Words per minute
            'volume': 0.9,
            'length_scale': 0.9,  # Piper: <1 = más rápido/fluido
        }
    
    def save_config(self, config):
        """Save TTS configuration."""
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def is_available(self):
        """Check if TTS is available (pyttsx3 or Piper)."""
        try:
            import pyttsx3
            return True
        except ImportError:
            try:
                import piper
                return True
            except ImportError:
                return False
    
    def _get_engine(self):
        """Get or create TTS engine."""
        if self._engine is None:
            try:
                import pyttsx3
                self._engine = pyttsx3.init()
                
                # Build voice map: match each profile to the best available
                # espeak-ng voice id (e.g. 'roa/es', 'gmw/en-us').
                voices = self._engine.getProperty('voices')
                ids = [v.id for v in voices]
                self._voice_map = {}
                for profile, hints in self._PROFILE_HINTS.items():
                    for hint in hints:
                        match = next((vid for vid in ids if hint in vid), None)
                        if match:
                            self._voice_map[profile] = match
                            break
                if 'default' not in self._voice_map and ids:
                    self._voice_map['default'] = ids[0]
                    
            except ImportError:
                return None
        return self._engine
    
    def _piper_model_for(self, config):
        """Devuelve (modelo, speaker_id, length_scale) de Piper."""
        if not self.PIPER_DIR.exists():
            return None, None, None
        vid = config.get('voice_id')
        if vid:
            # Formato 'modelo' o 'modelo:speaker'
            parts = vid.rsplit(':', 1)
            name = parts[0]
            speaker = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else None
            if (self.PIPER_DIR / f'{name}.onnx').exists():
                if speaker is None:
                    speaker = self.PIPER_VOICES.get(name, (None, 0))[1]
                return name, speaker, None
        profile = self.VOICE_ALIASES.get(config.get('voice_profile', 'default'),
                                         config.get('voice_profile', 'default'))
        entry = self._PROFILE_TO_PIPER.get(profile)
        if entry:
            name, speaker, ls = entry
            if (self.PIPER_DIR / f'{name}.onnx').exists():
                return name, speaker, ls
        models = sorted(self.PIPER_DIR.glob('*.onnx'))
        if models:
            name = models[0].stem
            return name, self.PIPER_VOICES.get(name, (None, 0))[1], None
        return None, None, None

    def _speak_piper(self, text, model_name, speaker_id=None, length_scale=None):
        """Sintetiza con Piper (voz neuronal) y reproduce con aplay/pw-play."""
        import subprocess, tempfile, wave
        from piper import PiperVoice
        from piper.config import SynthesisConfig
        model = self.PIPER_DIR / f'{model_name}.onnx'
        voice = PiperVoice.load(str(model), config_path=str(model) + '.json')
        syn = SynthesisConfig(speaker_id=speaker_id, length_scale=length_scale)
        fd, wav_path = tempfile.mkstemp(suffix='.wav')
        import os
        os.close(fd)
        try:
            with wave.open(wav_path, 'wb') as wf:
                voice.synthesize_wav(text, wf, syn_config=syn)
            for player in ('aplay', 'pw-play'):
                if shutil.which(player):
                    subprocess.run([player, wav_path], capture_output=True, timeout=300)
                    return True
            return False
        finally:
            try:
                os.unlink(wav_path)
            except OSError:
                pass

    def speak(self, text):
        """Speak text using TTS (Piper neural voice preferred, espeak fallback)."""
        if not self.is_available():
            return False
        
        config = self.load_config()
        if not config.get('enabled'):
            return False

        # Preferir voz neuronal Piper si hay modelo disponible.
        piper_model, piper_speaker, piper_ls = self._piper_model_for(config)
        if piper_model:
            try:
                # /voice rate (config['length_scale']) tiene prioridad; si no,
                # se usa la velocidad propia del perfil.
                ls = config.get('length_scale', piper_ls)
                return self._speak_piper(text, piper_model, piper_speaker, ls)
            except Exception:
                pass  # caer a espeak-ng
        
        engine = self._get_engine()
        if engine is None:
            return False
        
        try:
            # Set voice (raw id wins over profile mapping)
            voice_id = config.get('voice_id') or self._voice_map.get(
                config.get('voice_profile', 'default'), self._voice_map.get('default'))
            
            if voice_id:
                voices = engine.getProperty('voices')
                for voice in voices:
                    if voice.id == voice_id:
                        engine.setProperty('voice', voice.id)
                        break
            
            # Set rate and volume
            engine.setProperty('rate', config.get('rate', 200))
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
        """Set voice profile (nombre propio, alias antiguo, o id crudo)."""
        raw = profile.strip()
        profile = raw.lower()
        profile = self.VOICE_ALIASES.get(profile, profile)
        if profile not in self.VOICE_PROFILES:
            # Allow any raw voice id the engine actually has (espeak o Piper).
            if self.PIPER_DIR.exists():
                base = raw.split(':', 1)[0]
                match = next((m.stem for m in self.PIPER_DIR.glob('*.onnx')
                              if m.stem.lower() == base.lower()), None)
                if match:
                    config = self.load_config()
                    config['voice_profile'] = match
                    config['voice_id'] = raw if ':' in raw else match
                    self.save_config(config)
                    label = self.PIPER_VOICES.get(match, (match,))[0]
                    return True, f'Voz cambiada a: {label} (Piper)'
            engine = self._get_engine()
            if engine is not None:
                ids = [v.id for v in engine.getProperty('voices')]
                if profile in ids:
                    config = self.load_config()
                    config['voice_profile'] = profile
                    config['voice_id'] = profile
                    self.save_config(config)
                    return True, f'Voz cambiada a: {profile}'
            return False, f"Perfil '{profile}' no válido. Opciones: {', '.join(self.VOICE_PROFILES.keys())}"
        config = self.load_config()
        config['voice_profile'] = profile
        config.pop('voice_id', None)
        self.save_config(config)
        return True, f"Voz cambiada a: {self.VOICE_PROFILES[profile]}"
    
    def set_rate(self, rate):
        """Set speech rate (words per minute for espeak; length_scale for Piper)."""
        config = self.load_config()
        config['rate'] = max(80, min(400, rate))  # Clamp between 80 and 400 wpm
        # Piper: length_scale <1 = más rápido. 200wpm≈1.0, 250≈0.85, 300≈0.7
        config['length_scale'] = max(0.6, min(1.4, 200.0 / max(rate, 1)))
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
        profile = self.VOICE_ALIASES.get(config.get('voice_profile', 'default'),
                                         config.get('voice_profile', 'default'))
        return {
            'available': self.is_available(),
            'enabled': enabled,
            'voice_profile': profile,
            'voice_name': self.VOICE_PROFILES.get(profile, 'Desconocido'),
            'rate': config.get('rate', 200),
            'volume': config.get('volume', 0.9),
            'length_scale': config.get('length_scale', 0.9),
        }
    
    def list_voices(self):
        """List available voice profiles."""
        return self.VOICE_PROFILES
    
    def list_available_voices(self):
        """List actual system voices available (Piper models + espeak)."""
        voices = []
        if self.PIPER_DIR.exists():
            for model in sorted(self.PIPER_DIR.glob('*.onnx')):
                label, speaker = self.PIPER_VOICES.get(model.stem, (model.stem, 0))
                voices.append((model.stem, f'{label} (speaker {speaker})'))
        if self.is_available():
            engine = self._get_engine()
            if engine is not None:
                try:
                    voices += [(v.id, v.name) for v in engine.getProperty('voices')]
                except Exception:
                    pass
        return voices
