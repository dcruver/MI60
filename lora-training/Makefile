# Makefile for Docker-based LoRA training workflow for AMD GPUs

# Default values
MODEL_NAME ?= Qwen/Qwen3-8B
DATASET_NAME ?= 
HF_REPO_ID ?= 
GGUF_REPO_ID ?= 
GGUF_QUANTIZATION ?= q4_k_m
GGUF_OUTPUT_NAME ?= 
HF_TOKEN ?= $(shell cat ~/.huggingface/token 2>/dev/null)
ROLE_PROMPT_FILE ?= /workspace/role_prompt.txt

# Docker run command with common options
DOCKER_RUN = docker run --rm -it --shm-size=8g --device=/dev/kfd --device=/dev/dri \
             --group-add video --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
             -v $(PWD):/workspace

.PHONY: build train merge convert push push-gguf all all-gguf shell clean help

# Show help by default
help:
	@echo "LoRA Training Workflow for AMD GPUs"
	@echo ""
	@echo "Usage:"
	@echo "  make [command] [options]"
	@echo ""
	@echo "Commands:"
	@echo "  build        Build the Docker image"
	@echo "  train        Train LoRA adapter (requires DATASET_NAME)"
	@echo "  merge        Merge LoRA with base model"
	@echo "  convert      Convert merged model to GGUF format"
	@echo "  push         Push merged model to HuggingFace (requires HF_REPO_ID and HF_TOKEN)"
	@echo "  push-gguf    Push GGUF model to HuggingFace (requires GGUF_REPO_ID and HF_TOKEN)"
	@echo "  all          Run complete pipeline (train, merge, push)"
	@echo "  all-gguf     Run complete pipeline with GGUF conversion"
	@echo "  shell        Start an interactive shell"
	@echo "  clean        Clean up directories"
	@echo ""
	@echo "Options (set as environment variables or make parameters):"
	@echo "  MODEL_NAME           Base model name (default: $(MODEL_NAME))"
	@echo "  DATASET_NAME         Training dataset name (required for training)"
	@echo "  HF_REPO_ID           HuggingFace repository ID for merged model"
	@echo "  GGUF_REPO_ID         HuggingFace repository ID for GGUF model"
	@echo "  GGUF_QUANTIZATION    GGUF quantization method (default: $(GGUF_QUANTIZATION))"
	@echo "  GGUF_OUTPUT_NAME     Custom filename for the GGUF model"
	@echo ""
	@echo "Example:"
	@echo "  make train DATASET_NAME=your/dataset MODEL_NAME=your/model"
	@echo "  make all-gguf DATASET_NAME=your/dataset HF_REPO_ID=your/repo GGUF_REPO_ID=your/gguf-repo"

# Check required parameters
check-dataset:
	@if [ -z "$(DATASET_NAME)" ]; then \
		echo "Error: DATASET_NAME is required"; \
		echo "Usage: make train DATASET_NAME=your/dataset"; \
		exit 1; \
	fi

check-hf-repo:
	@if [ -z "$(HF_REPO_ID)" ]; then \
		echo "Error: HF_REPO_ID is required"; \
		echo "Usage: make push HF_REPO_ID=your/repo"; \
		exit 1; \
	fi

check-gguf-repo:
	@if [ -z "$(GGUF_REPO_ID)" ]; then \
		echo "Error: GGUF_REPO_ID is required"; \
		echo "Usage: make push-gguf GGUF_REPO_ID=your/gguf-repo"; \
		exit 1; \
	fi

# Build the Docker image
build:
	docker build -t lora-rocm docker/.

# Train LoRA adapter
train: check-dataset
	$(DOCKER_RUN) -e MODEL_NAME=$(MODEL_NAME) -e DATASET_NAME=$(DATASET_NAME) \
	-e ROLE_PROMPT_FILE=$(ROLE_PROMPT_FILE) \
	lora-rocm train

# Merge LoRA with base model
merge:
	$(DOCKER_RUN) -e MODEL_NAME=$(MODEL_NAME) \
	lora-rocm merge

# Convert merged model to GGUF
convert:
	$(DOCKER_RUN) -e GGUF_QUANTIZATION=$(GGUF_QUANTIZATION) -e GGUF_OUTPUT_NAME="$(GGUF_OUTPUT_NAME)" \
	lora-rocm convert

# Push merged model to HuggingFace
push: check-hf-repo
	$(DOCKER_RUN) -e HF_REPO_ID=$(HF_REPO_ID) -e HF_TOKEN=$(HF_TOKEN) \
	lora-rocm push

# Push GGUF model to HuggingFace
push-gguf: check-gguf-repo
	$(DOCKER_RUN) -e GGUF_REPO_ID=$(GGUF_REPO_ID) -e HF_TOKEN=$(HF_TOKEN) \
	lora-rocm push-gguf

# Run complete pipeline (without GGUF)
all: check-dataset check-hf-repo
	$(DOCKER_RUN) -e MODEL_NAME=$(MODEL_NAME) -e DATASET_NAME=$(DATASET_NAME) \
	-e HF_REPO_ID=$(HF_REPO_ID) -e HF_TOKEN=$(HF_TOKEN) \
	lora-rocm all

# Run complete pipeline with GGUF conversion
all-gguf: check-dataset check-hf-repo check-gguf-repo
	$(DOCKER_RUN) -e MODEL_NAME=$(MODEL_NAME) -e DATASET_NAME=$(DATASET_NAME) \
	-e HF_REPO_ID=$(HF_REPO_ID) -e GGUF_REPO_ID=$(GGUF_REPO_ID) \
	-e GGUF_QUANTIZATION=$(GGUF_QUANTIZATION) -e GGUF_OUTPUT_NAME="$(GGUF_OUTPUT_NAME)" \
	-e HF_TOKEN=$(HF_TOKEN) \
	lora-rocm all-gguf

# Start interactive shell
shell:
	$(DOCKER_RUN) lora-rocm

# Clean up directories
clean:
	rm -rf lora-adapters lora-merged gguf-model
