# MinerU AMD GPU 本地部署与加速方案

> **让 MinerU 在 AMD 显卡上以 vLLM + hybrid-auto-engine 满血运行！**
> 本项目是对官方文档中 AMD/ROCm 生态支持的有效补充。针对 MinerU 3.x 提供了一套完整的 ROCm 7.x + PyTorch 2.11.0 + vLLM 源码编译与部署方案，解析质量与速度对标 NVIDIA 旗舰显卡。
>
> 实测验证：RX 9070 (16GB) · 支持全系 RDNA2/3/4 显卡 · ROCm 7.1.1 · PyTorch 2.11.0 · vLLM 0.21.1rc1 · MinerU 3.1.15

---

## 💡 项目核心价值

官方团队专注于模型本身的迭代与底层解析能力的突破，对于多样化硬件生态主要通过社区（如 GitHub Discussions）进行共建。此前，社区先驱已经通过优秀的 [Discussion #3662](https://github.com/opendatalab/MinerU/discussions/3662) 奠定了 AMD 显卡适配的坚实基础。

本项目在这一社区成果的基础上，针对 MinerU 3.x 的全新架构（PyTorch 2.11.0、vLLM 0.21.x 等组件）做了全方位的演进、补丁开发与一致性完善。通过**一套完整的部署教程、WSL2/ROCm 平台补丁、MIOpen 预热机制**，让 AMD 用户能够：
1. **本地满血运行**：启用 vLLM 加速与 hybrid-auto-engine（视觉模型 + OCR），解析精度无损。
2. **极速解析**：实测 RX 9070 解析 13 页 PDF 仅需 **6-7 秒**，VLM 推理 **1.98 it/s**，OCR/版面阶段 **61 it/s**，总体效率逼近 NVIDIA A10 显卡。

---

## 🛠️ 部署与使用入口（快速开始）

不要盲目运行脚本！请按以下引导，一步步完成本地部署与测试。

### 第一步：确认硬件兼容性
**显存 ≥ 8GB（推荐 16GB+）的 AMD RDNA2/3/4 架构桌面显卡。**
- 支持：RX 9070 / 7900 / 7800 / 7700 / 7600 / 6900 / 6800 / 6700 系列。
- 不支持：RDNA1 全系（RX 5000 系列）、低端卡（RX 6400 / 6500 XT）、集成显卡（APU）。
- *8GB 显存显卡运行前需注意限制 vllm 显存占比（详见部署教程 0.0 节）。*

👉 **详细硬件说明请参考**：[0. 适用硬件与系统说明](教程/MinerU本地部署教程.md#0-适用硬件与系统)

### 第二步：开始本地部署
我们提供了一步一动的硬核实战教程，带你完成从零安装 WSL2、配置 ROCm 运行库、从源码编译 vLLM、以及应用 RDNA 性能补丁的全过程：

👉 **[点击这里阅读：MinerU AMD 本地部署教程](教程/MinerU本地部署教程.md)**

### 第三步：运行与日常使用
部署完成后，你可以通过命令行（CLI）、网页界面（WebUI）或本地 API 服务来使用 MinerU：

👉 **[点击这里阅读：MinerU 本地使用指南](教程/MinerU本地使用指南.md)**

本仓库根目录的 `mineru_api_client.py`（本地 API 客户端）与 `mineru_cli.py`（云端 API 客户端）可在部署完成后作为配套工具直接调用：

```bash
git clone https://github.com/buptanswer/mineru.git
cd mineru

# 安装极简依赖（仅 requests + httpx，无需 GPU）
uv sync

# 本地部署完成后，在 Windows 命令行一键调用本地 API 解析
uv run mineru_api_client.py example.pdf --full
```

---

## 📂 文档导航手册

如果在使用过程中遇到版本升级、模型管理或报错，请查阅以下手册：

| 你的需求 | 推荐阅读文档 |
| :--- | :--- |
| **升级 MinerU 版本** | [MinerU本地更新指南.md](教程/MinerU本地更新指南.md) (如何在更新时保留 AMD 补丁) |
| **升级 ROCm 版本** | [ROCm7.2升级指南.md](教程/ROCm7.2升级指南.md) (ROCm 7.1.1 升级 7.2.1 避坑指南) |
| **下载/替换/离线管理模型** | [MinerU模型管理指南.md](教程/MinerU模型管理指南.md) (解决模型与代码版本耦合问题) |
| **运行报错与性能调优** | [MinerU速查与运维手册.md](教程/MinerU速查与运维手册.md) (包含 26 项完整踩坑清单) |
| **云端 NVIDIA 部署对比** | [N卡部署教程.md](教程/N卡部署教程.md) (供有多卡或混合部署需求的用户参考) |

---

## 🤝 贡献与反馈

- **遇到部署问题**：欢迎提 [GitHub Issues](https://github.com/buptanswer/mineru/issues)。
- **其他显卡适配**：如果您在其他型号的 AMD 显卡上测试成功，欢迎提 Issue 补充兼容性列表。
- **项目优化**：有更好的方案或 Bug 修复欢迎直接提交 PR！

---

## 致谢

- [MinerU](https://github.com/opendatalab/MinerU) — 最优秀的开源文档解析引擎
- [Discussion #3662](https://github.com/opendatalab/MinerU/discussions/3662) (@healy-hub) — AMD RDNA 适配的开拓者
- [librocdxg](https://github.com/ROCm/librocdxg) — WSL2 GPU 桥接层
- [vllm](https://github.com/vllm-project/vllm) — 高性能 VLM 推理引擎

## License

本项目文档和辅助脚本按 MIT 协议开源。MinerU 本身的 License 见[官方仓库](https://github.com/opendatalab/MinerU)。
