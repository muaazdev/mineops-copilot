# M3 — LLM client abstraction, Ollama local, vLLM-ready

> **Scope change (2026-10-20):** all Colab/GPU work (task 5, benchmark parts of task 6, the Colab done-checklist item) is **deferred to M11**, after M10. In M3, do tasks 1–4, write `docs/gpu/vllm-notes.md` as a conceptual + config doc (no benchmark numbers yet), and add the `vllm` provider adapter tested against the fake server. Do not touch Colab.

**Goal:** a provider-agnostic, OpenAI-compatible client used by all later code; works locally with Ollama; `vllm` provider ready by config.

**Cost / approval gates:**
- Ollama local: free (CPU; warn about RAM and model download size).
- **Colab: ASK THE OWNER before every Colab step** (see `docs/gpu/colab-vllm.md`). Free tier first; paid Colab compute or GCP GPU only with explicit approval.
- Hosted API fallback: token-billed — ask before using.

**Owner is weaker in vLLM internals — go deep in comments and interview notes.**

## Tasks
1. `mineops_core.llm`: `LLMClient` (chat, stream, tool calls, JSON-mode/structured output), settings `MINEOPS_LLM_PROVIDER|BASE_URL|MODEL|API_KEY|TIMEOUT`, retries with jittered backoff, token usage capture, provider adapters for tool-call quirks.
2. Fake OpenAI-compatible server for tests (deterministic responses, tool-call fixtures).
3. Compose profile `llm` with Ollama; `make llm-pull` pulls the chosen small multilingual instruct model. Pin model at this milestone (Qwen-family default — verify current best small model with good Arabic + tool calling).
4. Smoke script `scripts/llm_smoke.py`: EN + AR prompt, one tool call, streaming, prints latency/tokens.
5. **vLLM notebook** `notebooks/vllm_colab.ipynb` (run via VS Code Colab extension, after approval):
   - install vLLM, serve same model family with OpenAI-compatible server inside the runtime
   - enable the correct tool-call parser for the model
   - call it with *our* `LLMClient` from inside the notebook
   - benchmark: throughput vs concurrency (1/4/16/64), TTFT, p95 latency; with/without prefix caching; record GPU type and memory
   - note GPU compatibility (verify the free GPU type is supported by current vLLM; if not, stop and report options + costs)
   - commit the executed notebook outputs (no secrets)
6. `docs/gpu/vllm-notes.md`: continuous batching, PagedAttention, KV-cache sizing math for the chosen model, `--max-model-len`, `--gpu-memory-utilization`, quantization options (AWQ/GPTQ/FP8) and their trade-offs, tensor parallelism — tied to the benchmark numbers.
7. K8s-ready config shape for vLLM (values only; manifests in M9).

## Done checklist
- [ ] Agents-to-be can switch provider via env only
- [ ] Ollama smoke passes locally; unit tests use the fake server
- [ ] Colab benchmark executed (if approved) and results in `docs/gpu/vllm-notes.md`
- [ ] `docs/interview/M03.md` (continuous batching, PagedAttention, KV cache math, quantization, OpenAI-compatible abstraction; sovereign note: air-gapped model registry/weights)
