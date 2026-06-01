"""
Penélope — Event Bus
Pub/sub system for decoupled inter-module communication.
"""

import asyncio
import inspect
from collections import defaultdict
from typing import Any, Callable, Coroutine, Dict, List, Optional, Union

from penelope.utils.constants import EventType
from penelope.utils.logger import get_logger

log = get_logger(__name__)

# Type aliases
SyncHandler = Callable[..., None]
AsyncHandler = Callable[..., Coroutine]
Handler = Union[SyncHandler, AsyncHandler]


class EventBus:
    """
    Central event bus for the Penélope system.

    Allows modules to communicate without direct coupling.
    Supports both synchronous and asynchronous handlers.

    Usage:
        bus = EventBus()
        bus.on(EventType.WAKE_WORD_DETECTED, my_handler)
        await bus.emit(EventType.WAKE_WORD_DETECTED, confidence=0.95)
    """

    def __init__(self) -> None:
        self._handlers: Dict[EventType, List[Handler]] = defaultdict(list)
        self._once_handlers: Dict[EventType, List[Handler]] = defaultdict(list)
        self._event_history: List[Dict[str, Any]] = []
        self._max_history = 100

    def on(self, event_type: EventType, handler: Handler) -> None:
        """
        Register a handler for an event type.

        Args:
            event_type: The event to listen for.
            handler: Callback function (sync or async).
        """
        self._handlers[event_type].append(handler)
        log.debug(f"Handler registered for {event_type.value}: {handler.__qualname__}")

    def once(self, event_type: EventType, handler: Handler) -> None:
        """
        Register a one-time handler that auto-removes after first call.

        Args:
            event_type: The event to listen for.
            handler: Callback function (sync or async).
        """
        self._once_handlers[event_type].append(handler)

    def off(self, event_type: EventType, handler: Handler) -> None:
        """
        Remove a handler for an event type.

        Args:
            event_type: The event type.
            handler: The handler to remove.
        """
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            log.debug(f"Handler removed for {event_type.value}: {handler.__qualname__}")

    async def emit(self, event_type: EventType, **kwargs: Any) -> None:
        """
        Emit an event, calling all registered handlers.

        Args:
            event_type: The event to emit.
            **kwargs: Data to pass to handlers.
        """
        # Record in history
        self._record_event(event_type, kwargs)

        handlers = list(self._handlers.get(event_type, []))
        once_handlers = list(self._once_handlers.pop(event_type, []))

        all_handlers = handlers + once_handlers

        if not all_handlers:
            return

        log.debug(f"Emitting {event_type.value} → {len(all_handlers)} handler(s)")

        for handler in all_handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(**kwargs)
                else:
                    handler(**kwargs)
            except Exception as e:
                log.error(
                    f"Error in handler {handler.__qualname__} "
                    f"for {event_type.value}: {e}"
                )

    def emit_sync(self, event_type: EventType, **kwargs: Any) -> None:
        """
        Emit an event synchronously (for use outside async context).

        Creates a new event loop task if an event loop is running,
        otherwise runs handlers directly (sync only).

        Args:
            event_type: The event to emit.
            **kwargs: Data to pass to handlers.
        """
        self._record_event(event_type, kwargs)

        handlers = list(self._handlers.get(event_type, []))
        once_handlers = list(self._once_handlers.pop(event_type, []))
        all_handlers = handlers + once_handlers

        for handler in all_handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(handler(**kwargs))
                    except RuntimeError:
                        asyncio.run(handler(**kwargs))
                else:
                    handler(**kwargs)
            except Exception as e:
                log.error(
                    f"Error in sync handler {handler.__qualname__} "
                    f"for {event_type.value}: {e}"
                )

    def _record_event(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """Record event in history ring buffer."""
        import time
        self._event_history.append({
            "type": event_type.value,
            "timestamp": time.time(),
            "data_keys": list(data.keys()),
        })
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

    def get_history(self, event_type: Optional[EventType] = None) -> List[Dict[str, Any]]:
        """
        Get event history, optionally filtered by type.

        Args:
            event_type: Filter by this event type (None = all).

        Returns:
            List of event records.
        """
        if event_type is None:
            return list(self._event_history)
        return [e for e in self._event_history if e["type"] == event_type.value]

    def clear(self) -> None:
        """Remove all handlers and clear history."""
        self._handlers.clear()
        self._once_handlers.clear()
        self._event_history.clear()
        log.info("Event bus cleared")


# Global singleton
_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get or create the global EventBus singleton."""
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
