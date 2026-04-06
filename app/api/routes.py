from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse

from app.core.alerts import AlertService
from app.core.guardrails import GuardrailPolicy, GuardrailViolation
from app.core.run_service import RunService
from app.core.run_store import RunStore
from app.orchestrator import ResearchOrchestrator
from app.providers.mcp.slack import SlackWebhookClient
from app.schemas.research_plan import (
    CandidateCollectionResponse,
    DeliveredReportResponse,
    FindingsResponse,
    PlanRequest,
    PlanResponse,
    PersistedFindingsResponse,
    ReportResponse,
)
from app.schemas.run import RunAcceptedResponse, RunStatusResponse
from app.settings import get_settings

router = APIRouter(tags=["research"])


RESEARCH_FORM_HTML = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Research Launcher</title>
  <style>
    :root {
      --bg-ink: #0f172a;
      --bg-paper: #f8fafc;
      --card: #ffffff;
      --accent: #0ea5e9;
      --accent-deep: #0369a1;
      --text: #0b1220;
      --muted: #4b5563;
      --ok: #059669;
      --warn: #b45309;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "Avenir Next", "Trebuchet MS", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 10% 10%, #e0f2fe 0%, transparent 40%),
        radial-gradient(circle at 90% 30%, #dbeafe 0%, transparent 45%),
        linear-gradient(140deg, var(--bg-paper) 0%, #ecfeff 100%);
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
    }
    .panel {
      width: min(820px, 100%);
      background: var(--card);
      border: 1px solid #dbeafe;
      border-radius: 18px;
      box-shadow: 0 22px 50px -28px rgba(15, 23, 42, 0.45);
      overflow: hidden;
    }
    .banner {
      padding: 18px 22px;
      color: white;
      background: linear-gradient(110deg, var(--bg-ink), var(--accent-deep));
    }
    .banner h1 {
      margin: 0;
      font-size: 1.1rem;
      letter-spacing: 0.03em;
    }
    .banner p {
      margin: 6px 0 0;
      font-size: 0.9rem;
      opacity: 0.9;
    }
    form {
      padding: 20px 22px 12px;
      display: grid;
      gap: 12px;
    }
    .row {
      display: grid;
      grid-template-columns: 1fr 220px;
      gap: 10px;
    }
    label {
      font-size: 0.84rem;
      font-weight: 600;
      color: var(--muted);
      display: block;
      margin-bottom: 4px;
    }
    input, textarea, select {
      width: 100%;
      border: 1px solid #cbd5e1;
      border-radius: 10px;
      padding: 10px 12px;
      font-size: 0.95rem;
      background: #fff;
    }
    textarea { min-height: 120px; resize: vertical; }
    button {
      border: 0;
      border-radius: 11px;
      padding: 11px 14px;
      font-size: 0.95rem;
      font-weight: 700;
      color: #fff;
      background: linear-gradient(120deg, var(--accent), var(--accent-deep));
      cursor: pointer;
    }
    .status {
      padding: 14px 22px 20px;
      border-top: 1px solid #e2e8f0;
      font-size: 0.92rem;
      line-height: 1.45;
    }
    .status code {
      font-family: Consolas, "Courier New", monospace;
      font-size: 0.86rem;
      background: #f1f5f9;
      padding: 2px 6px;
      border-radius: 6px;
    }
    .ok { color: var(--ok); font-weight: 700; }
    .warn { color: var(--warn); font-weight: 700; }
    @media (max-width: 700px) {
      .row { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <section class=\"panel\">
    <div class=\"banner\">
      <h1>Autonomous Research Launcher</h1>
      <p>Submit one request and track status to completion.</p>
    </div>
    <form id=\"run-form\">
      <div>
        <label for=\"query\">Research topic</label>
        <textarea id=\"query\" required placeholder=\"Example: North America battery recycling market outlook and policy landscape\"></textarea>
      </div>
      <div class=\"row\">
        <div>
          <label for=\"email\">Delivery email</label>
          <input id=\"email\" type=\"email\" required placeholder=\"analyst@company.com\" />
        </div>
        <div>
          <label for=\"depth\">Depth</label>
          <select id=\"depth\">
            <option value=\"quick\">quick</option>
            <option value=\"standard\" selected>standard</option>
            <option value=\"deep\">deep</option>
          </select>
        </div>
      </div>
      <button type=\"submit\">Start Research Run</button>
    </form>
    <div class=\"status\" id=\"status\">Waiting for submission.</div>
  </section>

  <script>
    const form = document.getElementById('run-form');
    const statusEl = document.getElementById('status');

    function setStatus(html) {
      statusEl.innerHTML = html;
    }

    async function pollStatus(runId) {
      for (;;) {
        const res = await fetch(`/v1/research/runs/${runId}`);
        if (!res.ok) {
          setStatus(`<span class=\"warn\">Status fetch failed</span> for <code>${runId}</code>`);
          return;
        }
        const data = await res.json();
        setStatus(
          `Run <code>${data.run_id}</code><br/>` +
          `Status: <strong>${data.status}</strong><br/>` +
          `Stage: <strong>${data.stage}</strong><br/>` +
          `${data.error ? `<span class=\"warn\">Error: ${data.error}</span>` : ''}`
        );
        if (data.status === 'completed') {
          setStatus(
            `<span class=\"ok\">Run completed.</span><br/>` +
            `Run: <code>${data.run_id}</code><br/>` +
            `Report: <code>${data.report_artifact_path || 'n/a'}</code><br/>` +
            `Delivery artifact: <code>${data.delivery_artifact_path || 'n/a'}</code><br/>` +
            `Message id: <code>${data.delivery_message_id || 'n/a'}</code>`
          );
          return;
        }
        if (data.status === 'failed') {
          return;
        }
        await new Promise(resolve => setTimeout(resolve, 2500));
      }
    }

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        query: document.getElementById('query').value,
        requester_email: document.getElementById('email').value,
        depth: document.getElementById('depth').value
      };

      setStatus('Submitting run...');
      const res = await fetch('/v1/research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const text = await res.text();
        setStatus(`<span class=\"warn\">Submission failed:</span> ${text}`);
        return;
      }

      const data = await res.json();
      setStatus(`Run accepted: <code>${data.run_id}</code>. Polling status...`);
      await pollStatus(data.run_id);
    });
  </script>
</body>
</html>
"""


def _build_run_service() -> RunService:
    settings = get_settings()
    orchestrator = ResearchOrchestrator(settings)
    store = RunStore()

    slack_alert_client = None
    if settings.slack_webhook_url:
        slack_alert_client = SlackWebhookClient(
            webhook_url=settings.slack_webhook_url,
            timeout_seconds=settings.slack_request_timeout_seconds,
        )

    alert_service = AlertService(
        store=store,
        failure_threshold=settings.alert_failure_threshold,
        window_minutes=settings.alert_window_minutes,
        slack_client=slack_alert_client,
    )

    return RunService(
        store=store,
        runner=orchestrator.plan_collect_compose_and_deliver_report,
        guardrail_policy=GuardrailPolicy.from_settings(settings),
        alert_service=alert_service,
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/research/form", response_class=HTMLResponse)
def research_form() -> str:
    return RESEARCH_FORM_HTML


@router.post("/research", response_model=RunAcceptedResponse)
async def submit_research_run(
    request: PlanRequest,
    background_tasks: BackgroundTasks,
) -> RunAcceptedResponse:
    run_id = str(uuid4())
    run_service = _build_run_service()

    try:
        run_service.validate_request(request)
    except GuardrailViolation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    accepted = run_service.create_run(run_id)
    background_tasks.add_task(run_service.execute_run, run_id, request)
    return accepted


@router.get("/research/runs/{run_id}", response_model=RunStatusResponse)
def get_research_run_status(run_id: str) -> RunStatusResponse:
    store = RunStore()
    status = store.get_status_response(run_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    return status


@router.post("/research/plan", response_model=PlanResponse)
def plan_research(request: PlanRequest) -> PlanResponse:
    orchestrator = ResearchOrchestrator(get_settings())
    return orchestrator.plan_only(request)


@router.post("/research/candidates", response_model=CandidateCollectionResponse)
def collect_research_candidates(request: PlanRequest) -> CandidateCollectionResponse:
    orchestrator = ResearchOrchestrator(get_settings())
    return orchestrator.plan_and_collect_candidates(request)


@router.post("/research/findings", response_model=FindingsResponse)
async def collect_research_findings(request: PlanRequest) -> FindingsResponse:
    orchestrator = ResearchOrchestrator(get_settings())
    return await orchestrator.plan_collect_and_summarize_findings(request)


@router.post("/research/persist-findings", response_model=PersistedFindingsResponse)
async def persist_research_findings(request: PlanRequest) -> PersistedFindingsResponse:
    orchestrator = ResearchOrchestrator(get_settings())
    return await orchestrator.plan_collect_summarize_and_persist_findings(request)


@router.post("/research/report", response_model=ReportResponse)
async def generate_research_report(request: PlanRequest) -> ReportResponse:
    orchestrator = ResearchOrchestrator(get_settings())
    return await orchestrator.plan_collect_persist_and_compose_report(request)


@router.post("/research/deliver", response_model=DeliveredReportResponse)
async def deliver_research_report(request: PlanRequest) -> DeliveredReportResponse:
    orchestrator = ResearchOrchestrator(get_settings())
    return await orchestrator.plan_collect_compose_and_deliver_report(request)
