# MinerU 本地更新指南

> 当 MinerU 官方发布新版本后，如何更新本地部署同时保留所有 AMD RDNA 适配

---

## 0. 更新前必读

MinerU 更新分两种情况：

| 更新类型 | 影响 | 操作量 |
|---------|------|--------|
| **小版本**（3.1.x→3.1.x+1） | 模型不变，代码微调 | ~5 分钟 |
| **大版本**（3.x→4.x） | 模型可能更新，架构可能变化 | ~30 分钟 + 模型下载 |

无论哪种情况，`pip install --upgrade` 都会**覆盖**我们手动打的 RDNA Patch 文件（`predict_rec.py`、`predict_det.py`），需要重新应用。

---

## 一、小版本更新（如 3.1.15 → 3.1.16）

### 1.1 备份当前 Patch

```bash
# 保存当前的 Patch 文件作为参考
cp ~/mineru_stable/.venv/lib/python3.13/site-packages/mineru/model/utils/tools/infer/predict_rec.py \
   ~/predict_rec_patched.py.bak
cp ~/mineru_stable/.venv/lib/python3.13/site-packages/mineru/model/utils/tools/infer/predict_det.py \
   ~/predict_det_patched.py.bak
```

### 1.2 更新 MinerU

```bash
cd ~/mineru_stable && . .venv/bin/activate

# ⚠️ 用 pip 而非 uv pip，避免覆盖 ROCm PyTorch
pip install --upgrade 'mineru[core]' -i https://pypi.mirrors.ustc.edu.cn/simple/
```

### 1.3 检查 PyTorch 是否被覆盖

```bash
.venv/bin/python -c "import torch; print(torch.__version__); print(torch.version.hip)"
```

如果输出不包含 `rocm`，说明 PyTorch 被覆盖成了 CUDA 版，需要重装：

```bash
pip install --force-reinstall \
    torch==2.11.0+rocm7.1 torchvision pytorch-triton-rocm \
    --index-url https://download.pytorch.org/whl/rocm7.1
```

### 1.4 重新应用 RDNA Patch

更新后 `predict_rec.py` 和 `predict_det.py` 被还原，需要重新打 patch：

#### Patch A：`predict_rec.py` — imgW 32 对齐

找到 `imgW = max(min(imgW, self.limited_max_width), self.limited_min_width)` 之后加一行：

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

将 `for rno in range(len(rec_result)):` 改为：

```python
                for rno in range(actual_batch_size):
```

#### Patch C：`predict_det.py` — contiguous 检查

在 `inp = inp.to(self.device)` 之后插入：

```python
            if not inp.is_contiguous():
                inp = inp.contiguous()
```

> 如果新版本的代码结构变了、找不到对应的行，说明官方可能已经修复了对应的 MIOpen 问题，可以跳过那个 patch。

### 1.5 快速验证

```bash
cd ~/mineru_stable && . .venv/bin/activate
export HSA_ENABLE_DXG_DETECTION=1 FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE MINERU_MODEL_SOURCE=huggingface

mineru -p ~/test.pdf -o ~/output_update_test -b hybrid-auto-engine
```

跑通即可。

---

## 二、大版本更新（如 3.x → 4.x）

### 2.1 完整备份

大版本可能有模型变更、依赖变更，建议先把当前环境全量备份：

```bash
# 备份虚拟环境
cp -r ~/mineru_stable ~/mineru_stable_backup_$(date +%Y%m%d)

# 导出当前包列表
~/mineru_stable/.venv/bin/pip freeze > ~/mineru_packages_backup.txt
```

### 2.2 检查 Release Notes

