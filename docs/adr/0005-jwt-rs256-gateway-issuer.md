# ADR-0005: Gateway-issued RS256 JWTs with JWKS; verify at every service

- Status: Accepted
- Date: 2026-10-20

## Context
Need authN/authZ with roles and site scoping across three services, no external IdP for local runs, and a credible path to a government IdP.

## Decision
The gateway issues short-lived (15 min) RS256 access tokens for seeded demo users and publishes `/.well-known/jwks.json`. agent-service and mcp-server verify signature, `iss`, `aud`, `exp` via JWKS. Claims: `sub, role, sites[], lang`. Swap to Keycloak/OIDC is documented: services only depend on JWKS + claims.

## Alternatives considered
- Session cookies — stateful, awkward across services and for SSE/API clients.
- HS256 shared secret — every verifier could also mint tokens.
- Keycloak in compose from day one — realistic but heavy; documented as the production path.

## Consequences
- No server-side revocation for access tokens; mitigated by short TTL (refresh tokens out of scope).
- Key rotation via `kid` in JWKS.

## Revisit when
Moving to a real deployment — replace issuer with Keycloak / national SSO.
