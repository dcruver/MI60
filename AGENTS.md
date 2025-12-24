# Repository Guidelines

## Project Structure & Module Organization

- `hardware-setup/`: Hardware notes, cooling tips, fan/service scripts; images in `images/`.
- `lora-training/`: Docker LoRA workflow; scripts in `docker/`, orchestration in `Makefile`, artifacts in `lora-adapters/`, `lora-merged/`, `gguf-model/`.
- `../configs/`: GPU configuration files (compose YAML) for different workloads.
- `../gpu-state-service.py`: Configuration switching and metrics service.

## vLLM Inference Runtime

Production inference uses vLLM with the `nalanzeyu/vllm-gfx906:v0.11.2-rocm6.3` image.

### Key Environment Variables

| Variable | Purpose |
|----------|---------|
| `HIP_VISIBLE_DEVICES=0,1` | Expose both MI60s to the container |
| `HSA_OVERRIDE_GFX_VERSION=9.0.6` | Force gfx906 architecture detection |

### Required Device Mappings

```yaml
devices:
  - /dev/kfd:/dev/kfd
  - /dev/dri/card1:/dev/dri/card1
  - /dev/dri/card2:/dev/dri/card2
  - /dev/dri/renderD128:/dev/dri/renderD128
  - /dev/dri/renderD129:/dev/dri/renderD129
group_add:
  - "44"   # video
  - "992"  # render
```

### Common vLLM Parameters

| Parameter | Typical Value | Notes |
|-----------|---------------|-------|
| `--tensor-parallel-size` | 2 | Split model across both GPUs |
| `--data-parallel-size` | 2 | Run separate instances per GPU |
| `--max-model-len` | 8192-32768 | Balance context vs memory |
| `--gpu-memory-utilization` | 0.7-0.9 | Higher for TP, lower for DP |
| `--quantization` | awq | Only if model requires explicit flag |

## GPU Configuration Management

### Configuration Files

Configs are stored in `../configs/` as compose YAML files:

- `big-chat.yaml` - Llama 3.3 70B with TP=2
- `coder.yaml` - Qwen3 32B with TP=2
- `dual-chat.yaml` - Two separate models
- `image-chat.yaml` - vLLM + ComfyUI

### Switching Configurations

```bash
# Via HTTP API
curl -X POST -H "Content-Type: application/json" \
  -d '{"config":"big-chat"}' \
  http://localhost:9100/switch

# Check status
curl http://localhost:9100/status
```

### gpu-state-service

The service (`../gpu-state-service.py`) manages:

- Configuration switching via HTTP API
- Prometheus metrics on port 9100
- Temperature monitoring with ntfy alerts
- vLLM health checks

States: `stopped` → `switching` → `loading` → `ready` (or `failed`)

## Metrics and Monitoring

### Prometheus Endpoints

| Port | Service | Metrics |
|------|---------|---------|
| 9100 | gpu-state-service | Config state, switches, uptime |
| 9101 | AMD GPU exporter | Temperature, utilization, power |
| 9102 | NVIDIA GPU exporter | RTX 2080 metrics |

### Key Metrics

```
gpu_config_info{config="...",model="..."} 1
gpu_state_info{state="ready|loading|..."} 1
gpu_ready 0|1
gpu_config_switches_total <counter>
amd_gpu_temperature_junction_celsius{gpu="0|1"}
amd_gpu_utilization_percent{gpu="0|1"}
```

### Temperature Alert Thresholds

| Temp | Level |
|------|-------|
| 97°C | Warning |
| 100°C | High |
| 105°C | Critical |
| 110°C | Emergency |

## Build, Test, and Development Commands

### LoRA Training

