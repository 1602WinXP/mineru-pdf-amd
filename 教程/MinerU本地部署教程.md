# MinerU 本地部署完整教程

> Windows 11 + WSL2 + AMD RX 9070 (gfx1201, RDNA4, 16GB)
> ROCm 7.1.1 + PyTorch 2.11.0 + vllm 0.21.1 + MinerU 3.1.15
> hybrid-auto-engine，输出质量对标官网精准解析 API
>
> 参考来源：[Discussion #3662](https://github.com/opendatalab/MinerU/discussions/3662)、[AMD WSL2 指南](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installrad/wsl/howto_wsl.html)、[librocdxg](https://github.com/ROCm/librocdxg)
>
> **教程状态**：每一步均已在 RX 9070 上实际执行并验证通过（2026-05-24）。

---

## 0. 适用硬件与系统

| 项目 | 要求 |
|------|------|
| GPU | AMD RX 9070 / 9070 XT (gfx1201, RDNA4)，或 RX 7900 XTX/XT (gfx1100, RDNA3) |
| 系统 | Windows 11 22H2+ |
| WSL | WSL2, 内核 >= 5.15 |
| 磁盘 | >= 50GB 剩余空间 |
| 内存 | >= 16GB |
| 网络 | 需访问 GitHub、HuggingFace、PyTorch 官网 |

### 0.1 版本为什么这样选

| 组件 | 版本 | 为什么 |
|------|------|--------|
| Ubuntu | **22.04** (jammy) | Discussion #3662 作者及 vllm 官方均在此版本测试；24.04 的 cmake 3.28 太旧 |
| ROCm | **7.1.1** | 7.2 重命名了 cmake 包（hiprand→rocrand），vllm 编译需要额外 wrapper；7.1.1 经社区充分验证 |
| Python | **3.13** | 与 Discussion #3662 作者一致；3.12 也可用 |
| PyTorch | **2.11.0**（不可变更） | **唯一硬约束**：2.12+ 在 WSL2 中因 rocprofiler SDK 找不到 KFD 拓扑而崩溃 |
| vllm | **0.21.1rc1**（源码编译） | PyPI 上只有 CUDA 版 wheel |
| MinerU | **3.1.15** | 当前最新稳定版 |

> **ROCm 7.2 能用吗？** 理论上可以，但 MIOpen kernel 缓存问题和 7.1.1 一样（7.2 没有解决 RDNA 的 conv3d/空洞卷积问题）。如果换 7.2，需要额外处理 cmake 包名变更。本教程用 7.1.1 是经社区充分验证的选择。

---

## 第一步：安装 WSL2 和 Ubuntu 22.04

### 1.1 Windows PowerShell（管理员）

```powershell
# 首次安装
wsl --install -d Ubuntu-22.04

# 或更新已有 WSL
wsl --update
wsl --set-default-version 2
```

重启电脑。重启后会自动弹出 Ubuntu 终端，设置 **用户名**（建议 `dev`）和 **密码**（记住，后续 sudo 需要）。

### 1.2 检查 GPU

在 PowerShell 中：
```powershell
Get-WmiObject Win32_VideoController | Where-Object { $_.Name -like "*AMD*" } | Format-List Name, DriverVersion
```
确认能看到 `AMD Radeon RX 9070`。

### 1.3 进入 WSL2 并更新系统

```bash
wsl -d Ubuntu-22.04
```

```bash
sudo apt update && sudo apt upgrade -y
```

---

## 第二步：安装基础工具和 SDK

### 2.1 编译工具链

```bash
sudo apt install -y build-essential cmake git wget curl \
    python3.13 python3.13-venv python3.13-dev \
    libnuma-dev libdrm2 libhwloc-dev ninja-build \
    pkg-config libgl1-mesa-glx
# libgl1-mesa-glx: WSL2 上 OpenCV 需要，否则可能报 libGL.so.1 找不到
```

> Ubuntu 22.04 默认没有 Python 3.13，需要先加 PPA：
> ```bash
> sudo apt update && sudo apt install -y software-properties-common
> sudo add-apt-repository -y ppa:deadsnakes/ppa
> sudo apt update
> sudo apt install -y python3.13 python3.13-venv python3.13-dev
> ```

### 2.2 安装最新 CMake（关键！）

> Ubuntu 22.04 自带 cmake 3.22，vllm 构建需要 4.x。

```bash
sudo snap install cmake --classic
# 或从 Kitware 下载
# wget https://github.com/Kitware/CMake/releases/download/v4.0.0/cmake-4.0.0-linux-x86_64.sh
# sudo sh cmake-4.0.0-linux-x86_64.sh --prefix=/usr/local --skip-license
cmake --version  # 应显示 >= 4.0
```

### 2.3 Windows SDK（Windows 侧）

> 用于编译 librocdxg（WSL2 GPU 桥接层）。

1. 下载 [Windows SDK](https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/)
2. 安装后确认路径（版本号可能不同）：
   ```
   C:\Program Files (x86)\Windows Kits\10\Include\10.0.28000.0\
   ```

---

## 第三步：安装 ROCm 7.1.1

### 3.1 添加 ROCm 仓库

```bash
wget https://repo.radeon.com/rocm/rocm.gpg.key -O - | \
    sudo gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/rocm.gpg > /dev/null

# ⚠️ 注意：Ubuntu 22.04 的代号是 'jammy'，不是 'noble'
echo 'deb [arch=amd64] https://repo.radeon.com/rocm/apt/7.1.1 jammy main' | \
    sudo tee /etc/apt/sources.list.d/rocm.list

sudo apt update
```

### 3.2 安装 ROCm 基础组件

```bash
sudo apt install -y rocminfo hip-dev miopen-hip
```

约 96 个包，~3GB，需要几分钟。

### 3.3 修复 rocminfo 版本

> ⚠️ Ubuntu 仓库自带的 rocminfo 5.7.1 不认识 librocdxg，必须替换为 ROCm 7.1.1 版本。

```bash
sudo apt install -y --allow-downgrades rocminfo=1.0.0.70101-38~22.04
```

ROCm 版的版本号数字虽小（1.0.0 vs 5.7.1），但它才是正确版本，必须加 `--allow-downgrades`。

---

## 第四步：编译和安装 librocdxg（核心步骤）

> WSL2 没有 Linux KFD（Kernel Fusion Driver），GPU 无法直接被 ROCm 访问。
> librocdxg 通过 Windows DXCore 接口桥接 ROCm 和物理 GPU。

### 4.1 克隆和编译

```bash
cd ~
git clone https://github.com/ROCm/librocdxg.git
cd librocdxg
mkdir build && cd build

# ⚠️ 关键：WIN_SDK 必须指向 shared/ 子目录！
# 如果指向 SDK 根目录，会报 "fatal error: ntstatus.h: No such file or directory"
cmake .. -DWIN_SDK='/mnt/c/Program Files (x86)/Windows Kits/10/Include/10.0.28000.0/shared'
make -j$(nproc)
```

> SDK 版本号（`10.0.28000.0`）可能不同，在 Windows 的 `C:\Program Files (x86)\Windows Kits\10\Include\` 下查看实际版本。

### 4.2 安装和配置

```bash
sudo make install

# 确保系统加载 ROCm 的 libhsa-runtime64 而非 Ubuntu 旧版
sudo sh -c 'echo /opt/rocm/lib > /etc/ld.so.conf.d/rocm.conf'
sudo ldconfig

# 添加用户到 render 和 video 组
sudo usermod -a -G render,video $USER
```

### 4.3 设置环境变量

```bash
cat >> ~/.bashrc << 'EOF'
export HSA_ENABLE_DXG_DETECTION=1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE
export MINERU_MODEL_SOURCE=huggingface
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
EOF
source ~/.bashrc
```

### 4.4 重启 WSL 并验证 GPU

```bash
exit
```
在 PowerShell 中：
```powershell
wsl --shutdown
wsl -d Ubuntu-22.04
```
在 Ubuntu 中：
```bash
export HSA_ENABLE_DXG_DETECTION=1
/opt/rocm/bin/rocminfo | grep -A5 "Agent 2"
```

预期输出：
```
Agent 2
  Name:            gfx1201
  Marketing Name:  AMD Radeon RX 9070
  Vendor Name:     AMD
  Compute Unit:    56
```

> 如果只显示 CPU Agent 没有 GPU Agent：
> 1. 检查 `/dev/dxg` 是否存在
> 2. 确认 `HSA_ENABLE_DXG_DETECTION=1` 已设置
> 3. 确认 Windows AMD 驱动已安装
> 4. 确认已执行 `newgrp video` 或重新登录

---

## 第五步：创建 Python 虚拟环境 + PyTorch

### 5.1 创建项目目录和虚拟环境

```bash
mkdir -p ~/mineru_stable && cd ~/mineru_stable
python3.13 -m venv .venv
```

### 5.2 安装 PyTorch ROCm

```bash
.venv/bin/pip install --pre \
    torch==2.11.0+rocm7.1 \
    torchvision \
    pytorch-triton-rocm \
    --index-url https://download.pytorch.org/whl/rocm7.1
```

> ⚠️ **为什么必须用 2.11.0？**
> PyTorch 2.12.0+ 集成了 rocprofiler SDK，启动时调用 `rocprofiler_register_library_api_table`，该函数在 WSL2 中因找不到 `/sys/class/kfd/` 而崩溃。错误：`Found 0 rocprofiler agents and 2 HSA agents`。此问题在 PyTorch 修复 WSL2 兼容性之前无解。

### 5.3 验证 PyTorch GPU

```bash
.venv/bin/python -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'ROCm:   {torch.version.hip}')
print(f'GPU:    {torch.cuda.is_available()}')
print(f'Name:   {torch.cuda.get_device_name(0)}')
x = torch.randn(100, 100).cuda()
print(f'Test:   {(x @ x).shape} — PASS')
"
```

预期输出：
```
PyTorch: 2.11.0+rocm7.1
ROCm:   7.1.52802
GPU:    True
Name:   AMD Radeon RX 9070
Test:   torch.Size([100, 100]) — PASS
```

---

## 第六步：安装 ROCm 开发包（vllm 编译依赖）

> 这些包是 vllm 从源码编译所必需的。不能只用符号链接替代——需要真实的头文件（如 1.4MB 的 hipblas.h）。

```bash
echo <你的密码> | sudo -S DEBIAN_FRONTEND=noninteractive apt install -y \
    hipblas-dev \
    hiprand-dev \
    hipsparse-dev \
    hipsolver-dev \
    hipcub-dev \
    rocprim-dev \
    rocthrust-dev \
    rocblas-dev \
    rocrand-dev \
    hipfft-dev \
    hipblaslt
