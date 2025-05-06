#!/usr/bin/env python3
# convert_to_gguf.py
import argparse
import os
import subprocess
import sys
from pathlib import Path
import json

def run_command(cmd, cwd=None):
    """Run a command and print its output"""
    print(f"Running: {' '.join(cmd)}")
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=cwd
    )
    
    # Print output in real-time
    for line in iter(process.stdout.readline, ''):
        print(line, end='')
    
    process.wait()
    
    if process.returncode != 0:
        print(f"Command failed with exit code {process.returncode}")
        sys.exit(process.returncode)

def convert_to_gguf(args):
    """Convert the merged model to GGUF format"""
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Get model type from config.json
    config_path = input_dir / "config.json"
    if not config_path.exists():
        print(f"Error: Config file not found at {config_path}")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Determine model architecture
    model_architecture = config.get("model_type", "").lower()
    
    # Set appropriate outfile name based on model type and quantization
    if args.output_name:
        outfile_name = args.output_name
    else:
        outfile_name = f"{Path(args.input_dir).name}"
    
    if args.quantization and not outfile_name.endswith(f".{args.quantization}.gguf"):
        outfile_name += f".{args.quantization}"
    
    if not outfile_name.endswith(".gguf"):
        outfile_name += ".gguf"
    
    outfile_path = output_dir / outfile_name
    
    print(f"Converting model from {input_dir} to GGUF format")
    print(f"Output will be saved to {outfile_path}")
    print(f"Model architecture detected: {model_architecture}")
    
    # Try multiple conversion methods in order of preference
    conversion_success = False
    
    # Method 1: Try with convert_hf_to_gguf.py (the known working method)
    print("Attempting conversion using convert_hf_to_gguf.py...")
    
    # Look for the script in llama.cpp directory
    convert_script_paths = [
        "/opt/llama.cpp/convert_hf_to_gguf.py",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "convert_hf_to_gguf.py")
    ]
    
    convert_script = None
    for path in convert_script_paths:
        if os.path.exists(path):
            convert_script = path
            break
    
    # If we don't find the script, download it
    if convert_script is None:
        print("Script not found, downloading convert_hf_to_gguf.py...")
        download_cmd = [
            "curl", "-o", "/tmp/convert_hf_to_gguf.py",
            "https://raw.githubusercontent.com/ggerganov/llama.cpp/master/convert_hf_to_gguf.py"
        ]
        try:
            run_command(download_cmd)
            convert_script = "/tmp/convert_hf_to_gguf.py"
        except Exception as e:
            print(f"Failed to download script: {e}")
    
    # Try to convert using the downloaded or found script
    if convert_script:
        convert_cmd = [
            "python3", convert_script,
            "--outfile", str(outfile_path),
            "--outtype", "f16",
            str(input_dir)
        ]
        
        try:
            run_command(convert_cmd)
            conversion_success = True
            print("Conversion successful using convert_hf_to_gguf.py!")
        except Exception as e:
            print(f"Error using convert_hf_to_gguf.py: {e}")
    
    # Method 2: Try using llama.cpp's convert.py
    if not conversion_success:
        print("Attempting conversion using llama.cpp convert.py...")
        convert_py_paths = [
            "/opt/llama.cpp/convert.py"
        ]
        
        convert_py = None
        for path in convert_py_paths:
            if os.path.exists(path):
                convert_py = path
                break
        
        if convert_py:
            convert_py_cmd = [
                "python3", convert_py,
                str(input_dir),
                "--outfile", str(outfile_path),
                "--outtype", "f16"
            ]
            
            try:
                run_command(convert_py_cmd, cwd="/opt/llama.cpp")
                conversion_success = True
                print("Conversion successful using llama.cpp convert.py!")
            except Exception as e:
                print(f"Error using llama.cpp convert.py: {e}")
    
    # Method 3: Try installing gguf package
    if not conversion_success:
        print("Attempting conversion using gguf package...")
        try:
            run_command(["pip", "install", "gguf", "--upgrade"])
            gguf_cmd = [
                "python3", "-c",
                f"import gguf; from pathlib import Path; gguf.write_model_to_gguf(Path('{str(input_dir)}'), Path('{str(outfile_path)}'))"
            ]
            run_command(gguf_cmd)
            conversion_success = True
            print("Conversion successful using gguf package!")
        except Exception as e:
            print(f"Error using gguf package: {e}")
    
    # If all conversion methods failed
    if not conversion_success:
        print("All conversion methods failed. Please check error messages above.")
        sys.exit(1)
    
    # If quantization is specified, quantize the model
    if args.quantization and os.path.exists(str(outfile_path)):
        print(f"Quantizing model to {args.quantization}")
        temp_outfile = outfile_path.with_suffix(".temp.gguf")
        
        # Look for the quantize tool
        quantize_paths = [
            "/opt/llama.cpp/build/bin/llama-quantize",
            "/usr/local/bin/llama-quantize",
            "llama-quantize"
        ]
        
        quantize_tool = None
        for path in quantize_paths:
            try:
                # Check if it's in PATH
                if any(os.path.exists(os.path.join(p, os.path.basename(path))) for p in os.environ["PATH"].split(os.pathsep)):
                    quantize_tool = os.path.basename(path)
                    break
                # Check specific path
                elif os.path.exists(path) and os.access(path, os.X_OK):
                    quantize_tool = path
                    break
            except:
                continue
        
        if quantize_tool:
            quantize_cmd = [
                quantize_tool,
                str(outfile_path),
                str(temp_outfile),
                args.quantization
            ]
            
            try:
                run_command(quantize_cmd)
                # Replace original with quantized version
                os.replace(str(temp_outfile), str(outfile_path))
                print(f"Quantization to {args.quantization} successful!")
            except Exception as e:
                print(f"Error during quantization: {e}")
                print("Quantization failed. Using unquantized model.")
        else:
            print("Could not find quantization tool. Using unquantized model.")
    
    print(f"✅ Model successfully converted to GGUF format: {outfile_path}")
    
    # Create simple model card
    model_card = f"""# {Path(args.input_dir).name} - GGUF

This is a GGUF version of the {Path(args.input_dir).name} model.

## Model Details

- **Base Model:** {args.input_dir}
- **Format:** GGUF 
- **Quantization:** {args.quantization if args.quantization else "None (F16)"}

## Usage

This model can be used with [llama.cpp](https://github.com/ggerganov/llama.cpp) and compatible applications.

```bash
# Example llama.cpp command
./main -m {outfile_name} -n 1024 -p "Your prompt here"
```
"""
    
    with open(output_dir / "README.md", "w") as f:
        f.write(model_card)
    
    return str(outfile_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert model to GGUF format")
    parser.add_argument("--input_dir", type=str, default="./lora-merged", 
                        help="Directory containing the merged model")
    parser.add_argument("--output_dir", type=str, default="./gguf-model", 
                        help="Directory to save the GGUF model")
    parser.add_argument("--output_name", type=str, default="", 
                        help="Custom filename for the GGUF model (default: uses input directory name)")
    parser.add_argument("--quantization", type=str, default="q4_k_m", 
                        help="Quantization method (empty for none, or q4_0, q4_k_m, q5_k_m, q8_0, etc.)")
    
    args = parser.parse_args()
    convert_to_gguf(args)

