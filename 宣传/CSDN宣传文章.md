# MinerU 3.x AMD 显卡本地部署完整教程（三轮验证，全系 RDNA2/3/4 适用，输出质量对标官网 API）

## 一、痛点：AMD 显卡玩转大模型，到底卡在哪？

MinerU 是目前最强的开源 PDF / 文档解析工具。官方团队专注于模型本身的性能突破，文档主要覆盖主流的 NVIDIA / CUDA 平台，其他算力生态则通过 GitHub Discussions 等板块由社区共同推进。此前，社区先驱已经贡献了非常有价值的 [Discussion #3662](https://github.com/opendatalab/MinerU/discussions/3662)（@healy-hub）适配分享，奠定了坚实基础。但随着 MinerU 升级到 3.x，部分组件和依赖发生了变化，老教程在新架构下需要不少调整。

我们在社区前期经验的基础上，针对 MinerU 3.x 整理出一套完整流程，并经过**三轮独立验证部署**：Ubuntu 22.04 + ROCm 7.1.1 跑通 → Ubuntu 24.04 + ROCm 7.1.1 撞 LLVM 20 不兼容、确认放弃 → Ubuntu 24.04 + ROCm 7.2.1 跑通。这意味着教程里每一行命令都不是想当然，是真的有人按它部署过。

**结论先行：AMD 显卡能跑 MinerU 3.x，解析质量和 N 卡完全一致，速度也非常给力。**
唯一的代价是：PyPI 没有 AMD ROCm 版本的 vLLM 预编译 wheel，需要花约 1 小时手动编译。

本文是**一步一动、实际验证过**的硬核部署教程。我们基于 **AMD RX 9070 (16GB) + Windows 11 Pro WSL2** 跑通了完整流程，同样适用于全系 RDNA2/3/4 显卡（RX 9070 / 9060 / 7900 / 7800 / 7700 / 7600 / 6900 / 6800 / 6700 系列）。

---

## 二、部署环境（两条已验证的路径）

| 路径 | 系统 | ROCm | PyTorch | 适用场景 |
| :--- | :--- | :--- | :--- | :--- |
| **A（推荐）** | Ubuntu 22.04 | 7.1.1 | 2.11.0+rocm7.1 | 求稳，社区主流 |
| **B（较新）** | Ubuntu 24.04 | 7.2.1 | 2.11.0+rocm7.2 | 想要 RDNA4 正式支持 / librocdxg 生产级 |

⚠️ **不要尝试 Ubuntu 24.04 + ROCm 7.1.1**：24.04 的 ROCm 7.1.1 仓库基于 LLVM 20，但 ROCm 头文件和 vllm 代码当初按 LLVM 17 写的，编译时会撞上无法绕过的 FP8 类型错误。我们在第二轮验证中花了 4 小时确认这条路死路一条。

无论走哪条路径，VLM 模型都是 `MinerU2.5-Pro-2605-1.2B`（MinerU 3.2.0 起），vllm 推荐用最新 main 而不是旧 commit `357fddf61`——旧 commit 还带着过时的 PEP 639 语法和 `logger.warning_once` 循环导入坑。

---

## 三、部署六步法核心命令（路径 A）

详细步骤（手把手教程）请直接看我们的 GitHub 仓库：[buptanswer/mineru](https://github.com/buptanswer/mineru)。这里浓缩出最核心的六大环节：

### 1. WSL2 + 网络代理配置（国内用户重点）

`.wslconfig` 启用 `networkingMode=mirrored` + `firewall=true`；管理员 PowerShell 执行：

```powershell
Set-NetFirewallHyperVVMSetting -Name '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -DefaultInboundAction Allow
```

放行 Hyper-V 防火墙，否则 vllm 子进程 IPC 会被拦截、浏览器也访问不到 WSL 端口。Clash TUN 用户务必把 MTU 调成 1500（默认 9000 会被 WSL2 网卡丢弃，导致 TLS 握手卡死）。

### 2. 基础依赖与 CMake 二进制包

```bash
sudo apt install -y build-essential git wget curl python3.13 python3.13-venv python3.13-dev \
    libnuma-dev ninja-build pkg-config libgl1-mesa-glx
# WSL2 下不要用 sudo snap install cmake（snapd 阻塞）
wget https://github.com/Kitware/CMake/releases/download/v4.0.0/cmake-4.0.0-linux-x86_64.tar.gz
tar -xzf cmake-4.0.0-linux-x86_64.tar.gz
sudo cp -r cmake-4.0.0-linux-x86_64/bin/* /usr/local/bin/
```

### 3. ROCm 7.1.1 + librocdxg 桥接

```bash
echo 'deb [arch=amd64] https://repo.radeon.com/rocm/apt/7.1.1 jammy main' | sudo tee /etc/apt/sources.list.d/rocm.list
sudo apt update && sudo apt install -y rocminfo hip-dev miopen-hip
# 替换系统自带的旧版 rocminfo + rocm-device-libs：
sudo apt install -y --allow-downgrades rocminfo=1.0.0.70101-38~22.04 rocm-device-libs=1.0.0.70101-38~22.04

# 编译 DXG 桥接（原生 Linux 跳过）
git clone https://github.com/ROCm/librocdxg.git && cd librocdxg/build
cmake .. -DWIN_SDK='/mnt/c/Program Files (x86)/Windows Kits/10/Include/10.0.28000.0/shared'
make -j$(nproc) && sudo make install && sudo ldconfig
```

注意 `WIN_SDK` 必须指向 `shared/` 子目录，不是 SDK 根目录。

### 4. PyTorch + ROCm 开发包（含验证遗漏的 hipsparselt-dev）

```bash
python3.13 -m venv ~/mineru_stable/.venv
~/mineru_stable/.venv/bin/pip install --pre torch==2.11.0+rocm7.1 torchvision pytorch-triton-rocm \
    --index-url https://download.pytorch.org/whl/rocm7.1

# 必装的开发包（hipsparselt-dev 在原教程中遗漏，PyTorch ROCm 的 Caffe2Targets.cmake 硬依赖）
sudo apt install -y hipblas-dev hiprand-dev hipsparse-dev hipsparselt-dev \
    hipsolver-dev hipcub-dev rocprim-dev rocthrust-dev rocblas-dev rocrand-dev \
    hipfft-dev hipblaslt
```

### 5. 源码编译并 Patch 适配 vLLM（最容易踩坑的环节）

```bash
git clone https://github.com/vllm-project/vllm.git && cd vllm
# 直接用 main，不要旧 commit 357fddf61

# 必装的 build 依赖
~/mineru_stable/.venv/bin/pip install -U "setuptools>=77.0.3" setuptools_scm setuptools_rust wheel

# cmake 关键 export（这三处都是验证部署中实测过的坑）：
# 1. PATH 必须含 /opt/rocm/bin（CMake 要调 hipconfig）
# 2. 必须显式 -DCMAKE_HIP_ARCHITECTURES（WSL2 中 rocm_agent_enumerator 失效）
# 3. 绝对不能设 -DCMAKE_HIP_COMPILER=hipcc（CMake 4.0 主动拒绝 Perl 包装器）
export PATH=/opt/rocm/bin:/opt/rocm/llvm/bin:$PATH
export PYTORCH_ROCM_ARCH=gfx1201   # 替换为你的 gfx 代号
cmake -S ~/vllm -B ~/vllm_build -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DVLLM_TARGET_DEVICE=rocm \
    -DVLLM_PYTHON_EXECUTABLE=~/mineru_stable/.venv/bin/python \
    -DHIP_ROOT_DIR=/opt/rocm -DROCM_PATH=/opt/rocm \
    -DCMAKE_HIP_ARCHITECTURES=gfx1201 \
    -DCMAKE_PREFIX_PATH="~/mineru_stable/.venv/lib/python3.13/site-packages/torch/share/cmake"

cd ~/vllm_build && ninja -j4   # 内存不够时降并行数
cp *.abi3.so ~/vllm/vllm/
cd ~/vllm && VLLM_TARGET_DEVICE=rocm PYTORCH_ROCM_ARCH=gfx1201 \
    ~/mineru_stable/.venv/bin/pip install -e . --no-build-isolation
```

编译完成后必须给 vllm 打两个 patch（WSL2 用户）：
- `vllm/platforms/__init__.py` 加 `torch.version.hip` 回退
- `vllm/platforms/rocm.py` 把 `logger.warning_once()` 替换为 `sys.stderr.write()`，断开循环导入链

第二个补丁是验证部署中重新挖出的根因——之前的教程以为 rocm.py 只是为了平台检测，实际它**双重作用**：amdsmi 失败兜底 + 断循环导入。只动 `__init__.py` 在子进程（EngineCore）里仍然会撞 `UnspecifiedPlatform`。

### 6. 安装 MinerU 与 RDNA 补丁

```bash
.venv/bin/pip install 'mineru[core]' -i https://pypi.mirrors.ustc.edu.cn/simple/
# 立即查 PyTorch：依赖解析可能拉 CUDA 版覆盖
.venv/bin/python -c "import torch; print(torch.__version__)"
```

如果 PyTorch 被覆盖，按**正确顺序**修复：先 `--force-reinstall pytorch-triton-rocm`，再 `uninstall triton triton-rocm`。反过来会把刚装好的 ROCm Triton 的 `.so` 文件一并删掉（两个包在 `site-packages` 共享 `triton/` 物理目录）。

最后对 `mineru/model/utils/tools/infer/predict_rec.py` 打两个 patch（imgW 32 像素对齐 + 批次零填充），对 `predict_det.py` 打一个 patch（contiguous 连续性检查），消除 MIOpen 冷启动延迟。

---

## 四、技术总结：避坑指南（验证中重新挖出的根因）

部署过程中总结了七个最致命的"天坑"：

1. **PyTorch 2.12+ 闪退**：ROCm 官方在 PyTorch 2.12 中默认集成了 `rocprofiler`，强依赖 Linux 内核 KFD 驱动。WSL2 通过 librocdxg 桥接没有 KFD 拓扑，导入 `torch` 直接报错 `Found 0 rocprofiler agents`。**必须锁定 PyTorch 2.11.0**。
2. **符号链接导致编译失败**：编译 vLLM 时切忌为了省事把 `hipblas.h` 指向 `rocblas.h`，因为头文件内部有相对路径的 include 引用。**必须 `apt install hipblas-dev` 安装完整兼容包**。
3. **`uv pip` 覆盖 PyTorch**：`uv pip` 速度虽快，但依赖解析非常激进，会强制将 ROCm 版 PyTorch 替换为官方 CUDA 版。**务必用原生 `pip`；若已被覆盖，按"先重装、后卸载"的顺序恢复**。
4. **Ninja 编译 OOM**：vLLM 的 C++ 编译极其吃内存，默认多线程会直接打爆 16GB 物理内存。**编译时必须 `ninja -j4`**。
5. **vllm 平台检测 + 循环导入双重坑**：amdsmi 在 WSL2 无法初始化，需要打补丁让 vllm 回退到 `torch.version.hip`；同时 `rocm.py` 中 `logger.warning_once()` 会触发循环导入，把 `current_platform` 设为 `UnspecifiedPlatform`，**两个补丁缺一不可**。
6. **CMake 4.0 拒绝 hipcc 包装器**：CMake 4.0 内置的 HIP 检测逻辑硬编码拒绝 `hipcc` Perl 包装器，要求直接用底层 Clang；同时 WSL2 中 `rocm_agent_enumerator` 经常失效，必须显式指定 `CMAKE_HIP_ARCHITECTURES`。
7. **Hyper-V 防火墙默认拦截入站**：`firewall=true` 的镜像网络下，vllm engine 子进程间通信、浏览器访问 WSL 端口都会被切断。必须 `Set-NetFirewallHyperVVMSetting` 放行。

完整 32 项踩坑清单在仓库的 [速查与运维手册](https://github.com/buptanswer/mineru/blob/main/%E6%95%99%E7%A8%8B/MinerU%E9%80%9F%E6%9F%A5%E4%B8%8E%E8%BF%90%E7%BB%B4%E6%89%8B%E5%86%8C.md)。

---

## 五、实测数据对比（AMD 本地 vs NVIDIA 云服务器）

`example.pdf`（13 页）实测：

| 阶段 / 平台 | AMD RX 9070（路径 A） | AMD RX 9070（路径 B） | NVIDIA A10（云端） | 结论 |
| :--- | :--- | :--- | :--- | :--- |
| **VLM 推理阶段** | ~6 秒（1.98 it/s） | ~5 秒 | ~5 秒（2.18 it/s） | A10 / 路径 B 微弱领先 |
| **版面与 OCR 阶段** | < 1 秒（61 it/s） | < 1 秒（**65-71 it/s**） | ~1 秒（36 it/s） | **AMD 高带宽（640GB/s）优势明显** |
| **13 页总耗时** | 6-7 秒 | 5-7 秒 | ~6 秒 | **三者综合体验基本打平，输出质量完全一致** |

路径 B 在 Processing pages 阶段领先得益于 hipBLASLt 在线 GEMM 调优。

---

## 六、获取源码与反馈

完整的代码、配置文件、Patch 脚本和排错附录已开源至 GitHub 仓库。

👉 **GitHub 仓库地址**：[https://github.com/buptanswer/mineru](https://github.com/buptanswer/mineru)

如果您有其他显卡的适配经验，或在部署中遇到疑难问题，欢迎来 GitHub 提交 Issue 和 PR！
