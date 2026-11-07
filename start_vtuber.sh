#!/usr/bin/env bash
# Start Open-LLM-VTuber with the GPU ASR environment.
# Do NOT use `uv run` here: uv would resync the lock file and replace the
# CUDA-enabled sherpa-onnx / onnxruntime-gpu wheels with CPU builds.
set -e
cd "$(dirname "$0")"
LIBS=$(find "$PWD/.venv/lib/python3.10/site-packages/nvidia" -maxdepth 2 -type d -name lib | paste -sd:)
# Qwen3-TTS Base: voice clone from the reference audio. Keep `instructions`
# empty for the pure cloned voice; seed 5 gave the closest pitch to the
# reference in local tests. Breeze-specific sample-rate / guidance params
# are not used.
export VTUBER_TTS_INSTRUCTIONS=""
export VTUBER_TTS_SEED="${VTUBER_TTS_SEED:-5}"
export VTUBER_TTS_REF_AUDIO="${VTUBER_TTS_REF_AUDIO:-$PWD/voice_samples/reference/reference_24k.wav}"
export VTUBER_TTS_REF_TEXT="${VTUBER_TTS_REF_TEXT:-四十六亿年前，漫天的尘埃和岩石碎片在太阳周围不断碰撞聚拢，团成了一颗滚烫的星球。他还没来得及喘口气，一场足以改写命运的撞击就来了，一颗颗火星。}"
unset VTUBER_TTS_SAMPLE_RATE VTUBER_TTS_EXTRA_PARAMS
export LD_LIBRARY_PATH="$LIBS${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec .venv/bin/python run_server.py "$@"
