"""Capture one live HW9/HW8 journey and evaluate its observed stages.

This runner reuses the existing authenticated HW9 endpoint and the existing
HW8 Kafka topics. Kafka consumers are observation-only: they use fresh groups,
disable auto-commit, and never publish, commit, seek, or alter worker code.
Only HW10 evidence is written.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "reports/hw10/raw"
END_TO_END_DIR = RAW_DIR / "end_to_end"
TRACE_INDEX = RAW_DIR / "traces/trace_index.json"
OUTPUT_PATH = END_TO_END_DIR / "live_evaluation_trace.json"

API_URL = os.getenv("HW10_API_URL", "http://127.0.0.1:8745/api/agent/ask")
BOOTSTRAP = os.getenv("HW10_KAFKA_BOOTSTRAP", "127.0.0.1:29092")
REDIS_HOST = os.getenv("HW9_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("HW9_REDIS_PORT", "16379"))
REPORT_ID = int(os.getenv("HW10_REPORT_ID", "5005"))
MODEL_NAME = "qwen3:8b"
OLLAMA_URL = "http://127.0.0.1:11434"
TEMPERATURE = 0.0
SEED = 8844
NUM_PREDICT = 1024
TIMEOUT_SECONDS = 180
PROMPT_VERSION = "hw10-live-geval-v1"

REFERENCE_PATH = ROOT / "reports/hw09/cases/reference_data.json"
REFERENCE_FACT_ID = "alpha-fix-1001"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def normalize_score(raw_score: float | None) -> int | None:
    if raw_score is None:
        return None
    bounded = min(1.0, max(0.0, float(raw_score)))
    return min(5, max(1, int(math.floor((bounded * 4.0) + 1.5))))


def load_reference() -> dict[str, Any]:
    rows = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    for row in rows:
        if row.get("fact_id") == REFERENCE_FACT_ID:
            return row
    raise ValueError(f"reference fact not found: {REFERENCE_FACT_ID}")


def stage_record(records: list[dict[str, Any]], stage: str) -> dict[str, Any] | None:
    matches = [item for item in records if item.get("observed_stage") == stage]
    return sorted(
        matches,
        key=lambda item: (item.get("kafka_timestamp_ms") or 0, item.get("offset") or 0),
    )[0] if matches else None


def add_timing_provenance(trace: dict[str, Any]) -> None:
    provenance = {
        "cache_lookup": "derived from HW9 response timings_ms.embedding + timings_ms.redis_search",
        "inbox": "derived from API request start and Kafka inbox record timestamp",
        "planner": "derived from matching Kafka inbox/tasks record timestamps",
        "tasks": "derived from matching Kafka tasks record timestamp; zero-duration topic marker",
        "writer": "derived from matching Kafka tasks/drafts record timestamps",
        "drafts": "derived from matching Kafka drafts record timestamp; zero-duration topic marker",
        "reviewer": "derived from matching Kafka drafts/final record timestamps",
        "final": "derived from matching Kafka final record timestamp; zero-duration topic marker",
    }
    for row in trace.get("stages", []):
        row["timing_provenance"] = provenance.get(row.get("stage"), "unavailable")


def extract_stage_data(trace: Mapping[str, Any], stage: str) -> dict[str, Any]:
    for row in trace.get("stages", []):
        if row.get("stage") == stage:
            details = row.get("details")
            return dict(details) if isinstance(details, Mapping) else {}
    return {}


def evaluate_one(
    *,
    criterion: str,
    criteria: str,
    steps: list[str],
    question: str,
    actual_output: str,
    expected_output: str,
    retrieval_context: list[str],
) -> dict[str, Any]:
    from deepeval.metrics import GEval
    from deepeval.models import OllamaModel
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams

    started_at = utc_now()
    start_clock = time.perf_counter_ns()
    result: dict[str, Any] = {
        "criterion": criterion,
        "score": None,
        "raw_geval_score": None,
        "reason": None,
        "model": MODEL_NAME,
        "endpoint": OLLAMA_URL,
        "prompt_version": PROMPT_VERSION,
        "temperature": TEMPERATURE,
        "seed": SEED,
        "generation_settings": {"seed": SEED, "num_predict": NUM_PREDICT},
        "timeout_seconds": TIMEOUT_SECONDS,
        "start_time": iso(started_at),
        "end_time": None,
        "duration_ms": None,
        "status": "error",
        "error": None,
        "criteria": criteria,
        "evaluation_steps": steps,
    }
    try:
        model = OllamaModel(
            model=MODEL_NAME,
            base_url=OLLAMA_URL,
            temperature=TEMPERATURE,
            timeout=TIMEOUT_SECONDS,
            generation_kwargs={"seed": SEED, "num_predict": NUM_PREDICT},
        )
        test_case = LLMTestCase(
            input=question,
            actual_output=actual_output,
            expected_output=expected_output,
            retrieval_context=retrieval_context,
        )
        metric = GEval(
            name=criterion,
            criteria=criteria,
            evaluation_steps=steps,
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.RETRIEVAL_CONTEXT,
            ],
            model=model,
            async_mode=False,
            verbose_mode=False,
        )
        metric.measure(test_case)
        result["raw_geval_score"] = float(metric.score)
        result["score"] = normalize_score(metric.score)
        result["reason"] = str(metric.reason or "")
        result["status"] = "completed"
    except Exception as exc:  # retain bounded per-criterion failure evidence
        result["error"] = f"{type(exc).__name__}: {exc}"
    result["end_time"] = iso(utc_now())
    result["duration_ms"] = round((time.perf_counter_ns() - start_clock) / 1_000_000, 3)
    return result


async def capture() -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "code"))
    from hw09.agent_schemas import AgentAskRequest  # noqa: F401  # import check for existing schema
    from web_application.auth_hw7 import create_access_token
    from run_phase5_live import (
        KafkaObserver,
        build_trace,
        call_api,
        find_entry,
        redis_client,
    )
    import httpx

    nonce = uuid.uuid4().hex
    trace_id = f"hw10-live-e2e-eval-{nonce[:12]}"
    question = (
        f"Which version fixes CVE-2026-1001 in package alpha? "
        f"HW10 live evaluation nonce {nonce}."
    )
    token = create_access_token("vikki1", "reader")
    observer = KafkaObserver()
    await observer.start()
    try:
        async with httpx.AsyncClient() as client:
            call = await call_api(client, token, question, trace_id, report_id=REPORT_ID)
        records = await observer.wait_for(trace_id, timeout=15.0)
    finally:
        await observer.stop()

    entry = await asyncio.to_thread(find_entry, redis_client(), question)
    trace = build_trace(call, records, entry=entry)
    trace["capture_kind"] = "live_end_to_end_observation"
    trace["source"] = {
        **trace.get("source", {}),
        "api": API_URL,
        "kafka_bootstrap": BOOTSTRAP,
        "redis": f"{REDIS_HOST}:{REDIS_PORT}",
    }
    trace["kafka_records"] = records
    trace["stage_payloads"] = {
        stage: record.get("payload")
        for stage in ("inbox", "tasks", "drafts", "final")
        if (record := stage_record(records, stage)) is not None
    }
    # build_trace adds the historical Phase 5 placeholder when per-request
    # evaluation was not executed.  This run has a real evaluator span, so
    # remove that placeholder before appending the instrumented span below.
    trace["stages"] = [
        stage for stage in trace.get("stages", [])
        if stage.get("stage") != "evaluation"
    ]
    add_timing_provenance(trace)

    planner = extract_stage_data(trace, "planner")
    writer = extract_stage_data(trace, "writer")
    reviewer = extract_stage_data(trace, "reviewer")
    plan = str(planner.get("plan", ""))
    draft = str(writer.get("draft", ""))
    final_answer = str(reviewer.get("answer", ""))
    reference = load_reference()
    reference_context = json.dumps(reference, sort_keys=True)

    evaluation_started = utc_now()
    evaluation_clock = time.perf_counter_ns()
    criteria = [
        (
            "Plan Quality",
            "Judge whether the Planner plan is coherent, relevant to the vulnerability question, and sufficient to guide a correct answer.",
            [
                "Identify the requested vulnerability fact.",
                "Check whether the plan addresses the question and uses the supplied reference context.",
                "Score the plan from 0 to 1 based on relevance and answerability.",
            ],
            plan,
            reference["fact"],
        ),
        (
            "Writer Helpfulness",
            "Judge whether the Writer draft directly answers the vulnerability question using the supplied reference context rather than merely repeating the question.",
            [
                "Identify the requested vulnerability fact.",
                "Compare the Writer draft with the supplied reference context.",
                "Score helpfulness from 0 to 1.",
            ],
            draft,
            reference["fact"],
        ),
        (
            "Final Answer Helpfulness",
            "Judge whether the Reviewer final answer directly and accurately answers the vulnerability question using the supplied reference context.",
            [
                "Identify the requested vulnerability fact.",
                "Compare the final answer with the supplied reference context.",
                "Score helpfulness from 0 to 1.",
            ],
            final_answer,
            reference["fact"],
        ),
        (
            "Final-vs-Draft Improvement",
            "Judge whether the Reviewer final answer improves on the Writer draft for factual coverage, directness, and usefulness without inventing unsupported claims.",
            [
                "Compare the Writer draft and Reviewer final answer.",
                "Use the supplied reference context to determine whether the final is more helpful.",
                "Score the improvement from 0 to 1; a final answer identical to an unhelpful draft should not receive improvement credit.",
            ],
            final_answer,
            f"Writer draft:\n{draft}\n\nReference answer:\n{reference['fact']}",
        ),
    ]
    evaluations = [
        evaluate_one(
            criterion=name,
            criteria=criteria_text,
            steps=steps,
            question=question,
            actual_output=actual,
            expected_output=expected,
            retrieval_context=[reference_context],
        )
        for name, criteria_text, steps, actual, expected in criteria
    ]
    draft_score = next((row["score"] for row in evaluations if row["criterion"] == "Writer Helpfulness"), None)
    final_score = next((row["score"] for row in evaluations if row["criterion"] == "Final Answer Helpfulness"), None)
    for row in evaluations:
        row["draft_score"] = draft_score
        row["final_score"] = final_score
        row["score_difference"] = None if draft_score is None or final_score is None else final_score - draft_score
    evaluation_ended = utc_now()
    evaluation_duration = round((time.perf_counter_ns() - evaluation_clock) / 1_000_000, 3)
    evaluation_errors = [row["error"] for row in evaluations if row.get("error")]
    evaluation_status = "completed" if not evaluation_errors else "completed_with_errors"
    evidence_path = str(OUTPUT_PATH.relative_to(ROOT))
    evaluation_span = {
        "trace_id": trace_id,
        "correlation_id": trace_id,
        "stage": "evaluation",
        "start_time": iso(evaluation_started),
        "end_time": iso(evaluation_ended),
        "duration_ms": evaluation_duration,
        "status": evaluation_status,
        "error": "; ".join(evaluation_errors) if evaluation_errors else None,
        "judge_model": MODEL_NAME,
        "endpoint": OLLAMA_URL,
        "prompt_version": PROMPT_VERSION,
        "temperature": TEMPERATURE,
        "seed": SEED,
        "timeout_seconds": TIMEOUT_SECONDS,
        "evidence_path": evidence_path,
        "timing_provenance": "instrumented span using UTC datetime and monotonic perf_counter_ns",
    }
    trace["stages"].append(
        {
            "stage": "evaluation",
            "start_time": evaluation_span["start_time"],
            "end_time": evaluation_span["end_time"],
            "duration_ms": evaluation_duration,
            "status": evaluation_status,
            "error": evaluation_span["error"],
            "topic": None,
            "partition": None,
            "offset": None,
            "message_type": None,
            "cache_status": trace.get("cache_status"),
            "similarity": trace.get("similarity"),
            "threshold": trace.get("threshold"),
            "entry_id": trace.get("entry_id"),
            "report_id": trace.get("report_id"),
            "timing_provenance": evaluation_span["timing_provenance"],
            "details": {
                "model": MODEL_NAME,
                "prompt_version": PROMPT_VERSION,
                "criterion_count": len(evaluations),
            },
        }
    )
    trace["evaluation_span"] = evaluation_span
    trace["evaluation"] = {
        "status": evaluation_status,
        "model": MODEL_NAME,
        "prompt_version": PROMPT_VERSION,
        "temperature": TEMPERATURE,
        "seed": SEED,
        "timeout_seconds": TIMEOUT_SECONDS,
        "reference_context": reference,
        "criteria": evaluations,
        "draft_score": draft_score,
        "final_score": final_score,
        "score_difference": None if draft_score is None or final_score is None else final_score - draft_score,
        "interpretation": (
            "The final answer is compared with the Writer draft using the same reference context. "
            "This is one live trace and is not evidence for deployment gating."
        ),
    }
    END_TO_END_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")

    index = json.loads(TRACE_INDEX.read_text(encoding="utf-8"))
    index.setdefault("trace_ids", {})["end_to_end_evaluation"] = trace_id
    index.setdefault("trace_files", {})["end_to_end_evaluation"] = evidence_path
    index["end_to_end_evaluation"] = {
        "trace_id": trace_id,
        "status": evaluation_status,
        "evidence_path": evidence_path,
        "evaluation_span": evaluation_span,
    }
    TRACE_INDEX.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return trace


def main() -> None:
    trace = asyncio.run(capture())
    print(
        json.dumps(
            {
                "trace_id": trace["trace_id"],
                "cache_status": trace.get("cache_status"),
                "status": trace.get("status"),
                "evaluation_status": trace.get("evaluation", {}).get("status"),
                "evidence_path": str(OUTPUT_PATH.relative_to(ROOT)),
                "evaluation_span": trace.get("evaluation_span"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
