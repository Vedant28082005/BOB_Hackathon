"""Redis client (async) — caching, rate limiting, job status."""
from __future__ import annotations
import json
from typing import Any, Optional

import redis.asyncio as aioredis
from config import settings

_redis: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def cache_set(key: str, value: Any, ttl: int = settings.cache_ttl_seconds) -> None:
    r = await get_redis()
    await r.set(key, json.dumps(value), ex=ttl)


async def cache_get(key: str) -> Optional[Any]:
    r = await get_redis()
    v = await r.get(key)
    return json.loads(v) if v is not None else None


async def rate_limit_check(identifier: str, limit: int = settings.rate_limit_per_minute) -> bool:
    """Returns True if the request is allowed (under limit)."""
    r = await get_redis()
    key = f"rl:{identifier}"
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, 60)
    results = await pipe.execute()
    count = results[0]
    return count <= limit


async def set_job_status(job_id: str, status: dict, ttl: int = 3600) -> None:
    r = await get_redis()
    await r.set(f"job:{job_id}", json.dumps(status), ex=ttl)


async def get_job_status(job_id: str) -> Optional[dict]:
    r = await get_redis()
    v = await r.get(f"job:{job_id}")
    return json.loads(v) if v else None


async def set_job_owner(job_id: str, owner: str, ttl: int = 86400) -> None:
    """Record which user submitted a job, for object-level authorization."""
    r = await get_redis()
    await r.set(f"job_owner:{job_id}", owner, ex=ttl)


async def get_job_owner(job_id: str) -> Optional[str]:
    r = await get_redis()
    return await r.get(f"job_owner:{job_id}")


async def publish_progress(job_id: str, stage: str, pct: int, detail: str = "") -> None:
    r = await get_redis()
    await r.publish(f"progress:{job_id}", json.dumps({
        "stage": stage, "pct": pct, "detail": detail
    }))
