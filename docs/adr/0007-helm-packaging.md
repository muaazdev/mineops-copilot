# ADR-0007: Helm for Kubernetes packaging

- Status: Accepted
- Date: 2026-10-20

## Context
Need to deploy the same stack to kind (local) and GKE with environment-specific values.

## Decision
One umbrella chart (`deploy/helm/mineops`) with subcharts or templates per service; `values-kind.yaml` and `values-gke.yaml`. Stateful dependencies (Postgres, OpenSearch, Qdrant) use their upstream charts as dependencies on kind, and are documented as managed/external options for GKE.

## Alternatives considered
- Kustomize — simpler, no templating, but weaker for parameterized multi-env installs and less common in JDs.
- Raw manifests — no environment parameterization.

## Consequences
- Templating complexity; mitigate with `helm lint`, `helm template` + kubeconform in CI.

## Revisit when
Moving to GitOps where Kustomize overlays fit the platform better.