```

> **踩坑记录**：之前尝试手动创建 `hipblas.h → rocblas.h` 符号链接，但 rocblas.h 内部有 `#include "internal/rocblas-auxiliary.h"`，编译器从 hipblas 目录查不到 internal/ 路径。必须安装 hipblas-dev 获取真实的 1.4MB 完整头文件。

---

## 第七步：安装 amd-aiter 和 flash_attn

### 7.1 amd-aiter（AMD AI Tensor Engine）

```bash
cd ~
git clone --recursive https://github.com/ROCm/aiter.git
cd ~/mineru_stable
.venv/bin/pip install -e ~/aiter
```

### 7.2 flash_attn（ROCm 版）

> ⚠️ 必须 checkout 特定 commit `bba578d`——Discussion #3662 作者验证后续版本在 RDNA3 有 ~30% 性能回退。

```bash
cd ~
git clone --recursive https://github.com/Dao-AILab/flash-attention.git
cd flash-attention
git checkout bba578d43974c1d3ba157ab597124dd0fe2ccdb4

cd ~/mineru_stable
export FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE
.venv/bin/pip install --no-build-isolation -e ~/flash-attention
```

---

## 第八步：编译 vllm

### 8.1 准备源码和构建目录

```bash
cd ~
git clone https://github.com/vllm-project/vllm.git
cd vllm
# 回退到已验证的 commit（可选，最新版也可以）
git checkout 357fddf61
```

