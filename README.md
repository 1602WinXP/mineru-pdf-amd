# MinerU AMD GPU 本地部署方案

> 让 MinerU 在 AMD 显卡上以 vllm + hybrid-auto-engine 满血运行
> 输出质量对标[官网精准解析 API](https://mineru.net)
>
> 实测: RX 9070 · 适用于全系 RDNA2/3/4 显卡 · ROCm 7.1.1 · PyTorch 2.11.0 · MinerU 3.1.15

## 为什么要有这个项目

MinerU 是目前最强的开源文档解析引擎，但官方几乎只维护 NVIDIA/CUDA 生态。AMD 显卡用户唯一的参考资料是 [GitHub Discussion #3662](https://github.com/opendatalab/MinerU/discussions/3662)（一位社区开发者的适配分享），且该讨论针对 MinerU 2.x 旧版本，与 3.x 有大量不兼容之处。

这个项目填补了这个空白：**从零开始，在 AMD 显卡上部署 MinerU 3.x + vllm，每一步都实际验证过**。

## 适用硬件

**显存 >= 16GB 的 AMD RDNA2/3/4 桌面显卡。** 查代号：`rocminfo | grep gfx`。

| 你的显卡 | gfx 代号 | 备注 |
|---------|---------|------|
| RX 9070 系列 | `gfx1201` | 实测通过 |
| RX 7900 系列 | `gfx1100` | 原生支持 |
| RX 7800 XT / 7700 XT | `gfx1102` | 可能需要 `HSA_OVERRIDE_GFX_VERSION=11.0.0` |
| RX 7600 XT / 7600 | `gfx1102`/`gfx1103` | 同上；8GB 版显存不够 |
| RX 6900 / 6800 / 6700 | `gfx1030` | 16GB 版可用 |

RDNA1（RX 5000）、RX 6400/6500、集成显卡不支持。12GB 显卡需限制 vllm 显存占用（详见部署教程 0.0 节）。

我们实测了 RX 9070。其他型号欢迎[反馈](https://github.com/buptanswer/mineru-local/issues)。

> Windows 需 WSL2。原生 Linux 更简单——跳过 librocdxg。

## 快速开始

```bash
git clone https://github.com/buptanswer/mineru-local.git
cd mineru-local

# 安装 Python 依赖（仅 requests + httpx，极小）
uv sync

# 调用 AMD/WSL2 本地 API（需先在 WSL2 内启动 mineru-api）
uv run mineru_api_client.py example.pdf --full

# Markdown 清理（对标官网"输出为Markdown"）
uv run mineru_md_clean.py full.md -o clean.md

# 调用官网云 API（需 Token，无论什么 GPU 都能用）
uv run mineru_cli.py example.pdf --api-key <token>
```

## 文档导航

| 你想做什么 | 看这篇 |
|-----------|--------|
| 从零部署到 AMD 显卡 | [教程/MinerU本地部署教程.md](教程/MinerU本地部署教程.md) |
| 部署到 NVIDIA 云服务器 | [教程/N卡部署教程.md](教程/N卡部署教程.md) |
| 日常使用 (CLI/API/WebUI/公网) | [教程/MinerU本地使用指南.md](教程/MinerU本地使用指南.md) |
| 更新 MinerU 版本 | [教程/MinerU本地更新指南.md](教程/MinerU本地更新指南.md) |
| 管理/替换/下载模型 | [教程/MinerU模型管理指南.md](教程/MinerU模型管理指南.md) |
| 出问题速查 | [教程/MinerU速查与运维手册.md](教程/MinerU速查与运维手册.md) |
| ROCm 7.1 → 7.2 升级 | [教程/ROCm7.2升级指南.md](教程/ROCm7.2升级指南.md) |

原始参考文档在 [`参考文档/`](参考文档/) 目录下。

## 核心经验

**AMD 和 NVIDIA 的输出质量完全一致**——两者运行相同的 VLM 模型和 hybrid 流水线。差异在工程层面：

| | NVIDIA (官方) | AMD (本项目) |
|---|---|---|
| vllm 安装 | `pip install vllm` 一分钟 | 从源码编译，约需 2 小时 |
| PyTorch | `pip install torch --index-url cu124` | 锁定 2.11.0（2.12+ 在 WSL2 崩溃） |
| CONV 优化 | cuDNN 原生高效 | MIOpen 冷启动需预热（一次性） |
| 平台检测 | 开箱即用 | 需 patch vllm 两个文件（WSL2） |
| 推理速度 | 极快（基准测试参照 A10） | 与 N 卡旗舰级几乎持平（实测 RX 9070 甚至在版面提取阶段更快） |

**关键版本锁**：PyTorch 必须 2.11.x（2.12+ 在 WSL2 中无法使用）。其余组件（ROCm、Python、Ubuntu）有小幅灵活性——详见部署教程。

## 问题和反馈

- 部署中遇到问题 → [GitHub Issues](https://github.com/buptanswer/mineru-local/issues)
- 在其他 AMD 显卡上测试成功/失败 → 欢迎提 Issue 补充兼容性列表
- 有更好的方案 → 欢迎 PR

## 致谢

- [MinerU](https://github.com/opendatalab/MinerU) — 最优秀的开源文档解析引擎
- [Discussion #3662](https://github.com/opendatalab/MinerU/discussions/3662) (@healy-hub) — AMD RDNA 适配的开拓者
- [librocdxg](https://github.com/ROCm/librocdxg) — WSL2 GPU 桥接层
- [vllm](https://github.com/vllm-project/vllm) — 高性能 VLM 推理引擎

## License

本项目文档和脚本按 MIT 协议开源。MinerU 本身的 License 见[官方仓库](https://github.com/opendatalab/MinerU)。
