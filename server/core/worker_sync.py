"""Worker synchronization for multi-worker deployments.

This module provides distributed coordination for initialization tasks
that should only run once across multiple workers.
"""

import os
import asyncio
from enum import Enum
from typing import Optional, Callable, Any
from datetime import datetime, timedelta

import redis.asyncio as redis_async
import redis

from server.logging_config import get_logger

logger = get_logger(name=__name__)


class InitTask(Enum):
    """Initialization tasks that should run only once."""
    ALEMBIC_MIGRATION = "alembic_migration"
    QDRANT_COLLECTIONS = "qdrant_collections"
    STORAGE_DIRECTORIES = "storage_directories"
    CONTEXT_PROVIDERS = "context_providers"
    CACHE_WARMUP = "cache_warmup"
    DASHBOARD_SNAPSHOT = "dashboard_snapshot"


class WorkerSync:
    """Handles distributed synchronization across multiple workers.

    Uses Redis for distributed locking to ensure initialization tasks
    run exactly once, even with multiple workers starting simultaneously.
    """

    def __init__(self, redis_client: redis_async.Redis):
        """Initialize worker synchronization.

        Args:
            redis_client: Async Redis client for distributed coordination
        """
        self.redis = redis_client
        self.worker_id = f"worker-{os.getpid()}"
        self.hostname = os.environ.get('HOSTNAME', 'local')
        self.lock_prefix = "worker:init:"
        self.complete_prefix = "worker:complete:"
        self.lock_timeout = 60  # seconds
        self.wait_timeout = 120  # seconds to wait for other worker

    async def run_once(
        self,
        task: InitTask,
        func: Callable,
        *args,
        **kwargs
    ) -> tuple[bool, Any]:
        """Run a function exactly once across all workers.

        Args:
            task: The initialization task identifier
            func: The async function to run
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Tuple of (was_leader, result):
                - was_leader: True if this worker ran the task
                - result: The function result if was_leader, else None
        """
        lock_key = f"{self.lock_prefix}{task.value}"
        complete_key = f"{self.complete_prefix}{task.value}"

        # Check if task is already complete
        if await self.redis.get(complete_key):
            logger.info(
                "{} skipping {} - already completed by another worker",
                self.worker_id, task.value
            )
            return False, None

        # Try to acquire lock
        lock_value = f"{self.worker_id}:{self.hostname}:{datetime.utcnow().isoformat()}"
        acquired = await self.redis.set(
            lock_key,
            lock_value,
            nx=True,  # Only set if not exists (atomic)
            ex=self.lock_timeout  # Auto-expire to prevent deadlock
        )

        if acquired:
            # This worker is the leader for this task
            logger.info(
                "{} acquired lock for {} - executing initialization",
                self.worker_id, task.value
            )

            try:
                # Execute the initialization function
                result = await func(*args, **kwargs)

                # Mark task as complete (persist for 24 hours)
                await self.redis.setex(
                    complete_key,
                    86400,  # 24 hour TTL
                    f"completed_by:{self.worker_id}:at:{datetime.utcnow().isoformat()}"
                )

                logger.info(
                    "{} successfully completed {}",
                    self.worker_id, task.value
                )

                return True, result

            except Exception as e:
                logger.error(
                    "{} failed to complete {}: {}",
                    self.worker_id, task.value, e
                )
                # Delete lock on failure so another worker can retry
                await self.redis.delete(lock_key)
                raise

            finally:
                # Clean up lock (if we still hold it)
                current_lock = await self.redis.get(lock_key)
                if current_lock and current_lock.startswith(f"{self.worker_id}:"):
                    await self.redis.delete(lock_key)

        else:
            # Another worker is handling this task
            logger.info(
                "{} waiting for another worker to complete {}",
                self.worker_id, task.value
            )

            # Wait for the task to be completed
            await self._wait_for_completion(complete_key, task.value)

            return False, None

    async def _wait_for_completion(self, complete_key: str, task_name: str):
        """Wait for another worker to complete a task.

        Args:
            complete_key: Redis key that will be set when task is complete
            task_name: Name of the task (for logging)
        """
        start_time = datetime.utcnow()
        check_interval = 0.5  # Check every 500ms

        while (datetime.utcnow() - start_time).total_seconds() < self.wait_timeout:
            if await self.redis.get(complete_key):
                logger.info(
                    "{} detected {} completed by another worker",
                    self.worker_id, task_name
                )
                return

            await asyncio.sleep(check_interval)

        logger.warning(
            "{} timed out waiting for {} to complete ({}s timeout)",
            self.worker_id, task_name, self.wait_timeout
        )

    async def is_leader(self) -> bool:
        """Check if this worker should be the overall initialization leader.

        This is a simpler check for cases where you want one worker
        to do multiple tasks without checking each one individually.
        """
        leader_key = f"{self.lock_prefix}leader"
        leader_value = f"{self.worker_id}:{datetime.utcnow().isoformat()}"

        acquired = await self.redis.set(
            leader_key,
            leader_value,
            nx=True,
            ex=300  # 5 minute leadership
        )

        if acquired:
            logger.info("{} is the initialization leader", self.worker_id)
        else:
            current_leader = await self.redis.get(leader_key)
            if current_leader:
                logger.info(
                    "{} is a follower (leader: {})",
                    self.worker_id, current_leader.split(':')[0]
                )

        return acquired

    async def clear_all_locks(self):
        """Clear all initialization locks (use with caution).

        This should only be used during development or when
        manually recovering from a stuck state.
        """
        pattern = f"{self.lock_prefix}*"
        cursor = 0
        deleted_count = 0

        while True:
            cursor, keys = await self.redis.scan(
                cursor,
                match=pattern,
                count=100
            )

            if keys:
                deleted_count += await self.redis.delete(*keys)

            if cursor == 0:
                break

        if deleted_count > 0:
            logger.warning(
                "{} cleared {} initialization locks",
                self.worker_id, deleted_count
            )

        return deleted_count


class WorkerSyncSync:
    """Synchronous version for use in sync contexts (like signal handlers).

    This is needed for contexts where we can't use async/await.
    """

    def __init__(self, redis_client: redis.Redis):
        """Initialize sync worker synchronization.

        Args:
            redis_client: Sync Redis client
        """
        self.redis = redis_client
        self.worker_id = f"worker-{os.getpid()}"
        self.lock_prefix = "worker:init:"
        self.complete_prefix = "worker:complete:"

    def run_once(self, task: InitTask, func: Callable, *args, **kwargs) -> tuple[bool, Any]:
        """Synchronous version of run_once."""
        lock_key = f"{self.lock_prefix}{task.value}"
        complete_key = f"{self.complete_prefix}{task.value}"

        if self.redis.get(complete_key):
            return False, None

        lock_value = f"{self.worker_id}:{datetime.utcnow().isoformat()}"
        acquired = self.redis.set(lock_key, lock_value, nx=True, ex=60)

        if acquired:
            try:
                result = func(*args, **kwargs)
                self.redis.setex(complete_key, 86400, f"completed_by:{self.worker_id}")
                return True, result
            except Exception:
                self.redis.delete(lock_key)
                raise
        else:
            # Wait for completion
            import time
            for _ in range(120):  # 2 minutes timeout
                if self.redis.get(complete_key):
                    return False, None
                time.sleep(1)
            return False, None