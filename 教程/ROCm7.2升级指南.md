# Ubuntu 24.04 + ROCm 7.2.1 部署指南（路径 B）

> 已验证可行的 Ubuntu 24.04 (noble) + ROCm 7.2.1 + PyTorch 2.11.0+rocm7.2 + vllm main + MinerU 3.2.0 完整流程
> 与 [MinerU本地部署教程.md](MinerU本地部署教程.md) 的路径 A（22.04 + 7.1.1）形成互补
> 实测：RX 9070 上 Processing pages 65-71 it/s，略快于路径 A

---

## 0. 什么时候该选这条路径

| 你的情况 | 选哪条 |
|---------|:----:|
| 求稳，跟着社区主流走 | **路径 A**（22.04 + 7.1.1） |
| 想要最新 Linux 内核 / Wayland / glibc | **路径 B**（本文） |
| 用 RX 9060 XT 等新发布的 RDNA4 显卡 | **路径 B**（7.2.1 才正式收录） |
| 已经装好 24.04 不想重来 | **路径 B**（24.04 + 7.1.1 不可行，详见下） |
| 需要 librocdxg 生产级特性 | **路径 B**（7.2.1 起 librocdxg 标记为生产级） |

⚠️ **明确不可行的组合：Ubuntu 24.04 + ROCm 7.1.1**

24.04 的 ROCm 7.1.1 仓库基于 LLVM 20（22.04 用 LLVM 17）。但 ROCm 头文件和 vllm 代码当初是按 LLVM 17 写的，没适配 LLVM 20 的语法收紧。第二轮验证遇到 7 个连环错误（`__hip_internal::conditional` 未定义、`__activemask` 未声明、`__AMDGCN_WAVEFRONT_SIZE` 未定义、`operator+(float2)` 重定义冲突、FP8 `h2r.x.data` 类型错误等），其中 FP8 错误需要改 vllm C++ 源码且修一个会冒出更多。**判定为不可行，请直接装 7.2.1**。

ROCm 7.2.1 升级到 LLVM 22 并修复了大部分兼容性问题，只剩 5 个头文件层面的小补丁，可控。

---

## 1. ROCm 7.2 相比 7.1 的关键变化

理解这些有助于你判断坑出在哪。

### 1.1 硬件支持

- **RDNA 4 正式列入**：RX 9070 / 9070 XT / 9070 GRE / 9060 XT / 9060 XT LP（gfx1200/gfx1201）在 7.2 中从"实验性"升级为"正式支持"
- **RDNA 3 中端补齐**：RX 7700 系列（gfx1101）官方收录
- **Ryzen AI APU 核显 Preview**：Strix Halo / Strix Point 的 RDNA 3.5 核显（gfx1150/gfx1151）获得 Preview 支持

### 1.2 WSL2 / Windows 增强

| 维度 | 7.1.1 | 7.2.1 |
|------|------|------|
| librocdxg 状态 | 实验性 | **生产级**（三方解耦：Windows 驱动、ROCm 版本、librocdxg 独立更新） |
| WSL2 GPU 穿透 | 不稳定 | ✅ 官方验证 |
| 核显 AI（核显 WSL） | 不支持 | ✅ 首次支持 |

### 1.3 LLVM 版本变化（坑的根源）

| ROCm 版本 | Ubuntu 22.04 (jammy) | Ubuntu 24.04 (noble) |
|-----------|---------------------|---------------------|
| 7.1.1 | LLVM 17 | LLVM 20（不兼容） |
| 7.2.1 | — | **LLVM 22**（已修复大部分问题） |

### 1.4 库性能（社区实测）

- hipBLASLt 在 Qwen3-30B 推理上实测提升 106%（在线 GEMM 调优 + Swizzle 内存访问优化）
- RDNA 4 上的 ComfyUI SDXL 比 6.4.4 提速 2.6 倍，Flux S 提速 5.2 倍（AMD CES 2026 官方基准）

### 1.5 没解决的问题

