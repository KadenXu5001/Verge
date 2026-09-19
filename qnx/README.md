# llama.cpp on QNX

This directory contains the first target-side integration for running a local
GGUF model from a QNX 8 target.

## What this does

`llama_prompt.sh` verifies that `llama-cli` is installed, accepts a model path
and generation settings, and starts an interactive prompt on the QNX shell.

The launcher uses the QNX `llama.cpp` package rather than copying a host-built
binary onto the target. CPU inference is the default; Vulkan can be enabled by
passing `--gpu-layers`.

## Target setup

On the QNX target, configure the QNX package repositories and install the CPU
packages:

```sh
sudo apk update
sudo apk add llama.cpp llama.cpp-libs
```

For Vulkan offload, install the backend and shader toolchain too:

```sh
sudo apk add \
  spirv-headers spirv-tools glslang shaderc \
  llama.cpp-vulkan
```

Copy a GGUF model to the target, then copy and run the launcher:

```sh
scp ./Qwen2.5-1.5B-Instruct-Q4_K_M.gguf root@TARGET:/data/models/
scp qnx/llama_prompt.sh root@TARGET:/tmp/
ssh root@TARGET 'chmod +x /tmp/llama_prompt.sh && /tmp/llama_prompt.sh --model /data/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf'
```

## Examples

CPU-only interactive prompt:

```sh
./llama_prompt.sh --model /data/models/model.gguf
```

Use 16 layers on the GPU when Vulkan is available:

```sh
./llama_prompt.sh --model /data/models/model.gguf --gpu-layers 16
```

Start with a one-shot prompt:

```sh
./llama_prompt.sh \
  --model /data/models/model.gguf \
  --prompt 'Explain what this QNX target is doing.' \
  --no-interactive
```

The model must be in GGUF format. Start with a small instruct model and a
quantization such as Q4_K_M; memory use depends on the model, context size,
and number of GPU layers.

## Target-specific notes

- This assumes QNX 8 and the `apk`-based package repositories.
- CPU inference should work on any QNX 8 target; Vulkan acceleration depends
  on the target's QNX graphics/Vulkan stack.
- The launcher intentionally does not download models on the target.
- If the application needs an in-process API, install `llama.cpp-dev` and link
  against the packaged C API rather than shelling out to `llama-cli`.