### 8.2 修复 Caffe2Targets.cmake（PyTorch ROCm cmake 包名兼容）

> ROCm 7.x 重命名了部分 cmake 包。PyTorch 2.11 的 cmake 文件引用了旧名称，需要修复。

```bash
# 检查当前 Caffe2Targets.cmake 中的库链接
grep "INTERFACE_LINK_LIBRARIES.*c10_hip" \
    ~/mineru_stable/.venv/lib/python3.13/site-packages/torch/share/cmake/Caffe2/Caffe2Targets.cmake
```

确认该行包含正确的 ROCm 7.x 包名（`roc::rocblas`, `roc::rocrand`, `roc::hipsparse`, `roc::rocsolver`）。如果不正确，手动编辑修复（保留 `hip::amdhip64` 和 `MIOpen` 不变）。

### 8.3 创建 cmake 包名别名 wrapper

> 某些 cmake 脚本仍查找 `hiprand` 而非 `rocrand`，需要创建 wrapper。

```bash
# hiprand → rocrand wrapper
sudo mkdir -p /opt/rocm/lib/cmake/hiprand
cat << 'EOF' | sudo tee /opt/rocm/lib/cmake/hiprand/hiprand-config.cmake
include(/opt/rocm/lib/cmake/rocrand/rocrand-config.cmake)
if(TARGET roc::rocrand AND NOT TARGET hip::hiprand)
  add_library(hip::hiprand ALIAS roc::rocrand)
endif()
EOF

# hipblas → rocblas wrapper
sudo mkdir -p /opt/rocm/lib/cmake/hipblas
cat << 'EOF' | sudo tee /opt/rocm/lib/cmake/hipblas/hipblas-config.cmake
include(/opt/rocm/lib/cmake/rocblas/rocblas-config.cmake)
if(TARGET roc::rocblas AND NOT TARGET hip::hipblas)
  add_library(hip::hipblas ALIAS roc::rocblas)
endif()
EOF
```

