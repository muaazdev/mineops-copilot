# ADR-0004: MCP server as a separate service over Streamable HTTP, with identity propagation

- Status: Accepted
- Date: 2026-10-20

## Context
Agents need controlled access to systems and data. MCP standardizes tool/resource exposure so any MCP-capable agent or client can use the same governed surface.

## Decision
`mcp-server` is its own deployable using the MCP Python SDK's Streamable HTTP transport. agent-service connects with an MCP client (LangChain MCP adapters). The caller's identity (JWT, or a short-lived downscoped token) is sent per request; the MCP server authorizes every call itself. stdio transport is used only in unit tests.

## Alternatives considered
- Plain function calling inside agent-service — simpler, but tools aren't reusable by other clients and the security boundary is in-process with the LLM loop.
- MCP over stdio as a subprocess — fine for desktop clients, wrong shape for K8s scaling and network policy.

## Consequences
- Extra network hop and service to operate; gains an independent security boundary, separate scaling, and a NetworkPolicy-enforceable path to the DB.
- Must design auth for MCP (bearer token validation, audience checks).

## Revisit when
Latency of the extra hop matters more than reuse/isolation.
