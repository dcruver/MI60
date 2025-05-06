FROM rocm/dev-ubuntu-22.04:5.6-complete

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTORCH_HIP_ALLOC_CONF=expandable_segments:True

# Install system dependencies
RUN apt update && apt install -y \
    git curl wget unzip software-properties-common \
    python3-pip python3-dev \
    build-essential cmake \
    libcurl4-openssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install ROCm-compatible PyTorch + torchvision from ROCm index
# Install numpy from PyPI
RUN pip install --upgrade pip && \
    pip install torch==2.2.2 torchvision==0.17.2 --index-url https://download.pytorch.org/whl/rocm5.6 && \
    pip install numpy==1.26.4

# Install project dependencies (transformers, peft, etc.)
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    huggingface_hub

# Clone and build llama.cpp with ROCm support
RUN git clone https://github.com/ggerganov/llama.cpp.git /opt/llama.cpp && \
    cd /opt/llama.cpp && \
    mkdir -p build && \
    cd build && \
    cmake .. \
      -DLLAMA_HIPBLAS=ON \
      -DLLAMA_NATIVE=OFF \
      -DLLAMA_AVX=OFF \
      -DLLAMA_AVX2=OFF \
      -DLLAMA_AVX512=OFF \
      -DLLAMA_FMA=OFF \
      -DLLAMA_F16C=OFF \
      -DCMAKE_BUILD_TYPE=Release \
      -DLLAMA_CURL=ON && \
    cmake --build . --config Release -j $(nproc) && \
    mkdir -p /opt/llama.cpp/models && \
    # Create symlinks to make llama.cpp tools available in PATH
    ln -s /opt/llama.cpp/build/bin/llama-quantize /usr/local/bin/ || true && \
    ln -s /opt/llama.cpp/build/bin/main /usr/local/bin/llama-main || true && \
    ln -s /opt/llama.cpp/convert.py /usr/local/bin/llama-convert || true

WORKDIR /workspace

COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

COPY train_lora.py /usr/local/bin/
RUN chmod +x /usr/local/bin/train_lora.py

COPY merge_lora.py /usr/local/bin/
RUN chmod +x /usr/local/bin/merge_lora.py

COPY push_to_hf.py /usr/local/bin/
RUN chmod +x /usr/local/bin/push_to_hf.py

COPY convert_to_gguf.py /usr/local/bin/
RUN chmod +x /usr/local/bin/convert_to_gguf.py

# Set the entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