### 8.4 cmake 配置

```bash
mkdir -p ~/vllm_build

export PYTORCH_ROCM_ARCH=gfx1201    # 根据你的 GPU：gfx1100=7900XTX, gfx1201=9070

cmake -S ~/vllm -B ~/vllm_build \
    -G Ninja \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DVLLM_TARGET_DEVICE=rocm \
    -DVLLM_PYTHON_EXECUTABLE=/home/$USER/mineru_stable/.venv/bin/python \
    -DHIP_ROOT_DIR=/opt/rocm \
    -DROCM_PATH=/opt/rocm \
    -DCMAKE_PREFIX_PATH="/home/$USER/mineru_stable/.venv/lib/python3.13/site-packages/torch/share/cmake"
```

预期输出结尾：
```
-- Configuring done (105.6s)
-- Generating done
-- Build files have been written to: /home/dev/vllm_build
```

### 8.5 ninja 编译

```bash
cd ~/vllm_build
PYTORCH_ROCM_ARCH=gfx1201 ninja -j4
```

> `-j4` 限制 4 个并行编译任务，避免 16GB 内存 OOM。

预期输出结尾：
```
[39/39] Linking HIP shared module _rocm_C.abi3.so
```

编译后产物：
- `_C.abi3.so`（~85MB）
- `_moe_C.abi3.so`（~25MB）
- `_rocm_C.abi3.so`（~65MB）
- `_C_stable_libtorch.abi3.so`（~24MB）
- `cumem_allocator.abi3.so`、`spinloop.abi3.so`

### 8.6 复制 .so 文件 + 安装 vllm

```bash
# 复制编译产物到 vllm 包目录
cp ~/vllm_build/*.abi3.so ~/vllm/vllm/

# 安装 vllm（editable 模式）
cd ~/vllm
VLLM_TARGET_DEVICE=rocm PYTORCH_ROCM_ARCH=gfx1201 \
    ~/mineru_stable/.venv/bin/pip install -e . --no-deps --no-build-isolation
```

