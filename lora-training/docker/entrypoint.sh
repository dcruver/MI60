#!/bin/bash
# entrypoint.sh - Docker container entrypoint for LoRA training workflow

set -e

# Default values
MODEL_NAME=${MODEL_NAME:-"Qwen/Qwen3-8B"}
DATASET_NAME=${DATASET_NAME:-""}
ROLE_PROMPT_FILE=${ROLE_PROMPT_FILE:-""}
LORA_DIR=${LORA_DIR:-"/workspace/lora-adapters"}
MERGED_DIR=${MERGED_DIR:-"/workspace/lora-merged"}
GGUF_DIR=${GGUF_DIR:-"/workspace/gguf-model"}
GGUF_QUANTIZATION=${GGUF_QUANTIZATION:-"q4_k_m"}
GGUF_OUTPUT_NAME=${GGUF_OUTPUT_NAME:-""}
HF_REPO_ID=${HF_REPO_ID:-""}
GGUF_REPO_ID=${GGUF_REPO_ID:-""}
HF_TOKEN=${HF_TOKEN:-""}

# Help message
show_help() {
  echo "Usage: $0 [command]"
  echo "Commands:"
  echo "  train       - Train LoRA adapter"
  echo "  merge       - Merge LoRA with base model"
  echo "  convert     - Convert merged model to GGUF format"
  echo "  push        - Push merged model to HuggingFace"
  echo "  push-gguf   - Push GGUF model to HuggingFace"
  echo "  all         - Run all steps in sequence (train, merge, push)"
  echo "  all-gguf    - Run all steps including GGUF conversion (train, merge, convert, push, push-gguf)"
  echo "  shell       - Start an interactive shell"
  echo "  help        - Show this help message"
  echo ""
  echo "Environment variables:"
  echo "  MODEL_NAME      - Base model name (default: ${MODEL_NAME})"
  echo "  DATASET_NAME    - Training dataset name (required)"
  echo "  ROLE_PROMPT_FILE - Path to role prompt file (optional)"
  echo "  LORA_DIR        - Directory to save LoRA adapter (default: ${LORA_DIR})"
  echo "  MERGED_DIR      - Directory to save merged model (default: ${MERGED_DIR})"
  echo "  GGUF_DIR        - Directory to save GGUF model (default: ${GGUF_DIR})"
  echo "  GGUF_QUANTIZATION - GGUF quantization method (default: ${GGUF_QUANTIZATION})"
  echo "  GGUF_OUTPUT_NAME - Custom filename for the GGUF model (default: uses model name)"
  echo "  HF_REPO_ID      - HuggingFace repository ID for merged model (required for push)"
  echo "  GGUF_REPO_ID    - HuggingFace repository ID for GGUF model (required for push-gguf)"
  echo "  HF_TOKEN        - HuggingFace API token (required for push and push-gguf)"
  echo ""
  echo "Example usage:"
  echo "  docker run --rm -it --device=/dev/kfd --device=/dev/dri --shm-size=8g \\"
  echo "    --group-add video -v \$PWD:/workspace \\"
  echo "    -e DATASET_NAME=your/dataset -e MODEL_NAME=your/model \\"
  echo "    -e HF_REPO_ID=username/my-model -e HF_TOKEN=hf_xxxx \\"
  echo "    lora-rocm train"
}

# Function to train LoRA adapter
run_train() {
  echo "Training LoRA adapter..."
  
  # Check if DATASET_NAME is provided
  if [ -z "$DATASET_NAME" ]; then
    echo "Error: DATASET_NAME environment variable is required for training"
    exit 1
  fi
  
  # Prepare role_prompt_file argument
  role_prompt_arg=""
  if [ -n "$ROLE_PROMPT_FILE" ]; then
    role_prompt_arg="--role_prompt_file $ROLE_PROMPT_FILE"
  fi
  
  python3 /usr/local/bin/train_lora.py \
    --model_name "$MODEL_NAME" \
    --dataset_name "$DATASET_NAME" \
    $role_prompt_arg \
    --lora_output_dir "$LORA_DIR" \
    "$@"
}

# Function to merge LoRA with base model
run_merge() {
  echo "Merging LoRA adapter with base model..."
  python3 /usr/local/bin/merge_lora.py \
    --model_name "$MODEL_NAME" \
    --lora_dir "$LORA_DIR" \
    --output_dir "$MERGED_DIR" \
    "$@"
}

# Function to convert to GGUF
run_convert() {
  echo "Converting merged model to GGUF format..."
  
  # Prepare output_name argument
  output_name_arg=""
  if [ -n "$GGUF_OUTPUT_NAME" ]; then
    output_name_arg="--output_name $GGUF_OUTPUT_NAME"
  fi
  
  python3 /usr/local/bin/convert_to_gguf.py \
    --input_dir "$MERGED_DIR" \
    --output_dir "$GGUF_DIR" \
    --quantization "$GGUF_QUANTIZATION" \
    $output_name_arg \
    "$@"
}

# Function to push merged model to HuggingFace
run_push() {
  if [ -z "$HF_REPO_ID" ]; then
    echo "Error: HF_REPO_ID environment variable is required for push"
    exit 1
  fi
  
  echo "Pushing merged model to HuggingFace..."
  
  # Debug the token
  echo "Token is present: $([ -n "$HF_TOKEN" ] && echo "Yes" || echo "No")"
  
  # Direct, simpler approach to passing the token
  python3 /usr/local/bin/push_to_hf.py \
    --model_dir "$MERGED_DIR" \
    --repo_id "$HF_REPO_ID" \
    --token "$HF_TOKEN" \
    "$@"
}

# Function to push GGUF model to HuggingFace
run_push_gguf() {
  if [ -z "$GGUF_REPO_ID" ]; then
    echo "Error: GGUF_REPO_ID environment variable is required for push-gguf"
    exit 1
  fi
  
  echo "Pushing GGUF model to HuggingFace..."
  
  # Debug the token
  echo "Token is present: $([ -n "$HF_TOKEN" ] && echo "Yes" || echo "No")"
  
  # Use the same push script but with different parameters
  python3 /usr/local/bin/push_to_hf.py \
    --model_dir "$GGUF_DIR" \
    --repo_id "$GGUF_REPO_ID" \
    --token "$HF_TOKEN" \
    --commit_message "Upload GGUF model" \
    "$@"
}

# Parse command
case "$1" in
  train)
    shift
    run_train "$@"
    ;;
  merge)
    shift
    run_merge "$@"
    ;;
  convert)
    shift
    run_convert "$@"
    ;;
  push)
    shift
    run_push "$@"
    ;;
  push-gguf)
    shift
    run_push_gguf "$@"
    ;;
  all)
    shift
    run_train "$@"
    run_merge "$@"
    run_push "$@"
    ;;
  all-gguf)
    shift
    run_train "$@"
    run_merge "$@"
    run_convert "$@"
    run_push "$@"
    run_push_gguf "$@"
    ;;
  shell|bash)
    exec /bin/bash
    ;;
  help|--help|-h)
    show_help
    ;;
  "")
    # Default to shell if no command provided
    exec /bin/bash
    ;;
  *)
    echo "Unknown command: $1"
    show_help
    exit 1
    ;;
esac
