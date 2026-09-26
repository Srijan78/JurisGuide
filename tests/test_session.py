"""Tests for Upstash Redis backed EphemeralSessionStore.

Validates:
1. Session creation and retrieval over the real Upstash Redis SDK (mocked execute).
2. Atomic single-use pop semantics (GETDEL).
3. Native Redis key TTL expiration.
4. Key scoping for active_session_count() and clear_all() (foreign keys untouched).
5. Cross-instance session sharing simulating separate serverless invocations (Vercel).
6. In-memory fallback mode when Upstash credentials are not configured.
"""

import time
import pytest
from upstash_redis import Redis
from core.session import EphemeralSessionStore, SESSION_KEY_PREFIX
from core.exceptions import SessionExpiredError


class MockUpstashRedis(Redis):
    """Subclass of upstash_redis.Redis that intercepts execute() and executes commands

    against an in-memory dictionary. This exercises the REAL upstash_redis.Redis SDK
    methods (set, get, getdel, expire, keys, delete) without making live HTTP requests.
    """

    def __init__(self, shared_storage=None):
        super().__init__(url="https://mock-db.upstash.io", token="mock-token-xyz")
        self.storage = shared_storage if shared_storage is not None else {}
        self.expirations = {}

    def execute(self, command: list):
        cmd = str(command[0]).upper()
        if cmd == "SET":
            # ["SET", key, value, "EX", seconds]
            key, val = command[1], command[2]
            self.storage[key] = val
            if len(command) >= 5 and str(command[3]).upper() == "EX":
                self.expirations[key] = time.time() + int(command[4])
            return "OK"
        elif cmd == "GET":
            key = command[1]
            if key not in self.storage:
                return None
            if key in self.expirations and time.time() > self.expirations[key]:
                del self.storage[key]
                self.expirations.pop(key, None)
                return None
            return self.storage[key]
        elif cmd == "GETDEL":
            key = command[1]
            val = self.execute(["GET", key])
            if key in self.storage:
                del self.storage[key]
            self.expirations.pop(key, None)
            return val
        elif cmd == "EXPIRE":
            key, secs = command[1], int(command[2])
            if key in self.storage:
                self.expirations[key] = time.time() + secs
                return 1
            return 0
        elif cmd == "KEYS":
            pattern = str(command[1]).rstrip("*")
            return [k for k in self.storage if k.startswith(pattern)]
        elif cmd == "DEL":
            keys = command[1:]
            deleted = 0
            for k in keys:
                if k in self.storage:
                    del self.storage[k]
                    deleted += 1
                self.expirations.pop(k, None)
            return deleted
        raise NotImplementedError(f"Command {cmd} not mocked in test suite")


def test_session_create_and_get_redis_path():
    """Verify session creation and retrieval using the Redis SDK path."""
    mock_redis = MockUpstashRedis()
    store = EphemeralSessionStore(ttl_seconds=600, redis_client=mock_redis)

    test_payload = {"filename": "offer.pdf", "text": "Confidential contract text"}
    session_id = store.create_session(test_payload)

    assert isinstance(session_id, str)
    assert len(session_id) > 10

    # Retrieve from Redis
    retrieved = store.get_session(session_id)
    assert retrieved == test_payload
    assert store.active_session_count() == 1


def test_session_pop_single_use_atomicity():
    """Verify pop_session uses atomic GETDEL so the session cannot be reused."""
    mock_redis = MockUpstashRedis()
    store = EphemeralSessionStore(ttl_seconds=600, redis_client=mock_redis)

    test_payload = {"filename": "lease.docx", "monthly_rent": 2500}
    session_id = store.create_session(test_payload)

    # First pop must succeed
    popped = store.pop_session(session_id)
    assert popped == test_payload

    # Second pop or get must fail with SessionExpiredError (single-use enforced)
    with pytest.raises(SessionExpiredError):
        store.pop_session(session_id)

    with pytest.raises(SessionExpiredError):
        store.get_session(session_id)


def test_session_ttl_expiration_redis_path():
    """Verify that expired Redis keys trigger SessionExpiredError."""
    mock_redis = MockUpstashRedis()
    store = EphemeralSessionStore(ttl_seconds=1, redis_client=mock_redis)

    session_id = store.create_session({"status": "pending"})

    # Manually advance expiration time in mock
    redis_key = f"{SESSION_KEY_PREFIX}{session_id}"
    mock_redis.expirations[redis_key] = time.time() - 5

    # Should raise SessionExpiredError due to TTL expiry
    with pytest.raises(SessionExpiredError):
        store.get_session(session_id)