去 [MinerU Releases](https://github.com/opendatalab/MinerU/releases) 看：

1. **VLM 模型版本**是否变更（`MinerU2.5-Pro-xxxx` 的名字变了就需要下载新模型）
2. **Python/torch 版本要求**是否有变化
3. **Backend/CLI 参数**是否有 breaking change
4. **vllm 版本兼容性**（大版本可能要求更新的 vllm）

### 2.3 更新 MinerU

```bash
cd ~/mineru_stable && . .venv/bin/activate
pip install --upgrade 'mineru[core]' -i https://pypi.mirrors.ustc.edu.cn/simple/
pip install --upgrade vllm  # 如果大版本需要新 vllm（可能需要从源码重编译）
```

### 2.4 重装被覆盖的 ROCm 依赖

```bash
pip install --force-reinstall \
    torch==2.11.0+rocm7.1 torchvision pytorch-triton-rocm \
    --index-url https://download.pytorch.org/whl/rocm7.1
```

### 2.5 重新应用所有 Patch

按 [1.4](#14-重新应用-rdna-patch) 重新应用 RDNA Patch。

如果大版本架构变化太大、patch 位置找不到：
1. 先在**不打 patch** 的情况下跑一次，观察速度
2. 如果无明显冷启动延迟（Layout/OCR 阶段没有单独耗时 >5s 的步骤），说明官方已修复，不需要 patch
3. 如果仍有延迟，用 `grep` 搜索关键字定位新位置后手动 patch

### 2.6 更新 vllm（如需要）

如果大版本要求新的 vllm：

```bash
cd ~/vllm && git pull
# 重新 cmake + ninja（gfx1201 换成你自己的显卡代号）
export PYTORCH_ROCM_ARCH=gfx1201
mkdir -p ~/vllm_build && cd ~/vllm_build
cmake -S ~/vllm -B . -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DVLLM_TARGET_DEVICE=rocm \
    -DVLLM_PYTHON_EXECUTABLE=~/mineru_stable/.venv/bin/python \
    -DHIP_ROOT_DIR=/opt/rocm -DROCM_PATH=/opt/rocm
ninja -j4
cp *.abi3.so ~/vllm/vllm/

# 重新安装
cd ~/vllm
VLLM_TARGET_DEVICE=rocm ~/mineru_stable/.venv/bin/pip install -e . --no-deps --no-build-isolation

# 重新应用 WSL2 平台检测 patch（参考部署教程第八步 8.8）
```

### 2.7 重新运行 MIOpen 预热（如模型架构变化）

如果 VLM 或 pipeline 模型结构发生了变化：

```bash
cd ~/mineru_stable && . .venv/bin/activate
export HSA_ENABLE_DXG_DETECTION=1
python cache_warmer.py --device cuda --max_side 960 --step 32
```

---

## 三、一键更新脚本

把下面内容保存为 `~/update_mineru.sh`：

```bash
#!/bin/bash
set -e

echo "=== MinerU 更新脚本 ==="

# 激活环境
cd ~/mineru_stable && . .venv/bin/activate
export HSA_ENABLE_DXG_DETECTION=1

# 备份 patch 文件
echo "[1/5] 备份当前文件..."
VENV_PKGS=".venv/lib/python3.13/site-packages"
cp "$VENV_PKGS/mineru/model/utils/tools/infer/predict_rec.py" /tmp/predict_rec.bak 2>/dev/null
cp "$VENV_PKGS/mineru/model/utils/tools/infer/predict_det.py" /tmp/predict_det.bak 2>/dev/null

# 更新
echo "[2/5] 更新 MinerU..."
pip install --upgrade 'mineru[core]' -i https://pypi.mirrors.ustc.edu.cn/simple/

# 检查 PyTorch
echo "[3/5] 检查 PyTorch..."
python -c "import torch; assert 'rocm' in torch.__version__, 'PyTorch 被覆盖！'; print('PyTorch:', torch.__version__)"

# 这里需要手动应用 patch（因为 sed 定位行号可能不准）
echo "[4/5] 请手动应用 RDNA Patch（参考 ~/MinerU本地更新指南.md）"
echo "       文件: $VENV_PKGS/mineru/model/utils/tools/infer/predict_rec.py"
echo "       文件: $VENV_PKGS/mineru/model/utils/tools/infer/predict_det.py"

# 验证
echo "[5/5] 运行快速测试..."
mineru -p ~/test.pdf -o /tmp/mineru_update_test -b hybrid-auto-engine 2>&1 | tail -3
echo "=== 更新完成 ==="
```

```bash
chmod +x ~/update_mineru.sh
```

---

## 四、版本回退

如果新版本有问题，快速回退：

```bash
cd ~/mineru_stable && . .venv/bin/activate
pip install 'mineru[core]==3.1.15' -i https://pypi.mirrors.ustc.edu.cn/simple/

# 然后重新应用 RDNA Patch（参考 1.4）
```

---

*最后更新: 2026-05-25*
