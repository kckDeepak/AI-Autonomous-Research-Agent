# Autonomous Research Agent - Phased Implementation Plan

## Project Snapshot

- Date: 2026-04-03
- Project: Autonomous Research Agent
- Context: Startup internal research automation
- Primary Goal: Accept a topic and autonomously produce, store, and deliver a polished research report with minimal human intervention.

### LLM Decision (OpenAI in place of Claude)

- Reason: Claude API key is not available.
- Decision: Use OpenAI models via OPENAI_API_KEY while keeping the rest of the MCP architecture unchanged.
- Engineering Note: Introduce an LLM provider abstraction so Anthropic can be re-enabled later without touching orchestration/business logic.

## Success Criteria

1. User submits one query (CLI, API, or web form) and receives a report without manual intervention.
2. At least 10 high-quality deduplicated sources are processed for medium-depth runs.
3. Structured findings are persisted to Notion with traceable run metadata.
4. Final report includes TL;DR, Executive Summary, Key Findings, Deep Dives, and References with URLs.
5. Delivery succeeds via Gmail MCP with retry/error handling.
6. Cost and scope limits are enforced (max_sources, token budget, timeout).
7. The system is observable with logs, run status, and failure reasons.

## Non-Functional Requirements

| Area            | Requirement                                                              |
| --------------- | ------------------------------------------------------------------------ |
| Reliability     | At-least-once execution with idempotent Notion writes and email delivery |
| Security        | Secrets only in environment variables or secret manager                  |
| Cost Control    | Hard caps on sources, summarization tokens, and retries                  |
| Performance     | Typical run (15 sources) in ~5-12 minutes, depending on source latency   |
| Maintainability | Modular architecture with clear contracts                                |

## Target Architecture

### Pattern

Orchestrated pipeline with typed module boundaries.

### Core Modules

| Module                                 | Responsibility                                       | Inputs                                     | Outputs                          |
| -------------------------------------- | ---------------------------------------------------- | ------------------------------------------ | -------------------------------- |
| Input Layer                            | Receives requests from CLI/API/Form and creates runs | query, requester_email, depth, max_sources | run_id, run status               |
| Planner Agent                          | Decomposes query into sub-topics and search strategy | query, depth, constraints                  | research_plan_json               |
| Search Connector (Tavily API)          | Executes planned web queries                         | search queries, per-query limits           | raw results, candidate URLs      |
| Fetcher + Extractor                    | Fetches URLs, extracts clean text, chunks docs       | candidate URLs                             | normalized documents             |
| Summarizer + Relevance Scorer (OpenAI) | Summarizes and scores relevance for each source      | normalized docs, original query            | finding records                  |
| Persistence (Notion MCP)               | Writes findings to Notion                            | findings, run metadata                     | notion page IDs, write status    |
| Report Composer (OpenAI)               | Synthesizes final report markdown + HTML             | findings, query, run stats                 | report markdown/html, references |
| Delivery (Gmail MCP)                   | Sends final report email, optional Slack mirror      | requester email, report html/markdown      | delivery status, message ID      |
| Filesystem Cache + Logs                | Stores run artifacts, logs, intermediates            | all stage events                           | replayable artifacts + logs      |

### Orchestration Flow

1. Validate request and create run_id.
2. Generate research plan from Planner.
3. Search and collect candidate URLs.
4. Deduplicate and rank URLs.
5. Fetch and extract page content.
6. Summarize and score relevance.
7. Persist findings to Notion.
8. Compose final report.
9. Send report via Gmail.
10. Mark run complete and persist run stats.

### Guardrails and Runtime Controls

- max_sources: default 20
- max_queries_per_plan: default 6
- per_url_timeout_seconds: default 20
- global_run_timeout_minutes: default 20
- llm_token_budget_per_run: configurable
- Retry policy:
  - Search retries: 2 with exponential backoff
  - Fetch retries: 2 with jitter
  - Gmail retries: 2 for transient failures
- Idempotency:
  - Notion writes keyed by run_id + source URL hash
  - Email send keyed by run_id + recipient

## Recommended Repository Structure

```text
app/
app/api/
app/cli/
app/core/
app/modules/planner/
app/modules/search/
app/modules/fetcher/
app/modules/summarizer/
app/modules/notion/
app/modules/reporting/
app/modules/delivery/
app/providers/llm/
app/providers/mcp/
app/schemas/
app/utils/
tests/
run_artifacts/
logs/
```

### Key Files

