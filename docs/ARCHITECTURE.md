# Architecture

## Component view

```mermaid
flowchart LR
    U[Client / curl / optional UI] -->|HTTPS + JWT| GW[gateway<br/>NestJS]
    GW -->|JWT forwarded + X-Request-ID| AS[agent-service<br/>FastAPI + LangGraph]
    AS --> SUP{Supervisor}
    SUP --> KA[Knowledge agent]
    SUP --> OA[Ops data agent]
    SUP --> RA[Reporting agent]
    SUP --> AA[Action agent<br/>HITL interrupt]
    KA --> RET[mineops-retrieval]
    RET --> OS[(OpenSearch<br/>BM25 en/ar)]
    RET --> QD[(Qdrant<br/>dense)]
    RET --> RR[Cross-encoder<br/>reranker]
    OA & RA & AA -->|MCP client<br/>Streamable HTTP| MCP[mcp-server]
    MCP -->|app_ro / drafts_rw| PG[(PostgreSQL)]
    AS -->|checkpoints| PG
    AS --> LLM[LLM client]
    LLM --> V[vLLM]
    LLM --> O[Ollama]
    LLM --> H[Hosted API]
    GW -.->|users, audit| PG
```

## Request flow: chat with a tool call

```mermaid
sequenceDiagram
    participant C as Client
    participant G as gateway
    participant A as agent-service
    participant M as mcp-server
    participant P as Postgres
    C->>G: POST /v1/chat (JWT)
    G->>G: verify JWT, RBAC, validate, rate-limit
    G->>A: POST /chat (JWT, X-Request-ID, traceparent)
    A->>A: verify JWT (JWKS), build graph state
    A->>M: tools/call get_kpis (caller identity)
    M->>M: validate args, enforce role + sites
    M->>P: parameterized SELECT (app_ro)
    P-->>M: rows
    M-->>A: result + audit id
    A-->>G: SSE tokens / tool events
    G-->>C: SSE passthrough
```

## HITL flow (action agent)

```mermaid
sequenceDiagram
    participant Op as Operator
    participant Eng as Engineer
    participant A as agent-service
    participant M as mcp-server
    Op->>A: "Raise a WO for crusher CR-03 vibration"
    A->>A: action agent prepares draft
    A-->>Op: SSE interrupt {run_id, draft}
    Note over A: state checkpointed in Postgres
    Eng->>A: POST /runs/{id}/resume {decision: approve}
    A->>M: create_work_order_draft (engineer identity)
    M-->>A: WO-xxxxx pending→approved
    A-->>Eng: confirmation
```

## Trust boundaries

1. **Internet → gateway**: only public surface. JWT required except `/auth/login`, `/healthz`, JWKS.
2. **gateway → agent-service**: internal network; agent-service re-verifies the JWT (defense in depth).
3. **agent-service → mcp-server**: identity propagated per call; MCP enforces authorization independently of the LLM.
4. **mcp-server → Postgres**: least-privilege DB roles; LLM never produces SQL.
5. **agent-service → LLM**: prompts never contain secrets; outputs are treated as untrusted (validated before tool calls).
