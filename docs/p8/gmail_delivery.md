# P8 Gmail Delivery

## Scope

This phase adds:

1. Gmail delivery service for final report dispatch.
2. OAuth refresh-token flow for access token renewal.
3. Retry handling for transient Gmail API failures.
4. Idempotent send behavior keyed by run_id + recipient.
5. Delivery artifacts and dead-letter logging.
6. Optional Slack mirror via webhook.

## Flow

```mermaid
flowchart LR
    A[ReportArtifact] --> B[DeliveryService]
    B --> C[Build delivery_key run_id + recipient]
    C --> D[Check local delivery registry]
    D -->|exists| E[skip_existing]
    D -->|new| F[GmailMCPClient send_email]
    F --> G[OAuth refresh if needed]
    G --> H[message id]
    H --> I[delivery.json artifact]
    F -->|failure| J[delivery_dead_letter.json]
    H --> K[optional Slack webhook mirror]
```

## API

- POST /v1/research/deliver
  - Executes P3-P8 path and returns delivery status + message id.
