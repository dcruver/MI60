# GPU Configuration Management

Rather than running a single fixed configuration, we dynamically switch between GPU configurations based on workload needs.

## Available Configurations

| Config | Model | Use Case |
|--------|-------|----------|
| `big-chat` | Llama 3.3 70B (TP=2) | Maximum quality chat |
| `coder` | Qwen3 32B (TP=2) | Coding tasks with thinking mode |
| `dual-chat` | Qwen3 8B + 14B | Two models, different tasks |
| `image-chat` | Qwen 7B + ComfyUI | Text + image generation |

Configuration files are stored in `../configs/` as compose YAML files.

## Configuration Switching

The `gpu-state-service.py` manages configuration switching via HTTP API:

```bash
# Check current state
curl http://localhost:9100/status

# Switch to a different configuration
curl -X POST -H "Content-Type: application/json" \
  -d '{"config":"big-chat"}' \
  http://localhost:9100/switch
```

### Switch Process

1. **Drain** - Wait for in-flight requests to complete
2. **Stop** - Tear down current containers
3. **Start** - Launch new configuration via nerdctl compose
4. **Ready** - Wait for vLLM health check to pass

## State Machine

```
         ┌─────────┐
         │ stopped │
         └────┬────┘
              │ switch
              ▼
         ┌─────────┐
         │switching│
         └────┬────┘
              │ containers started
              ▼
         ┌─────────┐
         │ loading │──────┐
         └────┬────┘      │ timeout/error
              │ health ok │
              ▼           ▼
         ┌─────────┐  ┌──────┐
         │  ready  │  │failed│
         └────┬────┘  └──────┘
              │ drain
              ▼
         ┌─────────┐
         │draining │
         └────┬────┘
              │ requests complete
              ▼
         ┌─────────┐
         │switching│
         └─────────┘
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Current status (JSON) |
| GET | `/status` | Current status (JSON) |
| GET | `/metrics` | Prometheus metrics |
| POST | `/drain` | Begin draining requests |
| POST | `/switch` | Switch configuration (requires `{"config": "name"}`) |
| POST | `/stop` | Stop all GPU services |

## Creating New Configurations

1. Create a new YAML file in `../configs/`:

```yaml
# Configuration: My Custom Config
# Use case: Description of what this is for

services:
  vllm:
    image: nalanzeyu/vllm-gfx906:v0.11.2-rocm6.3
    container_name: vllm
    # ... device mappings, environment, command

  embeddings:
    image: michaelf34/infinity:latest
    # ... embeddings config
```

2. The configuration will be automatically available via the switch API.

3. Test with: `curl -X POST -d '{"config":"my-config"}' http://localhost:9100/switch`
