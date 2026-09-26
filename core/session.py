"""Ephemeral session manager for JurisGuide backed by Upstash Redis.

Enables the two-step flow (Classify -> Confirm/Override -> Extract) across
stateless serverless function invocations (e.g. Vercel) and traditional servers.
Sessions automatically expire via native Redis key TTL (SESSION_TTL_SECONDS).
"""

from __future__ import annotations

import os
import json
import time
import secrets
import logging
from typing import Optional, Dict, Any, List
from upstash_redis import Redis

from core.config import settings
from core.exceptions import SessionExpiredError

logger = logging.getLogger(__name__)

SESSION_KEY_PREFIX = "jurisguide:session:"


class EphemeralSessionStore:
    """Thread-safe, serverless-ready ephemeral document store backed by Upstash Redis."""

    def __init__(
        self,
        ttl_seconds: Optional[int] = None,
        redis_client: Optional[Redis] = None,
        url: Optional[str] = None,
        token: Optional[str] = None,
    ) -> None:
        self._ttl_seconds = ttl_seconds if ttl_seconds is not None else settings.session_ttl_seconds
        self._url = url or os.getenv("UPSTASH_REDIS_REST_URL") or settings.upstash_redis_rest_url
        self._token = token or os.getenv("UPSTASH_REDIS_REST_TOKEN") or settings.upstash_redis_rest_token

        if redis_client is not None:
            self._redis = redis_client
        elif self._url and self._token:
            self._redis = Redis(url=self._url, token=self._token)
        else:
            self._redis = None
            self._memory_store: Dict[str, Dict[str, Any]] = {}

    def _get_key(self, session_id: str) -> str:
        return f"{SESSION_KEY_PREFIX}{session_id}"

    def create_session(self, payload: Dict[str, Any]) -> str:
        """Store document payload in Redis with native TTL and return an ephemeral session ID."""
        session_id = secrets.token_urlsafe(24)
        key = self._get_key(session_id)
        serialized = json.dumps(payload)

        if self._redis is not None:
            self._redis.set(key, serialized, ex=self._ttl_seconds)
        else:
            self._memory_store[session_id] = {
                "created_at": time.time(),
                "payload": payload,
            }

        return session_id

    def get_session(self, session_id: str, refresh: bool = False) -> Dict[str, Any]:
        """Retrieve payload for a valid, non-expired session. Raises SessionExpiredError if missing."""
        key = self._get_key(session_id)

        if self._redis is not None:
            raw = self._redis.get(key)
            if raw is None:
                raise SessionExpiredError(session_id=session_id)
            if refresh:
                self._redis.expire(key, self._ttl_seconds)
            return json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        else:
            item = self._memory_store.get(session_id)
            if not item or (time.time() - item["created_at"] > self._ttl_seconds):
                self._memory_store.pop(session_id, None)
                raise SessionExpiredError(session_id=session_id)
            if refresh:
                item["created_at"] = time.time()
            return item["payload"]

    def pop_session(self, session_id: str) -> Dict[str, Any]:
        """Atomically retrieve and delete payload to maximize privacy (single-use).

        Uses Redis GETDEL to atomically fetch and remove the session in one operation.
        """
        key = self._get_key(session_id)

        if self._redis is not None:
            raw = self._redis.getdel(key)
            if raw is None:
                raise SessionExpiredError(session_id=session_id)
            return json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        else:
            item = self._memory_store.pop(session_id, None)
            if not item or (time.time() - item["created_at"] > self._ttl_seconds):
                raise SessionExpiredError(session_id=session_id)
            return item["payload"]

    def active_session_count(self) -> int:
        """Return the count of active unexpired sessions."""
        if self._redis is not None:
            keys = self._redis.keys(f"{SESSION_KEY_PREFIX}*")
            return len(keys) if keys else 0
        else:
            now = time.time()
            valid = [k for k, v in self._memory_store.items() if now - v["created_at"] <= self._ttl_seconds]
            return len(valid)

    def clear_all(self) -> None:
        """Flush all session keys (used for test teardown)."""
        if self._redis is not None:
            keys = self._redis.keys(f"{SESSION_KEY_PREFIX}*")
            if keys:
                self._redis.delete(*keys)
        else:
            self._memory_store.clear()


# Global session store singleton
session_store = EphemeralSessionStore()
