# Qwen3-TTS 推理后端性能对比

日期：2026-11-06
环境：RTX 5070 Ti Laptop，12227 MiB 显存
模型：`qwen3-tts-custom-vllm`（Qwen3-TTS-12Hz-1.7B-CustomVoice）
参数（两轮相同）：

```json
["--omni",
 "--stage-overrides={\"0\":{\"max_num_seqs\":64,\"gpu_memory_utilization\":0.68,\"max_model_len\":1024,\"enforce_eager\":true},\"1\":{\"max_num_seqs\":16,\"gpu_memory_utilization\":0.15}}"]
```

音色：`vivian`；接口：`POST /v1/audio/speech`（非流式，`response_format=wav`）。

## 后端镜像

| 版本键 | 镜像 | vLLM 版本 |
|---|---|---|
| `omni-0.30.0-custom` | `vllm/vllm-omni:v0.30.0` | 0.30.0 |
| `omni-latest-custom`（本次新增） | `vllm/vllm-omni:latest` | 0.32.0 |

## 测试方法

- 短句：约 27 字；先 1 次预热，再测 5 次。
- 中句：约 90 字；先 1 次预热，再测 5 次。
- 并发：8 个中句请求同时发出，统计总耗时与成功率。
- 延迟为“请求到完整 WAV 返回”的时间（非流式）；RTF = 音频时长 / 生成耗时。

## 结果

| 指标 | v0.30.0 | latest（v0.32.0） | 变化 |
|---|---|---|---|
| 短句延迟（均值） | **1.18 s** | 1.29 s | +0.11 s（略慢） |
| 短句 RTF | 4.97x | 4.89x | 略低 |
| 中句延迟（均值） | 3.89 s | **3.59 s** | -0.30 s（略快） |
| 中句 RTF | 5.10x | 5.11x | 基本持平 |
| 并发 8 总耗时 | **17.98 s** | 20.54 s | +2.56 s（差约 14%） |
| 并发 8 吞吐 | **0.44 req/s** | 0.39 req/s | 下降 |
| 显存占用 | 9555 MiB | 9705 MiB | +150 MiB |

两轮 8/8 请求全部成功，没有报错。

## 结论

- 新镜像 **没有整体性能提升**。
- 短句首响和 8 并发吞吐反而略差；中句快到约 0.3 s，但 RTF 持平，差异可能来自生成音频长度波动。
- 显存略高。
- 如果只是为了性能，建议继续用 **v0.30.0**；如果 v0.32.0 有你需要的新特性，再保留新镜像。

## 音色试听样本

同一句测试文本，已生成在 `voice_samples/`：

| 音色 | 时长 | 响度 | FireRedASR 识别 |
|---|---|---|---|
| `vivian` | 6.96 s | -19.7 dBFS | 完全正确 |
| `serena` | 5.52 s | -27.5 dBFS | 完全正确 |
| `uncle_fu` | 6.08 s | -25.0 dBFS | 完全正确 |

三个音色识别都全对；`vivian` 响度最高、最明亮，推荐作为默认。
