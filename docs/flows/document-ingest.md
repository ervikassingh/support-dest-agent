# Document ingest

How a policy document uploaded in the browser becomes searchable. Parsing, chunking, and search are on the [rag](../services/rag.md#pipeline) page.

```mermaid
sequenceDiagram
  participant W as web (Documents)
  participant A as api
  participant R as rag API
  participant D as data/uploads
  participant Q as Redis 'ingest'
  participant K as rag worker
  participant P as Postgres
  W->>A: POST /documents (file or {url})
  A->>R: POST /documents/reserve
  R->>P: insert next version, status queued
  R-->>A: row + storage_path
  opt file upload
    A->>D: write bytes to storage_path
  end
  A->>Q: add job {documentId}
  A-->>W: document (queued)
  Q->>K: job
  K->>P: status parsing
  opt URL
    K->>K: download (Google links → PDF export)
  end
  K->>K: parse → chunk
  K->>P: status embedding
  K->>K: embed via OpenRouter
  K->>P: replace this document's chunks, status done
  loop every 2 s while anything is in progress
    W->>A: GET /documents
  end
```

- rag owns the document rows and storage layout; api only writes the bytes to the path rag reserved. They must share the `data/uploads` directory.
- The job id is the document id, so a repeated enqueue is a no-op. Failed jobs retry 3 times with backoff, then the row is marked `failed` with the error.
- Re-uploading the same file name or URL creates a new version; old versions stay searchable.
- `poetry run rag-seed --ingest` skips api and Redis and ingests the seed corpus directly.
