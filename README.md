# AMD MI60 GPU - Tools and Utilities

Scripts and resources for running AI workloads on AMD Instinct MI60 GPUs.

## Documentation

**Full documentation is available at [cruver.ai/gpu-ai/](https://cruver.ai/gpu-ai/)**

- [Hardware Setup & Cooling](https://cruver.ai/gpu-ai/posts/mi60-hardware-setup/) - BIOS settings, fan control, 3D-printed shrouds
- [vLLM Inference](https://cruver.ai/gpu-ai/posts/vllm-inference-mi60/) - Tensor parallelism, AWQ quantization, 70B models
- [ComfyUI Setup](https://cruver.ai/gpu-ai/posts/comfyui-mi60/) - Stable Diffusion with ROCm
- [Configuration Management](https://cruver.ai/gpu-ai/posts/gpu-config-management/) - Dynamic switching between workloads
- [Metrics & Monitoring](https://cruver.ai/gpu-ai/posts/gpu-metrics-monitoring/) - Prometheus, Grafana, temperature alerts

## 3D Printable Fan Shrouds

- **Single GPU:** [Thingiverse](https://www.thingiverse.com/thing:6636428)
- **Dual GPU:** [Thingiverse](https://www.thingiverse.com/thing:7203670)

## Repository Contents

### `/hardware-setup/scripts/`
Fan control scripts for temperature management:
- `ml-fan-control.py` - Data-driven fan controller with learned utilization→PWM curve
- `mi60-fan.sh` - Simple bash fallback
- `install-ml-fan-control.sh` - Systemd service installation
- `benchmark_ollama.sh` - Token generation benchmarking

### `/hardware-setup/images/`
Photos of fan housing setups.

### `/lora-training/`
Docker-based workflow for training LoRA adapters.

## Hardware Specs

| Spec | Value |
|------|-------|
| Memory | 32GB HBM2 per GPU |
| Architecture | gfx906 (Vega 20) |
| TDP | 300W |
| Interface | PCIe Gen3 |

## License

MIT License