- .env.example
- pyproject.toml
- README.md
- app/main.py
- app/orchestrator.py
- app/settings.py
- app/schemas/research_plan.py
- app/schemas/finding.py
- app/schemas/report.py

## Environment and Secrets

### Required

- OPENAI_API_KEY
- TAVILY_API_KEY
- NOTION_TOKEN
- NOTION_DATABASE_ID
- GMAIL_CLIENT_ID
- GMAIL_CLIENT_SECRET
- GMAIL_REFRESH_TOKEN
- GMAIL_SENDER_EMAIL

### Optional

- SLACK_WEBHOOK_URL
- SENTRY_DSN
- LOG_LEVEL
- MAX_SOURCES_DEFAULT
- OPENAI_MODEL_PLANNER
- OPENAI_MODEL_SUMMARIZER
- OPENAI_MODEL_REPORTER

### Security Practices

1. Use local .env for development and secret manager in production.
2. Never log full tokens or OAuth credentials.
3. Rotate Gmail refresh tokens and monitor refresh failures.

## Phased Build Plan

### P0 - Discovery and Technical Design

- Duration: 1-2 days
- Goal: Lock requirements, architecture, and operating constraints before coding.
- Depends on: None

Steps:

1. P0-S1: Define user journeys and run modes
   - Clarify CLI, API, and optional UI workflows, required input fields, and outputs.
   - Deliverables: user journey document, input/output contract.
2. P0-S2: Define quality bar for research output
   - Set standards for citation quality, report structure, and source diversity.
   - Deliverables: report quality rubric, source acceptance criteria.
3. P0-S3: Finalize architecture and module interfaces
   - Specify typed contracts across planner, search, fetch, summarize, persist, compose, and deliver modules.
   - Deliverables: architecture diagram, module interface spec.

Exit Criteria:

- Architecture reviewed and approved.
- Input/output contracts signed off.

Risk:

- Scope creep from enabling too many channels too early.

### P1 - Project Bootstrap and Environment Setup

- Duration: 0.5-1 day
- Goal: Create production-ready project skeleton and local runtime.
- Depends on: P0

Steps:

1. P1-S1: Initialize Python 3.11+ project
   - Set up venv, dependency management, formatter/linter, test runner.
   - Deliverables: pyproject.toml, baseline folder structure, tooling config.
2. P1-S2: Install baseline dependencies
   - Install fastapi, uvicorn, httpx, beautifulsoup4, pydantic, tenacity, loguru, mcp client stack, openai SDK.
   - Deliverables: locked dependencies, reproducible environment.
3. P1-S3: Create settings and secret loading
   - Implement central settings validation for required env vars.
   - Deliverables: settings loader, .env.example.

Exit Criteria:

- One command starts local API.
- Missing env values fail fast with clear errors.

Risk:

- Environment drift across machines.

### P2 - LLM Provider Abstraction (OpenAI-First)

- Duration: 1 day
- Goal: Decouple business logic from model vendor and enable OpenAI replacement for Claude.
- Depends on: P1

Steps:

1. P2-S1: Define LLM interface
   - Provider-agnostic methods for planning, summarization, report composition.
   - Deliverables: interface/protocol, typed request-response models.
2. P2-S2: Implement OpenAI adapter
   - Map prompts to OpenAI endpoint(s), enforce structured JSON outputs.
   - Deliverables: OpenAI provider module, retry/timeouts.
3. P2-S3: Keep Anthropic compatibility stubs
   - Preserve easy future switch-back path.
   - Deliverables: Anthropic placeholder adapter.

Exit Criteria:

- Planner and report prompts run through unified LLM interface.
- Structured outputs are validated and resilient.

Risk:

- Model-specific formatting differences breaking strict JSON parsing.

### P3 - Planner Agent

- Duration: 1 day
- Goal: Generate actionable, bounded research plans from raw queries.
- Depends on: P2

Steps:

1. P3-S1: Design planner prompt and schema
   - Output strict JSON: subtopics, query list, depth strategy, source estimate.
   - Deliverables: planner prompt template, research plan schema.
2. P3-S2: Add planning heuristics and caps
   - Clamp query breadth/depth to max limits.
   - Deliverables: post-processor, cost/safety constraints.
3. P3-S3: Persist plan artifact
   - Save plan JSON into run_artifacts for auditability.
   - Deliverables: plan artifact per run.

Exit Criteria:

- Sample topics produce valid and useful plan JSON.

Risk:

- Overly broad plans causing unnecessary API usage.

### P4 - Search and URL Collection via Tavily API

