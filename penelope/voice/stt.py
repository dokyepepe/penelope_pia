"""
Penélope — Speech-to-Text
Transcription using faster-whisper (CTranslate2 backend) with Vosk fallback.
"""

import json
import time
from pathlib import Path
from typing import Optional, Tuple

try:
    import numpy as np
except ImportError:
    from typing import Any
    class DummyNumPy:
        ndarray = Any
    np = DummyNumPy()

from penelope.utils.logger import get_logger

log = get_logger(__name__)


class SpeechToText:
    """
    Offline speech-to-text using faster-whisper.

    Converts spoken audio to text with support for Brazilian Portuguese.
    Includes VAD (Voice Activity Detection) for automatic silence detection.
    """

    def __init__(
        self,
        model_size: str = "medium",
        language: str = "pt",
        device: str = "auto",
        compute_type: str = "float16",
        silence_threshold: float = 0.03,
        silence_duration_ms: int = 1500,
        beam_size: int = 1,
    ) -> None:
        self.model_size = model_size
        self.language = language
        self.device = device
        self.compute_type = compute_type
        self.silence_threshold = silence_threshold
        self.silence_duration_ms = silence_duration_ms
        self.beam_size = beam_size
        self._model = None
        self._vosk_model = None
        self._vosk_active = False
        self._loaded = False

    def load_model(self) -> bool:
        """
        Load the Whisper model.

        Auto-detects CUDA availability and adjusts compute type.

        Returns:
            True if model loaded successfully.
        """
        try:
            from faster_whisper import WhisperModel

            # Determine device
            if self.device == "auto":
                try:
                    import torch
                    actual_device = "cuda" if torch.cuda.is_available() else "cpu"
                except ImportError:
                    actual_device = "cpu"
            else:
                actual_device = self.device

            # Adjust compute type for CPU
            compute = self.compute_type
            if actual_device == "cpu":
                compute = "int8"

            log.info(
                f"Loading Whisper model: {self.model_size} "
                f"(device={actual_device}, compute={compute})"
            )

            self._model = WhisperModel(
                self.model_size,
                device=actual_device,
                compute_type=compute,
            )
            self._loaded = True
            log.info("Whisper model loaded successfully")
            return True

        except ImportError:
            log.warning("faster-whisper não instalado — tentando fallback Vosk...")
            return self._load_vosk()
        except Exception as e:
            log.error(f"Failed to load Whisper model: {e}")
            log.info("Tentando fallback para Vosk...")
            return self._load_vosk()

    def _load_vosk(self) -> bool:
        """
        Load Vosk as a fallback STT engine.

        Vosk is lighter and works on CPU without CUDA,
        but has lower accuracy compared to Whisper.

        Returns:
            True if Vosk loaded successfully.
        """
        try:
            from vosk import Model as VoskModel, KaldiRecognizer

            # Try to find a Portuguese model
            vosk_model_path = None
            possible_paths = [
                Path("C:/Penelope/models/vosk-model-pt"),
                Path("C:/Penelope/models/vosk-model-small-pt"),
                Path.home() / ".cache" / "vosk" / "vosk-model-pt",
                Path.home() / ".cache" / "vosk" / "vosk-model-small-pt-0.3",
            ]

            for p in possible_paths:
                if p.exists():
                    vosk_model_path = str(p)
                    break

            if vosk_model_path:
                self._vosk_model = VoskModel(vosk_model_path)
            else:
                # Vosk auto-downloads a small model if none specified
                self._vosk_model = VoskModel(lang="pt")

            self._vosk_active = True
            self._loaded = True
            log.info("Vosk STT carregado como fallback (menor acurácia)")
            return True

        except ImportError:
            log.error("Vosk não instalado: pip install vosk")
            return False
        except Exception as e:
            log.error(f"Falha ao carregar Vosk: {e}")
            return False

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
    ) -> Tuple[str, float]:
        """
        Transcribe audio to text.

        Args:
            audio: NumPy array of float32 audio samples.
            sample_rate: Audio sample rate.

        Returns:
            Tuple of (transcribed_text, confidence_score).
        """
        if not self._loaded:
            log.error("Nenhum modelo STT carregado")
            return "", 0.0

        if self._vosk_active:
            return self._transcribe_vosk(audio, sample_rate)

        if self._model is None:
            log.error("Whisper model not loaded")
            return "", 0.0

        try:
            start_time = time.time()

            # Ensure float32
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            # Transcribe
            segments, info = self._model.transcribe(
                audio,
                language=self.language,
                beam_size=self.beam_size,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=self.silence_duration_ms,
                    threshold=0.5,
                ),
            )

            # Collect all segments
            text_parts = []
            total_prob = 0.0
            seg_count = 0

            for segment in segments:
                text_parts.append(segment.text.strip())
                total_prob += segment.avg_logprob
                seg_count += 1

            full_text = " ".join(text_parts).strip()
            avg_confidence = (total_prob / seg_count) if seg_count > 0 else 0.0
            # Convert log probability to 0-1 confidence
            confidence = min(1.0, max(0.0, 1.0 + avg_confidence))

            elapsed = time.time() - start_time
            log.info(
                f"Transcribed ({elapsed:.1f}s): '{full_text[:80]}...' "
                f"confidence={confidence:.2f}"
            )

            return full_text, confidence

        except Exception as e:
            log.error(f"Transcription failed: {e}")
            return "", 0.0

    def detect_speech_end(
        self,
        audio_chunk: np.ndarray,
        _silence_frames: list = [],
    ) -> bool:
        """
        Detect if the user has stopped speaking (silence detection).

        Uses energy-based VAD: if the RMS energy drops below
        the threshold for `silence_duration_ms`, speech is considered ended.

        Args:
            audio_chunk: Latest audio chunk.
            _silence_frames: Mutable default for tracking state (internal).

        Returns:
            True if silence detected (user stopped speaking).
        """
        rms = np.sqrt(np.mean(audio_chunk ** 2))

        if rms < self.silence_threshold:
            _silence_frames.append(len(audio_chunk))
            total_silence = sum(_silence_frames) / 16000 * 1000  # to ms
            if total_silence >= self.silence_duration_ms:
                _silence_frames.clear()
                return True
        else:
            _silence_frames.clear()

        return False

    def _transcribe_vosk(self, audio: np.ndarray, sample_rate: int = 16000) -> Tuple[str, float]:
        """
        Transcribe audio using Vosk fallback.

        Args:
            audio: NumPy array of float32 audio samples.
            sample_rate: Audio sample rate.

        Returns:
            Tuple of (transcribed_text, confidence_score).
        """
        try:
            from vosk import KaldiRecognizer

            start_time = time.time()

            rec = KaldiRecognizer(self._vosk_model, sample_rate)
            rec.SetWords(True)

            # Convert to int16 bytes for Vosk
            audio_int16 = (audio * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()

            # Process in chunks
            chunk_size = 4000
            for i in range(0, len(audio_bytes), chunk_size):
                rec.AcceptWaveform(audio_bytes[i:i + chunk_size])

            result = json.loads(rec.FinalResult())
            text = result.get("text", "").strip()

            # Vosk doesn't provide confidence per se, estimate from word count
            confidence = 0.6 if text else 0.0  # Lower confidence than Whisper

            elapsed = time.time() - start_time
            log.info(
                f"Vosk transcribed ({elapsed:.1f}s): '{text[:80]}' "
                f"confidence={confidence:.2f}"
            )

            return text, confidence

        except Exception as e:
            log.error(f"Vosk transcription failed: {e}")
            return "", 0.0

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def engine_name(self) -> str:
        """Get the name of the active STT engine."""
        if self._vosk_active:
            return "Vosk"
        elif self._model is not None:
            return f"Whisper ({self.model_size})"
        return "None"

    def unload(self) -> None:
        """Unload the model to free memory (for Game Mode)."""
        self._model = None
        self._vosk_model = None
        self._vosk_active = False
        self._loaded = False
        log.info("STT model unloaded")
