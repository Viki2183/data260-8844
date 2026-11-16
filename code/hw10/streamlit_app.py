"""DATA260 HW10 read-only Streamlit operations dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

try:
    from dashboard_data import REPO_ROOT, STAGE_ORDER, evidence_signature, load_evaluation, load_summary, load_traces, trace_rows
except ImportError:  # pragma: no cover - supports package-style imports in tests
    from code.hw10.dashboard_data import REPO_ROOT, STAGE_ORDER, evidence_signature, load_evaluation, load_summary, load_traces, trace_rows


@st.cache_resource
def get_evidence_resource(root_text: str) -> dict[str, str]:
    """Cache immutable path configuration, not dynamic metrics or service clients."""
    return {"root": root_text}


@st.cache_data(show_spinner=False)
def cached_summary(root_text: str, signature: tuple[tuple[str, int, int], ...]) -> dict[str, Any]:
    del signature
    return load_summary(Path(root_text))


@st.cache_data(show_spinner=False)
def cached_evaluation(root_text: str, signature: tuple[tuple[str, int, int], ...]) -> dict[str, Any]:
    del signature
    return load_evaluation(Path(root_text))


@st.cache_data(show_spinner=False)
def cached_traces(root_text: str, signature: tuple[tuple[str, int, int], ...]) -> list[dict[str, Any]]:
    del signature
    return load_traces(Path(root_text))


def _value_text(metric: dict[str, Any]) -> str:
    if metric["value"] is None:
        return "Unavailable"
    value = metric["value"]
    if metric["unit"] == "%":
        return f"{value}%"
    return f"{value} {metric['unit']}"


def render_summary(data: dict[str, Any]) -> None:
    st.title("HW10 Operations Dashboard")
    st.caption("Read-only evidence view; no live Kafka, Redis, or service polling is configured.")
    st.info("Live values are unavailable. Available values below are historical live evidence or offline evidence, explicitly labeled.")
    st.subheader("Summary")
    metrics = data["metrics"]
    for start in range(0, len(metrics), 3):
        columns = st.columns(3)
        for column, metric in zip(columns, metrics[start : start + 3]):
            with column:
                column.metric(metric["metric"], _value_text(metric))
                column.caption(metric["status"].replace("_", " "))
    st.dataframe(metrics, use_container_width=True, hide_index=True)
    if data.get("live_metrics"):
        st.subheader("Live Phase 5 latency experiment")
        st.dataframe(data["live_metrics"], use_container_width=True, hide_index=True)
    for note in data.get("notes", []):
        st.caption(note)


def render_evaluation(data: dict[str, Any]) -> None:
    st.title("Evaluation")
    st.info("Frozen 20-case validation remains offline and degenerate. The separate single-trace evaluation below is live evidence and is not a deployment gate.")
    live = data.get("live_evaluation")
    if live:
        st.subheader("Live end-to-end evaluation")
        st.caption(f"Status: {live.get('status', 'unavailable')} | trace_id = correlation_id = {live.get('trace_id')} | Evidence: {live.get('evidence_path')}")
        st.write({"question": live.get("question"), "Planner plan": live.get("plan")})
        st.text_area("Live Writer draft", live.get("writer_draft") or "Unavailable", height=100, disabled=True)
        st.text_area("Live Reviewer/final answer", live.get("reviewer_final") or "Unavailable", height=100, disabled=True)
        live_columns = st.columns(3)
        live_columns[0].metric("Writer score", live.get("draft_score") if live.get("draft_score") is not None else "Unavailable")
        live_columns[1].metric("Final score", live.get("final_score") if live.get("final_score") is not None else "Unavailable")
        live_columns[2].metric("Final − draft", live.get("score_difference") if live.get("score_difference") is not None else "Unavailable")
        st.dataframe(live.get("criteria", []), use_container_width=True, hide_index=True)
        st.caption(live.get("interpretation") or "No interpretation was recorded.")
    statistics = data["statistics"]
    columns = st.columns(4)
    columns[0].metric("MAD", statistics.get("mean_absolute_difference"))
    columns[1].metric("Changed scores", statistics.get("number_of_changed_scores"))
    columns[2].metric("Mean absolute change", statistics.get("mean_absolute_change"))
    columns[3].metric("Repeatability", f"{statistics.get('repeatability_percentage')}%")
    st.subheader("Judge settings")
    st.dataframe([data["settings"]], use_container_width=True, hide_index=True)
    st.subheader("Spearman status")
    st.write({
        "spearman_correlation": statistics.get("spearman_correlation"),
        "spearman_status": statistics.get("spearman_status"),
        "explanation": data.get("spearman_explanation"),
    })
    st.subheader("Scores by case")
    st.dataframe(data["rows"], use_container_width=True, hide_index=True)
    st.subheader("Historical draft versus final")
    st.caption("Per-case final outputs are unavailable for the frozen evaluation cases, so no draft-to-final score is inferred.")
    if data.get("observed_comparison"):
        st.dataframe([data["observed_comparison"]], use_container_width=True, hide_index=True)
    st.subheader("Interpretation")
    st.write(data["interpretation"])


def _cache_banner(row: dict[str, Any]) -> None:
    if row["stage"] != "cache_lookup":
        return
    if row["status"] == "cache_hit":
        st.success("CACHE HIT — this trace has recorded semantic-cache reuse.")
    elif row["status"] == "cache_miss":
        st.warning("CACHE MISS — this trace has recorded a semantic-cache miss.")


def render_trace_lookup(traces: list[dict[str, Any]]) -> None:
    st.title("Trace Lookup")
    st.caption("trace_id is the existing correlation_id; no second request identifier is introduced.")
    trace_ids = [trace["trace_id"] for trace in traces]
    trace_id = st.text_input("trace_id (correlation_id)", value=trace_ids[0] if trace_ids else "")
    selected = next((trace for trace in traces if trace["trace_id"] == trace_id.strip()), None)
    if selected is None:
        st.warning("No matching evidence trace. Live lookup is unavailable in this read-only dashboard.")
        if trace_ids:
            st.caption(f"Available evidence trace IDs: {', '.join(trace_ids)}")
        return
    st.write({"trace_id": selected["trace_id"], "source_kinds": selected.get("source_kinds")})
    rows = trace_rows(selected)
    _cache_banner(next((row for row in rows if row["stage"] == "cache_lookup"), {}))
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption("Stages are always displayed in the required order; unavailable stages are shown explicitly rather than inferred.")


def main() -> None:
    st.set_page_config(page_title="DATA260 HW10 Operations", layout="wide")
    resource = get_evidence_resource(str(REPO_ROOT))
    signature = evidence_signature(REPO_ROOT)
    summary = cached_summary(resource["root"], signature)
    evaluation = cached_evaluation(resource["root"], signature)
    traces = cached_traces(resource["root"], signature)
    page = st.sidebar.radio("Page", ("Summary", "Evaluation", "Trace Lookup"))
    st.sidebar.caption("Data mode: historical/offline evidence only")
    if page == "Summary":
        render_summary(summary)
    elif page == "Evaluation":
        render_evaluation(evaluation)
    else:
        render_trace_lookup(traces)


if __name__ == "__main__":
    main()
