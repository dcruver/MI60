# 🖥️ How to Get an AMD Instinct MI60 Running for AI Workloads

## Table of Contents

1. [Introduction](#1-introduction)
2. [Parts List](#-parts-list)
3. [Photos](#-photos)
4. [Hardware and Compatibility Checklist](#2-hardware-and-compatibility-checklist)
5. [Software Stack Overview](#3-software-stack-overview)
6. [Verifying ROCm Installation](#4-verifying-rocm-installation)
7. [Cooling and Fan Control Setup](#5-cooling-and-fan-control-setup)
8. [Running AI Workloads](#6-running-ai-workloads)
    - [Whisper.cpp and Stable Diffusion Notes](#6-running-ai-workloads)
    - [Ollama + Open WebUI](#ollama--open-webui-with-rocm-and-mi60)
9. [Benchmarks](#7-benchmarks)
    - [Benchmarking Token Generation Rate](#benchmarking-token-generation-rate)
    - [Benchmark Results](#benchmark-results)
10. [Known Issues and Workarounds](#8-known-issues-and-workarounds)
11. [Final Notes](#9-final-notes)

## 1. Introduction

The AMD Instinct MI60 is a powerful server GPU featuring 32 GB of HBM2 VRAM and PCIe 3.0 connectivity. It remains a 
good choice for budget-conscious AI developers looking for high VRAM capacity at a fraction of modern GPU prices. With 
proper setup, the MI60 can handle local LLM inference, Whisper transcription, Stable Diffusion, and other workloads.

## 🛠 Parts List

| Item                  | Details        | Notes                     |
| --------------------- | -------------- | ------------------------- |
| AMD Instinct MI60 GPU | 32GB HBM2 VRAM | Passive-cooled server GPU |
| **92mm x 38mm Fan**       | High static pressure, 12V, PWM or 3-pin | Example: GDSTIME 92x38mm fan. Needed to force air through MI60's dense heatsink                                         |
| Fan Mounting              | 3D printed shroud                          | A shroud ensures airflow stays directed through the heatsink. [Download STL](https://www.thingiverse.com/thing:6636428) |
| High Wattage PSU          | 600W+ with 2x 8-pin PCIe                | MI60 can draw 300W under AI workloads                                                                                   |

> **Tip**: Look for "**92mm x 38mm high static pressure fan**" on Amazon or eBay. GDSTIME, Delta, and Sunon are common brands. Some models can be loud — use PWM or undervolting to reduce noise.

## 📸 Photos

MI60 with 92mm GDSTIME fan attached using a 3D-printed shroud. The 3D-printed fan housing also doubles as a physical 
support for the GPU.

<img src="images/MI60-fan-housing1.jpg" alt="Fan Mount" width="500"/>

## 2. Hardware and Compatibility Checklist

### BIOS Settings Checklist

To ensure the MI60 initializes properly and operates with maximum stability, adjust these BIOS settings:

- **Above 4G Decoding**: `Enabled`

    - Required for proper BAR mapping and ROCm support.

- **Resizable BAR**: `Disabled`

    - ROCm does not benefit and may break compatibility with some MI-series cards.

- **PCIe Link Speed**: `Auto` or `Gen 3`

    - The MI60 is a PCIe 3.0 card. Setting Gen 4 may work but is unnecessary.

- **CSM (Compatibility Support Module)**: `Disabled`

    - Use UEFI boot mode for best compatibility with modern Linux distros and ROCm.

- **Integrated Graphics**: `Disabled` (if not needed)

    - Frees up resources and avoids conflicts.

- **Primary GPU**: Set to `PCIe Slot` or `PEG`

    - Ensures the MI60 is initialized at boot.

- **Motherboards**:

    - PCIe 4.0 not strictly required (works well on PCIe 3.0 platforms)
    - Tested platforms: X570, B550, TRX40

- **Power Supply**:

    - Expect \~300W power draw under load
    - Requires two 8-pin PCIe power connectors

- **Cooling Requirements**:

    - Passive GPU (no built-in fan)
    - Requires external fan for reliable cooling

- **Physical Space**:

    - Double-slot width
    - Ensure good airflow around the card

## 3. Software Stack Overview

- **Operating System**: Ubuntu 22.04 LTS or Linux Mint 21.x
- **Driver Stack**: ROCm 5.6 (newer versions dropped MI60 support)

## 4. Verifying ROCm Installation

- Check if the GPU is detected:
  ```bash
  rocminfo
  ```
- Verify HIP support:
  ```bash
  /opt/rocm/bin/hipInfo
  ```
- Troubleshooting:
    - Kernel versions 5.15 or 6.2 are recommended.
    - Ensure `/dev/kfd` exists and that your user belongs to the `video` group.
    - Stick to ROCm 5.6 to maintain compatibility.

## 5. Cooling and Fan Control Setup

### Physical Setup

- Mount a 92mm x 38mm fan (e.g., GDSTIME) directly onto the MI60 heatsink using a 3D printed bracket.
- Connect the fan to:
    - Motherboard CHA\_FAN or SYS\_FAN header
    - Or use an external powered fan hub

### Software Fan Control

You can automate fan behavior using a custom script and systemd service.

#### Example Fan Control Script
[This](scripts/mi60-fan.sh) is the fan control script that I'm using. Depending on your motherboard and which fan control header you're using,
you may need to modify the value of PWM_PATH and PWM_ENABLE_PATH. Further, depending on the output of your particular
fan, you may want to change the values for MIN_PWM, MAX_PWM, MIN_TEMP, MAX_TEMP, UTIL_THRESH and/or BOOST_PWM. The
values in the script should work reasonably well as a starting point.

Save the script at `/usr/local/bin/mi60-fan.sh`

Make it executable:

```bash
sudo chmod +x /usr/local/bin/mi60-fan.sh
```

#### Create a systemd Service

Create [mi60-fan.service](scripts/mi60-fan.service) in `/etc/systemd/system/`

Enable and start the service:

```bash
sudo systemctl daemon-reexec
sudo systemctl enable --now mi60-fan.service
```

> **Note**: Use `sensors` to identify the correct `hwmon` path for your system and adjust `FAN_PATH` and `TEMP_PATH` accordingly.

1. Install `lm-sensors` and `fancontrol`:

   ```bash
   sudo apt install lm-sensors fancontrol
   ```

2. Detect all available sensors:

   ```bash
   sudo sensors-detect
   ```

    - Answer "yes" to all prompts.

3. View sensor output:

   ```bash
   sensors
   ```

    - Identify the relevant temperature inputs (usually motherboard CPU or system temp).

4. Configure PWM fan control:

   ```bash
   sudo pwmconfig
   ```

    - Follow the prompts to associate PWM outputs with temperature inputs.

5. Enable fancontrol service:

   ```bash
   sudo systemctl enable fancontrol
   sudo systemctl start fancontrol
   ```

> **Tip**: If your motherboard does not expose fine PWM controls, set a BIOS fan curve instead.

## 6. Running AI Workloads
Before diving in, it’s worth noting a couple of tools that may require more effort to get working:

+ **Whisper.cpp**: I was unable to get whisper.cpp running on the GPU — it consistently fell back to CPU despite being 
built with OpenCL support. It's likely possible; I just haven’t found the right incantation yet.

+ **Stable Diffusion**: In my testing, attempting to run Stable Diffusion caused the GPU to become unresponsive until 
reboot. This may be solvable with additional configuration or a more ROCm-compatible fork, but I haven’t resolved it yet.


### Ollama + Open WebUI (with ROCm and MI60)

You can run Ollama with MI60 using the ROCm-enabled container provided by the project. 


> **Notes:**
>
> - Be sure to use the `--device=/dev/kfd --device=/dev/dri` options to pass GPU access into the container.
> - `HSA_OVERRIDE_GFX_VERSION=9.0.0` ensures Ollama initializes properly with Vega 20 architecture (MI60).
> - You may want to add `group_add: [video]` to ensure proper access rights inside the container.
> - Logs and models will be stored in `./ollama` relative to where you launch Docker.

Once running, Open WebUI will be accessible at [http://localhost:8080](http://localhost:8080) and Ollama at port `11434`.


## 7. Benchmarks
### Benchmarking Token Generation Rate
You can use [this](scripts/benchmark_ollama.sh) script below to benchmark Ollama's token generation speed via the HTTP 
API.

Make it executable:
```bash
chmod +x benchmark_ollama.sh
```

Then run:
```bash
./benchmark_ollama.sh
```

Each run will append the results to ollama_benchmark.log for later comparison.

### Benchmark Results
These are the results that I saw on my local machine. GPU temperatures never exceeded 73°C.

| Model             | Tokens/sec    | temperature |
|-------------------|---------------|-------------|
| qwen2.5-coder:32B | 15.13         | ~70°C       |
| qwen2.5:8b        | 57.40         | ~60°C       |
| qwen3:8b          | 46.61         | ~60°C       |
| qwen3:30b         | 29.86         | ~65°C       |
| qwen3:32b         | 14.06         | ~73°C       |



## 8. Known Issues and Workarounds

Section 8: Known Issues and Workarounds (modified bullet list)
- ROCm 6.x+ drops MI60 support (stick with 5.6).
- Docker containers require manual device mapping.
- MI60 lacks native FP16 acceleration; full precision FP32 models perform better.
- Whisper.cpp falls back to CPU — GPU support might work with the right OpenCL build setup, but it’s not functioning 
yet in my tests.
- Stable Diffusion causes GPU lockups — system becomes unresponsive until reboot. This may be solvable but remains 
unresolved.

## 9. Final Notes

- The MI60 is a good choice for affordable local AI compute.
- Proper cooling setup is critical to stable operation.
- With ROCm 5.6, Linux, and some tuning, the MI60 remains usable for AI workloads.

---