- `cd lora-training && make build`: Build the `lora-rocm` image.
- `make train DATASET_NAME=... MODEL_NAME=... [-- ...]`: Train LoRA (writes to `lora-adapters/`).
- `make merge MODEL_NAME=...`: Merge adapter into base model (writes to `lora-merged/`).
- `make convert GGUF_OUTPUT_NAME=... GGUF_QUANTIZATION=q4_k_m`: Export GGUF to `gguf-model/`.
- `make push HF_REPO_ID=... HF_TOKEN=...` / `make push-gguf GGUF_REPO_ID=...`: Publish merged or GGUF models.
- `make all-gguf ...`: Full pipeline; smoke-test on a small dataset first.

### GPU State Service

```bash
# Start the service
python3 ../gpu-state-service.py

# Test locally
curl http://localhost:9100/status
curl http://localhost:9100/metrics
```

## Embeddings Service

Each config includes an Infinity embeddings service:

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

Currently runs on CPU. GPU acceleration requires nvidia-container-toolkit for the RTX 2080.

## Cooling & Fan Control (Dual MI60)

**Critical for GPU longevity**: The MI60 is passive-cooled and will spike to 95-100°C under load without
proper cooling. The data-driven controller described here reduces junction temps from 96-97°C to 80°C,
significantly extending the operational life of these GPUs.

### Data-Driven Controller (Recommended)

Unlike reactive temperature-based control (which always plays catch-up), this controller is **preemptive**:
it ramps the fan based on GPU utilization before temperatures have time to rise.

**Key Features:**
- Installed at `/opt/gpu-fan-control/` via `install-ml-fan-control.sh`
- Uses a utilization→PWM curve learned from 300k+ historical samples
- Preemptive control: fan leads temperature changes instead of chasing them
- Adaptive polling: 0.5s at ≥90% util, 1s otherwise
- Linear interpolation for smooth fan response
- Temperature monitoring as safety backstop

**Results:**
- Junction temps: **80°C max** (was 96-97°C with reactive control)
- Fan behavior: Smooth curves, maxes at ~88% instead of spiking to 100%

**Tunables** in `ml-fan-control.py`:
- `TARGET_TEMP` (82°C): Desired operating temperature
- `MAX_TEMP` (92°C): Emergency threshold
- `UTIL_PWM_POINTS`: The learned curve (rebuild with `train_pwm_curve.py`)

### Simple Bash Script (Fallback)
- Source in `hardware-setup/scripts/mi60-fan.sh`, auto-detects `nct6798`
- Basic utilization-based control without Python dependencies
- Use if Python isn't available; expect higher temps

### General Notes
- Logs to `/var/log/gpu-fan-control.csv` (CSV format for curve analysis)
- Rebuild curve after collecting your own data: `train_pwm_curve.py`
- Dual-duct STL: `https://www.thingiverse.com/thing:7203670`
- Dual-duct photos: `hardware-setup/images/MI60-dual-fan-housing{1,2,3}.jpg`

## Coding Style & Naming Conventions

- Python (`docker/*.py`, `gpu-state-service.py`): PEP8, 4-space indents, snake_case functions/vars, UpperCamelCase classes; prefer explicit CLI args and type hints.
- Shell scripts: Bash with `set -euo pipefail`, 2-space indents, lowercase function names; keep hardware paths configurable.
- YAML configs: 2-space indents, descriptive comments at top explaining use case.

## Testing Guidelines

- No automated suite; run the smallest relevant `make` target and confirm outputs land correctly.
- For config switches, verify via `/status` endpoint and check `nerdctl ps` for expected containers.
- For cooling changes, monitor `rocm-smi --showtemp --showuse` plus fan logs to ensure both GPUs are handled.
- Verify Prometheus metrics appear in Grafana after changes.

## Commit & Pull Request Guidelines

- Commit messages: single-line, present-tense summaries.
- PRs: describe scope, commands run, resulting artifacts/metrics, and any cooling/duct changes. Link issues; include before/after notes when behavior or hardware steps change.
- Do not commit secrets (HF tokens, ntfy URLs) or large model artifacts; keep generated outputs in `lora-adapters/`, `lora-merged/`, and `gguf-model/` out of version control.
