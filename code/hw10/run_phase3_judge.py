"""Run the bounded three-trial HW10 GEval judge against frozen inputs.

This runner reads, but never edits, eval_cases.json and human_labels.csv. It
writes only the four requested raw evidence files under reports/hw10/raw/.
"""

from __future__ import annotations

import csv
import json
import math
import multiprocessing as mp
import queue
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CASES_PATH = ROOT / "reports" / "hw10" / "eval_cases.json"
LABELS_PATH = ROOT / "reports" / "hw10" / "human_labels.csv"
REFERENCE_PATH = ROOT / "reports" / "hw09" / "cases" / "reference_data.json"
RAW_DIR = ROOT / "reports" / "hw10" / "raw"

MODEL_NAME = "qwen3:8b"
BASE_URL = "http://127.0.0.1:11434"
TEMPERATURE = 0.0
SEED = 8844
NUM_PREDICT = 1024
TIMEOUT_SECONDS = 180
PROMPT_VERSION = "hw10-geval-v1"
PROMPT_CRITERIA = (
    "Judge the helpfulness of the candidate Writer draft for the vulnerability "
    "question. The draft must answer the question using the supplied reference "
    "context. A draft that only repeats or paraphrases the question without the "
    "requested answer is not helpful. Do not reward stylistic fluency over factual "
    "coverage."
)
PROMPT_STEPS = [
    "Identify the requested vulnerability fact in the question.",
    "Compare the candidate Writer draft with the supplied reference context.",
    "Check whether the draft provides the requested answer rather than repeating the question.",
    "Assign a helpfulness score from 0 to 1 and explain the decision.",
]

SOURCE_TO_FACT = {
    "exact-01": "alpha",
    "exact-02": "beta",
    "exact-03": "severity-0003",
    "exact-04": "traversal",
    "exact-05": "gamma-fix",
    "exact-06": "local",
    "exact-07": "injection",
    "exact-08": "delta",
    "exact-09": "epsilon",
    "exact-10": "zeta",
    "paraphrase-01": "alpha",
    "paraphrase-02": "beta",
    "paraphrase-03": "severity-0003",
    "paraphrase-04": "traversal",
    "paraphrase-05": "gamma-fix",
    "paraphrase-06": "local",
    "paraphrase-07": "injection",
    "paraphrase-08": "delta",
    "paraphrase-09": "epsilon",
    "paraphrase-10": "zeta",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_inputs() -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, dict[str, Any]]]:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    with LABELS_PATH.open("r", encoding="utf-8", newline="") as handle:
        labels = list(csv.DictReader(handle))
    reference_rows = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    reference = {str(row["fact_id"]): row for row in reference_rows}
    if len(cases) != 20 or len(labels) != 20:
        raise ValueError("frozen inputs must contain exactly 20 cases and labels")
    if [case["case_id"] for case in cases] != [row["case_id"] for row in labels]:
        raise ValueError("frozen case and label order does not match")
    if any(str(row["human_label"]) not in {"1", "2", "3", "4", "5"} for row in labels):
        raise ValueError("human labels must be integer scores from 1 through 5")
    for case in cases:
        if case["source_question_id"] not in SOURCE_TO_FACT:
            raise ValueError(f"no reference mapping for {case['case_id']}")
        if SOURCE_TO_FACT[case["source_question_id"]] not in reference:
            raise ValueError(f"missing reference fact for {case['case_id']}")
    return cases, labels, reference


def normalize_score(raw_score: float) -> int:
    """Map GEval's [0, 1] score to the required integer [1, 5] scale."""
    bounded = min(1.0, max(0.0, float(raw_score)))
    return min(5, max(1, int(math.floor((bounded * 4.0) + 1.5))))