> `--no-deps` 跳过 vllm 的 Python 依赖安装（其中 `amd-quark>=0.8.99` 没有 Python 3.13 的 wheel）

### 8.7 安装 amdsmi（vllm 平台检测需要）

```bash
cp -r /opt/rocm/share/amd_smi ~/amd_smi
cd ~/amd_smi
~/mineru_stable/.venv/bin/pip install . --no-build-isolation
```

### 8.8 应用 vllm WSL2 平台检测 Patch（关键！）

> amdsmi 在 WSL2 中无法初始化（需要 Linux KFD 驱动，WSL2 不存在）。vllm 默认的 ROCm 检测依赖 amdsmi，在 WSL2 中会回退为 `UnspecifiedPlatform`，导致 `RuntimeError: Device string must not be empty`。

**Patch 1**：`~/vllm/vllm/platforms/__init__.py`——在 `rocm_platform_plugin()` 末尾增加 `torch.version.hip` 回退：

查找函数结尾的：
```python
    return "vllm.platforms.rocm.RocmPlatform" if is_rocm else None
```

替换为：
```python
    # WSL2 fallback: amdsmi requires Linux AMDGPU KFD driver which is absent in WSL2.
    if not is_rocm:
        try:
            import torch
            if torch.version.hip is not None:
                is_rocm = True
                logger.debug("Confirmed ROCm platform via torch.version.hip (WSL2 fallback).")
        except Exception:
            pass

    return "vllm.platforms.rocm.RocmPlatform" if is_rocm else None
```

**Patch 2**：`~/vllm/vllm/platforms/rocm.py`——修改 `_get_gcn_arch()` 优先使用 `torch.cuda` 而非 amdsmi：

将函数体替换为：
```python
def _get_gcn_arch() -> str:
    # WSL2: amdsmi requires Linux KFD driver, absent in WSL2.
    # Use torch.cuda.get_device_properties as primary method.
    try:
        return torch.cuda.get_device_properties("cuda").gcnArchName
    except Exception:
        pass
    try:
        return _query_gcn_arch_from_amdsmi()
    except Exception as e:
        raise RuntimeError(
            "Failed to detect AMD GPU GCN architecture."
        ) from e
```

### 8.9 验证 vllm

```bash
export HSA_ENABLE_DXG_DETECTION=1
~/mineru_stable/.venv/bin/python -c "
from vllm.platforms import current_platform
print('Platform:', type(current_platform).__name__)
print('is_rocm:', current_platform.is_rocm())
print('device_type:', current_platform.device_type)
"
```

预期输出：
```
Platform: RocmPlatform
is_rocm: True
device_type: cuda
```

---

## 第九步：安装 MinerU + 应用 RDNA 适配 Patch

### 9.1 安装 MinerU

```bash
cd ~/mineru_stable
# ⚠️ AMD ROCm 用户用 pip 而非 uv pip
# 官方推荐 uv pip，但在 AMD ROCm 环境下 uv pip 的依赖解析会主动将
# 已安装的 ROCm PyTorch 替换为 CUDA 版。pip 则保留已安装版本。
.venv/bin/pip install 'mineru[core]' -i https://pypi.mirrors.ustc.edu.cn/simple/
```

> 如果 `mineru[core]` 覆盖了 PyTorch，立即重装：
> ```bash
> .venv/bin/pip install --force-reinstall \
>     torch==2.11.0+rocm7.1 torchvision pytorch-triton-rocm \
>     --index-url https://download.pytorch.org/whl/rocm7.1
> ```

### 9.2 应用 Discussion #3662 RDNA 适配 Patch

> 以下 Patch 解决 AMD RDNA 架构上 MIOpen 的卷积 kernel 冷启动问题（每次遇到新的 shape 组合需要 1-7 秒搜索最优 kernel）。

#### Patch A：`predict_rec.py` — imgW 32 字节对齐

文件：`~/mineru_stable/.venv/lib/python3.13/site-packages/mineru/model/utils/tools/infer/predict_rec.py`

