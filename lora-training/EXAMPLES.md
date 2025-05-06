# LoRA Training Examples

This guide provides step-by-step examples for training LoRA adapters on your AMD MI60 GPU. These examples demonstrate common use cases for the LoRA training workflow.

## Prerequisites

- AMD MI60 GPU with ROCm drivers installed (see [main README](../README.md))
- Docker installed on your system
- Hugging Face account (if you want to push models)

## Basic Training Example

This example demonstrates training a LoRA adapter for Qwen3-8B.

### 1. Build the Docker image

```bash
cd lora-training
make build
```

### 2. Train the LoRA adapter

```bash
make train DATASET_NAME=dcruver/keip-assistant-dataset
```

This command:
- Uses the dataset "dcruver/keip-assistant-dataset" from Hugging Face
- Uses the default model (Qwen/Qwen3-8B)
- Saves the LoRA adapter to `./lora-adapters`

### 3. Merge the LoRA adapter with the base model

```bash
make merge
```

This command:
- Takes the LoRA adapter from `./lora-adapters`
- Merges it with the base model
- Saves the merged model to `./lora-merged`

### 4. Convert the merged model to GGUF format

```bash
make convert GGUF_QUANTIZATION=q4_k_m
```

This command:
- Takes the merged model from `./lora-merged`
- Converts it to GGUF format with q4_k_m quantization
- Saves the GGUF model to `./gguf-model`

## Training with Custom Options
### Training with a Role Prompt

Role prompts are an important part of training an AI assistant. A role prompt defines the assistant's persona, capabilities, and constraints. It's injected at the beginning of each training example to provide consistent context.

#### What is a Role Prompt?

A role prompt typically includes:
- The assistant's identity and purpose
- The assistant's tone and communication style
- Specific skills or knowledge the assistant has
- Any limitations or guidelines the assistant should follow

#### Creating a Role Prompt

Create a file called `role_prompt.txt` with content like this:

```
You are an AI assistant specializing in Linux and system administration.
You provide clear, concise instructions with practical examples.
You excel at explaining complex technical concepts in simple terms.
When you don't know something, you acknowledge it rather than guessing.
You format command-line instructions as code blocks for clarity.
```

#### Training with the Role Prompt

```bash
# Mount the role prompt file into the Docker container
make train \
  DATASET_NAME=your/dataset \
  ROLE_PROMPT_FILE=/workspace/role_prompt.txt
```

#### How the Role Prompt Works

During training, the system prepends your role prompt to each conversation example:

```
You are an AI assistant specializing in Linux and system administration.
You provide clear, concise instructions with practical examples.
You excel at explaining complex technical concepts in simple terms.
When you don't know something, you acknowledge it rather than guessing.
You format command-line instructions as code blocks for clarity.

User: How do I check disk space on Linux?

### Training a Llama 3 model

```bash
make train \
  DATASET_NAME=mlabonne/guanaco-llama2-1k \
  MODEL_NAME=meta-llama/Llama-3-8B-hf \
  -- --max_length 512 --num_epochs 3 --batch_size 2
```

This command:
- Uses the Llama 3 8B model
- Increases the maximum sequence length to 512
- Sets the number of training epochs to 3
- Uses a batch size of 2

### Training with a Role Prompt

First, create a role prompt file:

```bash
echo "You are a helpful AI assistant that specializes in technical support for programming and system administration." > role_prompt.txt
```

Then train with the role prompt:

```bash
make train \
  DATASET_NAME=your/dataset \
  ROLE_PROMPT_FILE=/workspace/role_prompt.txt
```

## Complete Pipeline Example

This example demonstrates the full pipeline from training to pushing to Hugging Face.

```bash
# First set your HF_TOKEN or pass it directly
export HF_TOKEN=$(cat ~/.huggingface/token)

# Run the complete pipeline
make all-gguf \
  DATASET_NAME=mlabonne/guanaco-llama2-1k \
  MODEL_NAME=Qwen/Qwen3-8B \
  HF_REPO_ID=your-username/your-assistant \
  GGUF_REPO_ID=your-username/your-assistant-gguf \
  GGUF_OUTPUT_NAME=your-assistant
```

This command:
- Trains a LoRA adapter
- Merges it with the base model
- Converts it to GGUF format
- Pushes both the merged model and GGUF model to Hugging Face

## Using the GGUF Model with llama.cpp

After generating your GGUF model, you can run it using llama.cpp:

```bash
# Download llama.cpp if you don't have it
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
mkdir build && cd build
cmake .. -DLLAMA_HIPBLAS=ON
make -j

# Run your model
./bin/main -m /path/to/gguf-model/your-model.q4_k_m.gguf -n 512 -p "User: How do I install Python on Ubuntu?\n\nAssistant:"
```

## Troubleshooting Training

If you encounter out-of-memory errors during training:

1. Reduce the batch size:
   ```bash
   make train DATASET_NAME=your/dataset -- --batch_size 1
   ```

2. Reduce the sequence length:
   ```bash
   make train DATASET_NAME=your/dataset -- --max_length 128
   ```

3. Use a smaller model:
   ```bash
   make train DATASET_NAME=your/dataset MODEL_NAME=meta-llama/Llama-3-8B-instruct-hf
   ```

## Advanced Usage

### Custom Target Modules

Different models require different target modules for LoRA. Here are some common patterns:

- Llama/Mistral models: `--target_modules="q_proj,v_proj"`
- Gemma models: `--target_modules="q_proj,v_proj,k_proj,o_proj"`
- Phi models: `--target_modules="q_proj,v_proj,k_proj,attention.dense"`

Example:
```bash
make train \
  DATASET_NAME=your/dataset \
  MODEL_NAME=google/gemma-7b \
  -- --target_modules="q_proj,v_proj,k_proj,o_proj"
```

### Custom Quantization

Various GGUF quantization formats are supported:

```bash
# Higher quality, larger size
make convert GGUF_QUANTIZATION=q8_0

# Balanced option
make convert GGUF_QUANTIZATION=q5_k_m

# Smaller size, lower quality
make convert GGUF_QUANTIZATION=q4_0
```