def _judge_case_inner(case: dict[str, Any], label: dict[str, str], reference: dict[str, dict[str, Any]], trial: int) -> dict[str, Any]:
    from deepeval.metrics import GEval
    from deepeval.models import OllamaModel
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams

    reference_row = reference[SOURCE_TO_FACT[case["source_question_id"]]]
    started = now()
    start_clock = time.perf_counter()
    result: dict[str, Any] = {
        "case_id": case["case_id"],
        "question": case["question"],
        "candidate_writer_draft": case["candidate_draft"],
        "reference_context": reference_row,
        "expected_answer": reference_row["fact"],
        "human_score": int(label["human_label"]),
        "judge_score": None,
        "raw_geval_score": None,
        "judge_reason": None,
        "judge_model": MODEL_NAME,
        "prompt_version": PROMPT_VERSION,
        "temperature": TEMPERATURE,
        "seed": SEED,
        "generation_settings": {"seed": SEED, "num_predict": NUM_PREDICT},
        "timeout_seconds": TIMEOUT_SECONDS,
        "timestamp": started,
        "latency_seconds": None,
        "error_status": None,
        "error": None,
        "repeatability_trial_number": trial,
    }
    try:
        model = OllamaModel(
            model=MODEL_NAME,
            base_url=BASE_URL,
            temperature=TEMPERATURE,
            timeout=TIMEOUT_SECONDS,
            generation_kwargs={"seed": SEED, "num_predict": NUM_PREDICT},
        )
        test_case = LLMTestCase(
            input=case["question"],
            actual_output=case["candidate_draft"],
            expected_output=reference_row["fact"],
            retrieval_context=[json.dumps(reference_row, sort_keys=True)],
        )
        metric = GEval(
            name="HW10 Writer helpfulness",
            criteria=PROMPT_CRITERIA,
            evaluation_steps=PROMPT_STEPS,
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
        raw_score = float(metric.score)
        result["raw_geval_score"] = raw_score
        result["judge_score"] = normalize_score(raw_score)
        result["judge_reason"] = str(metric.reason or "")
        result["error_status"] = "none"
    except Exception as exc:  # bounded per-case failure record
        result["error_status"] = "error_or_timeout"
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["judge_reason"] = None
        result["traceback"] = traceback.format_exc()
    result["latency_seconds"] = round(time.perf_counter() - start_clock, 3)
    result["completed_timestamp"] = now()
    return result


def _judge_case_worker(
    case: dict[str, Any],
    label: dict[str, str],
    reference: dict[str, dict[str, Any]],
    trial: int,
    result_queue: Any,
) -> None:
    result_queue.put(_judge_case_inner(case, label, reference, trial))


def judge_case(case: dict[str, Any], label: dict[str, str], reference: dict[str, dict[str, Any]], trial: int) -> dict[str, Any]:
    """Run one GEval case in a hard-bounded child process."""
    reference_row = reference[SOURCE_TO_FACT[case["source_question_id"]]]
    started = now()
    start_clock = time.perf_counter()
    context = mp.get_context("spawn")
    result_queue = context.Queue()
    process = context.Process(
        target=_judge_case_worker,
        args=(case, label, reference, trial, result_queue),
    )
    process.start()
    process.join(TIMEOUT_SECONDS)
    if process.is_alive():
        process.terminate()
        process.join(10)
        result_queue.close()
        return {
            "case_id": case["case_id"],
            "question": case["question"],
            "candidate_writer_draft": case["candidate_draft"],
            "reference_context": reference_row,
            "expected_answer": reference_row["fact"],
            "human_score": int(label["human_label"]),
            "judge_score": None,
            "raw_geval_score": None,
            "judge_reason": None,
            "judge_model": MODEL_NAME,
            "prompt_version": PROMPT_VERSION,
            "temperature": TEMPERATURE,
            "seed": SEED,
            "timeout_seconds": TIMEOUT_SECONDS,
            "timestamp": started,
            "latency_seconds": round(time.perf_counter() - start_clock, 3),
            "error_status": "timeout",
            "error": f"hard per-case timeout after {TIMEOUT_SECONDS} seconds",
            "repeatability_trial_number": trial,
            "completed_timestamp": now(),
        }
    try:
        return result_queue.get_nowait()
    except queue.Empty:
        return {
            "case_id": case["case_id"],
            "question": case["question"],
            "candidate_writer_draft": case["candidate_draft"],
            "reference_context": reference_row,
            "expected_answer": reference_row["fact"],
            "human_score": int(label["human_label"]),
            "judge_score": None,
            "raw_geval_score": None,
            "judge_reason": None,
            "judge_model": MODEL_NAME,
            "prompt_version": PROMPT_VERSION,
            "temperature": TEMPERATURE,
            "seed": SEED,
            "timeout_seconds": TIMEOUT_SECONDS,
            "timestamp": started,
            "latency_seconds": round(time.perf_counter() - start_clock, 3),
            "error_status": "worker_error",
            "error": f"child process exited with code {process.exitcode} without a result",
            "repeatability_trial_number": trial,
            "completed_timestamp": now(),
        }
    finally:
        result_queue.close()


def run_trial(trial: int, cases: list[dict[str, Any]], labels: list[dict[str, str]], reference: dict[str, dict[str, Any]]) -> dict[str, Any]:
    started = now()
    rows = []
    for case, label in zip(cases, labels):
        row = judge_case(case, label, reference, trial)
        rows.append(row)
        print(
            json.dumps(
                {
                    "trial": trial,
                    "case_id": row["case_id"],
                    "status": row["error_status"],
                    "judge_score": row["judge_score"],
                    "latency_seconds": row["latency_seconds"],
                }
            ),
            flush=True,
        )
    output = {
        "trial_number": trial,
        "status": "completed_with_bounded_case_results",
        "started_at": started,
        "completed_at": now(),
        "model": MODEL_NAME,
        "endpoint": BASE_URL,
        "prompt_version": PROMPT_VERSION,
        "criteria": PROMPT_CRITERIA,
        "evaluation_steps": PROMPT_STEPS,
        "temperature": TEMPERATURE,
        "seed": SEED,
        "generation_settings": {"seed": SEED, "num_predict": NUM_PREDICT},
        "timeout_seconds": TIMEOUT_SECONDS,
        "score_normalization": "floor(clamp(raw_geval_score,0,1)*4+1.5), clamped to integer 1..5",
        "cases": rows,
    }
    (RAW_DIR / f"judge_run_{trial}.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    return output


def spearman_status(human: list[int], judged: list[int]) -> dict[str, Any]:
    if len(set(human)) < 2 or len(set(judged)) < 2:
        return {
            "spearman_correlation": None,
            "spearman_status": "undefined_constant_human_labels",
            "explanation": "Rank correlation cannot be estimated from constant human labels.",
        }
    from scipy.stats import spearmanr

    value = spearmanr(human, judged).statistic
    return {"spearman_correlation": float(value), "spearman_status": "defined", "explanation": None}


def aggregate(trials: list[dict[str, Any]], labels: list[dict[str, str]]) -> dict[str, Any]:
    human = [int(row["human_label"]) for row in labels]
    trial_vectors = [[row["judge_score"] for row in trial["cases"]] for trial in trials]
    mad_by_trial = []
    for vector in trial_vectors:
        valid = [(h, j) for h, j in zip(human, vector) if j is not None]
        mad_by_trial.append(
            None if not valid else sum(abs(h - j) for h, j in valid) / len(valid)
        )

    transitions = []
    for left, right in zip(trial_vectors, trial_vectors[1:]):
        changes = []
        for index, (before, after) in enumerate(zip(left, right)):
            changes.append(
                {
                    "case_id": trials[0]["cases"][index]["case_id"],
                    "before": before,
                    "after": after,
                    "absolute_change": None if before is None or after is None else abs(after - before),
                    "changed": None if before is None or after is None else before != after,
                }
            )
        valid_changes = [row["absolute_change"] for row in changes if row["absolute_change"] is not None]
        transitions.append(
            {
                "from_trial": trials[0]["trial_number"] if left is trial_vectors[0] else trials[1]["trial_number"],
                "to_trial": trials[1]["trial_number"] if left is trial_vectors[0] else trials[2]["trial_number"],
                "changed_score_count": sum(1 for row in changes if row["changed"] is True),
                "mean_absolute_change": None if not valid_changes else sum(valid_changes) / len(valid_changes),
                "maximum_absolute_change": None if not valid_changes else max(valid_changes),
                "repeatability_percentage": None if not valid_changes else 100.0 * sum(value == 0 for value in valid_changes) / len(valid_changes),
                "per_case_score_changes": changes,
            }
        )

    all_changes = [
        row["absolute_change"]
        for transition in transitions
        for row in transition["per_case_score_changes"]
        if row["absolute_change"] is not None
    ]
    final_vector = trial_vectors[-1]
    return {
        "trial_count": len(trials),
        "case_count": len(human),
        "mean_absolute_difference_by_trial": mad_by_trial,
        "mean_absolute_difference": None if not mad_by_trial or any(value is None for value in mad_by_trial) else sum(mad_by_trial) / len(mad_by_trial),
        "per_case_score_changes_across_trials": transitions,
        "number_of_changed_scores": sum(1 for value in all_changes if value != 0),
        "mean_absolute_change": None if not all_changes else sum(all_changes) / len(all_changes),
        "maximum_absolute_change": None if not all_changes else max(all_changes),
        "repeatability_percentage": None if not all_changes else 100.0 * sum(value == 0 for value in all_changes) / len(all_changes),
        **spearman_status(human, final_vector),
    }


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cases, labels, reference = load_inputs()
    trials = [run_trial(trial, cases, labels, reference) for trial in (1, 2, 3)]
    validation = {
        "phase": "phase-3",
        "status": "completed",
        "automated_judge_executed": True,
        "frozen_inputs": [str(CASES_PATH.relative_to(ROOT)), str(LABELS_PATH.relative_to(ROOT))],
        "reference_context": str(REFERENCE_PATH.relative_to(ROOT)),
        "model": MODEL_NAME,
        "endpoint": BASE_URL,
        "prompt_version": PROMPT_VERSION,
        "temperature": TEMPERATURE,
        "seed": SEED,
        "generation_settings": {"seed": SEED, "num_predict": NUM_PREDICT},
        "timeout_seconds": TIMEOUT_SECONDS,
        "score_scale": "integer 1..5",
        "normalization": "floor(clamp(raw_geval_score,0,1)*4+1.5), clamped to integer 1..5",
        "statistics": aggregate(trials, labels),
    }
    (RAW_DIR / "judge_validation.json").write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
