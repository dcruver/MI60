# ComfyUI on MI60

Node-based Stable Diffusion UI with AMD MI60 GPU acceleration via ROCm.

## Overview

ComfyUI runs as a containerized service using a custom ROCm 5.7 image built for the MI60's gfx906 architecture. It can run standalone on both GPUs or alongside vLLM in the `image-chat` configuration.

## Quick Start

```bash
# Build the container image
cd ../comfyui
make build

# Start ComfyUI (standalone, both GPUs)
make up

# Or use the image-chat config (vLLM on GPU0, ComfyUI on GPU1)
curl -X POST -H "Content-Type: application/json" \
  -d '{"config":"image-chat"}' http://localhost:9100/switch
```

Access the UI at http://localhost:8188 (or 8189/8190 for dual-instance setup).

## Container Configuration

The `image-chat` configuration runs ComfyUI on GPU1 alongside vLLM on GPU0:

```yaml
comfyui:
  image: comfyui-rocm57:latest
  container_name: comfyui
  ports:
    - "8188:8188"
  devices:
    - /dev/kfd:/dev/kfd
    - /dev/dri/card2:/dev/dri/card2
    - /dev/dri/renderD129:/dev/dri/renderD129
  group_add:
    - "44"   # video
    - "992"  # render
  security_opt:
    - seccomp=unconfined
    - apparmor=unconfined
  cap_add:
    - SYS_PTRACE
  volumes:
    - /mnt/cache/comfyui/ComfyUI:/app/ComfyUI
  environment:
    - HSA_OVERRIDE_GFX_VERSION=9.0.6
    - HSA_ENABLE_SDMA=0
    - ROC_ENABLE_PRE_VEGA=1
    - HCC_AMDGPU_TARGET=gfx906
    - ROCR_VISIBLE_DEVICES=0
    - HIP_VISIBLE_DEVICES=0
  command: ["python3", "main.py", "--listen", "--fp8_e4m3fn-unet", "--fast"]
```

### Key Environment Variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `HSA_OVERRIDE_GFX_VERSION` | 9.0.6 | Force gfx906 architecture detection |
| `HSA_ENABLE_SDMA` | 0 | Disable SDMA (stability fix) |
| `ROC_ENABLE_PRE_VEGA` | 1 | Enable pre-Vega compatibility |
| `HCC_AMDGPU_TARGET` | gfx906 | Target architecture for HIP |
| `ROCR_VISIBLE_DEVICES` | 0 | Limit to single GPU in container |
| `HIP_VISIBLE_DEVICES` | 0 | Limit to single GPU in container |

### Command Line Options

| Option | Purpose |
|--------|---------|
| `--listen` | Accept connections from any host |
| `--fp8_e4m3fn-unet` | Enable FP8 for UNet (faster, less VRAM) |
| `--fast` | Enable fast mode optimizations |

## Building the Image

The Dockerfile is based on `rocm/dev-ubuntu-22.04:5.7` and includes:

- Python 3.11
- PyTorch 2.3.1 with ROCm 5.7 support
- ComfyUI dependencies
- Common custom node dependencies (opencv, insightface, ultralytics, etc.)

```bash
cd ../comfyui
make build  # Creates comfyui-rocm57:latest
```

## Storage Layout

All data is stored on the host and mounted into containers:

```
/mnt/cache/comfyui/ComfyUI/
├── models/
│   ├── checkpoints/      # SD models (.safetensors)
│   ├── loras/            # LoRA adapters
│   ├── vae/              # VAE models
│   ├── controlnet/       # ControlNet models
│   └── upscale_models/   # Upscaler models
├── output/               # Generated images
├── input/                # Input images for img2img
└── custom_nodes/         # Installed extensions
```

## Installing Models

Download models to the checkpoints directory:

```bash
cd /mnt/cache/comfyui/ComfyUI/models/checkpoints

# Example: SDXL base
wget https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors

# Example: SD 1.5
wget https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned.safetensors
```

## Installing Custom Nodes

Clone custom nodes into the custom_nodes directory:

```bash
cd /mnt/cache/comfyui/ComfyUI/custom_nodes

# ComfyUI Manager (recommended - enables in-UI node installation)
git clone https://github.com/ltdrdata/ComfyUI-Manager.git

# Restart ComfyUI to load new nodes
```

## GPU Device Mapping

The MI60s appear as card1/card2 (card0 is the NVIDIA GPU):

| Device | PCI Address | GPU |
|--------|-------------|-----|
| card1, renderD128 | 06:00.0 | MI60 #0 |
| card2, renderD129 | 10:00.0 | MI60 #1 |
| card3, renderD130 | 0d:00.0 | RTX 2080 (unused) |

Identify your mapping:
```bash
ls -la /dev/dri/by-path/
rocm-smi
```

## Troubleshooting

### "No HIP GPUs are available"

1. **Don't rename devices**: Mount as-is (`card2:/dev/dri/card2`, not `card2:/dev/dri/card0`)
2. **Mount both devices**: Need card AND renderD for each GPU
3. **Set ROCR_VISIBLE_DEVICES=0**: When container sees only one GPU

### Out of Memory

- Each MI60 has 32GB VRAM
- SDXL uses ~6-8GB, SD 1.5 uses ~4GB
- Reduce batch size or image dimensions
- Use `--fp8_e4m3fn-unet` for reduced memory

### Slow Generation

- Verify GPU usage: `rocm-smi` during generation
- Ensure HSA_OVERRIDE_GFX_VERSION=9.0.6 is set
- Use `--fast` flag

### Check Container Logs

```bash
sudo nerdctl logs comfyui
```

## Dual-Instance Setup

For running two independent ComfyUI instances (one per GPU), see the full documentation in [../comfyui/README.md](../comfyui/README.md).

## Resources

- [ComfyUI GitHub](https://github.com/comfyanonymous/ComfyUI)
- [ComfyUI Examples](https://comfyanonymous.github.io/ComfyUI_examples/)
- [Model Repository](https://huggingface.co/models?pipeline_tag=text-to-image)
