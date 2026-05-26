"""
Penélope — Wake Word Detector
Continuous listening for the wake word "Penélope" using OpenWakeWord.
"""

import threading
import time
from typing import Callable, Optional

import numpy as np

from penelope.core.event_bus import get_event_bus
from penelope.utils.constants import EventType
from penelope.utils.logger import get_logger

log = get_logger(__name__)


class WakeWordDetector:
    """
    Always-on wake word detector.

    Listens continuously for the wake word "Penélope" using OpenWakeWord.
    Falls back to keyboard shortcut (Alt+Space) if audio detection fails.

    The detector runs in a dedicated thread with configurable check intervals
    based on the current system mode.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        threshold: float = 0.7,
        check_interval_ms: int = 100,
    ) -> None:
        self.model_path = model_path
        self.threshold = threshold
        self.check_interval_ms = check_interval_ms
        self._oww_model = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._audio_buffer: list[np.ndarray] = []
        self._buffer_lock = threading.Lock()
        self._on_wake_callbacks: list[Callable] = []
        self._fallback_active = False
        self.bus = get_event_bus()

    def initialize(self) -> bool:
        """
        Initialize the wake word model.

        Returns:
            True if initialized successfully, False if falling back.
        """
        try:
            from openwakeword.model import Model as OWWModel

            # Load default or custom model
            if self.model_path:
                self._oww_model = OWWModel(
                    wakeword_models=[self.model_path],
                    inference_framework="onnx",
                )
            else:
                # Use built-in model (closest to "Penélope")
                # OpenWakeWord includes "hey_jarvis" which we can use
                # or train a custom model for "Penélope"
                self._oww_model = OWWModel(
                    inference_framework="onnx",
                )

            log.info("Wake word detector initialized (OpenWakeWord)")
            return True

        except ImportError:
            log.warning(
                "OpenWakeWord not installed — using keyboard fallback (Alt+Space)"
            )
            self._setup_keyboard_fallback()
            return False
        except Exception as e:
            log.error(f"Failed to initialize wake word detector: {e}")
            self._setup_keyboard_fallback()
            return False

    def _setup_keyboard_fallback(self) -> None:
        """Set up Alt+Space as fallback wake word trigger."""
        try:
            import keyboard
            keyboard.add_hotkey(
                "alt+space",
                self._on_hotkey_trigger,
                suppress=True,
            )
            self._fallback_active = True
            log.info("Keyboard fallback active: Alt+Space to trigger wake word")
        except ImportError:
            log.error("keyboard module not installed for fallback")
        except Exception as e:
            log.error(f"Failed to set up keyboard fallback: {e}")

    def _on_hotkey_trigger(self) -> None:
        """Handle keyboard hotkey as wake word trigger."""
        log.info("Wake word triggered via keyboard (Alt+Space)")
        self._fire_wake_callbacks()

    def on_audio_chunk(self, audio: np.ndarray) -> None:
        """
        Receive an audio chunk from the AudioManager.

        This is registered as a callback on the AudioManager.

        Args:
            audio: Float32 audio samples.
        """
        with self._buffer_lock:
            self._audio_buffer.append(audio)
            # Keep only last ~1 second of audio
            max_chunks = int(16000 / len(audio)) if len(audio) > 0 else 16
            if len(self._audio_buffer) > max_chunks:
                self._audio_buffer.pop(0)

    def start(self) -> None:
        """Start the wake word detection loop in a background thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._detection_loop,
            name="wake_word_detector",
            daemon=True,
        )
        self._thread.start()
        log.info("Wake word detection started")

    def stop(self) -> None:
        """Stop the wake word detection loop."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        log.info("Wake word detection stopped")

    def _detection_loop(self) -> None:
        """Main detection loop running in background thread."""
        while self._running:
            try:
                if self._oww_model is not None:
                    self._check_wake_word()

                time.sleep(self.check_interval_ms / 1000.0)
            except Exception as e:
                log.error(f"Wake word detection error: {e}")
                time.sleep(1.0)  # Back off on error

    def _check_wake_word(self) -> None:
        """Check accumulated audio for wake word."""
        with self._buffer_lock:
            if not self._audio_buffer:
                return
            audio = np.concatenate(self._audio_buffer)
            self._audio_buffer.clear()

        if len(audio) < 1280:  # Minimum chunk size for OWW
            return

        try:
            # Convert to int16 for OpenWakeWord
            audio_int16 = (audio * 32767).astype(np.int16)
            prediction = self._oww_model.predict(audio_int16)

            # Check all model predictions
            for model_name, score in prediction.items():
                if score >= self.threshold:
                    log.info(
                        f"Wake word detected! model={model_name} "
                        f"score={score:.3f} threshold={self.threshold}"
                    )
                    self._fire_wake_callbacks()
                    self._oww_model.reset()
                    return

        except Exception as e:
            log.debug(f"Wake word check error: {e}")

    def _fire_wake_callbacks(self) -> None:
        """Notify all registered callbacks that wake word was detected."""
        self.bus.emit_sync(EventType.WAKE_WORD_DETECTED, confidence=1.0)

        for callback in self._on_wake_callbacks:
            try:
                callback()
            except Exception as e:
                log.error(f"Wake callback error: {e}")

    def on_wake(self, callback: Callable) -> None:
        """Register a callback for when wake word is detected."""
        self._on_wake_callbacks.append(callback)

    def set_interval(self, interval_ms: int) -> None:
        """
        Update the detection check interval.

        Lower intervals = faster detection but more CPU.

        Args:
            interval_ms: Check interval in milliseconds.
        """
        old = self.check_interval_ms
        self.check_interval_ms = max(10, interval_ms)
        log.debug(f"Wake word interval changed: {old}ms → {self.check_interval_ms}ms")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_fallback(self) -> bool:
        return self._fallback_active

    def cleanup(self) -> None:
        """Release all resources."""
        self.stop()
        self._on_wake_callbacks.clear()
        if self._fallback_active:
            try:
                import keyboard
                keyboard.remove_all_hotkeys()
            except Exception:
                pass
        log.info("Wake word detector cleaned up")
