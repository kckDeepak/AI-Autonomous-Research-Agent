# P0-S1 Input/Output Contract

## Request Schema

```json
{
  "query": "Market outlook for battery recycling in North America",
  "requester_email": "analyst@company.com",
  "depth": "standard",
  "max_sources": 20,
  "max_queries_per_plan": 6,
  "llm_token_budget_per_run": 25000
}
```

### Field Definitions

| Field                      | Type    | Required | Constraints                                         |
| -------------------------- | ------- | -------- | --------------------------------------------------- |
| `query`                    | string  | yes      | 10-1000 chars                                       |
| `requester_email`          | string  | yes      | valid email                                         |
| `depth`                    | enum    | no       | `quick` \| `standard` \| `deep`; default `standard` |
| `max_sources`              | integer | no       | 1-50; default from settings                         |
| `max_queries_per_plan`     | integer | no       | 1-12; default from settings                         |
| `llm_token_budget_per_run` | integer | no       | positive; default from settings                     |

## Accepted Response

```json
{
  "run_id": "f95b9348-ec13-4e84-9924-fc87eec69757",
  "status": "accepted",
  "status_url": "/v1/research/runs/f95b9348-ec13-4e84-9924-fc87eec69757",
  "submitted_at": "2026-04-05T10:30:00Z"
}
```

## Run Status Response

```json
{
  "run_id": "f95b9348-ec13-4e84-9924-fc87eec69757",
  "status": "completed",
  "stage": "delivery",
  "started_at": "2026-04-05T10:30:00Z",
  "completed_at": "2026-04-05T10:37:41Z",
  "error": null,
  "report_artifact_path": "run_artifacts/f95b9348-ec13-4e84-9924-fc87eec69757/report.md"
}
```

## Error Contract

| Type                     | HTTP | Example                                   |
| ------------------------ | ---- | ----------------------------------------- |
| Validation error         | 422  | Invalid email or malformed request        |
| Secret/config error      | 500  | Missing required environment variable(s)  |
| Execution timeout        | 504  | Run exceeded global timeout               |
| Upstream transient error | 502  | Search/LLM/Notion/Gmail temporary failure |
