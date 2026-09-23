"""Ephemeral in-memory session manager for JurisGuide.

Enables the two-step flow (Classify -> Confirm/Override -> Extract)
without persisting any documents or PII to disk or database.
Sessions automatically expire after SESSION_TTL_SECONDS.
"""

from __future__ import annotations

import time
import secrets
from threading import Lock
from typing import Optional, Dict, Any
from core.config import settings
from core.exceptions import SessionExpiredError


class EphemeralSessionStore:
    """Thread-safe, in-memory ephemeral document store with TTL expiration."""

    def __init__(self, ttl_seconds: Optional[int] = None) -> None:
        self._ttl_seconds = ttl_seconds if ttl_seconds is not None else settings.session_ttl_seconds
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()

    def _purge_expired(self) -> None:
        """Internal helper to sweep away expired sessions."""
        now = time.time()
        expired_keys = [
            sid for sid, item in self._store.items()
            if now - item["created_at"] > self._ttl_seconds
        ]
        for sid in expired_keys:
            self._store.pop(sid, None)

    def create_session(self, payload: Dict[str, Any]) -> str:
        """Store document payload in memory and return an ephemeral session ID."""
        with self._lock:
            self._purge_expired()
            session_id = secrets.token_urlsafe(24)
            self._store[session_id] = {
                "created_at": time.time(),
                "payload": payload,
            }
            return session_id

    def get_session(self, session_id: str, refresh: bool = False) -> Dict[str, Any]:
        """Retrieve payload for a valid, non-expired session. Raises SessionExpiredError if missing."""
        with self._lock:
            self._purge_expired()
            item = self._store.get(session_id)
            if not item:
                raise SessionExpiredError(session_id=session_id)

            if refresh:
                item["created_at"] = time.time()
            return item["payload"]

    def pop_session(self, session_id: str) -> Dict[str, Any]:
        """Retrieve and immediately delete payload to maximize privacy."""
        with self._lock:
            self._purge_expired()
            item = self._store.pop(session_id, None)
            if not item:
                raise SessionExpiredError(session_id=session_id)
            return item["payload"]

    def active_session_count(self) -> int:
        """Return the number of unexpired sessions currently in memory."""
        with self._lock:
            self._purge_expired()
            return len(self._store)

    def clear_all(self) -> None:
        """Flush all active sessions (used primarily in test fixtures)."""
        with self._lock:
            self._store.clear()


# Global ephemeral store singleton
session_store = EphemeralSessionStore()
