"""
Penélope — Memory Manager
Three-tier memory: short-term buffer, medium-term SQLite, long-term ChromaDB.
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from penelope.utils.constants import DATA_DIR, SESSIONS_DB_PATH, CHROMA_DIR
from penelope.utils.logger import get_logger

log = get_logger(__name__)


class MemoryManager:
    """
    Three-layer memory system for Penélope.

    - Short-term: In-memory buffer of current conversation
    - Medium-term: SQLite database of past sessions per profile
    - Long-term: ChromaDB vector database for learned facts and preferences
    """

    def __init__(
        self,
        sessions_db: Optional[Path] = None,
        chroma_dir: Optional[Path] = None,
    ) -> None:
        self.sessions_db = sessions_db or SESSIONS_DB_PATH
        self.chroma_dir = chroma_dir or CHROMA_DIR

        # Short-term: current conversation buffer
        self._short_term: List[Dict[str, str]] = []
        self._max_short_term = 20

        # Medium-term: SQLite
        self._init_sessions_db()

        # Long-term: ChromaDB (lazy init)
        self._chroma_client = None
        self._chroma_collection = None

    def _init_sessions_db(self) -> None:
        """Initialize the sessions SQLite database."""
        self.sessions_db.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.sessions_db))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER NOT NULL,
                    profile_name TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    ended_at REAL,
                    messages TEXT NOT NULL DEFAULT '[]',
                    summary TEXT DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    learned_at REAL NOT NULL,
                    last_used REAL,
                    use_count INTEGER DEFAULT 0
                )
            """)
            conn.commit()
            log.debug("Sessions database initialized")
        finally:
            conn.close()

    def _get_chroma(self):
        """Lazy-init ChromaDB client and collection."""
        if self._chroma_client is None:
            try:
                import chromadb
                self.chroma_dir.mkdir(parents=True, exist_ok=True)
                self._chroma_client = chromadb.PersistentClient(
                    path=str(self.chroma_dir)
                )
                self._chroma_collection = self._chroma_client.get_or_create_collection(
                    name="penelope_memory",
                    metadata={"description": "Long-term memory for Penélope"},
                )
                log.info("ChromaDB initialized for long-term memory")
            except ImportError:
                log.warning("ChromaDB not installed — long-term memory disabled")
                return None
            except Exception as e:
                log.error(f"Failed to initialize ChromaDB: {e}")
                return None
        return self._chroma_collection

    # =============================================
    # Short-term memory (conversation buffer)
    # =============================================

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the current conversation buffer."""
        self._short_term.append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
        })
        if len(self._short_term) > self._max_short_term:
            self._short_term.pop(0)

    def get_conversation(self) -> List[Dict[str, str]]:
        """Get the current conversation history."""
        return [
            {"role": m["role"], "content": m["content"]}
            for m in self._short_term
        ]

    def clear_conversation(self) -> None:
        """Clear the short-term conversation buffer."""
        self._short_term.clear()

    # =============================================
    # Medium-term memory (session history)
    # =============================================

    def save_session(
        self,
        profile_id: int,
        profile_name: str,
        messages: List[Dict[str, str]],
        summary: str = "",
    ) -> None:
        """Save the current conversation as a session record."""
        conn = sqlite3.connect(str(self.sessions_db))
        try:
            conn.execute(
                """
                INSERT INTO sessions
                    (profile_id, profile_name, started_at, ended_at, messages, summary)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_id,
                    profile_name,
                    self._short_term[0]["timestamp"] if self._short_term else time.time(),
                    time.time(),
                    json.dumps(messages, ensure_ascii=False),
                    summary,
                ),
            )
            conn.commit()
            log.debug(f"Session saved for {profile_name} ({len(messages)} messages)")
        finally:
            conn.close()

    def get_recent_sessions(
        self, profile_id: int, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent sessions for a profile."""
        conn = sqlite3.connect(str(self.sessions_db))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT * FROM sessions
                WHERE profile_id = ?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (profile_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    # =============================================
    # Long-term memory (facts & preferences)
    # =============================================

    def remember(
        self,
        key: str,
        value: str,
        category: str = "general",
        profile_id: Optional[int] = None,
        confidence: float = 1.0,
    ) -> None:
        """
        Store a fact or preference in long-term memory.

        Uses both SQLite (structured) and ChromaDB (semantic search).

        Args:
            key: Fact identifier (e.g., "favorite_browser").
            value: Fact value (e.g., "Chrome").
            category: Category for organization.
            profile_id: Associated profile (None = global).
            confidence: Confidence level (0.0 to 1.0).
        """
        # SQLite structured storage
        conn = sqlite3.connect(str(self.sessions_db))
        try:
            # Upsert: update if exists, insert if not
            existing = conn.execute(
                "SELECT id FROM facts WHERE key = ? AND profile_id IS ?",
                (key, profile_id),
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE facts
                    SET value = ?, confidence = ?, learned_at = ?, category = ?
                    WHERE id = ?
                    """,
                    (value, confidence, time.time(), category, existing[0]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO facts
                        (profile_id, category, key, value, confidence, learned_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (profile_id, category, key, value, confidence, time.time()),
                )
            conn.commit()
        finally:
            conn.close()

        # ChromaDB semantic storage
        collection = self._get_chroma()
        if collection is not None:
            try:
                doc_id = f"{profile_id or 'global'}:{key}"
                collection.upsert(
                    ids=[doc_id],
                    documents=[f"{key}: {value}"],
                    metadatas=[{
                        "profile_id": str(profile_id or "global"),
                        "category": category,
                        "key": key,
                        "confidence": confidence,
                        "timestamp": time.time(),
                    }],
                )
            except Exception as e:
                log.warning(f"Failed to store in ChromaDB: {e}")

        log.debug(f"Remembered: {key} = {value} (category={category})")

    def recall(
        self,
        key: Optional[str] = None,
        category: Optional[str] = None,
        profile_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Recall facts from structured memory (SQLite).

        Args:
            key: Specific fact key to look up.
            category: Filter by category.
            profile_id: Filter by profile.

        Returns:
            List of matching fact records.
        """
        conn = sqlite3.connect(str(self.sessions_db))
        conn.row_factory = sqlite3.Row
        try:
            query = "SELECT * FROM facts WHERE 1=1"
            params = []

            if key:
                query += " AND key = ?"
                params.append(key)
            if category:
                query += " AND category = ?"
                params.append(category)
            if profile_id is not None:
                query += " AND profile_id = ?"
                params.append(profile_id)

            query += " ORDER BY learned_at DESC"
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def semantic_search(
        self,
        query: str,
        n_results: int = 5,
        profile_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search long-term memory semantically using ChromaDB.

        Args:
            query: Natural language search query.
            n_results: Maximum number of results.
            profile_id: Filter by profile.

        Returns:
            List of matching documents with metadata.
        """
        collection = self._get_chroma()
        if collection is None:
            return []

        try:
            where_filter = None
            if profile_id is not None:
                where_filter = {"profile_id": str(profile_id)}

            results = collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter,
            )

            output = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    output.append({
                        "document": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0,
                    })
            return output

        except Exception as e:
            log.error(f"Semantic search failed: {e}")
            return []
