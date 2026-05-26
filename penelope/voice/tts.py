"""
Penélope — Text-to-Speech
Speech synthesis using Piper TTS with Windows SAPI5 fallback.
"""

import io
import subprocess
import platform
import tempfile
import wave
from pathlib import Path
from typing import Optional

import numpy as np

from penelope.core.event_bus import get_event_bus
from penelope.utils.constants import EventType
from penelope.utils.logger import get_logger

log = get_logger(__name__)


class TextToSpeech:
    """
    Offline text-to-speech using Piper TTS.

    Generates natural female voice in Brazilian Portuguese.
    Falls back to Windows SAPI5 if Piper is unavailable.
    """

    def __init__(
        self,
        model: str = "pt_BR-faber-medium",
        speaker_id: int = 0,
        sample_rate: int = 22050,
        volume_scale: float = 1.0,
    ) -> None:
        self.model = model
        self.speaker_id = speaker_id
        self.sample_rate = sample_rate
        self.volume_scale = volume_scale
        self._piper_available = False
        self._sapi_available = False
        self._piper_exe: Optional[Path] = None
        self.bus = get_event_bus()

    def initialize(self) -> bool:
        """
        Initialize TTS engine.

        Tries Piper first, falls back to SAPI5.

        Returns:
            True if any TTS engine is available.
        """
        # Try Piper TTS
        if self._init_piper():
            self._piper_available = True
            log.info(f"Piper TTS initialized (model={self.model})")
            return True

        # Fallback to SAPI5
        if self._init_sapi():
            self._sapi_available = True
            log.warning("Using Windows SAPI5 fallback for TTS")
            return True

        log.error("No TTS engine available")
        return False

    def _init_piper(self) -> bool:
        """Try to initialize Piper TTS."""
        try:
            # Check if piper is available as a Python package
            import piper
            self._piper_available = True
            return True
        except ImportError:
            pass

        # Check if piper executable is available
        try:
            result = subprocess.run(
                ["piper", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
            )
            if result.returncode == 0:
                self._piper_exe = Path("piper")
                return True
        except FileNotFoundError:
            pass
        except Exception as e:
            log.debug(f"Piper check failed: {e}")

        return False

    def _init_sapi(self) -> bool:
        """Try to initialize Windows SAPI5."""
        if platform.system() != "Windows":
            return False
        try:
            import win32com.client
            self._sapi_engine = win32com.client.Dispatch("SAPI.SpVoice")
            # Try to find a Portuguese voice
            voices = self._sapi_engine.GetVoices()
            for i in range(voices.Count):
                voice = voices.Item(i)
                desc = voice.GetDescription()
                if "portug" in desc.lower() or "brazil" in desc.lower():
                    self._sapi_engine.Voice = voice
                    log.info(f"SAPI5 voice selected: {desc}")
                    break
            return True
        except ImportError:
            log.debug("win32com not available for SAPI5")
            return False
        except Exception as e:
            log.debug(f"SAPI5 init failed: {e}")
            return False

    async def speak(self, text: str) -> bool:
        """
        Convert text to speech and play it.

        Args:
            text: Text to speak.

        Returns:
            True if speech was produced.
        """
        if not text.strip():
            return False

        await self.bus.emit(EventType.TTS_STARTED, text=text)

        try:
            if self._piper_available:
                success = self._speak_piper(text)
            elif self._sapi_available:
                success = self._speak_sapi(text)
            else:
                log.error("No TTS engine available")
                success = False

            await self.bus.emit(EventType.TTS_FINISHED, text=text, success=success)
            return success

        except Exception as e:
            log.error(f"TTS failed: {e}")
            await self.bus.emit(EventType.TTS_FINISHED, text=text, success=False)
            return False

    def _speak_piper(self, text: str) -> bool:
        """Generate and play speech using Piper TTS."""
        try:
            # Try Python API first
            try:
                import piper
                voice = piper.PiperVoice.load(self.model)
                audio_stream = voice.synthesize_stream_raw(text)

                all_audio = b""
                for audio_chunk in audio_stream:
                    all_audio += audio_chunk

                # Convert to numpy and play
                audio_np = np.frombuffer(all_audio, dtype=np.int16).astype(np.float32) / 32768.0
                audio_np *= self.volume_scale

                import sounddevice as sd
                sd.play(audio_np, samplerate=self.sample_rate)
                sd.wait()
                return True

            except ImportError:
                pass

            # Fallback to CLI
            if self._piper_exe:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    tmp_path = f.name

                process = subprocess.run(
                    [
                        str(self._piper_exe),
                        "--model", self.model,
                        "--output_file", tmp_path,
                    ],
                    input=text,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
                )

                if process.returncode == 0:
                    # Play the WAV file
                    import sounddevice as sd
                    with wave.open(tmp_path, "rb") as wf:
                        audio = np.frombuffer(
                            wf.readframes(wf.getnframes()),
                            dtype=np.int16,
                        ).astype(np.float32) / 32768.0
                        audio *= self.volume_scale
                        sd.play(audio, samplerate=wf.getframerate())
                        sd.wait()

                    Path(tmp_path).unlink(missing_ok=True)
                    return True

            return False

        except Exception as e:
            log.error(f"Piper TTS error: {e}")
            return False

    def _speak_sapi(self, text: str) -> bool:
        """Speak using Windows SAPI5."""
        try:
            self._sapi_engine.Speak(text)
            return True
        except Exception as e:
            log.error(f"SAPI5 error: {e}")
            return False

    def set_volume(self, scale: float) -> None:
        """
        Set the TTS volume scale.

        Args:
            scale: Volume multiplier (0.0 to 2.0).
        """
        self.volume_scale = max(0.0, min(2.0, scale))
        log.debug(f"TTS volume set to {self.volume_scale:.1f}")

    @property
    def is_available(self) -> bool:
        return self._piper_available or self._sapi_available

    @property
    def engine_name(self) -> str:
        if self._piper_available:
            return "Piper TTS"
        elif self._sapi_available:
            return "Windows SAPI5"
        return "None"
