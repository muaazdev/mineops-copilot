# vLLM on Google Colab via VS Code — plan and rules

The owner has no local GPU. vLLM is exercised on a Colab GPU runtime, opened from VS Code with Google's official Colab extension.

## Approval rule
**Ask the owner before every Colab step** (connecting a runtime, installing vLLM, downloading weights, running benchmarks). Free tier first. Paid Colab compute units or a GCP GPU VM require an explicit "yes" with a stated budget.

## What we do on Colab (allowed: interactive compute)
- Install vLLM in the runtime, start its OpenAI-compatible server **inside the runtime** (localhost only).
- From the same notebook, call it with our `mineops_core.llm.LLMClient` to prove provider parity (chat, streaming, tool calls, EN + AR).
- Benchmark throughput/latency vs concurrency, prefix caching on/off, and record GPU type + memory.
- Commit the executed notebook (`notebooks/vllm_colab.ipynb`) and results in `docs/gpu/vllm-notes.md`.

## What we do NOT do
- Do not expose the Colab runtime to the local stack via ngrok/cloudflared/other tunnels or proxies. Colab's FAQ disallows web-service offerings unrelated to interactive compute and connecting to remote proxies, and the free tier also disallows remote control (SSH/remote desktop) and bypassing the notebook UI. The local stack therefore runs on Ollama; vLLM parity is demonstrated in-notebook.

## Compatibility check (do first, before benchmarking)
- Record `nvidia-smi` GPU type. Verify the installed vLLM version supports that GPU's compute capability and the dtype used (older GPUs may need `--dtype half`, no bf16).
- If unsupported: stop and report options to the owner (different model/dtype, Colab paid GPU tier, or a short-lived GCP L4 VM) with costs.

## Settings to record
model + revision, vLLM version, `--max-model-len`, `--gpu-memory-utilization`, `--enable-prefix-caching`, tool-call parser flag, dtype/quantization.
