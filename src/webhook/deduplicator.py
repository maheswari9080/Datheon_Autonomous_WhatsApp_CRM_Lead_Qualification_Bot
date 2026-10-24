"""Message deduplication and idempotency engine."""

import time
from collections import OrderedDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.logging import get_logger
from src.database.models import Message

logger = get_logger(__name__)


class MessageDeduplicator:
    """Thread-safe, dual-layer deduplication cache (In-Memory LRU with TTL + DB check)."""

    def __init__(self, max_size: int = 10000, ttl_seconds: int = 86400):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, float] = OrderedDict()

    def _cleanup_expired(self) -> None:
        """Evict expired keys from cache."""
        now = time.time()
        keys_to_remove = [k for k, ts in self._cache.items() if now - ts > self.ttl_seconds]
        for k in keys_to_remove:
            self._cache.pop(k, None)

    def is_processed_in_memory(self, message_id: str) -> bool:
        """Fast LRU in-memory check."""
        if not message_id:
            return False

        self._cleanup_expired()
        now = time.time()
        if message_id in self._cache:
            if now - self._cache[message_id] <= self.ttl_seconds:
                # Refresh position in LRU
                self._cache.move_to_end(message_id)
                return True
            else:
                self._cache.pop(message_id, None)

        return False

    def mark_processed_in_memory(self, message_id: str) -> None:
        """Record message ID in LRU cache."""
        if not message_id:
            return
        if len(self._cache) >= self.max_size:
            # Pop oldest item
            self._cache.popitem(last=False)
        self._cache[message_id] = time.time()

    async def is_duplicate(self, message_id: str, db: AsyncSession) -> bool:
        """Dual-layer deduplication check: checks in-memory LRU first, then DB."""
        if not message_id:
            return False

        # Layer 1: In-memory cache
        if self.is_processed_in_memory(message_id):
            logger.info(f"Duplicate message detected in-memory cache: {message_id}")
            return True

        # Layer 2: Persistent database check
        stmt = select(Message.id).where(Message.meta_message_id == message_id).limit(1)
        result = await db.execute(stmt)
        exists = result.scalar_one_or_none() is not None

        if exists:
            self.mark_processed_in_memory(message_id)
            logger.info(f"Duplicate message detected in database: {message_id}")
            return True

        return False


# Singleton deduplicator instance
deduplicator = MessageDeduplicator()