[Discussion #3662](https://github.com/opendatalab/MinerU/discussions/3662) 作者明确说过：*"ROCm 7.2 并没有解决 RDNA 上 3D 卷积，2D 卷积的基数倍数，空洞卷积的问题"*。所以你仍然需要执行 [MinerU本地部署教程.md](MinerU本地部署教程.md) 第十步的 RDNA 适配补丁和第十二步的 MIOpen 预热。**7.2 的性能优势主要来源于库优化和固件支持，不来自 MIOpen kernel 修复**。

---

## 2. 先把路径 A 的章节读懂

本文只描述路径 B **额外的**或**不同的**步骤。下列章节请先参照 [MinerU本地部署教程.md](MinerU本地部署教程.md) 的内容：

- 0.0 显卡兼容性表
- 第一步 1.1-1.4（WSL2 安装、`.wslconfig`）
- 第二步全节（网络、Hyper-V 防火墙、DNS、sudo 环境）
- 第三步 3.2 CMake 4.0.0 二进制包安装
- 第三步 3.3 Windows SDK 准备
- 第五步整节（librocdxg 编译）
- 第八步 amd-aiter（aiter 是 OK 的，flash_attn 有差异，见本文 6.2）
- 第十步 10.3 RDNA 适配补丁（**Python 路径要改为 3.12**）
- 第十一步、第十二步、第十三步（测试 / 预热 / 日常使用）

下面进入路径 B 特有的步骤。

---

## 3. 第三步：基础工具（24.04 包名差异）

```bash
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa  # 可选，24.04 默认 Python 3.12 已经够用
sudo apt update
sudo apt install -y build-essential git wget curl \
    python3.12 python3.12-venv python3.12-dev \
    libnuma-dev libdrm2 libhwloc-dev ninja-build \
    pkg-config libgl1
```

| 与 22.04 相比的差异 | 说明 |
|----|------|
| Python 3.12 而非 3.13 | 24.04 默认就是 3.12。`pytorch-triton-rocm` 的 ROCm 7.2 wheel 同时支持 cp312 和 cp313；如果你坚持要 3.13，仍需 deadsnakes PPA |
| `libgl1` 而非 `libgl1-mesa-glx` | 24.04 中后者已经移除，前者是替代品 |

CMake 4.0 二进制包安装与 22.04 完全相同（[MinerU本地部署教程.md 3.2 节](MinerU本地部署教程.md#32-安装最新-cmake直接装二进制包不要用-snap)）。

---

## 4. 第四步：安装 ROCm 7.2.1

### 4.1 添加 ROCm 仓库

```bash
wget https://repo.radeon.com/rocm/rocm.gpg.key -O - | \
    sudo gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/rocm.gpg > /dev/null

# 24.04 代号是 noble
echo 'deb [arch=amd64] https://repo.radeon.com/rocm/apt/7.2.1 noble main' | \
    sudo tee /etc/apt/sources.list.d/rocm.list

sudo apt update
```

### 4.2 安装基础组件

```bash
sudo apt install -y rocminfo hip-dev miopen-hip
```

### 4.3 修复 rocminfo / rocm-device-libs 版本

注意版本号后缀变为 `~24.04` 和 `1.0.0.70201`：

```bash
sudo apt install -y --allow-downgrades \
    rocminfo=1.0.0.70201-38~24.04 \
    rocm-device-libs=1.0.0.70201-38~24.04
```

"降级"的解释与路径 A 相同——见 [部署教程 4.3 节](MinerU本地部署教程.md#43-修复-rocminfo--rocm-device-libs-版本)。

---

## 5. 第五步：编译 librocdxg

完全照搬路径 A 的[第五步](MinerU本地部署教程.md#第五步编译-librocdxg仅-wsl2-用户)。`/opt/rocm` 已升级到 7.2.1，源码无需改动。

---

## 6. 第六、七、八步：Python 虚拟环境与依赖（24.04 + 7.2.1 适配）

### 6.1 虚拟环境与 PyTorch

```bash
mkdir -p ~/mineru_stable && cd ~/mineru_stable
python3.12 -m venv .venv

.venv/bin/pip install --pre \
    torch==2.11.0+rocm7.2 \
    torchvision \
    pytorch-triton-rocm \
    --index-url https://download.pytorch.org/whl/rocm7.2

# 验证
.venv/bin/python -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'ROCm:    {torch.version.hip}')
print(f'GPU:     {torch.cuda.is_available()} {torch.cuda.get_device_name(0)}')
"
```

期望看到 `2.11.0+rocm7.2` + `7.2.x` + `True AMD Radeon RX 9070`。

### 6.2 ROCm 开发包

包名与 22.04 路径 A 完全一致，**必须包含 `hipsparselt-dev`**（PyTorch ROCm 版的硬依赖）：

```bash
sudo DEBIAN_FRONTEND=noninteractive apt install -y \
    hipblas-dev hiprand-dev hipsparse-dev hipsparselt-dev \
    hipsolver-dev hipcub-dev rocprim-dev rocthrust-dev \
    rocblas-dev rocrand-dev hipfft-dev hipblaslt
```

### 6.3 aiter 与 flash_attn

aiter 与路径 A 一致：

```bash
cd ~ && git clone --recursive https://github.com/ROCm/aiter.git
cd ~/mineru_stable && .venv/bin/pip install -e ~/aiter
```

flash_attn 在 ROCm 7.2 + Python 3.12 下安装时，会因 build-isolation 拉到 CUDA 版 torch；用 `--no-build-isolation` 并预先确保环境里有 ROCm torch：

```bash
cd ~
git clone --recursive https://github.com/Dao-AILab/flash-attention.git
cd flash-attention
git checkout bba578d43974c1d3ba157ab597124dd0fe2ccdb4

cd ~/mineru_stable
export FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE
.venv/bin/pip install --no-build-isolation -e ~/flash-attention
```

⚠️ 装完后**立刻**复查 PyTorch（同路径 A 8.3 节）：

```bash
.venv/bin/python -c "import torch; print(torch.__version__)"
# 期望: 2.11.0+rocm7.2
# 如果显示 +cu130，按下面顺序恢复：
.venv/bin/pip install --force-reinstall torch==2.11.0+rocm7.2 torchvision pytorch-triton-rocm \
    --index-url https://download.pytorch.org/whl/rocm7.2
.venv/bin/pip uninstall -y triton triton-rocm
```

---

## 7. 第九步：编译 vllm（路径 B 重点）

24.04 + 7.2.1 这条路径上，cmake 编译 vllm 会撞到 6 个独立问题，每个都要打一个补丁。下面按"先打补丁、再编译"的顺序给出。**逐条执行不要跳**。

### 7.1 准备 build 依赖

```bash
~/mineru_stable/.venv/bin/pip install -U \
    "setuptools>=77.0.3" setuptools_scm setuptools_rust wheel
```

> 旧 commit `357fddf61` 的 pyproject.toml PEP 639 写法与新 setuptools 已经匹配，不需要再改源码。

### 7.2 克隆 vllm（必须用 main，不要旧 commit）

```bash
cd ~
git clone https://github.com/vllm-project/vllm.git
cd vllm
```

### 7.3 补丁 1：hipcc / hipconfig wrapper

ROCm 7.2.1 的 `hipcc.pl` 在 24.04 上找不到伴生 Perl 模块，并且硬编码调用 `clang-17`（但 ROCm 7.2 实际带的是 `clang-22`）。

```bash
# Perl 模块路径修复
sudo ln -sf /usr/bin/hipvars.pm /usr/share/perl5/hipvars.pm

# 让 hipcc.pl 调用的 clang-17 指向实际的 clang-22
sudo ln -sf /opt/rocm/llvm/bin/clang-22 /opt/rocm/llvm/bin/clang-17
sudo ln -sf /opt/rocm/llvm/bin/clang++   /opt/rocm/llvm/bin/clang++-17

# 确保 /opt/rocm/bin/hipcc 指向 .pl（某些 ROCm 7.2 包改成了 shell wrapper）
sudo ln -sf /usr/bin/hipcc.pl /opt/rocm/bin/hipcc
```

### 7.4 补丁 2-4：ROCm 头文件适配

24.04 + ROCm 7.2.1 的 `/opt/rocm/include/hip/` 下的几个头文件还残留着 LLVM 17 时代的写法，LLVM 22 不接受，需要修。下面三条 sed 命令是一次性的，直接执行：

```bash
# 补丁 2: __hip_internal::conditional → std::conditional
sudo find /opt/rocm/include/hip -name "*.h" \
    -exec sed -i 's/__hip_internal::conditional/std::conditional/g' {} +

# 补丁 3: warpSize 常量修复（gfx1201 wavefront 是 32）
sudo find /opt/rocm/include/hip -name "amd_warp_functions.h" \
    -exec sed -i 's/static constexpr int warpSize = __AMDGCN_WAVEFRONT_SIZE;/constexpr int warpSize = 32;/g' {} +

# 补丁 4: __activemask() → __builtin_amdgcn_read_exec()（只动 amd_warp_sync_functions.h）
sudo sed -i 's/__activemask()/__builtin_amdgcn_read_exec()/g' \
    /opt/rocm/include/hip/amd_detail/amd_warp_sync_functions.h
```

⚠️ **不要把补丁 4 扩展到 `amd_warp_functions.h`**——该文件里 `__activemask()` 是通过 `__builtin_amdgcn_read_exec()` 实现的（即定义本身），改了反而递归崩溃。只动 `amd_warp_sync_functions.h`。

### 7.5 补丁 5：vllm mamba operator+ 冲突

新版 ROCm 头文件已经定义了 `operator+(float2, float2)`，vllm 的 mamba 模块又定义一遍，编译时 `redefinition` 报错。注释掉 vllm 那一段即可：

```bash
cd ~/vllm
sed -i '109,121s/^/\/\/ /' csrc/mamba/mamba_ssm/selective_scan.h
```

> 行号 109-121 对应 vllm main 当前的 mamba operator+ 块。如果未来 vllm 改了行号，去 `selective_scan.h` 搜索 `operator+`，找到 `__device__ float2 operator+(float2 a, float2 b)` 那一段统一注释掉。

### 7.6 cmake 配置

```bash
mkdir -p ~/vllm_build

export PATH=/opt/rocm/bin:/opt/rocm/llvm/bin:$PATH
export PYTORCH_ROCM_ARCH=gfx1201   # 改成你的 gfx 代号

cmake -S ~/vllm -B ~/vllm_build -G Ninja \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DVLLM_TARGET_DEVICE=rocm \
    -DVLLM_PYTHON_EXECUTABLE=/home/$USER/mineru_stable/.venv/bin/python \
    -DHIP_ROOT_DIR=/opt/rocm \
    -DROCM_PATH=/opt/rocm \
    -DCMAKE_HIP_ARCHITECTURES=gfx1201 \
    -DCMAKE_PREFIX_PATH="/home/$USER/mineru_stable/.venv/lib/python3.12/site-packages/torch/share/cmake"
```

注意 `python3.12`（不是 22.04 路径的 `python3.13`）。

三处关键细节（`PATH` 必须包含 `/opt/rocm/bin`、`-DCMAKE_HIP_ARCHITECTURES` 必须显式、**不能**设 `-DCMAKE_HIP_COMPILER=hipcc`）与路径 A 9.4 节一致，详细原因不再重复。

### 7.7 ninja 编译

```bash
cd ~/vllm_build
PYTORCH_ROCM_ARCH=gfx1201 ninja -j4
```

期望看到 `41/41 通过`（vllm main 当前的 target 数）。耗时 10-15 分钟（24.04 的 LLVM 22 编译速度比 22.04 LLVM 17 快）。

### 7.8 安装 vllm（让 pip 完整解析依赖）

```bash
cp ~/vllm_build/*.abi3.so ~/vllm/vllm/

cd ~/vllm
VLLM_TARGET_DEVICE=rocm PYTORCH_ROCM_ARCH=gfx1201 \
    ~/mineru_stable/.venv/bin/pip install -e . --no-build-isolation
```

> vllm 0.21 main 的运行时依赖比旧 commit 多得多（`compressed_tensors`、`xgrammar`、`mistral_common`、`partial_json_parser`、`prometheus-client` 等）。不要加 `--no-deps`，让 pip 自动解析。装完后**第二次**复查 PyTorch（可能被 vllm 的依赖拉成 CUDA 版）：

```bash
.venv/bin/python -c "import torch; print(torch.__version__)"
# 如果不是 +rocm7.2:
.venv/bin/pip install --force-reinstall torch==2.11.0+rocm7.2 torchvision pytorch-triton-rocm \
    --index-url https://download.pytorch.org/whl/rocm7.2
.venv/bin/pip uninstall -y triton triton-rocm
```

### 7.9 补丁 6+7：vllm 平台检测与循环导入

这是 24.04 + 7.2.1 路径**必须**应用的两个补丁，原因与路径 A 9.10 节相同（amdsmi 不可用 + `logger.warning_once` 触发循环导入），补丁内容也完全一样：

- **补丁 6**：`~/vllm/vllm/platforms/__init__.py` 的 `rocm_platform_plugin()` 末尾加 `torch.version.hip` 回退
- **补丁 7**：`~/vllm/vllm/platforms/rocm.py` 的 `_get_gcn_arch()` except 块去掉 `logger.warning_once()`，改用 `sys.stderr.write()`

详细文本见路径 A 的 9.10 节，照搬即可。

### 7.10 验证 vllm

```bash
~/mineru_stable/.venv/bin/python -c "
from vllm.platforms import current_platform
print('Platform:', type(current_platform).__name__)
print('is_rocm:', current_platform.is_rocm())
print('device_type:', current_platform.device_type)
"
```

期望 `RocmPlatform / True / cuda`。

---

## 8. MinerU 安装与 RDNA 补丁（路径调整）

完全按 [MinerU本地部署教程.md 第十步](MinerU本地部署教程.md#第十步安装-mineru--rdna-适配) 执行，但 RDNA 补丁的目标文件路径里 `python3.13` 要换成 `python3.12`：

```bash
PYVER=$(.venv/bin/python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
MINERU_INFER_DIR="$HOME/mineru_stable/.venv/lib/python${PYVER}/site-packages/mineru/model/utils/tools/infer"
```

后续 patch A/B/C 完全相同。

MinerU 3.2.0 的代码结构与 3.1.x 略有调整，但 `predict_rec.py` 和 `predict_det.py` 的关键行没变，补丁仍然适用。如果未来某次升级后行号对不上，参考 [MinerU本地更新指南.md](MinerU本地更新指南.md) 的"找不到 patch 位置"说明。

---

## 9. 测试与预热

完全按路径 A 的[第十一、十二、十三步](MinerU本地部署教程.md#第十一步下载模型并测试)执行。

---

## 10. 性能数据（RX 9070，example.pdf 13 页）

| 阶段 | 路径 A (22.04 + 7.1.1) | 路径 B (24.04 + 7.2.1) |
|------|:---:|:---:|
| VLM 推理 (Two Step Extraction) | 6s (1.98 it/s) | ~5s 略快 |
| Layout Predict | ~1.5s | 1.2-1.5s |
| OCR-det | ~20 it/s | ~20 it/s |
| **Processing pages** | **61 it/s** | **65-71 it/s** |
| 13 页总耗时 | 6-7 秒 | 5-7 秒 |

路径 B 主要受益于 hipBLASLt 在线 GEMM 调优。如果你的工作负载以解析为主、单页复杂度高（多表格 / 多公式），路径 B 体验更好；如果就是日常 PDF，两条路径用起来差别有限。

---

## 11. 路径 B 全部补丁汇总（参考用）

升级或重装时，按下表顺序复查：

| # | 目标 | 命令 / 内容 | 何时需要 |
|---|------|-----------|---------|
| 1 | hipcc Perl 模块 | `ln -sf /usr/bin/hipvars.pm /usr/share/perl5/hipvars.pm` | 编译 vllm 前 |
| 2 | clang-22 → clang-17 符号链接 | `ln -sf /opt/rocm/llvm/bin/clang-22 /opt/rocm/llvm/bin/clang-17` | 编译 vllm 前 |
| 3 | ROCm 头文件 `__hip_internal::conditional` | `find ... sed std::conditional` | 编译 vllm 前 |
| 4 | ROCm 头文件 `warpSize` 常量 | `sed amd_warp_functions.h warpSize=32` | 编译 vllm 前 |
| 5 | ROCm 头文件 `__activemask` | `sed amd_warp_sync_functions.h __builtin_amdgcn_read_exec` | 编译 vllm 前 |
| 6 | vllm mamba `operator+` 冲突 | `sed -i '109,121s|^|//|' csrc/mamba/mamba_ssm/selective_scan.h` | 编译 vllm 前 |
| 7 | vllm `__init__.py` WSL2 平台回退 | `torch.version.hip` 兜底 | 安装 vllm 后 |
| 8 | vllm `rocm.py` 断循环导入 | `logger.warning_once → sys.stderr.write` | 安装 vllm 后 |
| 9 | mineru `predict_rec.py` imgW 对齐 + batch padding | 按教程 10.3 节 | 安装 mineru 后 |
| 10 | mineru `predict_det.py` contiguous 检查 | 按教程 10.3 节 | 安装 mineru 后 |

下面是把补丁 1-6 打包的脚本，复制保存为 `~/apply_rocm72_patches.sh` 一键应用：

```bash
#!/bin/bash
set -e
echo "[1/6] hipcc Perl module fix"
sudo ln -sf /usr/bin/hipvars.pm /usr/share/perl5/hipvars.pm
sudo ln -sf /usr/bin/hipcc.pl /opt/rocm/bin/hipcc

echo "[2/6] clang-22 → clang-17 symlink"
sudo ln -sf /opt/rocm/llvm/bin/clang-22 /opt/rocm/llvm/bin/clang-17
sudo ln -sf /opt/rocm/llvm/bin/clang++   /opt/rocm/llvm/bin/clang++-17

echo "[3/6] __hip_internal::conditional → std::conditional"
sudo find /opt/rocm/include/hip -name "*.h" \
    -exec sed -i 's/__hip_internal::conditional/std::conditional/g' {} +

echo "[4/6] warpSize constant fix"
sudo find /opt/rocm/include/hip -name "amd_warp_functions.h" \
    -exec sed -i 's/static constexpr int warpSize = __AMDGCN_WAVEFRONT_SIZE;/constexpr int warpSize = 32;/g' {} +

echo "[5/6] __activemask → __builtin_amdgcn_read_exec"
sudo sed -i 's/__activemask()/__builtin_amdgcn_read_exec()/g' \
    /opt/rocm/include/hip/amd_detail/amd_warp_sync_functions.h

echo "[6/6] vllm mamba operator+ conflict"
if [ -d ~/vllm ]; then
    cd ~/vllm
    git checkout csrc/mamba/mamba_ssm/selective_scan.h 2>/dev/null || true
    sed -i '109,121s/^/\/\/ /' csrc/mamba/mamba_ssm/selective_scan.h
fi

echo "All ROCm 7.2.1 + vllm patches applied."
```

---

## 12. 已知差异（路径 A vs 路径 B）

| 项目 | 路径 A (22.04 + 7.1.1) | 路径 B (24.04 + 7.2.1) |
|------|-----------|----------|
| Python 默认 | 3.10（教程用 3.13 PPA） | 3.12 |
| LLVM | 17 | 22 |
| cmake 包名差异 | 较少 | 较多（mamba/operator/__activemask 等需补） |
| vllm main 编译 | ~60 分钟 | ~30-45 分钟（LLVM 22 编译更快） |
| librocdxg 状态 | 实验性 | 生产级 |
| RDNA 4 官方支持 | 实验性 | ✅ 正式 |
| 社区验证深度 | 充分 | 我们独立验证一次 |
| 升级 ROCm 后维护成本 | 低 | 较高（每次需重应用 ROCm 头文件补丁） |

如果你以后想 7.2.1 → 7.2.3 升级（修了 vllm profiler 时间线 bug），需要重新跑一次 `apply_rocm72_patches.sh`，因为 apt 升级会把头文件覆盖回去。

---

## 13. 回退到路径 A

实在搞不定路径 B 也别硬撑。回到路径 A 步骤：

```powershell
# Windows PowerShell：导出当前 24.04 备份
wsl --export Ubuntu-24.04 D:\WSL\ubuntu-24.04-backup.tar
wsl --unregister Ubuntu-24.04
wsl --install -d Ubuntu-22.04
```

然后按 [MinerU本地部署教程.md](MinerU本地部署教程.md) 从头走一遍。第一次部署可能 2 小时，但跑通后就稳了。

---

*文档最后更新: 2026-05-27*
*实测环境：Windows 11 Pro + WSL2 Ubuntu 24.04 + AMD RX 9070 + ROCm 7.2.1 + PyTorch 2.11.0+rocm7.2 + vllm main + MinerU 3.2.0*