在 `imgW = max(min(imgW, self.limited_max_width), self.limited_min_width)` 之后增加：
```python
        imgW = math.ceil(imgW / 32) * 32
```

#### Patch B：`predict_rec.py` — batch 填充避免最后一批冷启动

在 `norm_img_batch = np.concatenate(norm_img_batch)` 之前增加：
```python
                # AMD RDNA MIOpen batch padding patch
                actual_batch_size = len(norm_img_batch)
                if actual_batch_size < batch_num:
                    pad_size = batch_num - actual_batch_size
                    pad_img = np.zeros_like(norm_img_batch[0])
                    for _ in range(pad_size):
                        norm_img_batch.append(pad_img)
```

在同一函数内，将 `for rno in range(len(rec_result)):` 改为：
```python
                # 只处理实际图像，忽略填充。
                for rno in range(actual_batch_size):
```

#### Patch C：`predict_det.py` — 内存连续性检查

文件：`~/mineru_stable/.venv/lib/python3.13/site-packages/mineru/model/utils/tools/infer/predict_det.py`

在 `inp = inp.to(self.device)` 之后增加：
```python
            # Check format (AMD RDNA contiguous memory patch)
            if not inp.is_contiguous():
                inp = inp.contiguous()
```

### 9.3 无需应用的 Patch

| Patch | 说明 |
|:------|:-----|
| vllm qwen2_vl.py conv3d→F.linear | vllm 0.21 内置 `Conv3dLayer._forward_mulmat()` 已实现此优化 |
| doclayout_yolo g2l_crm.py 空洞卷积→S2B | MinerU 3.x 已移除 doclayout_yolo，不适用 |

---

## 第十步：模型下载和首次测试

### 10.1 修复 WSL2 DNS（如需要）

WSL2 的 systemd-resolved 不完善，每次 `wsl --shutdown` 后 DNS 可能失效：

```bash
# 如果 ping huggingface.co 不通
sudo rm -f /etc/resolv.conf
sudo sh -c 'echo -e "nameserver 8.8.8.8\nnameserver 114.114.114.114" > /etc/resolv.conf'
```

### 10.2 创建测试 PDF 并运行

```bash
cd ~/mineru_stable && . .venv/bin/activate
export HSA_ENABLE_DXG_DETECTION=1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE
export MINERU_MODEL_SOURCE=huggingface
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1

# 创建测试 PDF
python -c "
with open('/home/\$USER/test.pdf', 'wb') as f:
    f.write(b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n')
"

# 首次运行（自动下载模型 ~2.3GB）
mineru -p ~/test.pdf -o ~/output -b hybrid-auto-engine
```

> 首次运行 VLM 模型加载 ~46s，后续可预热。Triton kernel JIT 编译 ~7s（首次），后续秒级。

模型自动下载到 `~/.cache/huggingface/hub/`：
- `models--opendatalab--MinerU2.5-Pro-2604-1.2B`（VLM 模型）
- `models--opendatalab--PDF-Extract-Kit-1.0`（pipeline 模型：Layout/OCR/MFR）

> 如果 huggingface.co 不通，改用 modelscope：
> ```bash
> export MINERU_MODEL_SOURCE=modelscope
> ```

---

## 第十一步：MIOpen 缓存预热（重要优化）

### 为什么需要？

AMD RDNA 的 MIOpen 在首次遇到新的卷积 shape 时，需搜索最优 kernel（冷启动），尤其当后两个维度是 32 的奇数次时延迟明显：

| 场景 | 冷启动耗时 | 预热后耗时 | 提升 |
|:-----|:----------|:----------|:----|
| OCR 检测 (1,3,544,672) | 1320ms | ~30ms | **44x** |
| OCR 检测 (1,3,416,704) | 1133ms | ~30ms | **38x** |

预热就是提前把所有常用 shape 跑一遍，让 kernel 缓存下来。缓存存储在 `~/.cache/miopen/`，重启不丢失，但升级 ROCm 后需重新运行。

### 预热脚本

