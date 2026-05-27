# MinerU 本地更新指南

> 当 MinerU 官方发布新版本后，如何更新本地部署同时保留所有 AMD RDNA 适配

---

## 0. 更新前必读

MinerU 更新分两种情况：

| 更新类型 | 影响 | 操作量 |
|---------|------|--------|
| **小版本**（3.2.0 → 3.2.x） | 模型不变，代码微调 | ~5 分钟 |
| **大版本**（3.x → 4.x） | 模型可能更新，架构可能变化 | ~30 分钟 + 模型下载 |

无论哪种情况，`pip install --upgrade` 都会**覆盖**我们手动打的 RDNA Patch 文件（`predict_rec.py`、`predict_det.py`），需要重新应用。此外，pip 依赖解析还可能把 ROCm 版 PyTorch 替换成 CUDA 版，必须立即检查并恢复。

在所有命令中我们用 `PYVER` 这个 shell 变量代替 Python 版本号，让脚本对路径 A（3.13）和路径 B（3.12）都可用：

```bash
cd ~/mineru_stable && . .venv/bin/activate
export PYVER=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
export SITE_PKG="$HOME/mineru_stable/.venv/lib/python${PYVER}/site-packages"
export MINERU_INFER="$SITE_PKG/mineru/model/utils/tools/infer"
```

---

## 一、小版本更新（如 3.2.0 → 3.2.1）

### 1.1 备份当前 Patch

```bash
cp $MINERU_INFER/predict_rec.py ~/predict_rec_patched.py.bak
cp $MINERU_INFER/predict_det.py ~/predict_det_patched.py.bak
```

### 1.2 更新 MinerU

```bash
# ⚠️ 用 pip 而非 uv pip，避免覆盖 ROCm PyTorch
pip install --upgrade 'mineru[core]' -i https://pypi.mirrors.ustc.edu.cn/simple/
```

### 1.3 检查 PyTorch 是否被覆盖

```bash
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"
```

如果第一行不含 `rocm`（如显示 `2.11.0+cu130`），按**正确顺序**修复（先重装、后卸载）：

```bash
# 路径 A（22.04 + ROCm 7.1.1）
pip install --force-reinstall \
    torch==2.11.0+rocm7.1 torchvision pytorch-triton-rocm \
    --index-url https://download.pytorch.org/whl/rocm7.1

# 路径 B（24.04 + ROCm 7.2.1）则改为 +rocm7.2 和对应 index-url

pip uninstall -y triton triton-rocm
```

⚠️ **顺序很关键**：`pytorch-triton-rocm` 和 `triton` 在 `site-packages` 中共享 `triton/` 物理目录。如果先 uninstall 再 force-reinstall，会把刚装好的 ROCm Triton 的 `.so` 文件也删掉。**必须先强制重装、后卸载冲突包**。

### 1.4 重新应用 RDNA Patch

更新后 `predict_rec.py` 和 `predict_det.py` 被还原，需要重打 patch：

#### Patch A：`predict_rec.py` — imgW 32 对齐

找到 `imgW = max(min(imgW, self.limited_max_width), self.limited_min_width)`，在它**下一行**加：

```python
        imgW = math.ceil(imgW / 32) * 32
```

#### Patch B：`predict_rec.py` — batch 填充

在 `norm_img_batch = np.concatenate(norm_img_batch)` 之前插入：

```python
                actual_batch_size = len(norm_img_batch)
                if actual_batch_size < batch_num:
                    pad_size = batch_num - actual_batch_size
                    pad_img = np.zeros_like(norm_img_batch[0])
                    for _ in range(pad_size):
                        norm_img_batch.append(pad_img)
```

把 `for rno in range(len(rec_result)):` 改为：

```python
                for rno in range(actual_batch_size):
```

#### Patch C：`predict_det.py` — contiguous 检查

在 `inp = inp.to(self.device)` 之后插入：

```python
            if not inp.is_contiguous():
                inp = inp.contiguous()
```

