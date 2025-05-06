import argparse
import os
from huggingface_hub import HfApi, login

def push_to_huggingface(args):
    # Ensure we have a token
    token = args.token or os.environ.get("HF_TOKEN")
    if not token:
        raise ValueError("No Hugging Face token found. Please provide a token via --token or HF_TOKEN environment variable.")
    
    print(f"Authenticating with Hugging Face Hub...")
    # Explicitly login with the token
    login(token=token, add_to_git_credential=False)
    
    print(f"Pushing model from {args.model_dir} to {args.repo_id}")
    
    # Initialize the API with explicit token
    api = HfApi(token=token)
    
    # Create the repository if it doesn't exist
    api.create_repo(
        repo_id=args.repo_id, 
        exist_ok=True, 
        repo_type="model", 
        private=args.private,
    )
    
    # Upload the model folder with all necessary files
    api.upload_folder(
        folder_path=args.model_dir,
        repo_id=args.repo_id,
        commit_message=args.commit_message,
    )
    
    print(f"✅ Model successfully uploaded to {args.repo_id}")
    print(f"Now you can visit https://huggingface.co/spaces/ggml-org/gguf-my-repo to convert it to GGUF format")
    print(f"Enter your model ID: {args.repo_id}")
    print("Select the quantization formats you want to create")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Push model to Hugging Face Hub")
    parser.add_argument("--model_dir", type=str, default="./lora-merged", 
                        help="Directory containing the model to upload")
    parser.add_argument("--repo_id", type=str, required=True, 
                        help="Target repository ID on Hugging Face (username/repo-name)")
    parser.add_argument("--token", type=str, default=None, 
                        help="Hugging Face API token (if not provided, will use HF_TOKEN env var)")
    parser.add_argument("--private", action="store_true", 
                        help="Whether to create a private repository")
    parser.add_argument("--commit_message", type=str, 
                        default="Upload merged model with LoRA adapter",
                        help="Commit message for the upload")
    
    args = parser.parse_args()
    push_to_huggingface(args)

