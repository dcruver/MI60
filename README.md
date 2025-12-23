# AMD MI60 GPU - Tools and Utilities

Tools, guides, and workflows for the AMD Instinct MI60 GPU for AI training and inference workloads.

## Contents

### [Hardware Setup](./hardware-setup/README.md)
Driver installation, system requirements, troubleshooting, and cooling guides for single- and dual-GPU setups. Includes a [dual-duct STL](https://www.thingiverse.com/thing:7203670).

### [LoRA Training](./lora-training/README.md)
Docker-based workflow for training LoRA adapters, merging with base models, and converting to GGUF format.

### [vLLM Inference](./vllm-inference.md)
Production inference using vLLM with tensor parallelism. Covers why vLLM, ROCm compatibility, AWQ quantization, and the big-chat configuration example.

### [Configuration Management](./configuration-management.md)
Dynamic switching between GPU configurations (big-chat, coder, etc.) via HTTP API. Includes state machine and API reference.

### [Metrics and Monitoring](./metrics-monitoring.md)
Prometheus metrics, temperature alerts, and Grafana dashboard setup for GPU health monitoring.

## Hardware Specifications

| Spec | Value |
|------|-------|
| Memory | 32GB HBM2 per GPU (64GB total with dual) |
| FP64 | 7.4 TFLOPS |
| FP32 | 10.6 TFLOPS |
| Interface | PCIe Gen4 |
| Architecture | gfx906 (Vega 20) |

## Quick Start

1. Set up hardware per [Hardware Setup](./hardware-setup/README.md)
2. Install ROCm 6.x and verify with `rocm-smi`
3. Start the gpu-state-service: `python3 gpu-state-service.py`
4. Switch to a configuration:
   ```bash
   curl -X POST -H "Content-Type: application/json" \
     -d '{"config":"big-chat"}' http://localhost:9100/switch
   ```
5. Query the model at `http://localhost:8000` (OpenAI-compatible API)

## System Requirements

- Linux (Ubuntu 22.04/24.04 recommended)
- ROCm 6.x
- 300W power per GPU
- Adequate cooling ([see hardware-setup](./hardware-setup/README.md))
- 32GB+ system RAM (64GB+ for dual-GPU)
- containerd with nerdctl

## License

MIT License - see LICENSE file.
