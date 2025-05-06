# AMD MI60 GPU - Tools and Utilities

This repository provides tools, guides, and workflows for working with the AMD Instinct MI60 GPU, a high-performance 
compute GPU designed for AI training and inference workloads.

## Contents

### [Hardware Setup](./hardware-setup/README.md)

Documentation of my experience with installing, configuring, and troubleshooting the AMD MI60 GPU hardware on a standard
PC:

- Driver installation and configuration
- System requirements and compatibility
- Troubleshooting common issues
- Performance optimization

### [LoRA Training](./lora-training/README.md)

A Docker-based workflow for training LoRA (Low-Rank Adaptation) adapters for large language models on AMD GPUs:

- Train LoRA adapters for any Hugging Face model
- Merge LoRA adapters with base models
- Convert to GGUF format for efficient inference
- Push models to Hugging Face repositories

## Hardware Specifications

The AMD Instinct MI60 GPU offers:

- 32GB HBM2 (High-Bandwidth Memory)
- Up to 7.4 TFLOPS FP64 performance
- ROCm platform support
- PCIe Gen4 interface
- 10.6 TFLOPS FP32 performance

## Getting Started

1. Begin with the [Hardware Setup](./hardware-setup/README.md) guide to install and configure your MI60 GPU
2. Once your hardware is properly configured, explore the [LoRA Training](./lora-training/README.md) workflow to 
fine-tune language models

## System Requirements

- Linux operating system (Ubuntu 20.04/22.04 recommended)
- ROCm-compatible kernel
- Sufficient power supply (300W recommended)
- Adequate cooling solution
- At least 16GB system RAM (32GB+ recommended for ML workloads)

## Contributing

Contributions to improve documentation or add new tools are welcome! Please feel free to submit pull requests or open 
issues with suggestions.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- AMD for creating the MI60 hardware and ROCm platform
- The open-source community for providing valuable resources and tools
