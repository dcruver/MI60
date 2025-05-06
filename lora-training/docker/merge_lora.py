# merge_lora.py (updated)
import argparse
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

def merge_model(args):
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
    
    args = parser.parse_args()
    merge_model(args)
