# MinerU AMD RX 9070 本地部署项目

> Windows 11 + WSL2 (Ubuntu 22.04) + AMD RX 9070 (gfx1201, RDNA4, 16GB)
> ROCm 7.1.1 + PyTorch 2.11.0 + vllm 0.21.1 + MinerU 3.1.15
> **hybrid-auto-engine 全功能跑通，输出质量对标官网精准解析 API**

## 快速开始

```bash
# 安装依赖
uv sync

# 调用本地 API
uv run mineru_api_client.py example.pdf --full

# 清理 Markdown（对标官网"输出为Markdown"）
uv run mineru_md_clean.py full.md -o clean.md

# 调用官网云 API
uv run mineru_cli.py example.pdf --api-key <your_token>
```

## 项目结构

```
mineru/
├── README.md                  ← 你在这
├── pyproject.toml             ← uv 依赖 (requests, httpx)
├── mineru_api_client.py       ← 本地/远程 API 客户端
├── mineru_md_clean.py         ← Markdown 清理 (MM_MD → NLP_MD)
├── mineru_cli.py              ← 官网云 API 客户端
├── 教程/                      ← 我们写的实战教程（AMD 部署全流程）
│   ├── MinerU本地部署教程.md       # 从零部署，14 步
│   ├── N卡部署教程.md             # NVIDIA 云端部署
│   ├── MinerU本地使用指南.md       # CLI / WebUI / API / 公网 / IPv6
│   ├── MinerU本地更新指南.md       # 版本升级 + Patch 重打
│   ├── MinerU模型管理指南.md       # 模型下载 / 替换 / 本地
│   ├── MinerU速查与运维手册.md     # 速查卡片 + 26 踩坑清单
│   └── ROCm7.2升级指南.md         # ROCm A/B 测试
└── 参考文档/                  ← 官方文档 & 社区讨论（原始依据）
    ├── 基础使用 - MinerU.md        # 官方快速入门
    ├── MinerU命令行工具参考.md      # 官方 CLI 帮助 + 环境变量
    ├── MinerU进阶参数参考.md       # 官方 GPU 选择 + vllm 参数
    ├── MinerU模型源配置参考.md      # 官方模型源配置
    ├── MinerU扩展模块安装参考.md    # 官方 core/vllm/pipeline 变体
    ├── MinerU API 文档（新的）.md   # 官网云 API 文档
    ├── README_zh-CN.md             # MinerU 官方 README
    ├── Discussion-3662-AMD-RDNA-适配参考.md
    └── WSL2-依赖库补充.md          # WSL2 libGL 缺失修复
```

## 关键版本锁定

| 组件 | 版本 | 可否变更 |
|------|------|---------|
| PyTorch | **2.11.0** | 不可变 (2.12+ 在 WSL2 崩溃) |
| ROCm | 7.1.1 | 可试 7.2 (见 ROCm7.2升级指南) |
| Python | 3.13 | 3.12 也可用 |
| Ubuntu | 22.04 | 24.04 cmake 太旧 |
| vllm | 0.21.1 源码编译 | 随 MinerU 更新 |
| MinerU | 3.1.15 | 可按更新指南升级 |

## 输出质量

本地 AMD、云端 NVIDIA、官网 API — 三者使用**相同的 VLM 模型和 hybrid 流水线**，输出质量一致。差异：
- **速度**: NVIDIA (cuDNN) > AMD (MIOpen 需预热)
- **文件**: `--full` 参数可获得与官网 API 相同的 zip 内容
- **随机性**: VLM 每次推理有微小差异 (±10% 文本量)，属正常
