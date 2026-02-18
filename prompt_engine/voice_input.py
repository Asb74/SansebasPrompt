"""Voice input module for PROM-9™ using OpenAI transcription API."""

from __future__ import annotations

from pathlib import Path
import tempfile
import wave
from threading import Lock
from typing import Optional

import numpy as np
import sounddevice as sd
from openai import APIConnectionError, APIError, APITimeoutError, OpenAI


class VoiceInput:
    """Handles microphone recording and transcription with OpenAI."""

    def __init__(self, sample_rate: int = 16_000, channels: int = 1) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._is_recording = False
        self._audio_chunks: list[np.ndarray] = []
        self._lock = Lock()
        self._stream: Optional[sd.InputStream] = None

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

        def _callback(indata: np.ndarray, frames: int, time: object, status: sd.CallbackFlags) -> None:
            _ = (frames, time)
            if status:
                return
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

        api_key_path = Path(__file__).resolve().parent / "KeySecret.txt"
        if not api_key_path.exists():
            raise RuntimeError("No se encontró la API key en prompt_engine/KeySecret.txt.")

        api_key = api_key_path.read_text(encoding="utf-8").strip()
        if not api_key:
            raise RuntimeError("La API key en prompt_engine/KeySecret.txt está vacía.")

        audio_mono = np.asarray(audio, dtype=np.float32)
        if audio_mono.ndim > 1:
            audio_mono = np.mean(audio_mono, axis=1)
        audio_mono = np.clip(audio_mono, -1.0, 1.0)
        pcm16 = (audio_mono * 32767.0).astype(np.int16)

        temp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                temp_path = tmp_file.name

            with wave.open(temp_path, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(pcm16.tobytes())

            client = OpenAI(api_key=api_key)

            with open(temp_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
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
