# merge_lora.py (updated)
import argparse
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from huggingface_hub import login

def merge_model(args):
    # Check for HuggingFace token and login if provided
    if args.hf_token:
        print("HF token provided. Logging in to Hugging Face...")
        login(token=args.hf_token)
        print("Successfully logged in to Hugging Face")
    else:
        print("Warning: No HF token provided. You may not be able to access gated models like Mistral.")
        print("Use the --hf_token parameter if needed.")

    print(f"Loading base model: {args.model_name}")
    # Load base model
    base_model = AutoModelForCausalLM.from_pretrained(
        args.model_name, 
        trust_remote_code=True
    )

    print(f"Loading LoRA adapter from: {args.lora_dir}")
    # Load and merge LoRA adapter
    model = PeftModel.from_pretrained(base_model, args.lora_dir)
    merged_model = model.merge_and_unload()

    print(f"Saving merged model to: {args.output_dir}")
    # Save merged model
    merged_model.save_pretrained(args.output_dir)
    tokenizer = AutoTokenizer.from_pretrained(args.model_name, trust_remote_code=True)
    tokenizer.save_pretrained(args.output_dir)
    
    print(f"✅ Model successfully merged and saved to {args.output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge LoRA adapter with base model")
    parser.add_argument("--model_name", type=str, default="Qwen/Qwen3-8B", 
                        help="Base model name from HuggingFace")
    parser.add_argument("--lora_dir", type=str, default="./lora-adapters", 
                        help="Directory containing the LoRA adapter")
    parser.add_argument("--output_dir", type=str, default="./lora-merged", 
                        help="Directory to save the merged model")
    parser.add_argument("--hf_token", type=str, default=None,
                        help="Hugging Face token for accessing gated models")
    
    args = parser.parse_args()
    merge_model(args)
