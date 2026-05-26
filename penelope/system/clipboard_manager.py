"""
Penélope — Clipboard Manager
Monitors and indexes clipboard history with semantic search.
"""

import sqlite3
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

from penelope.utils.constants import CLIPBOARD_DB_PATH
from penelope.utils.logger import get_logger

log = get_logger(__name__)


class ClipboardManager:
    """
    Monitors the system clipboard and maintains a searchable history.

    Supports text-based search and integrates with ChromaDB
    for semantic search capabilities.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        max_entries: int = 500,
        poll_interval: float = 1.0,
    ) -> None:
        self.db_path = db_path or CLIPBOARD_DB_PATH
        self.max_entries = max_entries
        self.poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_content: str = ""
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the clipboard history database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS clipboard_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    content_type TEXT DEFAULT 'text',
                    timestamp REAL NOT NULL,
                    app_source TEXT DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_clipboard_timestamp
                ON clipboard_history(timestamp DESC)
            """)
            conn.commit()
        finally:
            conn.close()

    def start(self) -> None:
        """Start monitoring the clipboard."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="clipboard_monitor",
            daemon=True,
        )
        self._thread.start()
        log.info("Clipboard monitor started")

    def stop(self) -> None:
        """Stop monitoring the clipboard."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        log.info("Clipboard monitor stopped")

    def _monitor_loop(self) -> None:
        """Continuously poll the clipboard for changes."""
        while self._running:
            try:
                self._check_clipboard()
                time.sleep(self.poll_interval)
            except Exception as e:
                log.debug(f"Clipboard check error: {e}")
                time.sleep(2.0)

    def _check_clipboard(self) -> None:
        """Check if clipboard content has changed."""
        try:
            import pyperclip
            content = pyperclip.paste()

            if content and content != self._last_content:
                self._last_content = content
                self._save_entry(content)
        except Exception:
            pass

    def _save_entry(self, content: str) -> None:
        """Save a clipboard entry to the database."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "INSERT INTO clipboard_history (content, timestamp) VALUES (?, ?)",
                (content[:10000], time.time()),  # Limit size
            )

            # Prune old entries
            conn.execute(
                """
                DELETE FROM clipboard_history
                WHERE id NOT IN (
                    SELECT id FROM clipboard_history
                    ORDER BY timestamp DESC
                    LIMIT ?
                )
                """,
                (self.max_entries,),
            )

            conn.commit()
            log.debug(f"Clipboard entry saved: '{content[:50]}...'")
        finally:
            conn.close()

    def get_history(self, limit: int = 20) -> List[Dict]:
        """Get recent clipboard history."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM clipboard_history ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search clipboard history by text content.

        Args:
            query: Search text.
            limit: Maximum results.

        Returns:
            Matching clipboard entries.
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT * FROM clipboard_history
                WHERE content LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (f"%{query}%", limit),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_last(self) -> Optional[str]:
        """Get the most recent clipboard content."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute(
                "SELECT content FROM clipboard_history ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def clear_history(self) -> None:
        """Clear all clipboard history."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("DELETE FROM clipboard_history")
            conn.commit()
            log.info("Clipboard history cleared")
        finally:
            conn.close()
