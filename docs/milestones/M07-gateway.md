# M7 — NestJS gateway

**Goal:** the public API: login, JWT issuance + JWKS, RBAC + site scoping, validation, rate limiting, SSE proxy to agent-service, dashboard/report endpoints.

**Cost:** none.

**Owner is weaker in NestJS/TypeScript — explain module/provider/guard/interceptor/pipe roles in comments and in `docs/interview/M07.md`. Prefer idiomatic Nest patterns over clever code.**

## Tasks
1. Scaffold with Nest CLI (pin Node LTS + Nest major), TS strict, ESLint + Prettier, Jest. pnpm.
2. Config module with schema validation of env at boot (fail fast).
3. `AuthModule`: seeded users in `auth.users` (argon2 hashes), `POST /auth/login`, RS256 signing (keys from env/secret mount, `kid`), `GET /.well-known/jwks.json`. Short TTL.
4. Guards: `JwtAuthGuard` (global, `@Public()` opt-out), `RolesGuard` with `@Roles(...)`, `SiteScopeGuard` validating `siteId` params/query against claims.
5. DTOs with class-validator/class-transformer; global `ValidationPipe` (whitelist, forbidNonWhitelisted, transform).
6. Global exception filter → error envelope; request-ID middleware; logging interceptor (pino) with JSON output.
7. Rate limiting (`@nestjs/throttler`), per-user + per-IP, stricter on `/auth/login` and `/v1/chat`.
8. Proxy: `POST /v1/chat` streams SSE from agent-service (handle client abort → upstream abort); `GET /v1/runs/:id`, `POST /v1/runs/:id/approve|reject` (engineer only).
9. Dashboard/report endpoints: `GET /v1/dashboard/kpis` (calls agent-service or reads `ops` via `gateway_ro` view — decide and record an ADR), `GET /v1/reports/daily|weekly`.
10. Switch agent-service and mcp-server to verify against gateway JWKS.
11. Tests: unit (guards, pipes, filters), e2e with supertest (login → chat → approve; RBAC denials; validation errors; rate-limit 429).
12. Dockerfile (multi-stage, non-root), compose `app` profile.

## Done checklist
- [ ] End-to-end demo through the gateway only
- [ ] `docs/interview/M07.md` (Nest DI & request lifecycle, guards vs middleware vs interceptors, JWT vs sessions, RS256/JWKS rotation, rate limiting strategies; sovereign note: national SSO / Keycloak)
