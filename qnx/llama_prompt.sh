#!/bin/sh
set -eu

usage() {
    echo "Usage: $0 --model MODEL.gguf [options]"
    echo ""
    echo "Options:"
    echo "  --model PATH          GGUF model to load (required)"
    echo "  --ctx SIZE            Context size (default: 2048)"
    echo "  --threads COUNT       CPU threads (default: auto)"
    echo "  --gpu-layers COUNT    Layers to offload to Vulkan (default: 0)"
    echo "  --temperature VALUE   Sampling temperature (default: 0.7)"
    echo "  --prompt TEXT         One-shot prompt"
    echo "  --no-interactive      Exit after one-shot generation"
    echo "  --help                Show this help"
}

model=""
ctx="2048"
threads=""
gpu_layers="0"
temperature="0.7"
prompt=""
interactive="1"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --model)
            [ "$#" -ge 2 ] || { echo "--model requires a path" >&2; exit 2; }
            model="$2"
            shift 2
            ;;
        --ctx)
            [ "$#" -ge 2 ] || { echo "--ctx requires a value" >&2; exit 2; }
            ctx="$2"
            shift 2
            ;;
        --threads)
            [ "$#" -ge 2 ] || { echo "--threads requires a value" >&2; exit 2; }
            threads="$2"
            shift 2
            ;;
        --gpu-layers)
            [ "$#" -ge 2 ] || { echo "--gpu-layers requires a value" >&2; exit 2; }
            gpu_layers="$2"
            shift 2
            ;;
        --temperature)
            [ "$#" -ge 2 ] || { echo "--temperature requires a value" >&2; exit 2; }
            temperature="$2"
            shift 2
            ;;
        --prompt)
            [ "$#" -ge 2 ] || { echo "--prompt requires text" >&2; exit 2; }
            prompt="$2"
            shift 2
            ;;
        --no-interactive)
            interactive="0"
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [ -z "$model" ]; then
    echo "error: --model is required" >&2
    usage >&2
    exit 2
fi

if [ ! -f "$model" ]; then
    echo "error: model does not exist: $model" >&2
    exit 1
fi

if ! command -v llama-cli >/dev/null 2>&1; then
    echo "error: llama-cli is not installed" >&2
    echo "Install it with: sudo apk add llama.cpp llama.cpp-libs" >&2
    exit 127
fi

set -- llama-cli \
    -m "$model" \
    -c "$ctx" \
    -ngl "$gpu_layers" \
    --temp "$temperature"

if [ -n "$threads" ]; then
    set -- "$@" -t "$threads"
fi

if [ -n "$prompt" ]; then
    set -- "$@" -p "$prompt"
fi

if [ "$interactive" = "1" ]; then
    echo "Starting llama.cpp on QNX. Type /exit or press Ctrl+C to stop."
    exec "$@" -cnv
else
    exec "$@"
fi
