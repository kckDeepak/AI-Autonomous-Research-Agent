# P6 Notion Integration

## Scope

This phase adds:

1. Structured Notion persistence for findings.
2. Idempotent writes keyed by run_id + source URL hash.
3. Retry handling for transient Notion failures.
4. Dead-letter artifacts for failed writes.

## Flow

```mermaid
flowchart LR
    A[Findings] --> B[NotionPersistenceService]
    B --> C[Compute SourceKey = run_id + sha256(url)]
    C --> D[Query Notion by SourceKey]
    D -->|exists| E[Skip existing receipt]
    D -->|not found| F[Create Notion page]
    F --> G[Write receipt]
    F -->|error after retries| H[Dead-letter failure]
    G --> I[notion_persistence.json]
    H --> J[notion_dead_letter.json]
```

## Notion Properties Expected

- Title (title)
- Summary (rich_text)
- URL (url)
- Relevance (number)
- Confidence (number)
- Tags (multi_select)
- Query (rich_text)
- RunID (rich_text)
- SourceKey (rich_text)
- Timestamp (date)

## API

- POST /v1/research/persist-findings
  - Executes P3-P6 path and returns write receipts plus failure details.
