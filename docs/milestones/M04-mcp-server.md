# M4 — MCP server + tools + resources

**Goal:** `services/mcp-server` exposes governed tools/resources over Streamable HTTP; an MCP client script can list and call them with a demo identity; authorization is enforced server-side.

**Cost:** none.

## Tasks
1. Service scaffold with the official MCP Python SDK (pin version; check current Streamable HTTP + auth APIs), plus `/healthz`, `/readyz`.
2. Auth: validate bearer JWT (JWKS URL from settings; in M4 use a local test keypair + `scripts/mint_token.py` until the gateway exists in M7). Build a `CallerContext(sub, role, sites, lang)`.
3. Tools per SPEC §8, each with: Pydantic args (enums, bounded date ranges, `limit ≤ 200`), named SQL template from `mineops_data.queries`, `app_ro` connection pool, statement timeout, role/site enforcement, audit insert into `audit.tool_calls` (who, tool, args hash, rows, latency, outcome).
4. `create_work_order_draft` uses `drafts_rw`; only creates `pending` drafts; approval is a separate tool `approve_work_order_draft` restricted to `engineer`.
5. `search_sops` wraps `HybridRetriever` (hybrid_rerank default, filter args exposed).
6. Resources: `sop://{doc_id}` (latest version, markdown), `site://{site_id}` (summary).
7. Tool descriptions written for LLM consumption: when to use, args semantics, examples. Keep them short and unambiguous.
8. Tests: in-process client (stdio or SDK test client) for each tool: happy path, validation errors, cross-site denial for operator, executive cannot create drafts, timeout behavior.
9. `scripts/mcp_demo.py`: list tools, call a few as each role.

## Done checklist
- [ ] All tools tested incl. negative authz cases
- [ ] Audit rows written for every call
- [ ] `docs/interview/M04.md` (MCP vs plain function calling, transports, identity propagation, tool design for LLMs, confused-deputy risk; sovereign note)
