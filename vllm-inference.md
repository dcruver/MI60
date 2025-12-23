# vLLM Inference on MI60

Production inference using vLLM with tensor parallelism across dual MI60 GPUs.

## Why vLLM?

After evaluating Ollama, llama.cpp, and vLLM for MI60 inference, **vLLM** emerged as the best choice for several reasons:

1. **Tensor Parallelism**: vLLM natively supports splitting large models across multiple GPUs. With dual MI60s (64GB total), we can run 70B parameter models that wouldn't fit on a single GPU.

2. **PagedAttention**: vLLM's memory management is more efficient than alternatives, allowing higher GPU memory utilization (we run at 90%) without OOM errors.

3. **OpenAI-Compatible API**: Drop-in replacement for OpenAI API, making integration with existing tools seamless.

4. **AWQ Quantization Support**: Native support for AWQ (Activation-Aware Weight Quantization), providing 4-bit inference with minimal quality loss.

5. **Production-Ready**: Continuous batching, request scheduling, and proper health endpoints for production deployments.

## ROCm Compatibility

The MI60 uses the `gfx906` architecture, which requires a specialized vLLM build. We use the community image `nalanzeyu/vllm-gfx906:v0.11.2-rocm6.3` which includes the necessary ROCm 6.3 support and gfx906-specific optimizations.

## Example: big-chat Configuration

The `big-chat` configuration runs Llama 3.3 70B across both MI60 GPUs using tensor parallelism:

```yaml
services:
  vllm:
    image: nalanzeyu/vllm-gfx906:v0.11.2-rocm6.3
    container_name: vllm
    devices:
      - /dev/kfd:/dev/kfd
      - /dev/dri/card1:/dev/dri/card1
      - /dev/dri/card2:/dev/dri/card2
      - /dev/dri/renderD128:/dev/dri/renderD128
      - /dev/dri/renderD129:/dev/dri/renderD129
    group_add:
      - "44"   # video group
      - "992"  # render group
    shm_size: 16g
    environment:
      - HIP_VISIBLE_DEVICES=0,1
    command:
      - python
      - -m
      - vllm.entrypoints.openai.api_server
      - --model
      - casperhansen/llama-3.3-70b-instruct-awq
      - --tensor-parallel-size
      - "2"
      - --max-model-len
      - "32768"
      - --gpu-memory-utilization
      - "0.9"
```

### Configuration Choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `tensor-parallel-size` | 2 | Split model across both GPUs |
| `max-model-len` | 32768 | Balance context length with memory |
| `gpu-memory-utilization` | 0.9 | Leave 10% headroom for KV cache growth |
| Model | llama-3.3-70b-instruct-awq | AWQ 4-bit quantization fits in 64GB |

## AWQ Quantization

We use AWQ (Activation-Aware Weight Quantization) models because:

- **4-bit weights** reduce memory footprint by ~4x vs FP16
- **Minimal quality loss** compared to GPTQ or naive quantization
- **Native vLLM support** with optimized CUDA/HIP kernels
- **Tensor parallel compatible** when model dimensions align (divisible by group_size × TP)

**Note**: Not all AWQ models support tensor parallelism. The model's hidden dimensions must be divisible by `(group_size × tensor_parallel_size)`. Llama models work well; some MoE models don't.

## Embeddings Service

Each configuration includes an embeddings service using [Infinity](https://github.com/michaelfeil/infinity):

```yaml
embeddings:
  image: michaelf34/infinity:latest
  container_name: infinity-embeddings
  ports:
    - "8080:7997"
  command:
    - v2
    - --model-id
    - nomic-ai/nomic-embed-text-v1.5
    - --device
    - cpu
```

This provides OpenAI-compatible embeddings at `http://localhost:8080` for RAG and semantic search workloads.
