"""Celery application configuration for NFR Connect.

This module configures Celery for background task processing,
particularly for long-running ingestion and computation tasks.
"""

import os
from celery import Celery
from kombu import Queue

from server.settings import get_settings

# Get settings
settings = get_settings()

# Create Celery application
celery_app = Celery(
    'nfr_connect',
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        'server.workers.tasks.ingestion',
        'server.workers.tasks.export',
        'server.workers.tasks.snapshots',
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task execution limits
    task_time_limit=settings.celery_task_time_limit,  # Hard limit
    task_soft_time_limit=settings.celery_task_soft_time_limit,  # Soft limit

    # No automatic retry (as requested - user must retry manually)
    task_autoretry_for=(),
    task_max_retries=0,

    # Result configuration
    result_expires=86400,  # Keep results for 24 hours
    result_persistent=True,  # Persist results in Redis
    result_compression='gzip',  # Compress large results

    # Worker configuration
    worker_prefetch_multiplier=1,  # Take one task at a time (important for long tasks)
    worker_max_tasks_per_child=settings.celery_max_tasks_per_child,  # Restart after N tasks
    worker_disable_rate_limits=True,  # No rate limiting
    task_acks_late=True,  # Acknowledge task after completion (safer)

    # Serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',

    # Timezone
    timezone='UTC',
    enable_utc=True,

    # Monitoring
    worker_send_task_events=True,  # Enable task monitoring
    task_send_sent_event=True,  # Track when tasks are sent

    # Queue configuration
    task_default_queue='default',
    task_queues=(
        Queue('default', routing_key='default'),
        Queue('ingestion', routing_key='ingestion'),  # Heavy ingestion tasks
        Queue('compute', routing_key='compute'),  # Computation tasks
        Queue('export', routing_key='export'),  # Export tasks
        Queue('snapshot', routing_key='snapshot'),  # Snapshot tasks
    ),

    # Route specific tasks to specific queues
    task_routes={
        'server.workers.tasks.ingestion.*': {'queue': 'ingestion'},
        'server.workers.tasks.compute.*': {'queue': 'compute'},
        'server.workers.tasks.export.*': {'queue': 'export'},
        'server.workers.tasks.snapshots.*': {'queue': 'snapshot'},
    },

    # Redis-specific settings
    redis_max_connections=10,
    redis_socket_keepalive=True,
    redis_socket_keepalive_options={
        1: 3,  # TCP_KEEPIDLE
        2: 3,  # TCP_KEEPINTVL
        3: 3,  # TCP_KEEPCNT
    },
)

# Configure task tracking
celery_app.conf.task_track_started = True
celery_app.conf.task_publish_retry = True
celery_app.conf.task_publish_retry_policy = {
    'max_retries': 3,
    'interval_start': 0,
    'interval_step': 0.2,
    'interval_max': 0.2,
}

if __name__ == '__main__':
    celery_app.start()