```bash
cat > ~/mineru_stable/cache_warmer.py << 'PYEOF'
import argparse, torch, torch.nn as nn, torch.nn.functional as F
from tqdm import tqdm

def get_args():
    p = argparse.ArgumentParser(description="ROCm MIOpen Cache Warmer")
    p.add_argument("--device", type=str, default="cuda")
    p.add_argument("--max_side", type=int, default=960)
    p.add_argument("--step", type=int, default=32)
    return p.parse_args()

class MockOCRModel(nn.Module):
    def __init__(self, in_channels=3):
        super().__init__()
        self.stem = nn.Conv2d(in_channels, 16, 3, stride=2, padding=1)
        self.dw_3x3 = nn.Conv2d(16, 16, 3, stride=1, padding=1, groups=16)
        self.pw_1 = nn.Conv2d(16, 64, 1)
        self.dw_5x5 = nn.Conv2d(64, 64, 5, stride=2, padding=2, groups=64)
        self.pw_2 = nn.Conv2d(64, 128, 1)
        self.dw_3x3_s2 = nn.Conv2d(128, 128, 3, stride=2, padding=1, groups=128)
        self.pw_3 = nn.Conv2d(128, 256, 1)
        self.out_conv = nn.Conv2d(256, 64, 1)
        self.binarize_conv = nn.Conv2d(64, 1, 3, stride=1, padding=1)
        self.act = nn.ReLU()
    def forward(self, x):
        x = self.stem(x); x = self.act(x)
        x = self.dw_3x3(x); x = self.pw_1(x)
        x = self.dw_5x5(x); x = self.act(x); x = self.pw_2(x)
        x = self.dw_3x3_s2(x); x = self.pw_3(x)
        x = self.out_conv(x)
        x = F.interpolate(x, scale_factor=2, mode="bilinear", align_corners=True)
        x = self.binarize_conv(x)
        return x

def main():
    args = get_args()
    assert torch.cuda.is_available(), "GPU not available"
    device = torch.device(args.device)
    print("=" * 50)
    print("ROCm MIOpen Cache Warmer")
    print("=" * 50)
    model = MockOCRModel().to(device).eval()
    sizes = list(range(64, args.max_side + 1, args.step))
    combos = [(h, w) for h in sizes for w in sizes]
    print(f"Warming {len(combos)} shapes...")
    ok = 0
    with torch.no_grad():
        for h, w in tqdm(combos, desc="Warming"):
            try:
                model(torch.zeros((1, 3, h, w), device=device, dtype=torch.float32))
                ok += 1
            except RuntimeError as e:
                if "out of memory" in str(e):
                    torch.cuda.empty_cache()
    print(f"Done! {ok}/{len(combos)} shapes cached (~3-4 min)")
    print("Cache location: ~/.cache/miopen/")

if __name__ == "__main__":
    main()
PYEOF

cd ~/mineru_stable && . .venv/bin/activate
export HSA_ENABLE_DXG_DETECTION=1
python cache_warmer.py --device cuda --max_side 960 --step 32
```

841 个 shape 组合，约 3-4 分钟。

---

## 第十二步：日常使用

### 12.1 环境激活（每次启动 WSL 后）

```bash
cd ~/mineru_stable && . .venv/bin/activate
export HSA_ENABLE_DXG_DETECTION=1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE
export MINERU_MODEL_SOURCE=huggingface
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
```

> 以上环境变量已写入 `~/.bashrc`，新终端自动加载。

### 12.2 CLI 解析

```bash
# 单个文件
mineru -p input.pdf -o output_dir -b hybrid-auto-engine

# 整个目录
mineru -p /path/to/docs/ -o output_dir -b hybrid-auto-engine

# 指定语言（提升 OCR 精度）
mineru -p input.pdf -o output_dir -b hybrid-auto-engine -l ch
```

### 12.3 启动 WebUI

```bash
mineru-gradio --server-name 0.0.0.0 --server-port 7860
```
浏览器打开 `http://localhost:7860`，拖拽文件即可解析。

### 12.4 启动 API 服务

```bash
mineru-api --host 0.0.0.0 --port 8000
```
API 文档：`http://localhost:8000/docs`

