# MinerU AMD GPU 本地部署教程

> 在 AMD 显卡上部署 MinerU 3.x + vllm + hybrid-auto-engine
> 我们实际跑通了 RX 9070，其他 RDNA2/3/4 显卡可按相同流程套用
> ROCm 7.1.1 + PyTorch 2.11.0 + vllm 0.21.1rc1 + MinerU 3.1.15

本教程参考了 [Discussion #3662](https://github.com/opendatalab/MinerU/discussions/3662)、[AMD WSL2 官方指南](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installrad/wsl/howto_wsl.html)和 [librocdxg](https://github.com/ROCm/librocdxg)。每一步都在 RX 9070 (gfx1201) + Windows 11 WSL2 上实际执行过（2026-05-25）。

**声明**：我们只在 RX 9070 上实测过。表格里其他显卡型号写"预期可用"，是因为流程相同（只需改 gfx 代号），但无法保证 100% 不出问题。试过之后欢迎来[提 Issue](https://github.com/buptanswer/mineru/issues) 补充兼容性数据。

---

## 0. 适用硬件与系统

### 0.0 哪些 AMD GPU 能用

vllm 的 CMakeLists.txt 只编译特定 gfx 架构的代码；ROCm 运行时也不一定认得所有显卡型号，有时候需要"伪装"成同代旗舰。

查自己的 gfx 代号：`rocminfo | grep gfx`

**显存要求**：hybrid-auto-engine 我们实测显存占用约 8.3GB（RX 9070 16GB，不含 Windows 系统占用）。官方最低要求是 8GB 显存。实际体验：
- 16GB：从容，随便跑
- 12GB：实测才用 8.3GB，完全够用
- 8GB：能跑起来，但余量很小，复杂文档可能 OOM。建议优先用 pipeline 后端

**各显卡的兼容情况**：

| 你的显卡 | 实际 gfx | 编译用 `PYTORCH_ROCM_ARCH` | 是否需要 `HSA_OVERRIDE_GFX_VERSION` | 备注 |
|---------|---------|--------------------------|-------------------------------------|------|
| RX 9070 XT / 9070 | gfx1201 | `gfx1201` | 不需要 | 我们实测通过 |
| RX 7900 XTX / XT / GRE | gfx1100 | `gfx1100` | 不需要 | 旗舰卡，ROCm 原生支持 |
| RX 7800 XT | gfx1102 | `gfx1102` | 如果 rocminfo 不识别则加 `11.0.0` | vllm 编译支持，但 ROCm 运行时可能不认 |
| RX 7700 XT | gfx1102 | `gfx1102` | 同上 | 12GB 够用 |
| RX 7600 XT | gfx1102 | `gfx1102` | 同上 | 16GB 版显存安全 |
| RX 7600 | gfx1103 | `gfx1103` | 如果 rocminfo 不识别则加 `11.0.0` | 8GB 显存，勉强能跑但不宽裕 |
| RX 6950 / 6900 / 6800 系 | gfx1030 | `gfx1030` | 不需要 | 16GB 版显存安全，未实测 |
| RX 6750 / 6700 XT | gfx1030 | `gfx1030` | 不需要 | 12GB 够用 |

**明确不支持的**：
- RDNA1 全系（RX 5000 系列，gfx1010）——vllm 不支持此架构
- RX 6400 / 6500 XT（gfx1031/gfx1032）——vllm 未包含这些变体
- 集成显卡（APU / 核显）——WSL2 下共享显存机制容易出问题，未测试

**关于 `HSA_OVERRIDE_GFX_VERSION`**：

ROCm 编译时（vllm 的 `PYTORCH_ROCM_ARCH`）和运行时（rocminfo 识别）是两套机制。某些中端卡的架构代码虽然在 vllm 编译列表中，但 ROCm 运行时可能不主动识别它们。

如果 `rocminfo` 看不到你的显卡，或者运行时 MIOpen 报 "no kernel found"，在 `~/.bashrc` 中加一行：

```bash
# RX 7000 系中端卡伪装成 7900 XTX（同是 RDNA3，架构兼容）
export HSA_OVERRIDE_GFX_VERSION=11.0.0

# RX 6000 系卡伪装成 6900 XT
export HSA_OVERRIDE_GFX_VERSION=10.3.0
```

然后 `source ~/.bashrc` 生效。这不会影响性能——同代架构内部是兼容的。

**8GB 显存遇到 OOM 怎么办**：

12GB 和 16GB 卡实测不会爆显存。8GB 卡如果遇到 `hipErrorOutOfMemory`：

1. 限制 vllm 的 KV Cache 占比：
   ```bash
   export VLLM_GPU_MEMORY_UTILIZATION=0.4
   ```
2. 或者换 pipeline 后端（不需要 vllm，显存占用低很多）：
   ```bash
   mineru -p input.pdf -o output -b pipeline -l ch
   ```

### 0.1 系统要求

| 项目 | 要求 |
|------|------|
| 系统 | Windows 11 (WSL2) 或 原生 Linux (Ubuntu 22.04/24.04) |
| 内存 | >= 16GB |
| 显存 | >= 8GB（推荐 16GB+，否则调低并发或换 pipeline 后端） |
| 磁盘 | >= 50GB |

如果你是原生 Linux（不是 WSL2），部署会简单不少——跳过第四步（librocdxg 编译），amdsmi 也能正常工作，vllm 不需要 patch。

### 0.2 为什么选这些版本

| 组件 | 版本 | 说明 |
|------|------|------|
| Ubuntu | 22.04 | vllm 编译需要 cmake >= 4.0，22.04 可通过 snap 安装。24.04 的 cmake 3.28 太旧且 snap 可能有冲突 |
| ROCm | 7.1.1 | 社区验证最充分的版本。7.2 理论上也能用，但 cmake 包名有变化（见下文），我们没实际测过 |
| Python | 3.13 | 和社区参考环境一致；3.12 也可以用 |
| PyTorch | 2.11.0 | 见下方详细解释 |
| vllm | 0.21.1rc1 | PyPI 只有 CUDA 版，所以需要从源码编译 |
| MinerU | 3.1.15 | 当前最新版 |

**关于 PyTorch 2.11.0**：如果你用 WSL2，必须锁定这个版本。原因如下：

ROCm 版 PyTorch 从 2.12 开始，官方把 rocprofiler 这个性能分析工具默认集成进去了——程序一启动就会自动调用它。但 rocprofiler 依赖 KFD（AMD 显卡在原生 Linux 里的底层驱动），而 WSL2 里并没有 KFD——WSL2 是通过微软的 librocdxg 技术"借用" Windows 的显卡驱动的。结果就是：新版 PyTorch 启动时找不到 KFD，直接报错退出（`Found 0 rocprofiler agents`）。

如果你用的是原生 Linux（不是 WSL2），这个限制就不存在，可以用更新的 PyTorch。

**关于 ROCm 7.2**：7.2 里 AMD 把一些 cmake 包重命名了（比如 `hiprand` 改成了 `rocrand`）。这会导致 vllm 的 cmake 配置找不到旧包名。如果你的 ROCm 版本恰好是 7.2，需要在第八步额外创建 cmake 别名文件（我们已经提供了命令）。但我们自己没在 7.2 上完整跑通过，所以不能保证全程无坎。已经装了 7.2 且不想降级的话，可以按教程试试——遇到 cmake 找不到包的错误就去第八步创建别名；实在搞不定就降回 7.1.1。

---

## 第一步：安装 WSL2 和 Ubuntu 22.04

（原生 Linux 用户跳过本节）

### 1.1 Windows PowerShell（管理员）

```powershell
wsl --install -d Ubuntu-22.04
wsl --set-default-version 2
```

重启电脑后会自动弹出 Ubuntu 终端，设置用户名和密码。

### 1.2 确认显卡被 Windows 识别

在 PowerShell 中：
```powershell
Get-WmiObject Win32_VideoController | Where-Object { $_.Name -like "*AMD*" } | Format-List Name, DriverVersion
```

### 1.3 进入 WSL2 并更新系统

```bash
wsl -d Ubuntu-22.04
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
```

Ubuntu 22.04 默认没有 Python 3.13，需要先加 PPA：
```bash
sudo apt update && sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.13 python3.13-venv python3.13-dev
```

### 2.2 安装最新 CMake

vllm 构建需要 cmake >= 4.0，Ubuntu 22.04 自带的是 3.22。

```bash
sudo snap install cmake --classic
cmake --version  # 确认 >= 4.0
```

### 2.3 Windows SDK（仅 WSL2 用户）

编译 librocdxg 需要 Windows SDK。

1. 下载 [Windows SDK](https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/)
2. 安装后确认路径存在（版本号可能不同）：
   ```
   C:\Program Files (x86)\Windows Kits\10\Include\10.0.28000.0\
   ```

---

## 第三步：安装 ROCm 7.1.1

### 3.1 添加 ROCm 仓库

```bash
wget https://repo.radeon.com/rocm/rocm.gpg.key -O - | \
    sudo gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/rocm.gpg > /dev/null

# Ubuntu 22.04 的代号是 'jammy'，注意不要写成 'noble'
echo 'deb [arch=amd64] https://repo.radeon.com/rocm/apt/7.1.1 jammy main' | \
    sudo tee /etc/apt/sources.list.d/rocm.list

sudo apt update
```

### 3.2 安装基础组件

```bash
sudo apt install -y rocminfo hip-dev miopen-hip
```

约 96 个包，3GB 左右，需要几分钟。

### 3.3 修复 rocminfo 版本

Ubuntu 软件源自带的 rocminfo 是 5.7.1 版本，它不知道 librocdxg 的存在，会报 "ROCk module NOT loaded"。需要替换成 ROCm 仓库的版本：

```bash
sudo apt install -y --allow-downgrades rocminfo=1.0.0.70101-38~22.04
```

注意：ROCm 版的版本号数字（1.0.0）比 Ubuntu 的（5.7.1）小，需要加 `--allow-downgrades`。

---

## 第四步：编译 librocdxg（仅 WSL2 用户）

原生 Linux 用户请跳过这一步。

### 4.1 这是什么

WSL2 没有原生 Linux 的 KFD 驱动，GPU 无法被 ROCm 直接访问。librocdxg 是 AMD 提供的一个桥接层——它通过 Windows 的 DXCore 接口让 ROCm 运行时能间接操作 GPU。

### 4.2 编译

```bash
cd ~
git clone https://github.com/ROCm/librocdxg.git
cd librocdxg
mkdir build && cd build

# 注意：WIN_SDK 必须指向 shared/ 子目录，不是 SDK 根目录
# 指向根目录会报 "fatal error: ntstatus.h: No such file or directory"
cmake .. -DWIN_SDK='/mnt/c/Program Files (x86)/Windows Kits/10/Include/10.0.28000.0/shared'
make -j$(nproc)
```

如果你的 SDK 版本号不是 10.0.28000.0，去 `C:\Program Files (x86)\Windows Kits\10\Include\` 下面看实际版本号。

### 4.3 安装

```bash
sudo make install
sudo sh -c 'echo /opt/rocm/lib > /etc/ld.so.conf.d/rocm.conf'
sudo ldconfig
sudo usermod -a -G render,video $USER
```

### 4.4 环境变量

```bash
cat >> ~/.bashrc << 'EOF'
export HSA_ENABLE_DXG_DETECTION=1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE
export MINERU_MODEL_SOURCE=huggingface
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
EOF

# 如果你的显卡不是 RX 7900/9070 这类旗舰型号，可能需要加一行伪装（见 0.0 节表格）
# echo 'export HSA_OVERRIDE_GFX_VERSION=11.0.0' >> ~/.bashrc

source ~/.bashrc
```

### 4.5 重启 WSL 并验证

```bash
exit
```
PowerShell：
```powershell
wsl --shutdown
wsl -d Ubuntu-22.04
```
Ubuntu：
```bash
export HSA_ENABLE_DXG_DETECTION=1
/opt/rocm/bin/rocminfo | grep -A5 "Agent 2"
```

应该能看到你的 AMD 显卡信息。如果只看到 CPU 没有 GPU：
- 检查 `/dev/dxg` 是否存在
- 确认 `HSA_ENABLE_DXG_DETECTION=1` 已设置
- 确认 Windows AMD 驱动已安装
- 试试 `newgrp video` 或重新登录

---

## 第五步：Python 虚拟环境 + PyTorch

### 5.1 创建虚拟环境

```bash
mkdir -p ~/mineru_stable && cd ~/mineru_stable
python3.13 -m venv .venv
```

### 5.2 安装 PyTorch（ROCm 版）

```bash
.venv/bin/pip install --pre \
    torch==2.11.0+rocm7.1 \
    torchvision \
    pytorch-triton-rocm \
    --index-url https://download.pytorch.org/whl/rocm7.1
```

如果你用的是原生 Linux（不是 WSL2），可以试试更新的 PyTorch 版本。但 WSL2 用户请锁定 2.11.0——原因在 0.2 节解释过了。

### 5.3 验证

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

如果 GPU 显示 True 且计算测试 PASS，继续下一步。

---

## 第六步：安装 ROCm 开发包

这些是 vllm 编译需要的头文件和库。注意 `hipblas-dev` 和 `hiprand-dev` 必须安装真正的包——之前我们试过手动创建符号链接 `hipblas.h → rocblas.h`，结果 rocblas.h 内部有 `#include "internal/rocblas-auxiliary.h"` 这样的相对路径引用，编译器从符号链接目录查不到 internal 子目录。

```bash
sudo DEBIAN_FRONTEND=noninteractive apt install -y \
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

---

## 第七步：安装 amd-aiter 和 flash_attn

### 7.1 amd-aiter

```bash
cd ~
git clone --recursive https://github.com/ROCm/aiter.git
cd ~/mineru_stable
.venv/bin/pip install -e ~/aiter
```

### 7.2 flash_attn

根据 Discussion #3662 作者的测试，flash_attn 在特定 commit 之后在 RDNA3 上有性能回退。我们使用的 commit 是他验证过的版本：

```bash
cd ~
git clone --recursive https://github.com/Dao-AILab/flash-attention.git
cd flash-attention
git checkout bba578d43974c1d3ba157ab597124dd0fe2ccdb4

cd ~/mineru_stable
export FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE
.venv/bin/pip install --no-build-isolation -e ~/flash-attention
```

更新的 commit 不一定有问题，但这是我们验证过的版本。如果你想试新版，可以跳过 checkout 这一步。

---

## 第八步：编译 vllm

这是整个部署里最耗时的一步，大概 30-60 分钟。

### 8.1 准备源码

```bash
cd ~
git clone https://github.com/vllm-project/vllm.git
cd vllm
git checkout 357fddf61   # 我们验证过的 commit，你也可以用最新版试试
```

### 8.2 检查 Caffe2Targets.cmake

ROCm 7.x 改了一些 cmake 包名。PyTorch 的 cmake 配置文件可能引用旧名称，需要确认一下：

```bash
grep "INTERFACE_LINK_LIBRARIES.*c10_hip" \
    ~/mineru_stable/.venv/lib/python3.13/site-packages/torch/share/cmake/Caffe2/Caffe2Targets.cmake
```

该行应该包含 `roc::rocblas`, `roc::rocrand`, `roc::hipsparse`, `roc::rocsolver` 这些名称。如果看到 `hip::hiprand` 或 `roc::hipblas` 等旧名称，需要手动改成新名称。

### 8.3 创建 cmake 别名（如果用 ROCm 7.2 的话可能需要）

如果你的 ROCm 版本是 7.1.1 且 vllm cmake 能找到所有包，可以跳过这步。如果报 "hiprand not found" 之类的错误，创建以下别名：

```bash
sudo mkdir -p /opt/rocm/lib/cmake/hiprand
cat << 'EOF' | sudo tee /opt/rocm/lib/cmake/hiprand/hiprand-config.cmake
include(/opt/rocm/lib/cmake/rocrand/rocrand-config.cmake)
if(TARGET roc::rocrand AND NOT TARGET hip::hiprand)
  add_library(hip::hiprand ALIAS roc::rocrand)
endif()
EOF

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

# 替换成你自己的 gfx 代号（见 0.0 节表格）
export PYTORCH_ROCM_ARCH=gfx1201

cmake -S ~/vllm -B ~/vllm_build \
    -G Ninja \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DVLLM_TARGET_DEVICE=rocm \
    -DVLLM_PYTHON_EXECUTABLE=/home/$USER/mineru_stable/.venv/bin/python \
    -DHIP_ROOT_DIR=/opt/rocm \
    -DROCM_PATH=/opt/rocm \
    -DCMAKE_PREFIX_PATH="/home/$USER/mineru_stable/.venv/lib/python3.13/site-packages/torch/share/cmake"
```

如果 cmake 报错找不到某个包，先去看第六步的包装了没，再看 8.3 的别名创建了没。

### 8.5 编译

```bash
cd ~/vllm_build
PYTORCH_ROCM_ARCH=gfx1201 ninja -j4
```

`-j4` 是限制并行编译数为 4。我们 16GB 内存的机器开 -j20 会 OOM 被系统 kill。如果你的内存更大可以适当调高。

编译成功后 `~/vllm_build/` 下会有几个 `.abi3.so` 文件。

### 8.6 安装 vllm

```bash
cp ~/vllm_build/*.abi3.so ~/vllm/vllm/

cd ~/vllm
VLLM_TARGET_DEVICE=rocm PYTORCH_ROCM_ARCH=gfx1201 \
    ~/mineru_stable/.venv/bin/pip install -e . --no-deps --no-build-isolation
```

`--no-deps` 是因为 vllm 有一个依赖 `amd-quark>=0.8.99` 没有 Python 3.13 的 wheel，跳过不影响核心功能。

### 8.7 安装 amdsmi

```bash
cp -r /opt/rocm/share/amd_smi ~/amd_smi
cd ~/amd_smi
~/mineru_stable/.venv/bin/pip install . --no-build-isolation
```

### 8.8 WSL2 平台检测修复（仅 WSL2 用户）

原生 Linux 用户跳过这一步。

amdsmi 在 WSL2 里无法初始化，因为它的底层依赖 KFD 驱动。vllm 默认用 amdsmi 来检测"是不是 ROCm 平台"，在 WSL2 里检测失败就会认为没有 GPU。需要改 vllm 的两个文件，让它改用其他方式判断。

**第一个文件**：`~/vllm/vllm/platforms/__init__.py`

找到 `rocm_platform_plugin()` 函数，把结尾的：
```python
    return "vllm.platforms.rocm.RocmPlatform" if is_rocm else None
```
替换为：
```python
    # WSL2: amdsmi doesn't work, fall back to torch.version.hip
    if not is_rocm:
        try:
            import torch
            if torch.version.hip is not None:
                is_rocm = True
        except Exception:
            pass

    return "vllm.platforms.rocm.RocmPlatform" if is_rocm else None
```

**第二个文件**：`~/vllm/vllm/platforms/rocm.py`

把 `_get_gcn_arch()` 函数体替换为：
```python
def _get_gcn_arch() -> str:
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

### 8.9 验证

```bash
export HSA_ENABLE_DXG_DETECTION=1
~/mineru_stable/.venv/bin/python -c "
from vllm.platforms import current_platform
print('Platform:', type(current_platform).__name__)
print('is_rocm:', current_platform.is_rocm())
print('device_type:', current_platform.device_type)
"
```

应该显示 `RocmPlatform / True / cuda`。

---

## 第九步：安装 MinerU + RDNA 适配

### 9.1 安装 MinerU

```bash
cd ~/mineru_stable
# AMD ROCm 用户注意：用 pip 不要用 uv pip
# uv pip 的依赖解析比较激进，会主动把已安装的 ROCm PyTorch 替换成 CUDA 版
.venv/bin/pip install 'mineru[core]' -i https://pypi.mirrors.ustc.edu.cn/simple/
```

如果发现 PyTorch 被覆盖了（`import torch; print(torch.__version__)` 显示不带 `rocm`）：
```bash
.venv/bin/pip install --force-reinstall \
    torch==2.11.0+rocm7.1 torchvision pytorch-triton-rocm \
    --index-url https://download.pytorch.org/whl/rocm7.1
```

### 9.2 应用 RDNA 适配补丁

AMD RDNA 架构上 MIOpen 遇到新的卷积尺寸组合时需要搜索最优 kernel（冷启动），每次可能花 1-7 秒。以下补丁来自 Discussion #3662 作者，作用是避免某些容易触发冷启动的场景。

以下几个文件位于 `.venv/lib/python3.13/site-packages/mineru/model/utils/tools/infer/` 下。

**predict_rec.py — imgW 对齐到 32**

在 `imgW = max(min(imgW, self.limited_max_width), self.limited_min_width)` 之后加一行：
```python
        imgW = math.ceil(imgW / 32) * 32
```

**predict_rec.py — 批次填充**

在 `norm_img_batch = np.concatenate(norm_img_batch)` 之前插入：
```python
                actual_batch_size = len(norm_img_batch)
                if actual_batch_size < batch_num:
                    pad_size = batch_num - actual_batch_size
                    pad_img = np.zeros_like(norm_img_batch[0])
                    for _ in range(pad_size):
                        norm_img_batch.append(pad_img)
```

然后把同一函数里的 `for rno in range(len(rec_result)):` 改成：
```python
                for rno in range(actual_batch_size):
```

**predict_det.py — 内存连续性检查**

在 `inp = inp.to(self.device)` 之后加：
```python
            if not inp.is_contiguous():
                inp = inp.contiguous()
```

### 9.3 不需要改的

| 原本 Discussion #3662 提到的 | 现状 |
|:--|:--|
| vllm qwen2_vl.py 的 conv3d 改 F.linear | vllm 0.21 已经自带了等价优化 |
| doclayout_yolo g2l_crm.py 的空洞卷积改造 | MinerU 3.x 已经移除了 doclayout_yolo |

---

## 第十步：下载模型并测试

### 10.1 DNS 修复（WSL2 常见问题）

WSL2 每次 `wsl --shutdown` 后 DNS 可能失效：

```bash
sudo rm -f /etc/resolv.conf
sudo sh -c 'echo -e "nameserver 8.8.8.8\nnameserver 114.114.114.114" > /etc/resolv.conf'
```

### 10.2 首次运行

```bash
cd ~/mineru_stable && . .venv/bin/activate
export HSA_ENABLE_DXG_DETECTION=1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE
export MINERU_MODEL_SOURCE=huggingface
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1

# 随便放一个 PDF 到 ~/test.pdf，或者用下面的最小 PDF 测试
mineru -p ~/test.pdf -o ~/output -b hybrid-auto-engine
```

首次运行会自动从 HuggingFace 下载约 2.3GB 的模型。VLM 模型首次加载约 46 秒，Triton 首次编译 kernel 约 7 秒——这些都是一次性的，后面就快了。

如果 HuggingFace 连不上，改用 ModelScope：
```bash
export MINERU_MODEL_SOURCE=modelscope
```

---

## 第十一步：MIOpen 缓存预热

### 为什么要预热

AMD 的 MIOpen 库在遇到新尺寸的卷积运算时，需要花时间搜索最优的 GPU kernel。预热就是提前把常用尺寸跑一遍，让 kernel 缓存到磁盘。缓存存在 `~/.cache/miopen/`，重启不丢失，只有升级 ROCm 后才需要重新跑。

以下数据来自 Discussion #3662 作者的测试（7900 XTX）：

| 输入尺寸 | 冷启动耗时 | 预热后 |
|---------|----------|-------|
| (1, 3, 544, 672) | 1320ms | ~30ms |
| (1, 3, 416, 704) | 1133ms | ~30ms |

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

if __name__ == "__main__":
    main()
PYEOF

cd ~/mineru_stable && . .venv/bin/activate
export HSA_ENABLE_DXG_DETECTION=1
python cache_warmer.py --device cuda --max_side 960 --step 32
```

约 841 个尺寸组合，3-4 分钟。

---

## 第十二步：日常使用

环境变量已写入 `~/.bashrc`，新终端自动生效。

```bash
cd ~/mineru_stable && . .venv/bin/activate

# CLI
mineru -p input.pdf -o output_dir -b hybrid-auto-engine

# WebUI
mineru-gradio --server-name 0.0.0.0 --server-port 7860

# API
mineru-api --host 0.0.0.0 --port 8000
```

---

## 性能参考

以下是我们用 `example.pdf` (13页) 在 RX 9070 上连续运行三次实测的数据（预热后，稳定状态）：

| 阶段 | 耗时/速度 |
|:-----|:------|
| VLM 推理 (Two Step Extraction) | 约 6 秒 (1.98 it/s) |
| 版面与 OCR (Processing pages) | < 1 秒 (61.13 it/s) |
| 13 页总耗时 | 约 6-7 秒 |

得益于 RX 9070 的 640 GB/s 高显存带宽，MinerU 在 Pipeline (版面与 OCR) 阶段的处理速度极快。你的实际耗时取决于 PDF 的页数和复杂程度。

---

## 常见问题

**Q: rocminfo 显示 "ROCk module is NOT loaded"**
检查 rocminfo 版本是 ROCm 版的（`dpkg -l | grep rocminfo` 应显示 1.0.0.70101），并且 `HSA_ENABLE_DXG_DETECTION=1` 已设置、`/dev/dxg` 存在。

**Q: PyTorch 报 "Found 0 rocprofiler agents"**
大概率是 PyTorch >= 2.12 被装上了。降回 2.11.0（见第五步）。如果你用原生 Linux 就不会有这个问题。

**Q: vllm 报 "Device string must not be empty"**
vllm 没检测到 ROCm 平台。确认 8.8 节的两个 patch 已应用（仅 WSL2 需要）。

**Q: cmake 报 "hiprand not found" 或类似**
确认第六步的包都已安装。如果还报错，去 8.3 节创建 cmake 别名。

**Q: 安装 mineru 后 GPU 不能用了**
`mineru[core]` 可能覆盖了 PyTorch。按 9.1 节末尾的命令重装。

**Q: WSL2 重启后 GPU 不工作**
依次执行：修复 DNS → 检查 `/dev/dxg` → `rocminfo` 验证 → `torch.cuda.is_available()` 验证。

---

## 涉及的改动清单

升级或重装 MinerU / vllm 后，以下改动需要重新应用：

| 文件 | 改了什么 | 谁需要 |
|:-----|:--------|:------|
| `vllm/platforms/__init__.py` | rocm_platform_plugin() 加 torch.version.hip 回退 | WSL2 用户 |
| `vllm/platforms/rocm.py` | _get_gcn_arch() 改用 torch.cuda | WSL2 用户 |
| `mineru/.../predict_rec.py` | imgW 32对齐 + batch padding | 所有 AMD 用户 |
| `mineru/.../predict_det.py` | contiguous 检查 | 所有 AMD 用户 |

---

*最后更新: 2026-05-25*
*实测环境：Windows 11 + WSL2 Ubuntu 22.04 + AMD RX 9070 + ROCm 7.1.1 + PyTorch 2.11.0 + vllm 0.21.1rc1 + MinerU 3.1.15*
