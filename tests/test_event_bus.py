"""
Penélope — Tests: EventBus
Validates pub/sub event system with sync and async handlers.
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock

import pytest

from penelope.core.event_bus import EventBus
from penelope.utils.constants import EventType


def _mock_handler(name: str = "mock_handler") -> MagicMock:
    """Create a MagicMock that has __qualname__ (needed by EventBus logging)."""
    m = MagicMock()
    m.__qualname__ = name
    return m


def _async_mock_handler(name: str = "async_mock_handler") -> AsyncMock:
    """Create an AsyncMock that has __qualname__."""
    m = AsyncMock()
    m.__qualname__ = name
    return m


class TestEventBusRegistration:
    """Handler registration and removal."""

    def test_register_handler(self, event_bus: EventBus):
        handler = _mock_handler("register")
        event_bus.on(EventType.WAKE_WORD_DETECTED, handler)
        assert handler in event_bus._handlers[EventType.WAKE_WORD_DETECTED]

    def test_remove_handler(self, event_bus: EventBus):
        handler = _mock_handler("remove")
        event_bus.on(EventType.WAKE_WORD_DETECTED, handler)
        event_bus.off(EventType.WAKE_WORD_DETECTED, handler)
        assert handler not in event_bus._handlers[EventType.WAKE_WORD_DETECTED]

    def test_remove_nonexistent_handler_is_safe(self, event_bus: EventBus):
        handler = _mock_handler("nonexistent")
        event_bus.off(EventType.WAKE_WORD_DETECTED, handler)  # should not raise

    def test_clear_removes_all(self, event_bus: EventBus):
        event_bus.on(EventType.WAKE_WORD_DETECTED, _mock_handler("a"))
        event_bus.on(EventType.AUTH_SUCCESS, _mock_handler("b"))
        event_bus.clear()
        assert len(event_bus._handlers) == 0
        assert len(event_bus._event_history) == 0


class TestEventBusEmitAsync:
    """Async event emission."""

    @pytest.mark.asyncio
    async def test_emit_calls_sync_handler(self, event_bus):
        handler = _mock_handler("sync_emit")
        event_bus.on(EventType.WAKE_WORD_DETECTED, handler)
        await event_bus.emit(EventType.WAKE_WORD_DETECTED, confidence=0.95)
        handler.assert_called_once_with(confidence=0.95)

    @pytest.mark.asyncio
    async def test_emit_calls_async_handler(self, event_bus):
        handler = _async_mock_handler("async_emit")
        event_bus.on(EventType.AUTH_SUCCESS, handler)
        await event_bus.emit(EventType.AUTH_SUCCESS, user_name="Pietro")
        handler.assert_called_once_with(user_name="Pietro")

    @pytest.mark.asyncio
    async def test_emit_multiple_handlers(self, event_bus):
        h1 = _mock_handler("multi_sync")
        h2 = _async_mock_handler("multi_async")
        event_bus.on(EventType.MODE_CHANGED, h1)
        event_bus.on(EventType.MODE_CHANGED, h2)
        await event_bus.emit(EventType.MODE_CHANGED, new_mode="game")
        h1.assert_called_once()
        h2.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_no_handlers_is_noop(self, event_bus):
        # Should not raise
        await event_bus.emit(EventType.SYSTEM_SHUTDOWN)

    @pytest.mark.asyncio
    async def test_handler_exception_does_not_propagate(self, event_bus):
        def bad_handler(**kwargs):
            raise ValueError("boom")

        good_handler = _mock_handler("good")
        event_bus.on(EventType.MODE_CHANGED, bad_handler)
        event_bus.on(EventType.MODE_CHANGED, good_handler)

        await event_bus.emit(EventType.MODE_CHANGED, new_mode="normal")
        # Good handler should still be called despite bad handler raising
        good_handler.assert_called_once()


class TestEventBusOnce:
    """One-time handler support."""

    @pytest.mark.asyncio
    async def test_once_handler_fires_once(self, event_bus):
        handler = _mock_handler("once_sync")
        event_bus.once(EventType.AUTH_SUCCESS, handler)

        await event_bus.emit(EventType.AUTH_SUCCESS, user_name="X")
        await event_bus.emit(EventType.AUTH_SUCCESS, user_name="Y")

        handler.assert_called_once_with(user_name="X")

    @pytest.mark.asyncio
    async def test_once_async_handler(self, event_bus):
        handler = _async_mock_handler("once_async")
        event_bus.once(EventType.TRANSCRIPTION_READY, handler)
        await event_bus.emit(EventType.TRANSCRIPTION_READY, text="hello")
        handler.assert_called_once()


class TestEventBusEmitSync:
    """Synchronous event emission (for non-async contexts)."""

    def test_emit_sync_calls_sync_handler(self, event_bus):
        handler = _mock_handler("sync_only")
        event_bus.on(EventType.HUD_UPDATE, handler)
        event_bus.emit_sync(EventType.HUD_UPDATE, state="idle")
        handler.assert_called_once_with(state="idle")


class TestEventBusHistory:
    """Event history recording."""

    @pytest.mark.asyncio
    async def test_records_event_in_history(self, event_bus):
        await event_bus.emit(EventType.WAKE_WORD_DETECTED, confidence=0.9)
        history = event_bus.get_history()
        assert len(history) == 1
        assert history[0]["type"] == EventType.WAKE_WORD_DETECTED.value

    @pytest.mark.asyncio
    async def test_history_filter_by_type(self, event_bus):
        await event_bus.emit(EventType.WAKE_WORD_DETECTED)
        await event_bus.emit(EventType.AUTH_SUCCESS, user_name="X")
        await event_bus.emit(EventType.WAKE_WORD_DETECTED)

        wake_events = event_bus.get_history(EventType.WAKE_WORD_DETECTED)
        assert len(wake_events) == 2

        auth_events = event_bus.get_history(EventType.AUTH_SUCCESS)
        assert len(auth_events) == 1

    @pytest.mark.asyncio
    async def test_history_max_size(self, event_bus):
        event_bus._max_history = 5
        for _ in range(10):
            await event_bus.emit(EventType.HUD_UPDATE)
        assert len(event_bus.get_history()) == 5
