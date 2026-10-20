# M5 — LangGraph supervisor + agents + HITL

**Goal:** a runnable graph (CLI) that routes questions to the 4 agents, uses MCP tools via an MCP client, cites sources, and pauses for human approval on work-order drafts — with state persisted in Postgres.

**Cost:** none locally (Ollama). Hosted API only with approval.

## Tasks
1. Pin LangGraph / LangChain / langchain-mcp-adapters versions; check current APIs (interrupt/Command, Postgres checkpointer, subgraphs).
2. Graph state model (Pydantic/TypedDict): messages, caller context, route, citations, tool_events, draft, report.
3. Supervisor: structured-output router (`knowledge | ops | report | action | clarify | refuse`), with few-shot examples in EN + AR. Fallback rules when the small model returns invalid JSON.
4. Knowledge agent: retrieval → grounded answer with `[doc_id §section]` citations; "insufficient evidence" path; answer in user's language.
5. Ops data agent: MCP tools bound via adapters; max tool-call budget; numbers in answers must come from tool outputs (validate by checking presence in tool results where feasible).
6. Reporting agent: calls a fixed set of tools, fills a `ExecutiveReport` Pydantic model, renders markdown (EN/AR).
7. Action agent: build draft → `interrupt()` with draft payload → resume with `{decision, approver, reason}` → call tools accordingly. Approval requires `engineer` caller on resume (enforced in code and by MCP).
8. Postgres checkpointer in `agent` schema; thread_id = run_id.
9. CLI `uv run mineops-agent chat --as operator --site <id>` for manual testing; `--resume <run_id> --approve`.
10. Tests: router accuracy on a labeled set (~40 prompts, EN/AR) using the fake LLM for unit tests and a small live-model eval script; HITL interrupt/resume survives process restart; authz denial bubbles up as a clear message.

## Done checklist
- [ ] Demo transcript (EN + AR) committed to `docs/demo/m05-transcripts.md`
- [ ] Router eval numbers recorded
- [ ] `docs/interview/M05.md` (supervisor vs swarm, interrupts & checkpointing, grounding/citation validation, small-model reliability tactics; sovereign note)
