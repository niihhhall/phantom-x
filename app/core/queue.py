import json
import logging
import redis
from typing import Dict, Any, Optional
from app.config import settings
from app.core.database import create_job, update_job_status

logger = logging.getLogger("phantomx.queue")

# Main queue name requested by prompt specification
QUEUE_NAME = "phantom_x:jobs"

def _get_redis_client():
    return redis.from_url(settings.REDIS_URL, decode_responses=True)

async def enqueue_job(job_type: str, payload: dict, workspace_id: str) -> str:
    """
    Store a job record in Supabase 'jobs' table first in 'queued' status,
    then serialize and push the job ID and payload context to the Redis queue.
    """
    # 1. Store job record in database
    job_res = await create_job({
        "workspace_id": workspace_id,
        "type": job_type,
        "payload": payload,
        "status": "queued"
    })
    job_id = job_res.get("id")
    if not job_id:
        raise RuntimeError("Failed to create job record in database.")
        
    # 2. Push job details to Redis queue
    try:
        r_client = _get_redis_client()
        task_payload = {
            "id": job_id,
            "type": job_type,
            "payload": payload
        }
        r_client.rpush(QUEUE_NAME, json.dumps(task_payload))
        
        # Dual queue sync for backward compatibility with worker settings
        try:
            r_client.rpush("phantomx:jobs:queue", json.dumps(task_payload))
        except Exception:
            pass
    except Exception as re:
        logger.error(f"Failed to queue job to Redis: {re}")
        
    return str(job_id)

async def get_next_job() -> Optional[dict]:
    """Retrieve and pop the next task from the Redis list using BLPOP."""
    r_client = _get_redis_client()
    try:
        # blpop returns a tuple: (list_key, value_string)
        res = r_client.blpop(QUEUE_NAME, timeout=1)
        if res:
            _, item_str = res
            return json.loads(item_str)
    except Exception as e:
        logger.error(f"Failed to fetch next job from Redis: {e}")
    return None

async def complete_job(job_id: str, result: dict):
    """Mark a job in database as done with successful execution payload."""
    await update_job_status(job_id, "done", result=result)

async def fail_job(job_id: str, error: str, retries: int):
    """Mark a job as failed in database with remaining retries tracking."""
    result_payload = {
        "error": error,
        "retries_remaining": retries
    }
    await update_job_status(job_id, "failed", result=result_payload)
