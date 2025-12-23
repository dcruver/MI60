# lora-merged - GGUF

This is a GGUF version of the lora-merged model.

## Model Details

- **Base Model:** /workspace/lora-merged
- **Format:** GGUF 
- **Quantization:** q4_k_m

## Usage

This model can be used with [llama.cpp](https://github.com/ggerganov/llama.cpp) and compatible applications.

```bash
# Example llama.cpp command
./main -m keip-assistant.q4_k_m.gguf -n 1024 -p "Your prompt here"
```
