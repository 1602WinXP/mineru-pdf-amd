# ROCm 7.2 升级 & A/B 对比测试指南

> 当前生产环境：Ubuntu 22.04 + ROCm 7.1.1 + PyTorch 2.11.0+rocm7.1
> 目标：创建独立的 ROCm 7.2 环境，两边对比性能，零风险

---

## 0. 策略：并行环境而非原地升级

**不推荐直接升级现有 7.1.1 环境**，因为一旦出问题很难回退。而是在**同一个 Ubuntu 22.04** 中创建独立的 Python 虚拟环境，两个 ROCm 版本的库可以共存。

```
~/mineru_stable/          ← 生产环境 (ROCm 7.1.1 + vllm)
~/mineru_rocm72/          ← 测试环境 (ROCm 7.2 + vllm)
```

唯一需要**共享**的是 ROCm 运行时（`/opt/rocm`），升级后会从 7.1.1 变成 7.2。librocdxg 需要重新编译，但基本流程相同。

> ⚠️ 升级 ROCm 后，旧环境的 PyTorch 可能因为 `libamdhip64.so` 版本变化而无法启动。如果遇到，需要重装 PyTorch（仍然是 2.11.0+rocm7.2）。

---

## 一、升级 ROCm 7.1.1 → 7.2.1

### 1.1 备份当前环境

```bash
# 备份当前包列表
~/mineru_stable/.venv/bin/pip freeze > ~/mineru_packages_7.1.1.txt

# 记录当前 GPU 状态
export HSA_ENABLE_DXG_DETECTION=1
/opt/rocm/bin/rocminfo > ~/rocminfo_7.1.1.txt
```

### 1.2 更新 ROCm 仓库

```bash
# 修改 apt 源，7.1.1 → 7.2.1
sudo sed -i 's/7.1.1/7.2.1/g' /etc/apt/sources.list.d/rocm.list
# 或者直接重写：
echo 'deb [arch=amd64] https://repo.radeon.com/rocm/apt/7.2.1 jammy main' | \
    sudo tee /etc/apt/sources.list.d/rocm.list

sudo apt update
```

### 1.3 升级 ROCm 包

```bash
# 先查看有哪些可升级的包
apt list --upgradable 2>/dev/null | grep rocm

# 升级全部 ROCm 组件
echo <密码> | sudo -S DEBIAN_FRONTEND=noninteractive apt upgrade -y

# 确保关键开发包版本一致
echo <密码> | sudo -S DEBIAN_FRONTEND=noninteractive apt install -y \
    rocminfo hip-dev miopen-hip \
    rocblas-dev rocrand-dev rocsparse-dev rocsolver-dev \
    hipfft-dev hipcub-dev rocprim-dev rocthrust-dev
```

### 1.4 修复 rocminfo 版本

```bash
# 检查当前 rocminfo 版本（应为 ROCm 7.2.1 版）
dpkg -l | grep rocminfo
# 如果仍是 Ubuntu 自带 5.7.1，降级到 ROCm 版：
sudo apt install -y --allow-downgrades rocminfo=1.0.0.70201-38~22.04
```

### 1.5 重新编译 librocdxg

> ROCm 7.2 的 `libhsa-runtime64` 版本变了，librocdxg 需要重新链接。如果 librocdxg 源码之前已经 clone 过，只需重新 cmake+make。

```bash
cd ~/librocdxg/build
cmake .. -DWIN_SDK='/mnt/c/Program Files (x86)/Windows Kits/10/Include/10.0.28000.0/shared'
make -j$(nproc)
sudo make install
sudo ldconfig
```

### 1.6 重启验证 GPU

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
# 应显示你的 GPU 信息，如 gfx1201, AMD Radeon RX 9070
```

---

## 二、更新旧环境（7.1.1 → 7.2 兼容）

旧虚拟环境 `~/mineru_stable/` 的 PyTorch 编译时链接了 7.1.1 的库，现在 ROCm 升级到 7.2 了，需要重装 PyTorch：

```bash
cd ~/mineru_stable && . .venv/bin/activate

# 重装 PyTorch（ROCm 7.2 版，版本号仍是 2.11.0）
pip install --force-reinstall \
    torch==2.11.0+rocm7.2 \
    torchvision \
    pytorch-triton-rocm \
    --index-url https://download.pytorch.org/whl/rocm7.2

# 验证
python -c "
import torch
print(torch.__version__)
print(torch.version.hip)
print(torch.cuda.is_available())
"
# 预期: 2.11.0+rocm7.2, 7.2.xxxxx, True
```

> 如果这一步跑不通（PyTorch 2.11.0+rocm7.2 的 wheel 可能还没发布，取决于 PyTorch 官网），就用 `+rocm7.1` 的 wheel。PyTorch 的 ROCm 后端向后兼容，7.1 的 torch 链接在 7.2 运行时上一般也能跑。

---

## 三、创建独立 ROCm 7.2 测试环境

### 3.1 创建新虚拟环境

```bash
mkdir -p ~/mineru_rocm72 && cd ~/mineru_rocm72
python3.13 -m venv .venv
```

### 3.2 安装 PyTorch ROCm 7.2

```bash
.venv/bin/pip install --pre \
    torch==2.11.0+rocm7.2 \
    torchvision \
    pytorch-triton-rocm \
    --index-url https://download.pytorch.org/whl/rocm7.2

