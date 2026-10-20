# M11 — vLLM on Colab (deferred, optional)

**Status:** DEFERRED. Start only after M10 is DONE and the owner explicitly says go.

**Cost / approval gates:** ask before every Colab step. Free tier first; paid compute only with explicit approval and a stated budget. Follow `docs/gpu/colab-vllm.md` (no tunnels/proxies).

## Tasks
Carried over from M3:
1. `notebooks/vllm_colab.ipynb` run via the VS Code Colab extension: GPU compatibility check, install vLLM, serve the pinned model with the right tool-call parser, call it with `mineops_core.llm.LLMClient` (chat, stream, tool call, EN + AR).
2. Benchmarks: throughput vs concurrency (1/4/16/64), TTFT, p95 latency, prefix caching on/off; record GPU type, memory, flags.
3. Fill benchmark numbers into `docs/gpu/vllm-notes.md`; add KV-cache sizing math checked against observed memory.
4. Update README and `docs/interview/M03.md` with the measured numbers.

## Done checklist
- [ ] Executed notebook committed (no secrets)
- [ ] `docs/gpu/vllm-notes.md` has real numbers
- [ ] `docs/interview/M11.md`
