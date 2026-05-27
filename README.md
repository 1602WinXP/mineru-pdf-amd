# MinerU AMD GPU 本地部署与加速方案

> **让 MinerU 在 AMD 显卡上以 vLLM + hybrid-auto-engine 满血运行！**
> 本项目是对官方文档中 AMD / ROCm 生态支持的有效补充。针对 MinerU 3.x 提供了一套完整的 ROCm 7.x + PyTorch 2.11 + vLLM 源码编译与部署方案，解析质量与速度对标 NVIDIA 旗舰显卡。
>
> **实测验证（v1.2）**：RX 9070 (16GB) · 全系 RDNA2/3/4 桌面显卡 · MinerU 3.2.0 · vLLM main · 两条已跑通的 ROCm 路径

---

## 这套方案能给你什么

`example.pdf`（13 页）实测对比：

| 阶段 | AMD RX 9070（本地 WSL2） | NVIDIA A10（云端） |
|------|:-----------------------:|:-----------------:|
| VLM 视觉模型推理 | 6 秒（1.98 it/s） | 5 秒（2.18 it/s） |
| 版面与 OCR 处理 | < 1 秒（**61-71 it/s**） | ~1 秒（36 it/s） |
| **13 页 PDF 总耗时** | **6-7 秒** | ~6 秒 |
| 输出质量 | 与 N 卡完全一致 | — |

得益于 RX 9070 的 640 GB/s 高显存带宽，AMD 在版面 / OCR 阶段甚至比 NVIDIA A10 更快。**只要环境和补丁打对，AMD 显卡本地运行的效率完全不输云端主流 N 卡。**

---

## 💡 为什么需要这个项目