> 如果新版本代码结构变了、找不到对应的行，先 grep 关键字定位：
> ```bash
> grep -n "imgW = max" $MINERU_INFER/predict_rec.py
> grep -n "np.concatenate(norm_img_batch)" $MINERU_INFER/predict_rec.py
> grep -n "inp = inp.to(self.device)" $MINERU_INFER/predict_det.py
> ```
> 如果搜不到，说明官方可能已经修复了对应的 MIOpen 问题，可以跳过那个 patch（不打也能跑，只是冷启动延迟回来）。

### 1.5 快速验证

```bash
export HSA_ENABLE_DXG_DETECTION=1 FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE MINERU_MODEL_SOURCE=huggingface
mineru -p ~/test.pdf -o ~/output_update_test -b hybrid-auto-engine
```

跑通且 Processing pages 速度在 [速查手册 6.2 节](MinerU速查与运维手册.md#62-参考耗时rx-9070-实测)的预期范围内即可。

---

## 二、大版本更新（如 3.x → 4.x）

### 2.1 完整备份

大版本可能有模型变更、依赖变更，建议先全量备份：

```bash
# 备份虚拟环境
cp -r ~/mineru_stable ~/mineru_stable_backup_$(date +%Y%m%d)

# 导出当前包列表
~/mineru_stable/.venv/bin/pip freeze > ~/mineru_packages_backup.txt
```

或者更可靠地导出整个 WSL：

```powershell
# Windows PowerShell（管理员）
wsl --export Ubuntu-22.04 D:\WSL\mineru_pre_upgrade.tar
```

### 2.2 检查 Release Notes

去 [MinerU Releases](https://github.com/opendatalab/MinerU/releases) 看：

1. **VLM 模型版本**是否变更（`MinerU2.5-Pro-XXXX-1.2B` 的编号变了就需要下载新模型）
2. **Python / torch 版本要求**是否有变化
3. **Backend / CLI 参数**是否有 breaking change
4. **vllm 版本兼容性**（大版本可能要求重新编译 vllm）

### 2.3 更新 MinerU

```bash
cd ~/mineru_stable && . .venv/bin/activate
pip install --upgrade 'mineru[core]' -i https://pypi.mirrors.ustc.edu.cn/simple/
```

### 2.4 重装被覆盖的 ROCm 依赖

```bash
# 按你的路径选 +rocm7.1 或 +rocm7.2
pip install --force-reinstall \
    torch==2.11.0+rocm7.1 torchvision pytorch-triton-rocm \
    --index-url https://download.pytorch.org/whl/rocm7.1
pip uninstall -y triton triton-rocm
```

### 2.5 重新应用所有 Patch

按 [1.4](#14-重新应用-rdna-patch) 重新应用 RDNA Patch。

如果大版本架构变化太大、patch 位置找不到：

1. 先在**不打 patch** 的情况下跑一次，观察速度
2. 如果无明显冷启动延迟（Layout / OCR 阶段没有单独耗时 > 5s 的步骤），说明官方已修复，不需要 patch
3. 如果仍有延迟，用 `grep` 搜索关键字定位新位置后手动 patch

### 2.6 更新 vllm（如需要）

如果大版本要求新的 vllm，**完整重编译**：

```bash
cd ~/vllm && git pull
# 路径 B 用户：apt 升级如果覆盖了 ROCm 头文件，需要重跑 apply_rocm72_patches.sh
# 重新 cmake + ninja（gfx1201 换成你自己的显卡代号）
rm -rf ~/vllm_build && mkdir -p ~/vllm_build
export PATH=/opt/rocm/bin:/opt/rocm/llvm/bin:$PATH
export PYTORCH_ROCM_ARCH=gfx1201
cmake -S ~/vllm -B ~/vllm_build -G Ninja \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DVLLM_TARGET_DEVICE=rocm \
    -DVLLM_PYTHON_EXECUTABLE=$HOME/mineru_stable/.venv/bin/python \
    -DHIP_ROOT_DIR=/opt/rocm -DROCM_PATH=/opt/rocm \
    -DCMAKE_HIP_ARCHITECTURES=gfx1201 \
    -DCMAKE_PREFIX_PATH="$HOME/mineru_stable/.venv/lib/python${PYVER}/site-packages/torch/share/cmake"
cd ~/vllm_build && ninja -j4
cp ~/vllm_build/*.abi3.so ~/vllm/vllm/

# 重新安装
cd ~/vllm
VLLM_TARGET_DEVICE=rocm PYTORCH_ROCM_ARCH=gfx1201 \
    ~/mineru_stable/.venv/bin/pip install -e . --no-build-isolation

# 重新应用 WSL2 平台检测和循环导入 patch（参考部署教程 9.10）
```

### 2.7 重新运行 MIOpen 预热（如模型架构变化）

如果 VLM 或 pipeline 模型结构发生了变化（看 release notes）：

```bash
python ~/mineru_stable/cache_warmer.py --device cuda --max_side 960 --step 32
```

---

## 三、ROCm 版本升级

如果你想从 ROCm 7.1.1 升级到 7.2.1（路径 A → 路径 B 之类），**不要原地升级**，请按 [ROCm7.2升级指南.md](ROCm7.2升级指南.md) 创建独立环境后切换。原地升级 apt 包会覆盖头文件、可能让 vllm 二进制 `.abi3.so` 与新版 libamdhip64 不兼容，回退困难。

---

## 四、一键更新脚本

把下面内容保存为 `~/update_mineru.sh`：

```bash
#!/bin/bash
set -e

echo "=== MinerU 更新脚本 ==="

cd ~/mineru_stable && . .venv/bin/activate
export HSA_ENABLE_DXG_DETECTION=1

PYVER=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
SITE_PKG=".venv/lib/python${PYVER}/site-packages"
ROCM_VER=$(python -c "import torch; print(torch.version.hip)" 2>/dev/null | cut -d. -f1-2 | tr -d .)

echo "[1/5] 备份当前 patch..."
cp "$SITE_PKG/mineru/model/utils/tools/infer/predict_rec.py" /tmp/predict_rec.bak 2>/dev/null || true
cp "$SITE_PKG/mineru/model/utils/tools/infer/predict_det.py" /tmp/predict_det.bak 2>/dev/null || true

echo "[2/5] 更新 MinerU..."
pip install --upgrade 'mineru[core]' -i https://pypi.mirrors.ustc.edu.cn/simple/

echo "[3/5] 检查并修复 PyTorch..."
if ! python -c "import torch; assert 'rocm' in torch.__version__" 2>/dev/null; then
    echo "  → PyTorch 被覆盖，恢复 ROCm 版..."
    pip install --force-reinstall \
        torch==2.11.0+rocm${ROCM_VER} torchvision pytorch-triton-rocm \
        --index-url https://download.pytorch.org/whl/rocm${ROCM_VER}
    pip uninstall -y triton triton-rocm 2>/dev/null || true
fi
echo "  → PyTorch: $(python -c 'import torch; print(torch.__version__)')"

echo "[4/5] 请手动应用 RDNA Patch（参考 MinerU本地更新指南.md 1.4）"
echo "      文件: $SITE_PKG/mineru/model/utils/tools/infer/predict_rec.py"
echo "      文件: $SITE_PKG/mineru/model/utils/tools/infer/predict_det.py"

echo "[5/5] 运行快速测试..."
mineru -p ~/test.pdf -o /tmp/mineru_update_test -b hybrid-auto-engine 2>&1 | tail -5
echo "=== 更新完成 ==="
```

```bash
chmod +x ~/update_mineru.sh
```

> 脚本只能自动完成 PyTorch 恢复，RDNA patch 因为行号每个版本可能变，仍需手动按 1.4 节执行。

---

## 五、版本回退

如果新版本有问题，快速回退：

```bash
cd ~/mineru_stable && . .venv/bin/activate
pip install 'mineru[core]==3.2.0' -i https://pypi.mirrors.ustc.edu.cn/simple/

# 然后重新应用 RDNA Patch（参考 1.4）
```

也可以从备份的 WSL tar 还原：

```powershell
wsl --unregister Ubuntu-22.04
wsl --import Ubuntu-22.04 C:\WSL\Ubuntu-22.04 D:\WSL\mineru_pre_upgrade.tar
```

---

*文档最后更新: 2026-05-27*
