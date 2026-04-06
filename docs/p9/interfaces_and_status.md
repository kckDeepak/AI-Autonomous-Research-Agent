# P9 User Interfaces and Run Status

## Scope

This phase delivers:

1. Unified run trigger endpoint.
2. Run status endpoint.
3. CLI path using the same backend execution stage.
4. Minimal internal web form that submits to the same API path.

## Unified Backend Path

All interfaces converge to the same orchestration path:

- plan -> search -> fetch -> summarize -> notion persist -> report compose -> delivery

## API Endpoints

- POST /v1/research
  - Accepts run request and returns run_id + status_url immediately.
- GET /v1/research/runs/{run_id}
  - Returns run lifecycle state and completion metadata.
- GET /v1/research/form
  - Minimal HTML form that submits to `/v1/research` and polls status.

## Run Lifecycle States

- accepted
- running
- completed
- failed

## Notes

- Status records are persisted under `run_artifacts/run_status/`.
- Delivery idempotency remains enforced via delivery keys in P8.
