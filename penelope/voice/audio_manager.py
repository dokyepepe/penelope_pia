"""
Penélope — Audio Manager
Manages audio input/output devices, buffers, and volume control.
"""

import threading
import time
from typing import Callable, Optional

try:
    import numpy as np
except ImportError:
    from typing import Any
    class DummyNumPy:
        ndarray = Any
    np = DummyNumPy()

from penelope.utils.logger import get_logger

log = get_logger(__name__)


class AudioManager:
    """
    Central audio manager for microphone input and speaker output.

    Handles device selection, audio capture, and volume control.
    Provides a shared audio buffer for wake word detection and STT.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 1024,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self._stream = None
        self._is_recording = False
        self._lock = threading.Lock()
        self._audio_callbacks: list[Callable] = []
        self._sd = None

    def _ensure_sounddevice(self):
        """Lazy-import sounddevice."""
        if self._sd is None:
            try:
                import sounddevice as sd
                self._sd = sd
            except ImportError:
                log.error("sounddevice not installed: pip install sounddevice")
                raise

    def get_input_devices(self) -> list[dict]:
        """
        List available audio input devices.

        Returns:
            List of device info dicts.
        """
        self._ensure_sounddevice()
        devices = self._sd.query_devices()
        inputs = []
        for i, dev in enumerate(devices):
            if dev["max_input_channels"] > 0:
                inputs.append({
                    "index": i,
                    "name": dev["name"],
                    "channels": dev["max_input_channels"],
                    "sample_rate": dev["default_samplerate"],
                })
        return inputs

    def get_default_input(self) -> Optional[dict]:
        """Get the default input device info."""
        self._ensure_sounddevice()
        try:
            dev_id = self._sd.default.device[0]
            dev = self._sd.query_devices(dev_id)
            return {
                "index": dev_id,
                "name": dev["name"],
                "channels": dev["max_input_channels"],
                "sample_rate": dev["default_samplerate"],
            }
        except Exception as e:
            log.error(f"Failed to get default input device: {e}")
            return None

    def register_callback(self, callback: Callable[[np.ndarray], None]) -> None:
        """
        Register a callback to receive audio chunks.

        The callback is called with a numpy array of float32 samples.

        Args:
            callback: Function(np.ndarray) to receive audio data.
        """
        self._audio_callbacks.append(callback)

    def start_recording(self, device: Optional[int] = None) -> bool:
        """
        Start continuous audio recording.

        Audio data is dispatched to all registered callbacks.

        Args:
            device: Input device index (None = default).

        Returns:
            True if recording started.
        """
        if self._is_recording:
            return True

        self._ensure_sounddevice()

        def audio_callback(indata, frames, time_info, status):
            if status:
                log.debug(f"Audio status: {status}")
            audio_chunk = indata[:, 0].copy() if indata.shape[1] > 1 else indata.flatten().copy()
            for cb in self._audio_callbacks:
                try:
                    cb(audio_chunk)
                except Exception as e:
                    log.error(f"Audio callback error: {e}")

        try:
            self._stream = self._sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                blocksize=self.chunk_size,
                device=device,
                callback=audio_callback,
            )
            self._stream.start()
            self._is_recording = True
            log.info(
                f"Audio recording started "
                f"(rate={self.sample_rate}, chunk={self.chunk_size})"
            )
            return True
        except Exception as e:
            log.error(f"Failed to start recording: {e}")
            return False

    def stop_recording(self) -> None:
        """Stop audio recording."""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                log.warning(f"Error stopping audio stream: {e}")
            finally:
                self._stream = None
                self._is_recording = False
                log.info("Audio recording stopped")

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def record_chunk(self, duration_seconds: float = 5.0) -> Optional[np.ndarray]:
        """
        Record a single audio chunk of specified duration.

        Useful for one-shot recording (e.g., passphrase capture).

        Args:
            duration_seconds: Duration to record.

        Returns:
            NumPy array of recorded audio, or None on failure.
        """
        self._ensure_sounddevice()
        try:
            frames = int(self.sample_rate * duration_seconds)
            recording = self._sd.rec(
                frames,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
            )
            self._sd.wait()
            return recording.flatten()
        except Exception as e:
            log.error(f"Failed to record chunk: {e}")
            return None

    def play_audio(self, audio: np.ndarray, sample_rate: Optional[int] = None) -> None:
        """
        Play audio through the default output device.

        Args:
            audio: NumPy array of audio samples.
            sample_rate: Playback sample rate (None = use default).
        """
        self._ensure_sounddevice()
        try:
            rate = sample_rate or self.sample_rate
            self._sd.play(audio, samplerate=rate)
            self._sd.wait()
        except Exception as e:
            log.error(f"Failed to play audio: {e}")

    def set_system_volume(self, level: float) -> bool:
        """
        Set the system volume level.

        Args:
            level: Volume level from 0.0 to 1.0.

        Returns:
            True if successful.
        """
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(
                IAudioEndpointVolume._iid_, CLSCTX_ALL, None
            )
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMasterVolumeLevelScalar(max(0.0, min(1.0, level)), None)
            log.info(f"System volume set to {level:.0%}")
            return True
        except Exception as e:
            if level == 0.0:
                # Mute key fallback
                try:
                    import ctypes
                    ctypes.windll.user32.keybd_event(0xAD, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(0xAD, 0, 2, 0)
                    log.info("System volume toggled/muted via Win32 virtual key")
                    return True
                except Exception:
                    pass
            log.error(f"Failed to set volume (no pycaw or keybd_event): {e}")
            return False

    def get_system_volume(self) -> float:
        """Get current system volume (0.0 to 1.0)."""
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(
                IAudioEndpointVolume._iid_, CLSCTX_ALL, None
            )
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            return volume.GetMasterVolumeLevelScalar()
        except Exception as e:
            log.debug(f"Failed to get volume via pycaw: {e}")
            return 0.5

    def change_volume(self, delta: float = 0.1) -> float:
        """
        Change system volume by a delta.

        Args:
            delta: Volume change (+0.1 = up 10%, -0.1 = down 10%).

        Returns:
            New volume level.
        """
        # Try using pycaw first
        try:
            from pycaw.pycaw import AudioUtilities
            # If pycaw is available, use standard logic
            current = self.get_system_volume()
            new_level = max(0.0, min(1.0, current + delta))
            if self.set_system_volume(new_level):
                return new_level
        except Exception:
            pass

        # Fallback to keybd_event
        try:
            import ctypes
            # 1 key press on Windows changes volume by 2%.
            # So abs(delta) * 50 gives the number of keypresses needed.
            presses = int(abs(delta) * 50)
            if presses == 0:
                presses = 1
            
            key_code = 0xAF if delta > 0 else 0xAE
            for _ in range(presses):
                ctypes.windll.user32.keybd_event(key_code, 0, 0, 0)
                ctypes.windll.user32.keybd_event(key_code, 0, 2, 0)
                time.sleep(0.01)
            
            log.info(f"System volume adjusted via virtual keys (delta={delta:+.1f})")
            return 0.5
        except Exception as e:
            log.error(f"Failed to change volume via Win32 virtual keys: {e}")
            return 0.5

    def cleanup(self) -> None:
        """Release all audio resources."""
        self.stop_recording()
        self._audio_callbacks.clear()
        log.info("Audio manager cleaned up")
