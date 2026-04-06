# P0-S1 User Journeys and Run Modes

## Objective

Define how internal users submit a research request and retrieve outcomes across CLI, API, and optional web form channels.

## Actors

- Requester (employee): submits query + recipient email
- Platform service: orchestrates execution
- Reviewer (optional): inspects artifacts and logs

## Run Modes

| Mode       | Target User            | Trigger      | Output                                              | Typical Use             |
| ---------- | ---------------------- | ------------ | --------------------------------------------------- | ----------------------- |
| `quick`    | Individual contributor | CLI/API/form | concise report, 8-12 sources                        | fast scouting           |
| `standard` | Team lead              | CLI/API/form | full report, 12-20 sources                          | weekly research updates |
| `deep`     | Strategy leadership    | API/form     | expanded report, 20+ sources (capped by guardrails) | major topic analysis    |

## User Journeys

### CLI Journey

1. User runs CLI command with `query`, `email`, and optional `depth`.
2. Service validates payload and secrets, then creates `run_id`.
3. Pipeline executes and writes artifacts.
4. User receives immediate terminal acknowledgement with `run_id` and later email delivery.

### API Journey

1. Internal caller submits `POST /research` payload.
2. API returns accepted response with `run_id` and status URL.
3. Caller polls `/research/{run_id}` for status.
4. On completion, report is delivered via Gmail and optionally linked in API status response.

### Minimal Web Form Journey

1. User enters topic, recipient email, and depth preset.
2. Form submits to API backend.
3. UI displays run started state and `run_id`.
4. User receives report through email; UI can provide final status.

## Input Contract (High-Level)

- Required: `query`, `requester_email`
- Optional: `depth`, `max_sources`, `max_queries_per_plan`, `llm_token_budget_per_run`

## Output Contract (High-Level)

- Synchronous: `run_id`, status URL, accepted timestamp
- Asynchronous final: report markdown/html, references, Notion persistence status, delivery status
