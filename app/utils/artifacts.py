from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.schemas.content import DocumentBatch, FetchBatch, SummarizationBatch
from app.schemas.delivery import DeliveryResult
from app.schemas.notion import NotionWriteBatch
from app.schemas.report import ReportArtifact
from app.schemas.research_plan import PlanRequest, ResearchPlan, RuntimeConstraints
from app.schemas.search import SearchCandidate


def persist_plan_artifact(
    *,
    run_id: str,
    request: PlanRequest,
    constraints: RuntimeConstraints,
    plan: ResearchPlan,
    root_dir: Path | None = None,
) -> str:
    artifact_root = root_dir or Path("run_artifacts")
    run_dir = artifact_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = run_dir / "research_plan.json"
    payload = {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "request": request.model_dump(mode="json"),
        "constraints": constraints.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
    }
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return artifact_path.as_posix()


def persist_candidate_artifact(
    *,
    run_id: str,
    query: str,
    search_queries: list[str],
    candidates: list[SearchCandidate],
    raw_result_count: int,
    deduped_result_count: int,
    root_dir: Path | None = None,
) -> str:
    artifact_root = root_dir or Path("run_artifacts")
    run_dir = artifact_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = run_dir / "candidate_urls.json"
    payload = {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "query": query,
        "search_queries": search_queries,
        "raw_result_count": raw_result_count,
        "deduped_result_count": deduped_result_count,
        "candidate_count": len(candidates),
        "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
    }
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return artifact_path.as_posix()


def persist_document_artifact(
    *,
    run_id: str,
    fetch_batch: FetchBatch,
    document_batch: DocumentBatch,
    root_dir: Path | None = None,
) -> str:
    artifact_root = root_dir or Path("run_artifacts")
    run_dir = artifact_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = run_dir / "documents.json"
    payload = {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "fetched_count": len(fetch_batch.pages),
        "fetch_failures_count": len(fetch_batch.failures),
        "extracted_count": len(document_batch.documents),
        "extraction_issues_count": len(document_batch.issues),
        "fetch_failures": [failure.model_dump(mode="json") for failure in fetch_batch.failures],
        "extraction_issues": [issue.model_dump(mode="json") for issue in document_batch.issues],
        "documents": [document.model_dump(mode="json") for document in document_batch.documents],
    }
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return artifact_path.as_posix()


def persist_findings_artifact(
    *,
    run_id: str,
    query: str,
    summarization_batch: SummarizationBatch,
    min_relevance_score: float,
    root_dir: Path | None = None,
) -> str:
    artifact_root = root_dir or Path("run_artifacts")
    run_dir = artifact_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = run_dir / "findings.json"
    payload = {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "query": query,
        "min_relevance_score": min_relevance_score,
        "finding_count": len(summarization_batch.findings),
        "filtered_out_count": len(summarization_batch.rejected_findings),
        "issues_count": len(summarization_batch.issues),
        "findings": [finding.model_dump(mode="json") for finding in summarization_batch.findings],
        "rejected_findings": [
            finding.model_dump(mode="json") for finding in summarization_batch.rejected_findings
        ],
        "issues": [issue.model_dump(mode="json") for issue in summarization_batch.issues],
    }
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return artifact_path.as_posix()


def persist_notion_persistence_artifact(
    *,
    run_id: str,
    query: str,
    write_batch: NotionWriteBatch,
    root_dir: Path | None = None,
) -> str:
    artifact_root = root_dir or Path("run_artifacts")
    run_dir = artifact_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = run_dir / "notion_persistence.json"
    payload = {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "query": query,
        "created_count": write_batch.created_count,
        "skipped_count": write_batch.skipped_count,
        "failed_count": write_batch.failed_count,
        "receipts": [receipt.model_dump(mode="json") for receipt in write_batch.receipts],
        "failures": [failure.model_dump(mode="json") for failure in write_batch.failures],
    }
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return artifact_path.as_posix()


def persist_notion_dead_letter_artifact(
    *,
    run_id: str,
    query: str,
    write_batch: NotionWriteBatch,
    root_dir: Path | None = None,
) -> str | None:
    if not write_batch.failures:
        return None

    artifact_root = root_dir or Path("run_artifacts")
    run_dir = artifact_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = run_dir / "notion_dead_letter.json"
    payload = {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "query": query,
        "failed_count": write_batch.failed_count,
        "failures": [failure.model_dump(mode="json") for failure in write_batch.failures],
    }
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return artifact_path.as_posix()


def persist_report_artifact(
    *,
    run_id: str,
    query: str,
    report: ReportArtifact,
    root_dir: Path | None = None,
) -> str:
    artifact_root = root_dir or Path("run_artifacts")
    run_dir = artifact_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = run_dir / "report.json"
    payload = {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "query": query,
        "report": report.model_dump(mode="json"),
    }
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return artifact_path.as_posix()


def persist_delivery_artifact(
    *,
    run_id: str,
    query: str,
    delivery: DeliveryResult,
    root_dir: Path | None = None,
) -> str:
    artifact_root = root_dir or Path("run_artifacts")
    run_dir = artifact_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = run_dir / "delivery.json"
    payload = {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "query": query,
        "delivery": delivery.model_dump(mode="json"),
    }
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return artifact_path.as_posix()


def persist_delivery_dead_letter_artifact(
    *,
    run_id: str,
    query: str,
    delivery: DeliveryResult,
    root_dir: Path | None = None,
) -> str | None:
    if delivery.status != "failed":
        return None

    artifact_root = root_dir or Path("run_artifacts")
    run_dir = artifact_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = run_dir / "delivery_dead_letter.json"
    payload = {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "query": query,
        "delivery": delivery.model_dump(mode="json"),
    }
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return artifact_path.as_posix()



