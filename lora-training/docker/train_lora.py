# train_lora.py
import torch
import csv
import argparse
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import LoraConfig, get_peft_model, TaskType
from torch.utils.data import DataLoader
from tqdm import tqdm
from transformers import default_data_collator

def train_model(args):
    # Read role prompt from a file if provided
    ROLE_PROMPT = ""
    if args.role_prompt_file:
        try:
            with open(args.role_prompt_file, "r", encoding="utf-8") as f:
                ROLE_PROMPT = f.read().strip()
        except Exception as e:
            print(f"Warning: Could not read role prompt file: {e}")
            print("Continuing without role prompt...")

    # Load dataset
    dataset = load_dataset(args.dataset_name, split="train")

    # Check if dataset has the expected columns
    if "prompt" in dataset.column_names and "response" in dataset.column_names:
        # Dataset has the expected columns, proceed as normal
        pass
    else:
        # Try to map dataset columns to expected format
        mapped = False
        alternative_columns = {
            "prompt": ["instruction", "input", "question", "user_message"],
            "response": ["output", "answer", "completion", "assistant_message"]
        }
        
        for prompt_col in alternative_columns["prompt"]:
            for response_col in alternative_columns["response"]:
                if prompt_col in dataset.column_names and response_col in dataset.column_names:
                    # Found a matching pair, rename to expected format
                    print(f"Remapping dataset columns: {prompt_col} -> prompt, {response_col} -> response")
                    dataset = dataset.rename_columns({
                        prompt_col: "prompt",
                        response_col: "response"
                    })
                    mapped = True
                    break
            if mapped:
                break
        
        if not mapped:
            raise ValueError(f"Dataset must contain 'prompt' and 'response' columns or one of these alternatives: {alternative_columns}")

    # Inject the role prompt into each example if provided
    def format_example(example):
        if ROLE_PROMPT:
            return {
                "text": f"{ROLE_PROMPT}\nUser: {example['prompt']}\n\nAssistant: {example['response']}"
            }
        else:
            return {
                "text": f"User: {example['prompt']}\n\nAssistant: {example['response']}"
            }
    
    dataset = dataset.map(
        format_example,
        remove_columns=["prompt", "response"]
    )

    # === Tokenizer ===
    tokenizer = AutoTokenizer.from_pretrained(args.model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    def tokenize(example):
        tokens = tokenizer(
            example["text"],
            padding="max_length",
            truncation=True,
            max_length=args.max_length
        )
        tokens["labels"] = tokens["input_ids"].copy()
        return tokens

    tokenized_dataset = dataset.map(tokenize, batched=True)
    dataloader = DataLoader(tokenized_dataset, batch_size=args.batch_size, collate_fn=default_data_collator)

    # === Model + LoRA ===
    base_model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16
    )
    base_model = base_model.to("cuda")

    # LoRA config based on model architecture
    peft_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        target_modules=args.target_modules.split(","),
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type=TaskType.CAUSAL_LM
    )

    model = get_peft_model(base_model, peft_config)
    model.print_trainable_parameters()
    model.base_model.model.config.use_cache = False

    model.train()

    # === Optimizer ===
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)

    # === Training loop ===
    for epoch in range(args.num_epochs):
        print(f"Epoch {epoch + 1}")
        total_loss = 0
        for batch in tqdm(dataloader):
            inputs = {k: v.to(model.device) for k, v in batch.items()}
            outputs = model(**inputs)
            loss = outputs.loss
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()
            total_loss += loss.item()
        print(f"Epoch loss: {total_loss:.4f}")

    # === Save adapter ===
    model.save_pretrained(args.lora_output_dir)
    print(f"✅ LoRA adapter saved to {args.lora_output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train a LoRA adapter for language models")
    parser.add_argument("--model_name", type=str, default="Qwen/Qwen3-8B", 
                        help="Base model name from HuggingFace")
    parser.add_argument("--dataset_name", type=str, required=True, 
                        help="Dataset name from HuggingFace")
    parser.add_argument("--role_prompt_file", type=str, default="", 
                        help="Path to the role prompt file (optional)")
    parser.add_argument("--lora_output_dir", type=str, default="./lora-adapters", 
                        help="Directory to save the LoRA adapters")
    parser.add_argument("--max_length", type=int, default=256, 
                        help="Maximum sequence length for tokenization")
    parser.add_argument("--batch_size", type=int, default=4, 
                        help="Training batch size")
    parser.add_argument("--num_epochs", type=int, default=10, 
                        help="Number of training epochs")
    parser.add_argument("--learning_rate", type=float, default=2e-5, 
                        help="Learning rate")
    parser.add_argument("--lora_r", type=int, default=8, 
                        help="LoRA rank parameter")
    parser.add_argument("--lora_alpha", type=int, default=32, 
                        help="LoRA alpha parameter")
    parser.add_argument("--lora_dropout", type=float, default=0.05, 
                        help="LoRA dropout parameter")
    parser.add_argument("--target_modules", type=str, default="q_proj,v_proj", 
                        help="Comma-separated list of target modules for LoRA")
    
    args = parser.parse_args()
    train_model(args)
