# Repository Guidelines

## Project Structure & Module Organization
- `hardware-setup/`: Hardware notes, cooling tips, fan/service scripts; images in `images/`.
- `lora-training/`: Docker LoRA workflow; scripts in `docker/`, orchestration in `Makefile`, artifacts in `lora-adapters/`, `lora-merged/`, `gguf-model/`.
- Ollama inference uses the ROCm compose at `../ollama-rocm/docker-compose.yaml`; no local Dockerfile.

## Build, Test, and Development Commands
- `cd lora-training && make build`: Build the `lora-rocm` image.
- `make train DATASET_NAME=... MODEL_NAME=... [-- ...]`: Train LoRA (writes to `lora-adapters/`).
- `make merge MODEL_NAME=...`: Merge adapter into base model (writes to `lora-merged/`).
- `make convert GGUF_OUTPUT_NAME=... GGUF_QUANTIZATION=q4_k_m`: Export GGUF to `gguf-model/`.
- `make push HF_REPO_ID=... HF_TOKEN=...` / `make push-gguf GGUF_REPO_ID=...`: Publish merged or GGUF models.
- `make all-gguf ...`: Full pipeline; smoke-test on a small dataset first.

## Ollama ROCm Runtime
- Compose: `../ollama-rocm/docker-compose.yaml` with `ollama/ollama:0.12.3-rocm`. Key env: `ROCR_VISIBLE_DEVICES=0,1`, `HIP_VISIBLE_DEVICES=0,1`, `HSA_OVERRIDE_GFX_VERSION=9.0.6`, `OLLAMA_ROCM=1`.
- Volume `/mnt/cache/ollama` → `/root/.ollama`; port `11434:11434`. If GPU count changes, update device lists and ensure `/dev/kfd` + `/dev/dri` are mapped.

## Cooling & Fan Control (Dual MI60)
- `/opt/gpu-fan-control.sh` auto-detects `nct6798`, reads both GPU temps/utils via `rocm-smi`, and drives `pwm3` in manual mode.
- Tunables: `MIN_PWM=100`, `MAX_PWM=255`, `MIN_TEMP=30`, `MAX_TEMP=80`, `UTIL_THRESH=80`, `BOOST_PWM=200`. Adjust for new ducts or fans; logs show live temps/utils/PWM.
- Keep hwmon discovery dynamic; change `PWM_PATH` only if the controller differs.
- Maintain single- and dual-GPU docs: keep single-GPU notes in `hardware-setup/`; cross-link dual duct instructions and the STL (`https://www.thingiverse.com/thing:7203670`) from both. Dual-duct photos: `hardware-setup/images/MI60-dual-fan-housing{1,2,3}.jpg`.

## Coding Style & Naming Conventions
- Python (`docker/*.py`): PEP8, 4-space indents, snake_case functions/vars, UpperCamelCase classes; prefer explicit CLI args and type hints.
- Shell scripts: Bash with `set -euo pipefail`, 2-space indents, lowercase function names; keep hardware paths configurable.
- Make targets: lowercase names; environment inputs stay uppercase (`DATASET_NAME`, `HF_REPO_ID`, `GGUF_*`).

## Testing Guidelines
- No automated suite; run the smallest relevant `make` target and confirm outputs land correctly.
- For conversions/pushes, dry-run with disposable models; capture output when behavior changes (throughput, VRAM use, GPU detection).
- For cooling changes, monitor `rocm-smi --showtemp --showuse` plus fan logs to ensure both GPUs are handled.

## Commit & Pull Request Guidelines
- Commit messages: single-line, present-tense summaries.
- PRs: describe scope, commands run, resulting artifacts/metrics, and any cooling/duct changes. Link issues; include before/after notes when behavior or hardware steps change.
- Do not commit secrets (HF tokens) or large model artifacts; keep generated outputs in `lora-adapters/`, `lora-merged/`, and `gguf-model/` out of version control.
