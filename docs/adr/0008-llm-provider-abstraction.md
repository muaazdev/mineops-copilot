# ADR-0008: OpenAI-compatible LLM client with pluggable providers

- Status: Accepted
- Date: 2026-10-20

## Context
The JD requires vLLM. The owner has no local GPU. Development must work on CPU.

## Decision
All model calls go through one client in `mineops-core` that speaks the OpenAI Chat Completions API. Provider chosen by `MINEOPS_LLM_PROVIDER` (`vllm` | `ollama` | `hosted`) with `BASE_URL`, `MODEL`, `API_KEY`. Provider-specific quirks (tool-call parsing, max context) are isolated in small adapters. Local default is Ollama on CPU. vLLM is exercised on a Colab GPU (owner approval required each time) and in K8s manifests for a GPU node pool.

## Alternatives considered
- LangChain model classes per provider directly in agents — leaks provider choice into agent code.
- LiteLLM proxy — good option, but adds a service; the abstraction we need is thin.

## Consequences
- Agents are provider-agnostic; tests use a fake OpenAI-compatible server.
- Must verify tool-calling behavior per provider (vLLM needs a tool-call parser flag for the chosen model).

## Revisit when
Multiple teams/models need central routing, budgets, and keys → introduce a gateway like LiteLLM.