官方团队专注于模型本身的迭代与底层解析能力的突破，对于多样化硬件生态主要通过社区（如 GitHub Discussions）进行共建。此前，社区先驱已经通过优秀的 [Discussion #3662](https://github.com/opendatalab/MinerU/discussions/3662) 奠定了 AMD 显卡适配的坚实基础。

本项目在这一社区成果的基础上，针对 MinerU 3.x 的全新架构（PyTorch 2.11、vLLM 0.21.x 等组件）做了全方位的演进、补丁开发与一致性完善。我们经过**三轮独立部署验证**（22.04+7.1.1 跑通、24.04+7.1.1 撞墙、24.04+7.2.1 跑通），32 项踩坑清单全部填实，让 AMD 用户能够：

1. **本地满血运行**：启用 vLLM 加速与 hybrid-auto-engine（视觉模型 + OCR），解析精度无损。
2. **极速解析**：实测 13 页 PDF 仅需 6-7 秒，总体效率逼近 NVIDIA A10。
3. **两条已验证的部署路径**：稳定优先选 Ubuntu 22.04 + ROCm 7.1.1；想要 RDNA 4 正式支持选 Ubuntu 24.04 + ROCm 7.2.1。

---

## 🚦 在开始之前

| 项目 | 要求 |
|------|------|
| **硬件** | AMD RDNA2/3/4 桌面显卡，显存 ≥ 8GB（推荐 16GB+） |
| **系统** | Windows 11 (WSL2) 或 原生 Linux (Ubuntu 22.04/24.04) |
| **内存** | ≥ 16GB |
| **磁盘** | ≥ 50GB 可用空间 |
| **网络** | 稳定的国际网络（需下载 ROCm 仓库 ~3GB、PyTorch ~3GB、HuggingFace 模型 ~2.3GB） |
| **预算时间** | **约 2-3 小时**（其中 vllm 源码编译占 30-60 分钟） |
| **心理准备** | 这是一份硬核教程，每一步都需要按顺序执行，不要跳步 |

如果你只有 8GB 显存或网络不稳定，仍然可以部署，但需要按教程额外调整一些参数。如果你的显卡是 RDNA1（RX 5000 系列）、低端卡（RX 6400/6500 XT）或集成显卡，**不支持**，请到 [部署教程 0.0 节](教程/MinerU本地部署教程.md#0-适用硬件与系统) 查看完整的兼容性表。

---

## 🛠️ 部署三步走

### 第一步：选择部署路径（90% 的人选 A）

| 路径 | 系统 | ROCm | 适用场景 |
|------|------|------|---------|
| **🟢 A（强烈推荐）** | Ubuntu 22.04 (jammy) | 7.1.1 | **第一次部署、求稳定、不想多打补丁** — 这是你应该选的 |
| 🟡 B（较新） | Ubuntu 24.04 (noble) | 7.2.1 | 需要最新内核 / 用 RX 9060 等 7.2 才正式支持的卡 / 已经装好 24.04 不想重来 |

⚠️ **不要尝试 Ubuntu 24.04 + ROCm 7.1.1**：LLVM 版本不兼容，vllm 编译会撞死路。

### 第二步：按教程一步一步部署

我们提供了一步一动的硬核实战教程，从零安装 WSL2、配置 ROCm、编译 vLLM、应用 RDNA 补丁全程覆盖：

- 👉 **路径 A（推荐）**：[MinerU 本地部署教程.md](教程/MinerU本地部署教程.md)
- 👉 **路径 B（24.04 + 7.2.1）**：[ROCm 7.2 升级指南.md](教程/ROCm7.2升级指南.md)（先把路径 A 教程通读一遍，许多坑两条路都会踩）

**部署过程中遇到任何报错，直接到** [速查与运维手册的 32 项踩坑清单](教程/MinerU速查与运维手册.md#十一附录完整踩坑清单32-项) 按关键字搜索。

### 第三步：跑通后的日常使用

部署完成、`mineru -p test.pdf -o output` 能正常出结果后，你就可以通过 CLI / WebUI / API 三种方式使用 MinerU：

```bash
# 在 WSL2 中
cd ~/mineru_stable && . .venv/bin/activate

# CLI 命令行（批处理 / 脚本集成）
mineru -p input.pdf -o output_dir -b hybrid-auto-engine

# WebUI（浏览器拖拽上传）
mineru-gradio --server-name 0.0.0.0 --server-port 7860

# API 服务（程序调用，可对接局域网甚至公网）
mineru-api --host 0.0.0.0 --port 8000
```

👉 **完整用法、远程调用、输出格式说明等**：[MinerU 本地使用指南.md](教程/MinerU本地使用指南.md)

---

## 🧰 本仓库的辅助工具

部署完 MinerU 后，本仓库根目录提供了三个 Python 辅助脚本，可以让 Windows 端调用 WSL 内的 MinerU 服务更顺手。**这些脚本本身不需要 GPU，依赖极少**（仅 `requests` + `httpx`）：

| 脚本 | 用途 | 何时用 |
|------|------|--------|
| `mineru_api_client.py` | 调用**本地** MinerU API（你部署的服务） | 部署完成后在 Windows 命令行一键解析 |
| `mineru_cli.py` | 调用 MinerU **官网云端** API | 想用官网 API 而不是本地部署时（需要 API Key） |
| `mineru_md_clean.py` | 把 MinerU 输出的 Markdown 清理为纯文本 | 想要不含 `<details>` 块的 NLP_MD 格式时 |

用法：

```bash
git clone https://github.com/buptanswer/mineru.git
cd mineru

# 安装极简依赖（无需 GPU、无需 WSL）
uv sync

# 用法 1：本地部署已跑通后，从 Windows 一键调用本地 API
uv run mineru_api_client.py example.pdf --full

# 用法 2：直接调用官网云 API（不需要本地部署）
uv run mineru_cli.py example.pdf

# 用法 3：后处理 Markdown
uv run mineru_md_clean.py full.md -o clean.md
```

---

## 📂 完整文档地图

按你的需求挑选阅读：

| 你想做什么 | 看这个 |
|---------|-------|
| 🟢 **第一次从零部署**（路径 A） | [MinerU本地部署教程.md](教程/MinerU本地部署教程.md) |
| 🟡 部署到 Ubuntu 24.04（路径 B） | [ROCm7.2升级指南.md](教程/ROCm7.2升级指南.md) |
| 📖 部署完成后的日常使用 | [MinerU本地使用指南.md](教程/MinerU本地使用指南.md) |
| 🔄 升级 MinerU 版本（保留 AMD 补丁） | [MinerU本地更新指南.md](教程/MinerU本地更新指南.md) |
| 📦 下载 / 替换 / 离线管理模型 | [MinerU模型管理指南.md](教程/MinerU模型管理指南.md) |
| 🔧 运行报错、性能调优、踩坑速查 | [MinerU速查与运维手册.md](教程/MinerU速查与运维手册.md) |
| ☁️ NVIDIA 云端部署对比 | [N卡部署教程.md](教程/N卡部署教程.md) |
| 📚 官方原始文档（CLI / API / 模型源 / Discussion #3662 等） | [参考文档/](参考文档/) |

---

## 🤝 贡献与反馈

- **遇到部署问题**：欢迎提 [GitHub Issues](https://github.com/buptanswer/mineru/issues)。提 Issue 前先去[速查手册第十一节](教程/MinerU速查与运维手册.md#十一附录完整踩坑清单32-项)搜一下报错关键字，多半已经收录。
- **其他显卡适配**：如果你在其他型号的 AMD 显卡上测试成功（特别是 RX 7800 XT、6700 XT 等我们未实测的卡），欢迎提 Issue 补充兼容性数据。
- **项目优化**：有更好的方案或 Bug 修复欢迎直接提交 PR！

---

## 致谢

- [MinerU](https://github.com/opendatalab/MinerU) — 最优秀的开源文档解析引擎
- [Discussion #3662](https://github.com/opendatalab/MinerU/discussions/3662) (@healy-hub) — AMD RDNA 适配的开拓者
- [librocdxg](https://github.com/ROCm/librocdxg) — WSL2 GPU 桥接层
- [vllm](https://github.com/vllm-project/vllm) — 高性能 VLM 推理引擎

## License

本项目文档和辅助脚本按 MIT 协议开源。MinerU 本身的 License 见[官方仓库](https://github.com/opendatalab/MinerU)。
