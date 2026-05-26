"""
Penélope — Speech-to-Text
Transcription using faster-whisper (CTranslate2 backend).
"""

import time
from typing import Optional, Tuple

import numpy as np

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
    ) -> None:
        self.model_size = model_size
        self.language = language
        self.device = device
        self.compute_type = compute_type
        self.silence_threshold = silence_threshold
        self.silence_duration_ms = silence_duration_ms
        self._model = None
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
            log.error("faster-whisper not installed: pip install faster-whisper")
            return False
        except Exception as e:
            log.error(f"Failed to load Whisper model: {e}")
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
        if not self._loaded or self._model is None:
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
                beam_size=5,
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

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def unload(self) -> None:
        """Unload the model to free memory (for Game Mode)."""
        self._model = None
        self._loaded = False
        log.info("Whisper model unloaded")
