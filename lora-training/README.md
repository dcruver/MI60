# LoRA Training for AMD GPUs

A Docker-based workflow for training LoRA adapters for language models on AMD GPUs. This project was originally designed
for the MI60 GPU but works with other AMD GPUs that support ROCm.

## Features

- Train LoRA adapters for any Hugging Face model
- Support for AMD GPUs via ROCm
- Merge LoRA adapters with base models
- Convert models to GGUF format for efficient inference
- Push models to Hugging Face repositories

## Project Structure

```
.
├── docker/                  # Docker container files
│   ├── convert_to_gguf.py   # Script for converting models to GGUF format
│   ├── Dockerfile           # Docker configuration
│   ├── entrypoint.sh        # Docker entrypoint script
│   ├── merge_lora.py        # Script for merging LoRA adapters with base models
│   ├── push_to_hf.py        # Script for pushing models to Hugging Face
│   ├── requirements.txt     # Python dependencies
│   └── train_lora.py        # Main script for training LoRA adapters
├── lora-adapters/           # Output directory for trained LoRA adapters
├── lora-merged/             # Output directory for merged models
├── gguf-model/              # Output directory for GGUF models
└── Makefile                 # Make targets for running the workflow
```

## Setup Instructions

1. Rename the original `train_keip_assistant.py` to `train_lora.py`:
   ```bash
   mv docker/train_keip_assistant.py docker/train_lora.py
   ```

2. Update the script with the generalized code provided in this repository.

3. Update the `entrypoint.sh` script to reference the new `train_lora.py` instead of `train_keip_assistant.py`.

4. Build the Docker image:
   ```bash
   make build
   ```

## Usage

### Training a LoRA Adapter

```bash
make train DATASET_NAME=your/dataset MODEL_NAME=your/model
```

Requirements for the dataset:
- Must be a Hugging Face dataset
- Must have `prompt` and `response` columns (or columns that can be mapped to these)

### Using a Role Prompt

1. Create a role prompt file:
   ```bash
   echo "You are an AI assistant that..." > role_prompt.txt
   ```

2. Train with the role prompt:
   ```bash
   make train DATASET_NAME=your/dataset ROLE_PROMPT_FILE=/workspace/role_prompt.txt
   ```

### Merging the LoRA Adapter

```bash
make merge MODEL_NAME=your/model
```

### Converting to GGUF Format

```bash
make convert GGUF_QUANTIZATION=q4_k_m GGUF_OUTPUT_NAME=your-model-name
```

### Pushing to Hugging Face

```bash
make push HF_REPO_ID=your-username/your-model HF_TOKEN=hf_xxxxx
```

### Running the Complete Pipeline

```bash
make all-gguf \
  DATASET_NAME=your/dataset \
  MODEL_NAME=your/model \
  HF_REPO_ID=your-username/your-model \
  GGUF_REPO_ID=your-username/your-model-gguf \
  GGUF_OUTPUT_NAME=your-model-name
```

## Command-Line Options

Additional options can be passed directly to the scripts:

```bash
make train DATASET_NAME=your/dataset -- --max_length 384 --batch_size 2 --num_epochs 5
```

Available options for `train_lora.py`:
- `--max_length`: Maximum sequence length (default: 256)
- `--batch_size`: Batch size (default: 4)
- `--num_epochs`: Number of training epochs (default: 10)
- `--learning_rate`: Learning rate (default: 2e-5)
- `--lora_r`: LoRA rank parameter (default: 8)
- `--lora_alpha`: LoRA alpha parameter (default: 32)
- `--target_modules`: Target modules for LoRA (default: "q_proj,v_proj")

## License

MIT License