def test_session_invalid_id_raises_expired_error():
    """Verify querying non-existent session IDs returns clean SessionExpiredError."""
    mock_redis = MockUpstashRedis()
    store = EphemeralSessionStore(ttl_seconds=600, redis_client=mock_redis)

    with pytest.raises(SessionExpiredError):
        store.get_session("non_existent_id")

    with pytest.raises(SessionExpiredError):
        store.pop_session("non_existent_id")


def test_active_session_count_scoped_to_jurisguide_prefix():
    """Verify active_session_count only counts app sessions and ignores foreign Redis keys."""
    mock_redis = MockUpstashRedis()
    store = EphemeralSessionStore(ttl_seconds=600, redis_client=mock_redis)

    # Add 2 JurisGuide sessions
    store.create_session({"doc": "1"})
    store.create_session({"doc": "2"})

    # Add 2 foreign keys from another application sharing the Redis database
    mock_redis.storage["unrelated:analytics:daily"] = "123"
    mock_redis.storage["user:session:auth"] = "abc"

    # Must only count the 2 JurisGuide sessions
    assert store.active_session_count() == 2


def test_clear_all_scoped_does_not_delete_foreign_keys():
    """Verify clear_all only purges jurisguide:session:* keys and leaves other keys intact."""
    mock_redis = MockUpstashRedis()
    store = EphemeralSessionStore(ttl_seconds=600, redis_client=mock_redis)

    session_id = store.create_session({"doc": "to_be_cleared"})

    # Add a foreign key
    foreign_key = "external_app:user_tokens:999"
    mock_redis.storage[foreign_key] = "keep_me"

    # Clear JurisGuide sessions
    store.clear_all()

    # Session must be deleted
    with pytest.raises(SessionExpiredError):
        store.get_session(session_id)

    # Foreign key must be completely untouched
    assert foreign_key in mock_redis.storage
    assert mock_redis.storage[foreign_key] == "keep_me"


def test_serverless_cross_instance_session_sharing():
    """Regression test: Two separate store client instances (simulating separate Vercel

    serverless invocations) must be able to read and pop sessions created by each other.
    """
    # Shared remote Upstash Redis database storage
    shared_redis_storage = {}

    # Instance 1: Handles Step 1 (Classify request in Vercel Invocation 1)
    client_instance_1 = MockUpstashRedis(shared_storage=shared_redis_storage)
    serverless_store_1 = EphemeralSessionStore(ttl_seconds=600, redis_client=client_instance_1)

    # Step 1: Document uploaded and session created
    original_payload = {
        "filename": "freelance_sow.docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "is_multimodal": False,
        "raw_text": "Hourly rate: $150. Payment terms: Net 60.",
    }
    session_id = serverless_store_1.create_session(original_payload)

    # Instance 2: Handles Step 2 (Confirm & Analyze request in Vercel Invocation 2)
    # Completely independent store object mimicking a new Lambda container
    client_instance_2 = MockUpstashRedis(shared_storage=shared_redis_storage)
    serverless_store_2 = EphemeralSessionStore(ttl_seconds=600, redis_client=client_instance_2)

    # Step 2: Reads the session created by Instance 1
    session_data = serverless_store_2.get_session(session_id)
    assert session_data == original_payload, "Instance 2 failed to read session written by Instance 1!"

    # Step 3: Instance 2 pops the session for analysis
    popped_data = serverless_store_2.pop_session(session_id)
    assert popped_data == original_payload

    # Now both instances must see the session as consumed/expired
    with pytest.raises(SessionExpiredError):
        serverless_store_1.get_session(session_id)

    with pytest.raises(SessionExpiredError):
        serverless_store_2.get_session(session_id)


def test_in_memory_fallback_mode_when_unconfigured():
    """Verify local development fallback when Upstash credentials are not set."""
    # Initialize without URL, token, or redis_client
    local_store = EphemeralSessionStore(ttl_seconds=600, redis_client=None, url="", token="")
    assert local_store._redis is None

    payload = {"source": "local_dev_test"}
    sid = local_store.create_session(payload)
    assert local_store.get_session(sid) == payload
    assert local_store.active_session_count() == 1

    popped = local_store.pop_session(sid)
    assert popped == payload
    assert local_store.active_session_count() == 0

    with pytest.raises(SessionExpiredError):
        local_store.get_session(sid)