# 验证
.venv/bin/python -c "
import torch
print(torch.__version__, torch.version.hip)
print(torch.cuda.is_available(), torch.cuda.get_device_name(0))
"
```

### 3.3 安装 AMD 优化组件

```bash
# aiter（源码）
.venv/bin/pip install -e ~/aiter

# flash_attn（ROCm 版，相同 commit）
cd ~/flash-attention
export FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE
~/mineru_rocm72/.venv/bin/pip install --no-build-isolation -e .
```

### 3.4 编译 vllm（ROCm 7.2 版）

#### 3.4.1 vllm 源码更新（可选）

```bash
cd ~/vllm && git pull  # 获取最新 vllm 代码
```

#### 3.4.2 ROCm 7.2 的 cmake 包名变化

ROCm 7.2 中，很多 cmake 包已经原生使用新名称，不需要像 7.1.1 那样创建 alias wrapper。但 vllm 可能仍然查找旧名称：

```bash
# 检查哪些包名在新旧间有差异
ls /opt/rocm/lib/cmake/ | grep -E "roc|hip"
```

对于 vllm 仍然需要旧名称的包，创建 wrapper：

```bash
# 如果 vllm 报 "hiprand not found"，创建 wrapper
sudo mkdir -p /opt/rocm/lib/cmake/hiprand
cat << 'EOF' | sudo tee /opt/rocm/lib/cmake/hiprand/hiprand-config.cmake
include(/opt/rocm/lib/cmake/rocrand/rocrand-config.cmake)
if(TARGET roc::rocrand AND NOT TARGET hip::hiprand)
  add_library(hip::hiprand ALIAS roc::rocrand)
endif()
EOF

# hipblas → rocblas wrapper（同样如果需要的话）
sudo mkdir -p /opt/rocm/lib/cmake/hipblas
cat << 'EOF' | sudo tee /opt/rocm/lib/cmake/hipblas/hipblas-config.cmake
include(/opt/rocm/lib/cmake/rocblas/rocblas-config.cmake)
if(TARGET roc::rocblas AND NOT TARGET hip::hipblas)
  add_library(hip::hipblas ALIAS roc::rocblas)
endif()
EOF
```

#### 3.4.3 cmake 配置和编译

```bash
mkdir -p ~/vllm_build_rocm72

export PYTORCH_ROCM_ARCH=gfx1201   # 替换为你的 gfx 代号（见部署教程 0.0 节）

cmake -S ~/vllm -B ~/vllm_build_rocm72 \
    -G Ninja \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DVLLM_TARGET_DEVICE=rocm \
    -DVLLM_PYTHON_EXECUTABLE=/home/$USER/mineru_rocm72/.venv/bin/python \
    -DHIP_ROOT_DIR=/opt/rocm \
    -DROCM_PATH=/opt/rocm \
    -DCMAKE_PREFIX_PATH="/home/$USER/mineru_rocm72/.venv/lib/python3.13/site-packages/torch/share/cmake"

