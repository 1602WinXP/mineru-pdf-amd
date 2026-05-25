# MinerU 3.x AMD 显卡本地部署完整教程（全系 RDNA2/3/4 适用，输出质量对标官网 API）

## 一、痛点：AMD 显卡玩转大模型，到底卡在哪？

MinerU 是目前最强的开源 PDF/文档解析工具。官方团队专注于模型本身的性能突破，官方文档主要覆盖主流的 NVIDIA/CUDA 平台，其他算力生态则通过 GitHub Discussions 等板块由社区共同推进。此前，社区先驱已经贡献了非常有价值的 [Discussion #3662](https://github.com/opendatalab/MinerU/discussions/3662)（@healy-hub）适配分享，奠定了坚实基础。但随着 MinerU 升级到 3.x，部分组件和依赖发生了变化，老教程在新架构下需要不少调整。本文在社区前期经验的基础上，整理并实际跑通了一套适用于 3.x 的完整部署流程。

**结论先行：AMD 显卡能跑 MinerU 3.x，解析质量和 N 卡完全一致，速度也非常给力。**
唯一的代价是：PyPI 没有提供 AMD ROCm 版本的 vLLM 预编译 wheel，我们需要花 1 小时左右手动编译。

本文是一套**一步一动、实际验证过**的硬核部署教程。我们基于 **AMD RX 9070 (16GB) + Windows 11 WSL2 (Ubuntu 22.04) + ROCm 7.1.1** 跑通了完整流程，同样适用于全系 RDNA2/3/4 显卡（如 7900 / 7800 / 7700 / 7600 / 6900 / 6800 / 6700 等系列）。

---

## 二、部署环境配置

| 组件 | 版本 | 说明 |
| :--- | :--- | :--- |
| **系统** | Windows 11（WSL2 Ubuntu 22.04）或 原生 Linux | WSL2 用户需要 librocdxg 桥接层 |
| **ROCm** | 7.1.1 | 社区验证最充分的版本 |
| **PyTorch** | 2.11.0+rocm7.1 | **WSL2 用户必须锁定此版本**（原因见下文踩坑点） |
| **vLLM** | 0.21.1rc1 | 视觉语言大模型推理加速，需源码编译 |
| **MinerU** | 3.1.15 | 当前最新版核心包 |

---

## 三、部署五步法核心命令

详细步骤（手把手教程）可直接查阅我们的 GitHub 仓库：[buptanswer/mineru](https://github.com/buptanswer/mineru)。这里为您浓缩出最核心的五个步骤：

### 1. 基础依赖与 CMake 安装
WSL2 用户需准备 Windows 10/11 SDK。WSL2 内执行：
```bash
sudo apt update && sudo apt install -y build-essential git wget curl python3.13 python3.13-venv python3.13-dev libnuma-dev ninja-build pkg-config
# vllm 编译需要 cmake >= 4.0，Ubuntu 自带的太旧，使用 snap 安装最新版：
sudo snap install cmake --classic
```

### 2. 安装 ROCm 7.1.1 与 编译 librocdxg（WSL2 专享）
添加 AMD 官方源并安装核心组件：
```bash
echo 'deb [arch=amd64] https://repo.radeon.com/rocm/apt/7.1.1 jammy main' | sudo tee /etc/apt/sources.list.d/rocm.list
sudo apt update && sudo apt install -y rocminfo hip-dev miopen-hip
# 替换系统自带的旧版 rocminfo（降级为 1.0.0.70101 以识别 WSL 桥接）：
sudo apt install -y --allow-downgrades rocminfo=1.0.0.70101-38~22.04

# 编译 DXG 桥接（Linux 原生用户跳过此步）：
git clone https://github.com/ROCm/librocdxg.git
cd librocdxg/build
cmake .. -DWIN_SDK='/mnt/c/Program Files (x86)/Windows Kits/10/Include/<你的SDK版本>/shared'
make -j$(nproc) && sudo make install && sudo ldconfig
```

### 3. 创建 Python 3.13 虚拟环境并配置 PyTorch
```bash
mkdir ~/mineru_stable && cd ~/mineru_stable
python3.13 -m venv .venv
.venv/bin/pip install --pre torch==2.11.0+rocm7.1 torchvision pytorch-triton-rocm --index-url https://download.pytorch.org/whl/rocm7.1
```

### 4. 源码编译并 Patch 适配 vLLM
```bash
# 1. 准备源码
git clone https://github.com/vllm-project/vllm.git && cd vllm && git checkout 357fddf61

# 2. 编译并安装（gfx1201 换成你自己的架构，如 7900 为 gfx1100，6800 为 gfx1030）
export PYTORCH_ROCM_ARCH=gfx1201
cmake -S ~/vllm -B ~/vllm_build -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DVLLM_TARGET_DEVICE=rocm -DVLLM_PYTHON_EXECUTABLE=~/mineru_stable/.venv/bin/python -DHIP_ROOT_DIR=/opt/rocm -DROCM_PATH=/opt/rocm -DCMAKE_PREFIX_PATH="~/mineru_stable/.venv/lib/python3.13/site-packages/torch/share/cmake"
cd ~/vllm_build && ninja -j4
cp ~/vllm_build/*.abi3.so ~/vllm/vllm/
cd ~/vllm && VLLM_TARGET_DEVICE=rocm PYTORCH_ROCM_ARCH=gfx1201 ~/mineru_stable/.venv/bin/pip install -e . --no-deps --no-build-isolation
```
*编译完成后，需按照 [README 文档](https://github.com/buptanswer/mineru) 指引对 `vllm/platforms` 下的 `__init__.py` 和 `rocm.py` 两个文件打补丁，修复 WSL2 下 amdsmi 无法初始化导致的平台识别报错。*

### 5. 安装 MinerU 与 RDNA 补丁
```bash
.venv/bin/pip install 'mineru[core]' -i https://pypi.mirrors.ustc.edu.cn/simple/
```
*由于 RDNA 架构上 MIOpen 在遇到新尺寸卷积时会触发冷启动搜索（每次延迟几秒），需要手动对 `mineru/model/utils/tools/infer/` 下的 `predict_rec.py`（imgW 32 像素对齐 + 批次填充）和 `predict_det.py`（contiguous 连续性检查）打补丁，彻底消除延迟。*

---

## 四、技术总结：避坑指南

部署过程中，我们总结了五个最致命的"天坑"：

1. **PyTorch 2.12+ 闪退**：ROCm 官方在 PyTorch 2.12 中默认集成了 `rocprofiler`，但它强依赖 KFD（Linux 底层内核驱动）。WSL2 通过 librocdxg 映射并没有 KFD 拓扑，导致导入 `torch` 直接报错 `Found 0 rocprofiler agents`。**必须锁定 PyTorch 2.11.0**。
2. **符号链接导致编译失败**：编译 vLLM 时，切忌为了省事把 `hipblas.h` 指向 `rocblas.h`，因为头文件内部有相对路径的 include 引用。**必须用 `apt install hipblas-dev` 安装完整兼容包**。
3. **`uv pip` 覆盖 PyTorch**：`uv pip` 速度虽快，但依赖解析非常激进。直接用它安装 MinerU 会强制将已有的 ROCm 版 PyTorch 替换为官方 CUDA 版，导致 GPU 离线。**务必用原生 `pip`；若已被覆盖，立即强制重装 ROCm 版 PyTorch**。
4. **Ninja 编译 OOM**：vLLM 的 C++ 编译极其吃内存，默认多线程会直接打爆 16GB 物理内存。**编译时必须限制并发数为 `ninja -j4`**。
5. **WSL2 重启后网络不通**：WSL2 每次 shutdown 重启后 `resolv.conf` 可能被覆盖为无效配置，连不上 HuggingFace。**需手动写入 `nameserver 8.8.8.8`**。

---

## 五、实测数据对比（AMD 本地 vs NVIDIA 云服务器）

为了验证 AMD 本地部署的成效，我们使用 `example.pdf`（13 页）对比了本地运行的 **AMD RX 9070** 与云端部署的 **NVIDIA A10（24GB）**：

| 阶段 / 平台 | AMD RX 9070（本地 WSL2） | NVIDIA A10（云端 Ubuntu） | 结论 |
| :--- | :--- | :--- | :--- |
| **VLM 推理阶段** | 约 **6 秒**（1.98 it/s） | 约 **5 秒**（2.18 it/s） | N 卡微弱领先 |
| **版面与 OCR 阶段** | **< 1 秒**（61 it/s） | **~1 秒**（36 it/s） | **AMD 高带宽（640GB/s）优势明显，胜出** |
| **13 页总耗时** | **约 6-7 秒** | **约 6 秒** | **两者综合体验基本打平，输出质量完全一致** |

---

## 六、获取源码与反馈

完整的代码、配置文件、Patch 脚本和排错附录已开源至 GitHub 仓库。

👉 **GitHub 仓库地址**：[https://github.com/buptanswer/mineru](https://github.com/buptanswer/mineru)

如果您有其他显卡的适配经验，或在部署中遇到疑难问题，欢迎来 GitHub 提交 Issue 和 PR！
