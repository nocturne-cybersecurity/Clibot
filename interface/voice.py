"""Local Vosk speech input for the interactive terminal."""
import json
import os
import queue
import shutil
import subprocess
import threading
from pathlib import Path


class VoiceInputError(RuntimeError):
    pass


class VoiceInput:
    SAMPLE_RATE = 16000
    MODEL_NAME = 'vosk-model-small-es-0.42'

    def __init__(self, model_path=None):
        configured = model_path or os.environ.get('CLIBOT_VOSK_MODEL')
        self.model_path = Path(configured).expanduser() if configured else (
            Path.home() / '.cache' / 'clibot' / self.MODEL_NAME)
        self._model = None
        self._events = queue.Queue()
        self._stop = None
        self._thread = None
        self._process = None
        self._lock = threading.Lock()

    def prepare(self):
        if self._model is not None:
            return
        if not self.model_path.is_dir():
            raise VoiceInputError(
                f'No encuentro el modelo de voz: {self.model_path}. '
                "Instala el extra con 'pip install -e \".[voice]\"' y consulta "
                'README.md para descargar el modelo español de Vosk.')
        try:
            from vosk import Model
        except ImportError as exc:
            raise VoiceInputError(
                "Falta Vosk. Instala el soporte opcional con 'pip install -e \".[voice]\"'.") from exc
        try:
            self._model = Model(str(self.model_path))
        except Exception as exc:
            raise VoiceInputError(f'No se pudo cargar el modelo Vosk {self.model_path}: {exc}') from exc

    def start(self):
        self.prepare()
        recorder = shutil.which('arecord')
        if not recorder:
            raise VoiceInputError("No encuentro arecord. Instala ALSA con 'sudo apt install alsa-utils'.")
        if self._thread and self._thread.is_alive():
            raise VoiceInputError('El micrófono ya está escuchando.')
        self._events = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._capture, args=(recorder,), daemon=True)
        self._thread.start()

    def poll(self):
        try:
            return self._events.get_nowait()
        except queue.Empty:
            return None

    def stop(self):
        if self._stop is not None:
            self._stop.set()
        with self._lock:
            process = self._process
        if process and process.poll() is None:
            process.terminate()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
            if self._thread.is_alive() and process and process.poll() is None:
                process.kill()
                self._thread.join(timeout=1)
        with self._lock:
            self._process = None
        self._thread = None

    def _capture(self, recorder):
        process = None
        try:
            from vosk import KaldiRecognizer

            process = subprocess.Popen(
                [recorder, '--quiet', '-D', 'default', '-f', 'S16_LE',
                 '-r', str(self.SAMPLE_RATE), '-c', '1', '-t', 'raw'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
            with self._lock:
                self._process = process
                should_stop = self._stop.is_set()
            if should_stop:
                process.terminate()
                return

            recognizer = KaldiRecognizer(self._model, self.SAMPLE_RATE)
            while not self._stop.is_set():
                audio = process.stdout.read(4000)
                if not audio:
                    if not self._stop.is_set():
                        detail = process.stderr.read().decode('utf-8', errors='replace').strip()
                        raise VoiceInputError(detail or 'La captura de audio terminó inesperadamente.')
                    return
                if recognizer.AcceptWaveform(audio):
                    transcript = json.loads(recognizer.Result()).get('text', '').strip()
                    if transcript:
                        self._events.put(('text', transcript))
                        return
        except Exception as exc:
            self._events.put(('error', str(exc)))
        finally:
            if process:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                if process.stdout:
                    process.stdout.close()
                if process.stderr:
                    process.stderr.close()
            with self._lock:
                if self._process is process:
                    self._process = None


def voice_command(text):
    """Map spoken microphone controls to terminal commands."""
    normalized = ' '.join(text.casefold().strip().split())
    if normalized in {
        'micro off', 'microfono off', 'micrófono off', 'apaga el microfono',
        'apaga el micrófono', 'desactiva el microfono', 'desactiva el micrófono',
        'deten el microfono', 'detén el micrófono',
    }:
        return '/micro off'
    return text