- Duration: 1 day
- Goal: Collect high-signal source URLs from planned queries.
- Depends on: P3

Steps:

1. P4-S1: Implement Tavily API client wrapper
   - Build service wrapper with retries/timeouts.
   - Deliverables: search service module.
2. P4-S2: Aggregate and deduplicate URLs
   - Merge results across queries and normalize URLs.
   - Deliverables: dedup pipeline, candidate URL list.
3. P4-S3: Rank and trim candidates
   - Prioritize source diversity and relevance.
   - Deliverables: ranked URL set.

Exit Criteria:

- Stable candidate list is returned within configured caps.

Risk:

- Search latency or inconsistent ranking quality.

### P5 - Fetcher, Content Extraction, and Source Summarization

- Duration: 2 days
- Goal: Convert raw URLs into clean, summarized, and scored findings.
- Depends on: P4

Steps:

1. P5-S1: Build robust fetcher
   - Async httpx client with retries, redirects, UA, and timeout controls.
   - Deliverables: async fetch module.
2. P5-S2: Parse and clean HTML
   - Extract title/body, remove boilerplate/nav text, normalize content.
   - Deliverables: content extractor.
3. P5-S3: Chunk and summarize
   - Chunk long text and request 3-sentence summary + tags + relevance score from OpenAI.
   - Deliverables: finding records.
4. P5-S4: Filter weak sources
   - Drop low-relevance records and keep confidence metadata.
   - Deliverables: quality-controlled finding set.

Exit Criteria:

- At least 70% of fetched URLs produce usable findings on standard topics.

Risks:

- Websites block bots or require JavaScript rendering.
- Noisy extraction reduces summary quality.

### P6 - Notion MCP Integration

- Duration: 1 day
- Goal: Persist findings in Notion in a structured, queryable format.
- Depends on: P5

Steps:

1. P6-S1: Create Notion schema
   - Properties: Title, Summary, URL, Relevance, Tags, Query, RunID, Timestamp.
   - Deliverables: Notion database schema.
2. P6-S2: Implement Notion write adapter
   - Insert records with idempotency checks.
   - Deliverables: notion service module.
3. P6-S3: Add retries and dead-letter logging
   - Failed writes are replayable, not silently dropped.
   - Deliverables: retry/replay flow.

Exit Criteria:

- All valid findings are written or logged for replay.

Risk:

- Notion rate limits and schema/property mismatch errors.

### P7 - Report Composer and Citation Engine

- Duration: 1 day
- Goal: Generate polished markdown and HTML reports with traceable citations.
- Depends on: P6

Steps:

1. P7-S1: Define report template
   - Sections: TL;DR, Executive Summary, Key Findings, Deep Dives (top 3), References.
   - Deliverables: report prompt + template.
2. P7-S2: Implement citation mapping
   - Map claim blocks to source URLs.
   - Deliverables: citation index, source footnotes.
3. P7-S3: Render markdown and HTML
   - Markdown for artifacts, HTML for email clients.
   - Deliverables: report.md artifact, email-ready HTML.

Exit Criteria:

- Report is coherent, cited, and delivery-ready.

Risk:

- Hallucinated statements not grounded in sources.

### P8 - Gmail MCP Delivery

- Duration: 0.5-1 day
- Goal: Send final report automatically and reliably.
- Depends on: P7

Steps:

1. P8-S1: Implement Gmail send service
   - Send HTML email with plain text fallback and structured subject.
   - Deliverables: gmail delivery module.
2. P8-S2: Implement token refresh and retry
   - Handle OAuth refresh lifecycle and transient send failures.
   - Deliverables: auto-refresh logic, retry policy.
3. P8-S3: Optional Slack mirror
   - Post summary + report link to team channel.
   - Deliverables: optional Slack notifier.

Exit Criteria:

- Email delivery succeeds in staging for 5 consecutive runs.

Risk:

- Expired refresh tokens causing silent delivery failures.

### P9 - User Interfaces (CLI, API, Minimal Web Form)

- Duration: 1-2 days
- Goal: Expose trigger interfaces while reusing one orchestration backend.
- Depends on: P8

Steps:

1. P9-S1: CLI interface
   - Example invocation: python -m app.cli --query "..." --email "..." --depth standard.
   - Deliverables: CLI command.
2. P9-S2: FastAPI endpoints
   - Implement POST /research and status endpoint.
   - Deliverables: API routes + request/response schemas.
3. P9-S3: Minimal HTML form
   - Internal form for topic/email/depth submission.
   - Deliverables: lightweight front-end page.

