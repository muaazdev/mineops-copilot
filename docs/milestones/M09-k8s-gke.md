# M9 — Helm + kind, GKE deployment docs

**Goal:** `make kind-up && make helm-install` brings the stack up on a local kind cluster; a GKE guide exists with cost warnings and teardown.

**Cost / approval gates:** kind is free. **Any GKE / GCP action requires explicit owner approval** — this milestone defaults to docs-only for GKE. If the owner wants a live GKE run: present a cost estimate (check current pricing at that time), a time box, and the teardown commands first.

**Owner is weaker in GCP/GKE — explain choices (Autopilot vs Standard, Workload Identity, node pools, ingress options) in the docs.**

## Tasks
1. Umbrella Helm chart `deploy/helm/mineops`: deployments for gateway, agent-service, mcp-server (+ optional vLLM GPU deployment, disabled by default); Services; Ingress (gateway only); ConfigMaps; Secrets (templated refs, never values); HPA for gateway/agent-service; PodDisruptionBudgets; probes; resource requests/limits; securityContext (non-root, readOnlyRootFilesystem, drop caps); NetworkPolicies (only agent-service → mcp-server, only mcp-server/agent-service/gateway → postgres, etc.); migration Job (Helm hook).
2. Dependencies for kind: Postgres, OpenSearch, Qdrant via upstream charts (pin), Ollama as a simple deployment.
3. `values-kind.yaml`, `values-gke.yaml`.
4. CI: `helm lint`, `helm template | kubeconform`.
5. `deploy/gcp/README.md`: Artifact Registry, GKE (Autopilot vs Standard trade-off), Workload Identity, GCP Secret Manager via Secret Manager CSI driver / External Secrets, Cloud SQL option, managed OpenSearch/Qdrant alternatives, GPU node pool for vLLM (L4) with taints/tolerations, ingress + TLS, budgets/alerts, **teardown script**.
6. `scripts/kind-demo.sh` end-to-end smoke on kind.

## Done checklist
- [ ] Stack healthy on kind; smoke passes
- [ ] GKE guide reviewed by owner
- [ ] `docs/interview/M09.md` (Helm vs Kustomize, probes, HPA for LLM workloads, GPU scheduling, Workload Identity, secrets in K8s; sovereign note: on-prem K8s / OpenShift, air-gapped registries, no managed cloud)