cd ~/vllm_build_rocm72 && ninja -j4
```

#### 3.4.4 安装 vllm

```bash
cp ~/vllm_build_rocm72/*.abi3.so ~/vllm/vllm/

cd ~/vllm
VLLM_TARGET_DEVICE=rocm PYTORCH_ROCM_ARCH=gfx1201 \   # 替换为你的 gfx 代号
    ~/mineru_rocm72/.venv/bin/pip install -e . --no-deps --no-build-isolation

# amdsmi
cp -r /opt/rocm/share/amd_smi ~/amd_smi_rocm72
cd ~/amd_smi_rocm72
~/mineru_rocm72/.venv/bin/pip install . --no-build-isolation

# 重新应用 vllm WSL2 平台检测 Patch
# （和 7.1.1 时一样的两个文件，参考部署教程第八步 8.8）
```

### 3.5 安装 MinerU + 应用 Patch

```bash
cd ~/mineru_rocm72

# ⚠️ 用 pip 而非 uv pip
.venv/bin/pip install 'mineru[core]' -i https://pypi.mirrors.ustc.edu.cn/simple/

# 重装 PyTorch（如被覆盖）
.venv/bin/pip install --force-reinstall \
    torch==2.11.0+rocm7.2 torchvision pytorch-triton-rocm \
    --index-url https://download.pytorch.org/whl/rocm7.2

# 应用 RDNA Patch（参考 MinerU本地更新指南.md 1.4）
# 文件：mineru/model/utils/tools/infer/predict_rec.py
# 文件：mineru/model/utils/tools/infer/predict_det.py
```

### 3.6 MIOpen 预热

```bash
cd ~/mineru_rocm72 && . .venv/bin/activate
export HSA_ENABLE_DXG_DETECTION=1

# 复制预热脚本
cp ~/mineru_stable/cache_warmer.py .
python cache_warmer.py --device cuda --max_side 960 --step 32
```

---

## 四、A/B 对比测试

### 4.1 准备测试 PDF

用同一个 300 页左右的 PDF 做基准测试。推荐用 [hello-algo](https://github.com/krahets/hello-algo/releases/tag/1.3.0) 的中文 Python 版 PDF（~90MB，348 页）。

```bash
cd ~
wget https://github.com/krahets/hello-algo/releases/download/1.3.0/hello-algo-1.3.0-zh-python.pdf -O benchmark.pdf
```

### 4.2 清除缓存再测

每次测试前清理 Triton 缓存（两种环境的 Triton kernel 可能不兼容）：

```bash
rm -rf ~/.triton/cache
```

### 4.3 对比测试脚本

保存为 `~/benchmark.sh`：

```bash
#!/bin/bash
set -e

RESULT_FILE=~/benchmark_results.txt
TEST_PDF=~/benchmark.pdf
OUTPUT_BASE=~/benchmark_output

echo "=== MinerU Benchmark $(date) ===" | tee $RESULT_FILE

for ENV in "mineru_stable 7.1.1" "mineru_rocm72 7.2"; do
    set -- $ENV
    DIR=$1
    LABEL=$2
    
    echo "" | tee -a $RESULT_FILE
    echo "--- Testing $LABEL ---" | tee -a $RESULT_FILE
    
    cd ~/$DIR && . .venv/bin/activate
    export HSA_ENABLE_DXG_DETECTION=1
    export FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE
    export MINERU_MODEL_SOURCE=huggingface
    
    rm -rf $OUTPUT_BASE/$LABEL
    rm -rf ~/.triton/cache
    
    START=$(date +%s)
    mineru -p $TEST_PDF -o $OUTPUT_BASE/$LABEL -b hybrid-auto-engine
    END=$(date +%s)
    
    echo "Duration: $((END-START))s" | tee -a $RESULT_FILE
done

echo "" | tee -a $RESULT_FILE
echo "Results saved to $RESULT_FILE"
cat $RESULT_FILE
```

```bash
chmod +x ~/benchmark.sh
```

### 4.4 观察要点

测试时注意观察日志中各阶段的 `it/s`：

- **VLM model load** 首次 ~46s，后续应 <5s
- **Two Step Extraction** 是 VLM 推理速度（关键指标，越高越好）
- **Layout Predict** 是版面分析速度
- **OCR-det** 是 OCR 检测速度
- **Processing pages** 是页面处理速度

### 4.5 结果判断

| 结果 | 行动 |
|------|------|
| 7.2 更快 | 将 7.2 环境提升为生产环境 |
| 差不多（±10%） | 保持 7.1.1，等后续版本 |
| 7.2 更慢或有错误 | 保持 7.1.1，反馈给社区 |

---

## 五、切换生产环境

如果 7.2 确实更快：

```bash
# 把当前 7.1.1 环境备份
mv ~/mineru_stable ~/mineru_stable_7.1.1_backup

# 把 7.2 环境设为默认
mv ~/mineru_rocm72 ~/mineru_stable

# 更新 ~/mineru_stable 路径（如有需要）
```

回退也一样简单：

```bash
mv ~/mineru_stable ~/mineru_stable_7.2_bad
mv ~/mineru_stable_7.1.1_backup ~/mineru_stable
```

---

## 六、已知差异总结

| 项目 | ROCm 7.1.1 | ROCm 7.2 |
|------|-----------|----------|
| cmake 包名 | `hiprand` / `rocrand` 混用 | 统一用 `rocrand` |
| vllm cmake wrapper | 需要 hiprand/hipblas alias | 可能不需要（或更少） |
| RDNA conv3d 问题 | 存在（MIOpen 未修复） | **同样存在**（作者确认） |
| RDNA 空洞卷积 | 存在 | **同样存在** |
| RDNA conv2d 冷启动 | 存在 | **同样存在** |
| gfx1201 固件支持 | 基本支持 | 可能更好 |
| PyTorch 版本 | 2.11.0+rocm7.1 | 2.11.0+rocm7.2 |
| 社区验证程度 | 充分（Discussion #3662） | 较少 |

> Discussion #3662 作者原话：*"ROCm 7.2 并没有解决 RDNA 上 3D 卷积，2D 卷积的基数倍数，空洞卷积的问题"*。所以 7.2 的性能提升主要来源于更好的固件支持和库优化，而非 MIOpen kernel 修复。

---

*最后更新: 2026-05-24*