Exit Criteria:

- All interfaces trigger the same orchestration path.

Risk:

- Diverging logic between interfaces.

### P10 - Guardrails, Observability, and Cost Governance

- Duration: 1 day
- Goal: Make the system safe, debuggable, and cost-predictable.
- Depends on: P9

Steps:

1. P10-S1: Runtime guardrails
   - Enforce max sources, token budgets, timeout, request-size limits.
   - Deliverables: guardrail middleware.
2. P10-S2: Structured logging and run tracing
   - Track stage-level latency, errors, and token stats by run_id.
   - Deliverables: JSON logs, run summaries.
3. P10-S3: Alert hooks
   - Alert on repeated stage failures or delivery failures.
   - Deliverables: failure alert integration.

Exit Criteria:

- Typical failures are diagnosable in under 10 minutes using artifacts and logs.

Risk:

- Insufficient telemetry slows incident resolution.

### P11 - Testing, Evaluation, and Hardening

- Duration: 2 days
- Goal: Validate correctness, resilience, and output quality before production.
- Depends on: P10

Steps:

1. P11-S1: Unit and contract tests
   - Mock MCP and OpenAI responses for module isolation.
   - Deliverables: unit tests, schema contract tests.
2. P11-S2: Integration scenarios
   - End-to-end staging runs validating persisted artifacts and email output.
   - Deliverables: integration suite, golden run samples.
3. P11-S3: Quality evaluation harness
   - Score relevance, grounding, citation coverage, readability.
   - Deliverables: quality checklist, baseline scores.

Exit Criteria:

- Test pass rate > 90%.
- No critical defects in end-to-end flow.

Risk:

- Missing test coverage for external API failure modes.

### P12 - Deployment and Operations

- Duration: 1-2 days
- Goal: Deploy with operational safeguards and scheduling.
- Depends on: P11

Steps:

1. P12-S1: Containerize service
   - Docker image with health checks and non-root user.
   - Deliverables: Dockerfile, runtime docs.
2. P12-S2: Deploy to Cloud Run
   - Integrate secret manager and autoscaling boundaries.
   - Deliverables: deployed service, deployment scripts.
3. P12-S3: Configure scheduler and auth
   - Scheduled execution and protected endpoint.
   - Deliverables: scheduled job, auth controls.
4. P12-S4: Ops runbook
   - Recovery playbooks for search outage, OAuth issues, model failures.
   - Deliverables: runbook.

Exit Criteria:

- Production deployment remains stable through a 1-week pilot.

Risk:

- Cloud misconfiguration or missing secret permissions.

## Execution Sequence

P0 -> P1 -> P2 -> P3 -> P4 -> P5 -> P6 -> P7 -> P8 -> P9 -> P10 -> P11 -> P12

## Milestones

| Milestone                     | Phases | Target Outcome                                             |
| ----------------------------- | ------ | ---------------------------------------------------------- |
| M1 - Core pipeline demo       | P0-P5  | Query to summarized findings works with OpenAI + Tavily    |
| M2 - Full report and delivery | P6-P8  | Findings persist in Notion and polished report is emailed  |
| M3 - Production readiness     | P9-P12 | Multi-interface, observable, tested, and deployable system |

## Risk Register

| Risk                                        | Impact | Mitigation                                                   |
| ------------------------------------------- | ------ | ------------------------------------------------------------ |
| LLM output format drift breaks JSON parsing | High   | Strict schema validation, repair pass, fallback parser       |
| Runaway API costs on broad queries          | High   | Hard caps on sources/tokens and planner constraints          |
| Gmail OAuth token expiry                    | High   | Auto-refresh, proactive checks, alerting                     |
| Extraction quality variance by site         | Medium | Source scoring, extraction fallbacks, optional headless path |
| External MCP outages                        | Medium | Retry strategy, graceful degradation, replay tooling         |

## KPI Targets

| KPI                                  | Target                               |
| ------------------------------------ | ------------------------------------ |
| End-to-end success rate              | >= 95%                               |
| Median run duration (standard depth) | <= 10 minutes                        |
| Average citations per key finding    | >= 1                                 |
| Email delivery success               | >= 99%                               |
| Average cost per run                 | Within team-defined budget threshold |

## Immediate Next Actions

1. Implement P1 project bootstrap in this repository.
2. Populate .env and validate MCP credential connectivity.
3. Build P2 OpenAI provider abstraction before deeper module work.
4. Build planner + Tavily pipeline first to validate core loop quickly.
