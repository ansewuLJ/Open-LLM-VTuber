#!/usr/bin/env bash
# Start Open-LLM-VTuber with the GPU ASR environment.
# Do NOT use `uv run` here: uv would resync the lock file and replace the
# CUDA-enabled sherpa-onnx / onnxruntime-gpu wheels with CPU builds.
set -e
cd "$(dirname "$0")"
LIBS=$(find "$PWD/.venv/lib/python3.10/site-packages/nvidia" -maxdepth 2 -type d -name lib | paste -sd:)
# Qwen3-TTS CustomVoice: the preset voice is set in conf.yaml (`voice`),
# and the style is controlled by `instructions`. It does not use reference
# audio or Breeze-specific sample-rate / guidance parameters.
export VTUBER_TTS_INSTRUCTIONS="${VTUBER_TTS_INSTRUCTIONS-吐字清晰，语速稍慢，语气自然，不要低沉。}"
export VTUBER_TTS_SEED="${VTUBER_TTS_SEED:-42}"
unset VTUBER_TTS_REF_AUDIO VTUBER_TTS_REF_TEXT VTUBER_TTS_SAMPLE_RATE VTUBER_TTS_EXTRA_PARAMS
export LD_LIBRARY_PATH="$LIBS${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec .venv/bin/python run_server.py "$@"
