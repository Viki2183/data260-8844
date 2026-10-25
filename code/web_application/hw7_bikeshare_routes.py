"""Local UI and read-only MRKL pipeline for the HW7 bike-share exercise."""

import csv
import io
import math
import time
from datetime import datetime

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import HTMLResponse

try:
    from ..hw7_bikeshare import recommend
    from ..hw7_mrkl import calculator, csv_sql, policy_retriever
except ImportError:
    from hw7_bikeshare import recommend
    from hw7_mrkl import calculator, csv_sql, policy_retriever

router = APIRouter(prefix="/hw7/bikeshare", tags=["HW7 bike share"])


def run_bikeshare_pipeline(csv_text: str, pricing_url: str) -> dict[str, object]:
    """Run the fixed read-only MRKL sequence and return a UI-safe result."""
    started = time.perf_counter()
    query = (
        "SELECT COUNT(*) AS ride_count, "
        "SUM(CAST(duration_minutes AS REAL)) AS total_minutes, "
        "AVG(CAST(duration_minutes AS REAL)) AS average_duration "
        "FROM trips"
    )
    csv_result = csv_sql(csv_text, query)
    if not csv_result.get("success"):
        return {"success": False, "error": csv_result.get("error", "csv_sql failed")}

    rows = csv_result.get("data", {}).get("rows", [])
    if not rows:
        return {"success": False, "error": "csv_sql returned no summary row"}
    summary = rows[0]
    try:
        ride_count = int(float(summary["ride_count"]))
        total_minutes = float(summary["total_minutes"] or 0)
        average_duration = float(summary["average_duration"] or 0)
    except (KeyError, TypeError, ValueError) as exc:
        return {"success": False, "error": f"invalid trip summary: {type(exc).__name__}"}
    if ride_count <= 0:
        return {"success": False, "error": "uploaded CSV contains no trips"}

    policy_result = policy_retriever(
        pricing_url,
        "membership price included ride minutes unlock fees overage rules",
        k=3,
    )
    if not policy_result.get("success"):
        return {"success": False, "error": policy_result.get("error", "policy retrieval failed")}

    dates = []
    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        dates = [
            datetime.fromisoformat(row["started_at"].replace("Z", "+00:00"))
            for row in reader
            if row.get("started_at")
        ]
    except (KeyError, ValueError):
        dates = []
    span_years = max(1, math.ceil((max(dates) - min(dates)).days / 365.25)) if dates else 1
    membership_price = 19.92 if span_years == 1 else 239.0 * span_years
    included_minutes = ride_count * 45
    pay_expression = f"{ride_count} * 4.99 + {total_minutes} * 0.41"
    membership_expression = f"{membership_price} + 0"
    pay_result = calculator(pay_expression, "USD")
    membership_result = calculator(membership_expression, "USD")
    if not pay_result.get("success") or not membership_result.get("success"):
        return {"success": False, "error": "calculator failed"}
    recommendation = recommend(
        ride_count,
        total_minutes,
        membership_price,
        4.99,
        0.41,
        included_minutes=included_minutes,
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    passages = policy_result.get("data", {}).get("passages", [])
    return {
        "success": True,
        "data": {
            **recommendation,
            "ride_count": ride_count,
            "total_minutes": total_minutes,
            "average_duration": round(average_duration, 2),
            "total_steps": 3,
            "total_time_ms": elapsed_ms,
            "stop_reason": "success",
            "citations": [
                {
                    "source": pricing_url,
                    "captured_at": policy_result.get("ts"),
                    "snippets": [item.get("text", "") for item in passages],
                }
            ],
            "tool_order": ["csv_sql", "policy_retriever", "calculator"],
            "calculator_pay_per_use": pay_result.get("data"),
            "calculator_membership": membership_result.get("data"),
        },
        "source": pricing_url,
        "ts": policy_result.get("ts"),
    }


@router.get("", response_class=HTMLResponse)
def bike_share_page() -> str:
    return """<!doctype html>
<html><head><title>HW7 Bike-share ReAct/MRKL</title></head><body>
<h1>HW7 Bike-share recommendation</h1>
<p>Student: Vrishin KunnathamParambath | SID4: 8844</p>
<label>Trip CSV <input id="trips" type="file" accept=".csv"></label>
<label>Official pricing URL <input id="policy" type="url" size="60"></label>
<button id="run">Run</button>
<section><h2>Tool-call timeline</h2><pre id="timeline">Waiting for a run.</pre></section>
<section><h2>Results</h2><pre id="results">Upload a CSV and provide the pricing URL.</pre></section>
<script>
document.getElementById('run').onclick = async () => {
  const file = document.getElementById('trips').files[0];
  const url = document.getElementById('policy').value;
  const timeline = document.getElementById('timeline');
  const results = document.getElementById('results');
  if (!file || !url) { results.textContent = 'CSV and pricing URL are required.'; return; }
  timeline.textContent = 'csv_sql -> policy_retriever -> calculator';
  results.textContent = 'Running read-only MRKL tools...';
  const form = new FormData();
  form.append('trips', file);
  form.append('pricing_url', url);
  try {
    const response = await fetch('/hw7/bikeshare/run', {method: 'POST', body: form});
    const payload = await response.json();
    if (!response.ok || !payload.success) {
      results.textContent = 'Error: ' + (payload.error || 'MRKL pipeline failed');
      return;
    }
    const data = payload.data;
    results.textContent = JSON.stringify({
      decision: data.decision,
      pay_per_use: data.pay_per_use,
      membership: data.membership,
      ride_count: data.ride_count,
      average_duration: data.average_duration,
      total_steps: data.total_steps,
      total_time_ms: data.total_time_ms,
      citations: data.citations,
      stop_reason: data.stop_reason,
      rationale: data.rationale,
    }, null, 2);
  } catch (error) {
    results.textContent = 'Error: ' + error.name + ' while running MRKL tools';
  }
};
</script></body></html>"""


@router.post("/run")
async def run_bikeshare(
    trips: UploadFile = File(...),
    pricing_url: str = Form(...),
) -> dict[str, object]:
    """Run the UI's read-only CSV → policy → calculator pipeline."""
    csv_text = (await trips.read()).decode("utf-8")
    return run_bikeshare_pipeline(csv_text, pricing_url)
