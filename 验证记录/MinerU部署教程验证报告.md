# MinerU AMD GPU 本地部署教程 — 验证报告

> **目的**：逐条验证 [MinerU本地部署教程.md](../教程/MinerU本地部署教程.md) 的可行性
> **开始时间**：2026-05-26
> **验证机器**：Windows 11 Pro + WSL2 + AMD Radeon RX 9070 (gfx1201, 16GB)

---

## 验证计划概览

| 轮次 | 系统 | ROCm 版本 | vllm 编译 | hybrid-auto-engine | 状态 |
|------|------|-----------|:---:|:---:|------|
| 第一轮 | Ubuntu 22.04 | ROCm 7.1.1 | ✅ | ✅ | ✅ 成功 |
| 第二轮 | Ubuntu 24.04 | ROCm 7.1.1 | ❌ | — | ❌ 不兼容 |
| 第三轮 | Ubuntu 24.04 | ROCm 7.2.1 | ✅ | ✅ | ✅ 成功 |

---

## 前置准备

### 备份现有环境

- **时间**：2026-05-26 16:19
- **操作**：将已有的 mineru 环境（Ubuntu 22.04, PyTorch 2.11.0+rocm7.1, MinerU 3.1.15）通过 `wsl --export` 导出为 `ubuntu-22.04-mineru.tar`（74GB）
- **存放路径**：`C:\Users\14044\Desktop\mineru_backup\`
- **额外备份**：
  - `~/.bashrc` → `bashrc_backup`
  - pip freeze 列表 → `pip_freeze.txt`
  - rocminfo 输出 → `rocminfo.txt`
  - 四个 patch 文件 → `patches/` 目录
- **恢复方法**：`wsl --import Ubuntu-22.04 C:\WSL\Ubuntu-22.04 ubuntu-22.04-mineru.tar`

### Windows SDK 确认

- **路径**：`C:\Program Files (x86)\Windows Kits\10\Include\10.0.28000.0\`
- **shared/ 子目录**：存在（含 `ntstatus.h`，715KB）
- **结论**：✅ 满足教程第四步要求

---

## 第一轮：Ubuntu 22.04 + ROCm 7.1.1

**开始时间**：2026-05-26 16:20 | **完成时间**：2026-05-26 19:55 | **结果**：✅ 成功

### 关键操作时间线

| 步骤 | 耗时 | 备注 |
|------|------|------|
| 备份 & 重装系统 | ~10 min | 74GB 备份导出 |
| 第一步：系统更新 | ~5 min | apt update/upgrade |
| 第二步：基础工具 | ~10 min | Python 3.13 PPA + cmake 4.0.0 |
| 第三步：ROCm 7.1.1 | ~15 min | 含 rocminfo/device-libs 降级 |
| 第四步：librocdxg | ~5 min | 编译 + 安装 |
| 第五步：PyTorch | ~15 min | 2.11.0+rocm7.1 下载约 3GB |
| 第六步：ROCm 开发包 | ~20 min | 11 个包 |
| 第七步：aiter + flash_attn | ~15 min | git clone + 编译安装 |
| 第八步：vllm 编译 | ~60 min | cmake 调试 + ninja 编译（最耗时） |
| 第九步：MinerU | ~15 min | pip install + RDNA patches |
| 第十步：模型下载+运行 | ~20 min | 模型 ~2.3GB + 首次运行 |

### 教程纠正 / 补充说明

#### 1. Step 2.2 — `snap install cmake` 在 WSL2 中不可行

**问题**：WSL2 中 snapd 无法正常启动。snapd 依赖 systemd 和 mount namespace，两者在 WSL2 内核中均受限，`sudo snap install cmake --classic` 会永久阻塞。

**解决**：直接从 Kitware GitHub 下载 cmake 二进制包：
```bash
wget https://github.com/Kitware/CMake/releases/download/v4.0.0/cmake-4.0.0-linux-x86_64.tar.gz
tar -xzf cmake-4.0.0-linux-x86_64.tar.gz
sudo cp -r cmake-4.0.0-linux-x86_64/bin/* /usr/local/bin/
sudo cp -r cmake-4.0.0-linux-x86_64/share/* /usr/local/share/
```
**建议**：教程应提供 snap 替代方案。

#### 2. Step 2.1/3.2 — WSL2 网络 + Clash 代理问题

**问题**：如果用户使用 Clash Verge Rev 的 TUN 模式，WSL2 网络会异常（DNS 被劫持但代理不通）。

**最终方案**：Clash TUN 模式（Fake-IP）+ WSL2 `networkingMode=mirrored` + MTU 1500 + Stack System 是最优方案，无需配显式代理。注意必须先开 TUN 再启 WSL2。详见 **[参考-WSL2网络深度配置.md](参考-WSL2网络深度配置.md)**。

> 原报告写了"两种方案（系统代理或 TUN）"——实测后 TUN 模式更好。但需要正确配置 MTU 和 Hyper-V 防火墙。

**建议**：教程应在开头添加网络/代理配置说明。

#### 3-4. rocminfo / rocm-device-libs "降级"（已验证）

✅ 正确。Ubuntu 自带版本太旧（5.0.0/5.7.1），不包含 librocdxg 支持和新架构 bitcode，必须替换为 ROCm 仓库的 1.0.0.7xxxx 版本。`--allow-downgrades` 参数必须。APT Pinning 是更优雅的替代方案。

> ⚠️ "降级"是误导性说法——ROCm 仓库的 `1.0.0.70101` 版本号虽比 Ubuntu 的 `5.0.0` 小，但**代码其实更新**。AMD 在 ROCm 仓库中重新启动了自己的版本号方案（`1.0.0.xxxxx`），而 Ubuntu 沿用了旧版命名法。APT 只看数字大小所以认为是"降级"，实则是**版本号命名的历史遗留问题，操作是用新代码替换旧代码**。详见参考文件 "发现 3-4" 节。

#### 5. Step 6 — `hipsparselt-dev` 缺失（教程遗漏！）

**问题**：cmake 配置时报 `roc::hipsparselt` target not found。PyTorch ROCm 版在 `Caffe2Targets.cmake` 中硬编码了对 `roc::hipsparselt` 的依赖。

**解决**：`sudo apt install -y hipsparselt-dev`

#### 6. Step 8.4 — cmake 4.0 HIP 配置需要额外变量（教程不完整）

**问题**：cmake 4.0.0 中 HIP 检测逻辑变严格，在 WSL2 中需要：
- `PATH` 必须包含 `/opt/rocm/bin`（否则报 "Failed to find ROCm root directory"）
- 需要 `-DCMAKE_HIP_ARCHITECTURES=gfx1201`（否则报 "Failed to find a default HIP architecture"）
- ⚠️ 不能设置 `-DCMAKE_HIP_COMPILER=/opt/rocm/bin/hipcc`。这不是 hipcc 坏了——CMake 4.0 内置的 HIP 检测逻辑**主动拒绝 `hipcc` 包装器**（`CMakeDetermineHIPCompiler.cmake` 检测到编译器名含 `hipcc` 直接 `FATAL_ERROR`），要求使用底层 Clang 编译器而非 Perl 包装脚本。这也是为什么 24.04 需要为 hipcc.pl 打 clang 符号链接补丁（详见第三轮补丁 1）

**实际使用的 cmake 命令**：
```bash
export PATH=/opt/rocm/bin:/opt/rocm/llvm/bin:$PATH
export PYTORCH_ROCM_ARCH=gfx1201
cmake -S ~/vllm -B ~/vllm_build -G Ninja \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DVLLM_TARGET_DEVICE=rocm \
    -DVLLM_PYTHON_EXECUTABLE=/home/$USER/mineru_stable/.venv/bin/python \
    -DHIP_ROOT_DIR=/opt/rocm -DROCM_PATH=/opt/rocm \
    -DCMAKE_HIP_ARCHITECTURES=gfx1201 \
    -DCMAKE_PREFIX_PATH="/home/$USER/mineru_stable/.venv/lib/python3.13/site-packages/torch/share/cmake"
```

**建议**：教程 Step 8.4 应明确说明 PATH 和 `CMAKE_HIP_ARCHITECTURES` 的必要性。

#### 7. Step 8.6 — vllm pip 安装需要额外 build 依赖（教程遗漏）

**问题**：`pip install -e .` 报错缺少 `wheel`、`setuptools_rust`、`setuptools_scm`。

**解决**：
```bash
pip install wheel setuptools_rust setuptools_scm
```

**额外问题**：vllm commit `357fddf61` 的 pyproject.toml 与新版 setuptools (70.x/81.x) 不兼容：
- `license = "Apache-2.0"` 需改为 `license = {text = "Apache-2.0"}`
- `license-files = ["LICENSE"]` 需删除（setuptools 70+ 不支持此字段）

**建议**：教程应说明 build 依赖和 pyproject.toml 修复。推荐升级 `setuptools >= 77.0.3` 而非手动改 pyproject.toml（vllm 最新版已原生支持 PEP 639）。

#### 8. Step 8.8 — WSL2 平台检测补丁需要更精确（教程补丁有误）

**问题**：教程的 rocm.py 补丁使用正则替换 `_get_gcn_arch()` 函数体，会意外删除后续的模块级常量定义（如 `_ON_GFX942`、`_ON_GFX950` 等），导致 `ImportError: cannot import name '_ON_GFX942'`。

**解决**：只替换 `_get_gcn_arch()` 函数内部逻辑，保留所有后续常量：
```python
def _get_gcn_arch() -> str:
    # WSL2: amdsmi doesn't work, use torch.cuda first
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

同时需要保留 `_GCN_ARCH = _get_gcn_arch()` 这一行（教程补丁会意外删除）。

**建议**：教程 Step 8.8 应使用精确的函数体替换而非正则。vllm 最新版（commit `193ce8812`+）的 `_get_gcn_arch()` 已经自带 `torch.cuda` 回退——**在最新 vllm 上 rocm.py 不需要 WSL2 平台检测补丁**。

> **🆕 重新部署发现**：教程的 `rocm.py` 补丁实际上有**双重作用**——除了 WSL2 平台检测，它还顺手删掉了 `logger.warning_once()` 调用，从而**断开了循环导入链**。只用 `__init__.py` 的 WSL2 回退而不动 `rocm.py`，vllm 会因 `logger.warning_once` → `parallel_state` → `from vllm.platforms import current_platform` → 循环导入而崩溃。22.04 和 24.04 都有这个问题，23.04 + ROCm 7.1.1 也不例外。**`rocm.py` 的 logger 修复是必须的独立补丁**（见补丁 `patch_rocm_logger.py`），不只是为了平台检测。

#### 9. Step 7.2 / 9.1 — flash_attn 和 mineru[core] 安装会覆盖 ROCm PyTorch（教程警告不足）

**问题**：安装 `flash_attn` 或 `mineru[core]` 时，pip 依赖解析会安装 CUDA 版 PyTorch 和 `triton`，覆盖 ROCm 版本。

**现象**：`import torch` → `torch.__version__` 显示 `2.11.0+cu130`（而非 `+rocm7.1`），`torch.cuda.is_available()` → `False`

**修复**（每次被覆盖后执行）：
```bash
pip install --force-reinstall torch==2.11.0+rocm7.1 torchvision pytorch-triton-rocm --index-url https://download.pytorch.org/whl/rocm7.1
pip uninstall -y triton triton-rocm  # 清除冲突
```

⚠️ **重要**：不要删除 `triton` 目录——`pytorch-triton-rocm` 和 `triton` 的物理文件夹都叫 `triton/`，互删会连带破坏 ROCm 版文件。正确顺序：先 `--force-reinstall pytorch-triton-rocm`，再 `uninstall triton triton-rocm`。

#### 10. Step 8.7 — amdsmi 安装可选

`/opt/rocm/share/amd_smi` 目录可能不存在。WSL2 中 amdsmi 永远无法工作（依赖 KFD + `/dev/kfd`，WSL2 中不存在），补丁已绕过。**此步骤完全可选，失败可忽略。**

> 以上 10 个发现的详细技术解析（根因、原理、正确做法），见 **[参考-第一轮发现的技术解析.md](参考-第一轮发现的技术解析.md)**。

### 网络/代理配置总结（最终版）

经过三轮调试确定的 Clash TUN + WSL2 最优方案，**无需显式代理环境变量**（详见上文「关键网络配置」节）：
1. Clash TUN 模式（Fake-IP）、MTU 1500、Stack System
2. WSL2 `networkingMode=mirrored` + `dnsTunneling=true`
3. WSL2 内 DNS 指向 `223.5.5.5`（绕过 systemd-resolved 的 `127.0.0.53`）
4. 纯 TUN 模式自动代理所有流量，无需配置 `http_proxy`

### 最终环境确认

```bash
$ python -c "import torch; print(torch.__version__)"
2.11.0+rocm7.1
$ python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
True AMD Radeon RX 9070
$ python -c "from vllm.platforms import current_platform; print(current_platform.is_rocm())"
True
```

### 测试命令

```bash
cd ~/mineru_stable && . .venv/bin/activate
export HSA_ENABLE_DXG_DETECTION=1 FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE MINERU_MODEL_SOURCE=huggingface TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1

# Pipeline 后端（不需要 vllm）
mineru -p ~/test.pdf -o ~/output -b pipeline

# Hybrid-auto-engine（需要 vllm，质量最高）
mineru -p ~/test.pdf -o ~/output -b hybrid-auto-engine
```

### 性能数据（RX 9070, 1 页简单 PDF）

| 后端 | 版面分析 | OCR | 页面处理 |
|------|---------|-----|---------|
| pipeline | 12.80s (冷启动) | ~1.8s/2p | 35.87 it/s |
| hybrid-auto-engine | 4.41s | 13.33 it/s | 63.57 it/s |

（首次运行有 JIT 编译和模型加载开销，后续会更快）

### 教程总体评价（第一轮）

- ✅ **主线流程正确**：12 个步骤的骨架是对的，按顺序走能跑通
- ⚠️ **细节需要补充**：cmake 配置、依赖包、pyproject.toml 修复等
- ⚠️ **网络/代理问题**：教程未涉及，但国内用户大概率会遇到
- ⚠️ **PyTorch 被覆盖**：多次出现，需要更强的警告和明确的恢复步骤
- ❌ **rocm.py 补丁有 bug**：教程的补丁可能删除关键常量，建议更新

> 以上 10 个发现 + 补充发现（snap 不可用）的详细技术解析，见 **[参考-第一轮发现的技术解析.md](参考-第一轮发现的技术解析.md)**。

---

## 关键网络配置（所有轮次通用）

经过反复调试，确定最优方案：

### Clash 端
- TUN 模式（虚拟网卡）：**开启**
- Fake-IP DNS 模式：**开启**
- IPv6（全局）：**开启**
- IPv6 DNS 解析：**关闭**
- **TUN 设置中 MTU 改为 1500，Stack 改为 System**（WSL2 兼容关键！）

### WSL2 端（`.wslconfig`）
```ini
[wsl2]
memory=12GB
processors=8
swap=4GB
networkingMode=mirrored
dnsTunneling=true
firewall=true
autoProxy=true
```

### 代码（`/etc/wsl.conf`）
```ini
[boot]
systemd=true
[network]
generateResolvConf = false
[user]
default=dev
```

```bash
# /etc/resolv.conf
nameserver 223.5.5.5
```

> **注意**：Ubuntu 24.04 使用 systemd-resolved，`/etc/resolv.conf` 会自动指向 `127.0.0.53`。需手动覆盖。`wsl --shutdown` 后会重置，每次重启 WSL 后可能需要重新设置 DNS。

---

## 第二轮：Ubuntu 24.04 + ROCm 7.1.1

**开始时间**：2026-05-26 20:30 | **完成时间**：2026-05-27 00:35 | **结果**：❌ 不兼容

### 核心结论

**vllm commit `357fddf61` 无法在 Ubuntu 24.04 + ROCm 7.1.1 上编译**，即使使用 vllm 最新 main（`0f698af`）也不行。

根因：Ubuntu 24.04（noble）的 ROCm 7.1.1 使用 **LLVM 20**（22.04 版用 LLVM 17），但 ROCm 头文件和 vllm 代码未适配 LLVM 20 的语法收紧。

### 不兼容错误清单

| # | 错误 | 根因 | 可修？ |
|---|------|------|:---:|
| 1 | `hipcc.pl` 找不到 `hipvars.pm` | Perl 模块在 `/usr/bin/` 但不在 @INC 路径中 | ✅ |
| 2 | `hipcc.pl` 调用 `clang-17` 但系统只有 `clang-22` | hipcc 硬编码了 LLVM 版本 | ✅ |
| 3 | `__hip_internal::conditional` 未定义 | ROCm 7.1.1 头文件模板缺失 | ✅ |
| 4 | `__activemask()` 未声明 | LLVM 20 不再内置此函数 | ✅ |
| 5 | `__AMDGCN_WAVEFRONT_SIZE` 未定义 | LLVM 20 不再定义此宏 | ✅ |
| 6 | **`operator+(float2)` 重定义冲突** | 新版 ROCm 头文件已包含，vllm mamba 也定义 | ⚠️ |
| 7 | **FP8 `h2r.x.data` 类型错误** | LLVM 20 中 FP8 类型系统不兼容 | ❌ |

第 6-7 项需要修改 vllm 源码（非简单补丁），且修复一个后可能还会出现更多同类问题。**判定为不可行。**

### 24.04 特殊注意事项
- 代号 `noble`（非 `jammy`）
- 默认 Python 3.12（非 3.13）。教程里所有 `python3.13` 路径需改为 `python3.12`
- `libgl1-mesa-glx` 包在 24.04 中不存在，改用 `libgl1`
- ROCm 包版本后缀为 `~24.04`（非 `~22.04`）

---

## 第三轮：Ubuntu 24.04 + ROCm 7.2.1

**开始时间**：2026-05-27 00:40 | **完成时间**：2026-05-27 13:40 | **结果**：✅ 成功

### 结论：**可行！**（与 ROCm 7.1.1 形成鲜明对比）

ROCm 7.2.1 修复了 7.1.1 的大部分 LLVM 20 兼容性问题（`operator+`、`__activemask`、FP8 类型等），只需少量头文件补丁 vllm 即可编译。

### 关键操作时间线

| 步骤 | 耗时 | 备注 |
|------|------|------|
| 系统恢复 & 基础工具 | ~10 min | 从 `ubuntu-24.04-clean.tar` 导入 |
| ROCm 7.2.1 | ~15 min | noble 仓库 + rocminfo/device-libs 降级 |
| librocdxg + PyTorch | ~15 min | 2.11.0+rocm7.2 |
| aiter + flash_attn | ~20 min | flash_attn 需 `--no-deps` + CUDA_HOME hack |
| vllm cmake 配置 | ~5 min | 大量调试（hipcc wrapper、头文件补丁） |
| vllm ninja 编译 | ~10 min | 41/41 通过！ |
| vllm pip 安装 + 依赖 | ~30 min | 循环导入修复 + 逐个安装依赖 |
| MinerU 安装 + 测试 | ~15 min | 3.2.0 版，pipeline 通过 |

### vllm 编译所需补丁（5 个）

vllm 使用**最新 main**（commit `193ce8812`，2026-05-26），旧 commit `357fddf61` 已放弃。

#### 补丁 1：hipcc/hi pconfig wrapper
ROCm 7.2.1 的 `hipcc.pl` 硬编码 `clang-17`，但实际用的是 `clang-22`。

```bash
# 创建符号链接使 hipcc 能找到编译器
sudo ln -sf /opt/rocm/llvm/bin/clang-22 /opt/rocm/llvm/bin/clang-17
sudo ln -sf /opt/rocm/llvm/bin/clang++ /opt/rocm/llvm/bin/clang++-17
# 修复 Perl 模块路径
sudo ln -sf /usr/bin/hipvars.pm /usr/share/perl5/hipvars.pm
# 恢复原版 hipcc
sudo ln -sf /usr/bin/hipcc.pl /opt/rocm/bin/hipcc
```

#### 补丁 2：ROCm 头文件 — `__hip_internal::conditional`
```bash
sudo find /opt/rocm/include/hip -name "*.h" -exec sed -i 's/__hip_internal::conditional/std::conditional/g' {} +
```

#### 补丁 3：ROCm 头文件 — `warpSize`
```bash
sudo find /opt/rocm/include/hip -name "amd_warp_functions.h" -exec sed -i 's/static constexpr int warpSize = __AMDGCN_WAVEFRONT_SIZE;/constexpr int warpSize = 32;/g' {} +
```

#### 补丁 4：ROCm 头文件 — `__activemask()`
仅 `amd_warp_sync_functions.h` 中需要替换（`amd_warp_functions.h` 不该动，因为有 `__builtin_amdgcn_read_exec()` 的定义）：
```bash
sudo sed -i 's/__activemask()/__builtin_amdgcn_read_exec()/g' /opt/rocm/include/hip/amd_detail/amd_warp_sync_functions.h
```

#### 补丁 5：vllm 源码 — mamba operator+ 冲突
```bash
cd ~/vllm
sed -i '109,121s/^/\/\/ /' csrc/mamba/mamba_ssm/selective_scan.h
```

#### 额外补丁：vllm 平台检测 — `__init__.py`
vllm 0.21 最新版使用 `__getattr__` 懒加载 `current_platform`，但存在循环导入 bug（`system_utils.py` 等模块的 module-level import 在 `__init__.py` 加载完成前触发）。需要：
1. WSL2 回退：amdsmi 失败后检查 `torch.version.hip`
2. 早期 placeholder：在 `__init__.py` 开头设置 `current_platform = UnspecifiedPlatform()`
3. 末尾覆盖：所有插件加载后替换为真实平台

详见 `patch_vllm_full2.py`。

### 依赖安装注意事项

- `mineru[core]` 安装后 PyTorch 被覆盖为 CUDA 版：**每次安装新包后需重装 ROCm PyTorch**
- `pytorch-triton-rocm` 和 `triton-rocm` 共享 `triton/` 目录：卸载 `triton-rocm` 会删除共享文件，**必须重装 `pytorch-triton-rocm`**
- vllm 0.21 依赖极多：建议先 `pip install -e .`（不带 `--no-deps`）让 pip 装全依赖，再 force-reinstall ROCm PyTorch
- MinerU 3.2.0（当前 PyPI 最新版）使用的 VLM 模型是 `MinerU2.5-Pro-2605-1.2B`（不是教程的 2604 版）

### 当前状态

| 指标 | 状态 |
|------|:---:|
| ROCm 7.2.1 | ✅ |
| PyTorch 2.11.0+rocm7.2 GPU | ✅ |
| vllm 编译 | ✅ 41/41 |
| vllm 平台检测 is_rocm | ✅ True |
| vllm AsyncLLM 可导入 | ✅ |
| pipeline 后端 | ✅ 65 it/s |
| **hybrid-auto-engine** | ✅ **已修复** |

### hybrid-auto-engine 修复

**根因**：vllm 0.21 的 `rocm.py` 中 `_get_gcn_arch()` 调用 `logger.warning_once()`，该 logger 内部触发 `from vllm.distributed.parallel_state import is_local_first_rank`，在子进程（EngineCore）中形成**循环导入**，导致 `current_platform` 被设为 `UnspecifiedPlatform()`。
`UnspecifiedPlatform.check_if_supports_dtype()` 直接 `raise NotImplementedError`，导致 engine core 初始化失败。

**修复**（补丁 6+7）：
- 补丁 6 (`rocm.py`)：将 `logger.warning_once()` 替换为 `sys.stderr.write()`，断开循环导入链
- 补丁 7 (`__init__.py`)：保留 WSL2 回退（amdsmi 失败后检查 `torch.version.hip`），无需早期 placeholder 或同步解析

之前的 Hyper-V 防火墙放行**不是根因**（修复后防火墙规则仍在，但对 engine core 无影响）。

### RDNA 性能补丁

MinerU 3.2.0 代码结构与教程（基于 3.1.15）不同，补丁位置需调整。补丁脚本：`patch_rdna_320.py`。

### 最终性能（RX 9070, 1 页简单 PDF, 稳定态）

| 指标 | 实测 (24.04+7.2.1) | 教程基准 (22.04+7.1.1, 13页) |
|------|:---:|:---:|
| VLM/Two Step Extraction | 4.3s (单页) | ~1.98 it/s (13页批量) |
| Layout Predict | 1.2-1.5s | — |
| OCR-det | ~20 it/s | — |
| **Processing pages** | **65-71 it/s** | **61.13 it/s** |

Processing pages 速度**超过教程基准**。总体结论：**24.04 + ROCm 7.2.1 性能达标。**

### 24.04 + ROCm 7.2.1 全部补丁汇总

| # | 目标文件 | 用途 |
|---|---------|------|
| 1 | `/opt/rocm/llvm/bin/clang-17` | hipcc.pl 编译器符号链接 |
| 2 | `/opt/rocm/include/hip/` | `__hip_internal::conditional` → `std::conditional` |
| 3 | `/opt/rocm/include/hip/amd_warp_functions.h` | `warpSize` 常量修复 |
| 4 | `/opt/rocm/include/hip/amd_warp_sync_functions.h` | `__activemask()` → `__builtin_amdgcn_read_exec()` |
| 5 | `vllm/csrc/mamba/mamba_ssm/selective_scan.h` | operator+ mamba 冲突 |
| 6 | `vllm/vllm/platforms/rocm.py` | logger.warning_once → stderr（**循环导入修复**） |
| 7 | `vllm/vllm/platforms/__init__.py` | WSL2 torch.version.hip 回退 |
| 8 | `mineru/.../predict_rec.py` | RDNA imgW 32-align + batch padding |
| 9 | `mineru/.../predict_det.py` | RDNA contiguous check |

---

## 参考文档

本报告配套三个参考文件，提供更深入的背景知识：

| 文件 | 内容 |
|------|------|
| **[参考-ROCm7.2核心变化.md](参考-ROCm7.2核心变化.md)** | ROCm 7.2 相比 7.1 的完整变化：硬件支持、WSL2 增强、库优化、工具变化、LLVM 版本演进。**帮助理解为什么推荐 7.2。** |
| **[参考-WSL2网络深度配置.md](参考-WSL2网络深度配置.md)** | WSL2 + Clash TUN 代理的完整配置指南：`.wslconfig` 参数详解、7 个已验证坑、Hyper-V 防火墙修复、验证命令。 |
| **[参考-第一轮发现的技术解析.md](参考-第一轮发现的技术解析.md)** | 第一轮 10 个发现的技术深度解析：根因分析、背景知识、正确做法。 |

## 关键建议（给教程修订者）

- **推荐组合**：Ubuntu 22.04 + ROCm 7.1.1（稳定）或 Ubuntu 24.04 + ROCm 7.2.1（较新）
- **不推荐组合**：Ubuntu 24.04 + ROCm 7.1.1（LLVM 版本不兼容）
- **vllm**：应使用最新 main，不推荐旧 commit `357fddf61`
- **网络**：Hyper-V 防火墙放行 + MTU 1500 必须加入教程
- **gfx 架构**：gfx1201 = RDNA 4，不是 RDNA 3.5（后者是 gfx1150/gfx1151）

---

*文档最后更新: 2026-05-27*

