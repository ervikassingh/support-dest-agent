# How the agent runs

One LangGraph compiled with `PostgresSaver` (thread checkpoints) and `PostgresStore` (operator refund notes). Cheap path is `gpt-4o-mini` with no tools. Main path is Claude Haiku with MCP read tools. Write tools (`send_email`, `issue_refund`) are not bound to the model.

Source: `apps/agent/src/agent/graph/build.py`.

```mermaid
flowchart TD
  startNode([POST /chat]) --> summarize["Summarize if tokens ≥ 70% of budget<br/>skip while an interrupt is open"]
  summarize --> router["Intent router · gpt-4o-mini"]

  router -->|chitchat or out of scope| cheap["Cheap agent · no tools"]
  router -->|policy or order| prepare["Prepare main<br/>RAG if policy"]
  router -->|refund| loadMem["Load PostgresStore notes"]
  router -->|email| draftEmail["Draft email"]

  cheap --> respond[Respond]
  prepare --> main["Main agent · Claude Haiku"]
  main -->|tool call, under step limit| tools["MCP reads<br/>get_order, shipping, eligibility, customer"]
  tools --> main
  main -->|final answer| respond

  loadMem --> draftRefund[Draft refund]
  draftRefund --> awaitRefund["interrupt · operator approval"]
  awaitRefund --> issue["issue_refund or reject<br/>then write PostgresStore"]
  issue --> respond

  draftEmail --> awaitEmail["interrupt · customer yes or no"]
  awaitEmail --> send["send_email stub<br/>requires confirmation id"]
  send --> respond

  respond --> endNode([Reply])

  saver[(PostgresSaver)] -.-> startNode
  saver -.-> awaitRefund
  saver -.-> awaitEmail
```

Resume paths:

- Email: next `POST /chat` with yes or no resumes the same thread.
- Refund: `POST /threads/{id}/resume` with approve, edit, or reject. Chat messages cannot skip the operator gate.