---

## 第十三步：Docker 方案（可选，适合不想编译的用户）

如果不想从源码编译 vllm，可以用 Docker 运行：

```powershell
# Windows PowerShell
docker run -it \
    -v /usr/lib/wsl/lib/libdxcore.so:/usr/lib/libdxcore.so \
    -v /opt/rocm/lib/librocdxg.so:/usr/lib/librocdxg.so \
    --device=/dev/dxg \
    -e HSA_ENABLE_DXG_DETECTION=1 \
    --ipc=host --shm-size 8G \
    rocm/vllm:latest
```

---

## 性能参考

AMD RX 9070 (gfx1201, 16GB)，MIOpen 预热后，MinerU 3.1.15 + vllm 0.21：

| 阶段 | 首次 | 预热后 |
|:-----|:-----|:------|
| VLM 模型加载 | ~46s | ~3s |
| VLM 推理 (Triton JIT) | ~8s/it | ~2-3s/it |
| Two Step Extraction | ~8s | ~3-5s |
| Layout 预测 | 10+ it/s | 10+ it/s |
| OCR 检测 | 10+ it/s | 10+ it/s |
| 页面处理 | 80+ it/s | 80+ it/s |

---

## 常见问题

### Q1: rocminfo 显示 "ROCk module is NOT loaded"
确认 rocminfo 版本是 ROCm 7.1.1 而非 Ubuntu 5.7.1：
```bash
dpkg -l | grep rocminfo   # 应显示 1.0.0.70101
```
确认 `HSA_ENABLE_DXG_DETECTION=1` 已设置，`/dev/dxg` 存在。

### Q2: PyTorch 提示 "Found 0 rocprofiler agents"
PyTorch 2.12.0 的已知问题。必须用 2.11.0（第五步已验证）。

### Q3: vllm 报 "Device string must not be empty"
vllm 平台检测失败（回退为 UnspecifiedPlatform）。确认已应用第八步的 WSL2 Patch。

### Q4: vllm cmake 报 "hiprand not found" 或类似
确认已安装第六步的所有 ROCm 开发包，并创建了 8.3 的 cmake wrapper。

### Q5: mineru 安装后 GPU 不能用了
`mineru[core]` 拉取了 CUDA 版 PyTorch。按 9.1 末尾的方式重装 ROCm 版。

### Q6: 安装 mineru 时网络超时
尝试国内镜像：
```bash
.venv/bin/pip install 'mineru[core]' -i https://pypi.mirrors.ustc.edu.cn/simple/
```

### Q7: WSL2 重启后 GPU 不工作
```bash
# 1. 修复 DNS
sudo rm -f /etc/resolv.conf
sudo sh -c 'echo -e "nameserver 8.8.8.8\nnameserver 114.114.114.114" > /etc/resolv.conf'
# 2. 验证 GPU
export HSA_ENABLE_DXG_DETECTION=1
/opt/rocm/bin/rocminfo | grep -A5 "Agent 2"
# 3. 验证 PyTorch
cd ~/mineru_stable && .venv/bin/python -c "import torch; print(torch.cuda.is_available())"
```

---

## 涉及的 vllm WSL2 Patch 文件清单

如需重装 vllm，以下 Patch 需要重新应用：

| 文件 | 修改内容 |
|:-----|:--------|
| `vllm/platforms/__init__.py` | `rocm_platform_plugin()` 增加 `torch.version.hip` 回退 |
| `vllm/platforms/rocm.py` | `_get_gcn_arch()` 优先使用 `torch.cuda.get_device_properties` |
| `mineru/.../predict_rec.py` | imgW 32对齐 + batch padding + actual_batch_size |
| `mineru/.../predict_det.py` | contiguous 内存检查 |

---

*最后更新: 2026-05-24*
*实测环境: Windows 11 10.0.26200 + WSL2 Ubuntu 22.04 + AMD RX 9070 + ROCm 7.1.1 + PyTorch 2.11.0 + vllm 0.21.1rc1 + MinerU 3.1.15*
