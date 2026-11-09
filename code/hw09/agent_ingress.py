"""HW9 wrapper around the existing producer-side HW8 Kafka agent ingress."""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status

try:
    from ..web_application import models
    from ..web_application.auth_hw7 import get_current_user
    from ..web_application.database import get_db
except ImportError:  # pragma: no cover
    from web_application import models
    from web_application.auth_hw7 import get_current_user
    from web_application.database import get_db

try:
    from ..hw08_kafka_config import FINAL_TOPIC, INBOX_TOPIC, KAFKA_BOOTSTRAP_SERVERS
    from ..hw08_kafka_runtime import build_manual_commit_consumer, build_producer
    from ..hw08_messages import build_message, deserialize_message, serialize_message, utc_timestamp
except ImportError:  # pragma: no cover - direct PYTHONPATH=code execution
    from hw08_kafka_config import FINAL_TOPIC, INBOX_TOPIC, KAFKA_BOOTSTRAP_SERVERS
    from hw08_kafka_runtime import build_manual_commit_consumer, build_producer
    from hw08_messages import build_message, deserialize_message, serialize_message, utc_timestamp

from .agent_schemas import AgentAskRequest, AgentAskResponse
from .data_versions import current_or_recorded_version
from .redis_client import RedisUnavailableError, get_redis_client
from .semantic_cache import SemanticCache

router = APIRouter(prefix="/api/agent", tags=["HW9 agent"])


async def publish_and_wait(question: str, report_id: int | None, correlation_id: str) -> str:
    timeout = float(os.getenv("HW9_AGENT_TIMEOUT_SECONDS", "30"))
    producer = None
    consumer = None
    producer_started = False
    consumer_started = False
    try:
        producer = await build_producer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
        consumer = await build_manual_commit_consumer(
            FINAL_TOPIC,
            group_id=f"s8844-hw9-agent-{correlation_id[:40]}",
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        )
        await producer.start()
        producer_started = True
        await consumer.start()
        consumer_started = True
        message = build_message(
            message_type="agent_request",
            correlation_id=correlation_id,
            reply_to=FINAL_TOPIC,
            data={"question": question, "report_id": report_id},
            timestamp=utc_timestamp(),
            metadata={"hw9_ingress": True, "producer_application_retries": 0},
        )
        await producer.send_and_wait(INBOX_TOPIC, serialize_message(message))

        async def receive() -> str:
            async for record in consumer:
                candidate = deserialize_message(record.value)
                if str(candidate.get("correlation_id")) != correlation_id:
                    continue
                data = candidate.get("data", {})
                if isinstance(data, dict) and "answer" in data:
                    return str(data["answer"])
                return str(candidate.get("answer", ""))
            raise RuntimeError("Kafka final consumer ended before the matching response")

        return await asyncio.wait_for(receive(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise TimeoutError("Timed out waiting for the HW8 final response") from exc
    except (ImportError, ModuleNotFoundError, OSError, ConnectionError) as exc:
        raise RuntimeError("Kafka dependencies are unavailable") from exc
    finally:
        if consumer_started and consumer is not None:
            await consumer.stop()
        if producer_started and producer is not None:
            await producer.stop()


@router.post("/ask", response_model=AgentAskResponse)
async def ask_agent(
    payload: AgentAskRequest,
    x_correlation_id: str | None = Header(default=None),
    db: Any = Depends(get_db),
    _user: models.UserDB = Depends(get_current_user),
) -> AgentAskResponse:
    question = payload.question.strip()
    correlation_id = (x_correlation_id or payload.correlation_id or uuid.uuid4().hex).strip()
    timings: dict[str, float] = {}
    started = time.perf_counter()
    try:
        redis_client = get_redis_client()
        cache = SemanticCache(redis_client=redis_client)
        before = time.perf_counter()
        embedding = await asyncio.to_thread(cache.embed, question)
        timings["embedding"] = round((time.perf_counter() - before) * 1000, 3)
        before = time.perf_counter()
        version = current_or_recorded_version(db, payload.report_id, redis_client)
        cached, similarity = await asyncio.to_thread(
            cache.lookup, question, embedding, version, payload.report_id
        )
        timings["redis_search"] = round((time.perf_counter() - before) * 1000, 3)
        if cached is not None:
            print(f"HW9 semantic cache hit similarity={similarity:.6f}", flush=True)
            timings["agent"] = 0.0
            timings["finalization"] = round((time.perf_counter() - before) * 1000, 3)
            return AgentAskResponse(
                answer=str(cached["answer"]),
                is_cached=True,
                similarity=round(similarity, 6),
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
                cache_status="hit",
                correlation_id=correlation_id,
                timings_ms=timings,
            )
        print(f"HW9 semantic cache miss similarity={similarity:.6f}", flush=True)
        before = time.perf_counter()
        answer = await publish_and_wait(question, payload.report_id, correlation_id)
        timings["agent"] = round((time.perf_counter() - before) * 1000, 3)
        before = time.perf_counter()
        await asyncio.to_thread(
            cache.store,
            question,
            embedding,
            answer,
            payload.report_id,
            version,
            {"correlation_id": correlation_id},
        )
        timings["finalization"] = round((time.perf_counter() - before) * 1000, 3)
        return AgentAskResponse(
            answer=answer,
            is_cached=False,
            similarity=round(similarity, 6),
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            cache_status="miss",
            correlation_id=correlation_id,
            timings_ms=timings,
        )
    except RedisUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
