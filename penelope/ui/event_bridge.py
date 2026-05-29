"""
Penélope — Qt Event Bridge
Bridges EventBus calls to PyQt6 Signals to ensure thread-safe UI updates.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from penelope.core.event_bus import get_event_bus
from penelope.utils.constants import EventType

class QtEventBridge(QObject):
    """
    Singleton bridge that subscribes to the EventBus
    and forwards events as PyQt signals.
    """
    _instance = None

    transcription_ready = pyqtSignal(str)
    llm_response_chunk = pyqtSignal(str)
    llm_response_complete = pyqtSignal(str)
    auth_success = pyqtSignal(str, object)
    session_expired = pyqtSignal()
    mode_changed = pyqtSignal(object)
    wake_word_detected = pyqtSignal()
    listening_stopped = pyqtSignal()
    tts_started = pyqtSignal()
    tts_finished = pyqtSignal()
    llm_offline = pyqtSignal()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        super().__init__()
        self.bus = get_event_bus()
        self._register_bus_listeners()
        self._initialized = True

    def _register_bus_listeners(self) -> None:
        self.bus.on(EventType.TRANSCRIPTION_READY, lambda text="", **_: self.transcription_ready.emit(text))
        self.bus.on(EventType.LLM_RESPONSE_CHUNK, lambda chunk="", **_: self.llm_response_chunk.emit(chunk))
        self.bus.on(EventType.LLM_RESPONSE_COMPLETE, lambda response="", **_: self.llm_response_complete.emit(response))
        self.bus.on(EventType.AUTH_SUCCESS, lambda user_name="", user_level=None, **_: self.auth_success.emit(user_name, user_level))
        self.bus.on(EventType.SESSION_EXPIRED, lambda **_: self.session_expired.emit())
        self.bus.on(EventType.MODE_CHANGED, lambda new_mode=None, **_: self.mode_changed.emit(new_mode))
        self.bus.on(EventType.WAKE_WORD_DETECTED, lambda **_: self.wake_word_detected.emit())
        self.bus.on(EventType.LISTENING_STOPPED, lambda **_: self.listening_stopped.emit())
        self.bus.on(EventType.TTS_STARTED, lambda **_: self.tts_started.emit())
        self.bus.on(EventType.TTS_FINISHED, lambda **_: self.tts_finished.emit())
        self.bus.on(EventType.LLM_OFFLINE, lambda **_: self.llm_offline.emit())
