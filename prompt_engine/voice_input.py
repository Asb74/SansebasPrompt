"""Voice input module for PROM-9™ using OpenAI transcription API."""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import wave
from threading import Lock
from time import monotonic
from typing import Any, Optional


def resource_path(relative_path: str) -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base_path / relative_path


_NUMPY_AVAILABLE = importlib.util.find_spec("numpy") is not None
np = importlib.import_module("numpy") if _NUMPY_AVAILABLE else None

_OPENAI_AVAILABLE = importlib.util.find_spec("openai") is not None
if _OPENAI_AVAILABLE:
    openai_module = importlib.import_module("openai")
    OpenAI = openai_module.OpenAI
    APITimeoutError = openai_module.APITimeoutError
    APIConnectionError = openai_module.APIConnectionError
    APIError = openai_module.APIError
else:
    OpenAI = None
    APITimeoutError = Exception
    APIConnectionError = Exception
    APIError = Exception

_SOUNDDEVICE_AVAILABLE = importlib.util.find_spec("sounddevice") is not None
sd = importlib.import_module("sounddevice") if _SOUNDDEVICE_AVAILABLE else None


class VoiceInput:
    """Handles microphone recording and transcription with OpenAI."""

    @classmethod
    def _missing_dependencies(cls) -> list[str]:
        missing: list[str] = []
        if not _SOUNDDEVICE_AVAILABLE or sd is None:
            missing.append("sounddevice")
        if not _NUMPY_AVAILABLE or np is None:
            missing.append("numpy")
        if not _OPENAI_AVAILABLE or OpenAI is None:
            missing.append("openai")
        return missing

    def __init__(self, sample_rate: int = 16_000, channels: int = 1) -> None:
        missing = self._missing_dependencies()
        if missing:
            raise RuntimeError(
                "El dictado por voz no está disponible: faltan dependencias opcionales "
                f"({', '.join(missing)})."
            )

        self.sample_rate = sample_rate
        self.channels = channels
        self.max_seconds = 120
        self._is_recording = False
        self._audio_chunks: list[np.ndarray] = []
        self._lock = Lock()
        self._stream: Optional[Any] = None
        self._recording_started_at: Optional[float] = None

        api_key_path = resource_path("prompt_engine/KeySecret.txt")
        if not api_key_path.exists():
            raise RuntimeError("No se encontró la API key en prompt_engine/KeySecret.txt.")

        api_key = api_key_path.read_text(encoding="utf-8").strip()
        if not api_key:
            raise RuntimeError("La API key en prompt_engine/KeySecret.txt está vacía.")

        self._client = OpenAI(api_key=api_key)

    @classmethod
    def is_supported(cls) -> bool:
        return not cls._missing_dependencies()

    @property
    def is_recording(self) -> bool:
        """Whether recording is currently active."""
        return self._is_recording

    def start_recording(self) -> None:
        """Start continuous microphone recording."""
        if self._is_recording:
            return

        try:
            sd.check_input_settings(samplerate=self.sample_rate, channels=self.channels)
        except Exception as exc:
            raise RuntimeError("No se detectó un micrófono disponible o válido.") from exc

        with self._lock:
            self._audio_chunks = []

        self._recording_started_at = monotonic()

        def _callback(indata: np.ndarray, frames: int, time: object, status: Any) -> None:
            _ = (frames, time)
            if status:
                return
            if self._recording_started_at is not None:
                elapsed = monotonic() - self._recording_started_at
                if elapsed >= self.max_seconds:
                    raise sd.CallbackStop
            with self._lock:
                self._audio_chunks.append(indata.copy())

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                callback=_callback,
            )
            self._stream.start()
            self._is_recording = True
        except Exception as exc:
            self._stream = None
            self._is_recording = False
            self._recording_started_at = None
            raise RuntimeError("No fue posible iniciar la grabación de audio.") from exc

    def stop_recording(self) -> str:
        """Stop recording and return transcription text."""
        if not self._is_recording or self._stream is None:
            raise RuntimeError("No hay una grabación activa para detener.")

        try:
            self._stream.stop()
            self._stream.close()
        finally:
            self._stream = None
            self._is_recording = False
            self._recording_started_at = None

        with self._lock:
            if not self._audio_chunks:
                raise RuntimeError("Audio vacío: no se capturaron datos del micrófono.")
            audio = np.concatenate(self._audio_chunks, axis=0)
            self._audio_chunks = []

        if audio.size == 0:
            raise RuntimeError("Audio vacío: no se capturaron muestras válidas.")

        return self.transcribe(audio)

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe provided audio samples using OpenAI API."""
        if audio.size == 0:
            raise RuntimeError("Audio vacío: no se puede transcribir.")

        audio_mono = np.asarray(audio, dtype=np.float32)
        if audio_mono.ndim > 1:
            audio_mono = np.mean(audio_mono, axis=1)
        audio_mono = np.clip(audio_mono, -1.0, 1.0)
        pcm16 = (audio_mono * 32767.0).astype(np.int16)

        if pcm16.nbytes > 5 * 1024 * 1024:
            raise RuntimeError("Audio demasiado largo para transcripción segura.")

        temp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                temp_path = tmp_file.name

            with wave.open(temp_path, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(pcm16.tobytes())

            with open(temp_path, "rb") as audio_file:
                transcript = self._client.audio.transcriptions.create(
                    model="gpt-4o-mini-transcribe",
                    file=audio_file
                )

            return transcript.text.strip()
        except APITimeoutError as exc:
            raise RuntimeError("Timeout al transcribir audio con OpenAI.") from exc
        except APIConnectionError as exc:
            raise RuntimeError("Error de conexión HTTP al transcribir audio con OpenAI.") from exc
        except APIError as exc:
            raise RuntimeError(f"Error HTTP de OpenAI al transcribir audio: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"Error inesperado durante la transcripción: {exc}") from exc
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)
