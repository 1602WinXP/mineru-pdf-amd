# MinerU 模型管理指南

> 模型下载到哪里了？如何更新？如何手动替换？为什么不能只换模型文件？

---

## 〇、重要认知：模型和代码是耦合的

**换模型不是只换文件那么简单。** 一个 MinerU 版本配套了一套固定的组件：

```
MinerU 3.1.15
  ├── mineru-vl-utils 0.2.8    ← VLM 模型加载/推理工具库
  ├── VLM 模型 2604-1.2B       ← 模型权重（结构和 vl-utils 耦合）
  └── Pipeline 模型 Kit-1.0    ← OCR/版面模型
```

2026 年 5 月 21 日官方发布了新 VLM 模型 `MinerU2.5-Pro-2605-1.2B`，同时 `mineru-vl-utils` 从 0.2.8 跳到 **1.0.0**，主版本号变更通常意味着接口/架构调整。

这意味着：

| 你想做的事 | 可行吗 | 原因 |
|-----------|--------|------|
| 只下载新模型文件 | ❌ | 模型名硬编码在 `enum_class.py` 里，MinerU 不会去找它 |
| 只改 `enum_class.py` 里的模型名 | ❌ | 旧 `vl-utils 0.2.8` 大概率无法加载新模型 |
| 只升级 `vl-utils` 到 1.0.0 | ❌ | 新 vl-utils 可能依赖新版本 MinerU |
| 等 MinerU 发布新版本再整体升级 | ✅ | 官方会同步更新模型引用 + vl-utils + 其他适配 |

**正确的模型更新方式是等待 MinerU 发新版，然后按 [MinerU本地更新指南.md](MinerU本地更新指南.md) 整体升级。**

---

## 一、两种模型，两个仓库

MinerU 使用两套模型，分别托管在两个 HuggingFace 仓库：

| 模型 | HuggingFace 仓库 | 大小 | 作用 |
|------|-----------------|------|------|
| **VLM 模型** | `opendatalab/MinerU2.5-Pro-2604-1.2B` | ~2.3GB | 视觉语言模型，决定解析精度 |
| **Pipeline 模型** | `opendatalab/PDF-Extract-Kit-1.0` | 仓库总量约 15GB；MinerU 实际只拉取所需子模块（约 1GB 左右） | 版面分析 / OCR / 公式 / 表格识别 |

> VLM 模型名字里的 `2604` 表示 2026 年 4 月版本。官方发新模型时会改这个编号。

---

## 二、模型存哪里了

### 2.1 默认缓存路径

模型源通过环境变量 `MINERU_MODEL_SOURCE` 控制：

| 模型源 | 环境变量 | 缓存路径 |
|--------|---------|---------|
| HuggingFace（默认） | `MINERU_MODEL_SOURCE=huggingface` | `~/.cache/huggingface/hub/` |
| ModelScope | `MINERU_MODEL_SOURCE=modelscope` | `~/.cache/modelscope/hub/` |
| 本地自定义 | `MINERU_MODEL_SOURCE=local` | 任意路径（需配置） |

### 2.2 当前缓存的实际位置

```bash
# VLM 模型
ls ~/.cache/huggingface/hub/models--opendatalab--MinerU2.5-Pro-2604-1.2B/snapshots/

# Pipeline 模型
ls ~/.cache/huggingface/hub/models--opendatalab--PDF-Extract-Kit-1.0/snapshots/
```

每个 snapshots 目录下有一个 hash 命名的子目录（如 `d3f5e08d...`），里面是实际的模型文件。

### 2.3 Pipeline 模型内部结构

```
PDF-Extract-Kit-1.0/
└── models/
    ├── Layout/PP-DocLayoutV2/    ← 版面检测
    ├── MFR/                       ← 公式识别
    │   ├── unimernet_hf_small_2503/
    │   └── pp_formulanet_plus_m/
    ├── OCR/paddleocr_torch/       ← OCR 文字识别
    ├── TabRec/                    ← 表格识别
    │   ├── SlanetPlus/
    │   └── UnetStructure/
    └── TabCls/                    ← 表格分类
```

---

## 三、模型下载工具（官方）

MinerU 自带 `mineru-models-download` 命令行工具，可以交互式选择模型下载，自动生成 `~/mineru.json`：

```bash
cd ~/mineru_stable && . .venv/bin/activate
mineru-models-download
# 按提示选择模型源（huggingface/modelscope）
# 下载完成后自动写入 ~/mineru.json
```

也可以直接指定参数：
```bash
mineru-models-download --help  # 查看完整选项
```

> 注意：这需要当前网络能访问 HuggingFace 或 ModelScope。如果已设置 `MINERU_MODEL_SOURCE=local`，该命令仅本次忽略，下载完成后仍会正确生成配置。

---

## 四、更新模型

### 4.1 常规更新：等 MinerU 发新版

> ⚠️ 模型和 `mineru-vl-utils` 版本耦合（见第〇节）。**不能只下载新模型文件**——需要等官方发布新 MinerU 后整体升级，过程参考 [MinerU本地更新指南.md](MinerU本地更新指南.md)。

升级后，新模型名会体现在新版 `enum_class.py` 中，首次运行时自动下载。

### 4.2 重新下载当前模型（修复损坏/清理空间）

如果只是想让当前模型重新下载（比如文件损坏了），删缓存即可：

```bash
rm -rf ~/.cache/huggingface/hub/models--opendatalab--MinerU2.5-Pro-*
rm -rf ~/.cache/huggingface/hub/models--opendatalab--PDF-Extract-Kit-*
```

然后运行一次 MinerU，模型会自动重新下载（**下载的仍是当前 MinerU 版本对应的模型，不是最新发布的模型**）。

### 4.3 查看当前用的是哪个版本

```bash
# VLM 模型版本（看目录名）
ls ~/.cache/huggingface/hub/models--opendatalab--MinerU2.5-Pro-*/

# Pipeline 模型版本
ls ~/.cache/huggingface/hub/models--opendatalab--PDF-Extract-Kit-*/

# 或者启动时观察日志，会打印下载的模型路径和版本
```

### 4.4 指定特定版本下载

如果不想用最新版，可以指定版本号：

```bash
cd ~/mineru_stable && . .venv/bin/activate

# 用 huggingface-hub 下载指定版本
python -c "
from huggingface_hub import snapshot_download
# 下载特定 commit 的模型（去 HuggingFace 页面查看 commit hash）
snapshot_download(
    'opendatalab/MinerU2.5-Pro-2604-1.2B',
    revision='<commit_hash>',
    cache_dir='~/.cache/huggingface/hub/'
)
"
```

---

## 五、手动下载模型（国内网络不好时）

### 5.1 方案 A：Windows 预下载，复制到 WSL2

在 Windows 上通过浏览器或下载工具下载模型文件，然后复制到 WSL2。

**步骤 1**：在 Windows 上下载

- VLM 模型：https://huggingface.co/opendatalab/MinerU2.5-Pro-2604-1.2B/tree/main
- Pipeline 模型：https://huggingface.co/opendatalab/PDF-Extract-Kit-1.0/tree/main
- 或者用 ModelScope 镜像（国内更快）：https://modelscope.cn/organization/OpenDataLab

**步骤 2**：从 Windows 复制到 WSL2

```bash
# 在 WSL2 中
mkdir -p ~/models_local

# Windows 的 C 盘在 /mnt/c/，假设下载到了 Desktop
cp -r /mnt/c/Users/<用户名>/Desktop/MinerU2.5-Pro-2604-1.2B ~/models_local/
cp -r /mnt/c/Users/<用户名>/Desktop/PDF-Extract-Kit-1.0 ~/models_local/
```

**步骤 3**：配置本地模型路径（见第六节）

### 5.2 方案 B：ModelScope 镜像下载

```bash
# 用 ModelScope 的 CLI 工具下载（国内快很多）
pip install modelscope

python -c "
from modelscope import snapshot_download
snapshot_download('OpenDataLab/MinerU2.5-Pro-2604-1.2B', cache_dir='~/.cache/modelscope/hub/')
snapshot_download('OpenDataLab/PDF-Extract-Kit-1.0', cache_dir='~/.cache/modelscope/hub/')
"

# 然后设置环境变量
export MINERU_MODEL_SOURCE=modelscope
```

### 5.3 方案 C：离线环境

在一台能上网的机器上：

```bash
# 用 huggingface-hub 下载到本地目录
pip install huggingface-hub

huggingface-cli download opendatalab/MinerU2.5-Pro-2604-1.2B \
    --local-dir ./MinerU2.5-Pro-2604-1.2B

huggingface-cli download opendatalab/PDF-Extract-Kit-1.0 \
    --local-dir ./PDF-Extract-Kit-1.0

# 打包
tar -czf mineru_models.tar.gz MinerU2.5-Pro-2604-1.2B PDF-Extract-Kit-1.0
```

把 `mineru_models.tar.gz` 传到离线机器，解压后配置本地模型路径（见第六节）。

---

## 六、使用本地模型（不联网）

### 6.1 配置 `mineru.json`

在 home 目录创建 `~/mineru.json`：

```json
{
    "models-dir": {
        "vlm": "~/models_local/MinerU2.5-Pro-2604-1.2B",
        "pipeline": "~/models_local/PDF-Extract-Kit-1.0"
    }
}
```

### 6.2 目录结构要求

```
~/models_local/
├── MinerU2.5-Pro-2604-1.2B/    ← VLM 模型文件（config.json, model.safetensors 等）
│   ├── config.json
│   ├── model-00001-of-00002.safetensors
│   ├── model-00002-of-00002.safetensors
│   ├── tokenizer.json
│   └── ...
└── PDF-Extract-Kit-1.0/        ← Pipeline 模型文件
    └── models/
        ├── Layout/
        ├── MFR/
        ├── OCR/
        └── ...
```

> 确保路径和 HuggingFace 仓库的目录结构完全一致。如果是手动下载的，不要把文件放到多余的子目录里。

### 6.3 使用

```bash
export MINERU_MODEL_SOURCE=local

# 验证配置是否生效
python -c "
from mineru.utils.config_reader import get_local_models_dir
print(get_local_models_dir())
"
# 输出: {'vlm': '~/models_local/MinerU2.5-Pro-2604-1.2B', ...}

# 正常运行
mineru -p input.pdf -o output -b hybrid-auto-engine
```

---

## 七、清理旧版本

HuggingFace 的缓存机制会保留多次下载的历史版本，长期使用可能占几十 GB：

```bash
# 查看当前缓存总大小
du -sh ~/.cache/huggingface/hub/

# 删除不再被引用的旧版本（安全）
pip install huggingface-hub
huggingface-cli delete-cache

# 或者直接删除整个 hub 目录（下次会重新下载最新版）
rm -rf ~/.cache/huggingface/hub/
```

> 删除后首次运行 MinerU 会重新下载（约 2.3GB），确保网络畅通。

---

## 八、模型版本对应关系

| MinerU 版本 | vl-utils 版本 | VLM 模型 | Pipeline 模型 |
|------------|--------------|-------------|--------------|
| 3.1.15（当前） | 0.2.8 | `MinerU2.5-Pro-2604-1.2B` | `PDF-Extract-Kit-1.0` |
| 下一个版本（推测） | 1.0.0+ | `MinerU2.5-Pro-2605-1.2B`（2026-05-21 发布） | 可能更新 |

> 2604 = 2026 年 4 月版，2605 = 2026 年 5 月版。官方大约每月更新一次 VLM 模型。

查看当前 MinerU 代码中锁定的模型版本：

```bash
grep -r "MinerU2.5\|PDF-Extract-Kit" \
    ~/mineru_stable/.venv/lib/python3.13/site-packages/mineru/utils/enum_class.py
```

查看当前 vl-utils 版本：

```bash
.venv/bin/pip show mineru-vl-utils | grep Version
```

---

## 九、模型文件说明

### VLM 模型文件 (MinerU2.5-Pro-2604-1.2B)

| 文件 | 说明 |
|------|------|
| `config.json` | 模型结构配置 |
| `model-*.safetensors` | 模型权重（分片，每个 ~1GB） |
| `tokenizer.json` | 分词器 |
| `preprocessor_config.json` | 图像预处理配置 |
| `vocab.json` / `merges.txt` | 词表 |

### Pipeline 模型文件 (PDF-Extract-Kit-1.0)

| 目录 | 说明 |
|------|------|
| `models/Layout/PP-DocLayoutV2/` | 版面检测模型 |
| `models/MFR/unimernet_hf_small_2503/` | 数学公式识别（unimernet small，单体约 770MB） |
| `models/MFR/pp_formulanet_plus_m/` | 公式识别备选（PP-FormulaNet+ M） |
| `models/OCR/paddleocr_torch/` | OCR 检测+识别 |
| `models/TabRec/SlanetPlus/` 等 | 表格识别 |
| `models/TabCls/` | 表格分类 |

> 整个 `PDF-Extract-Kit-1.0` 仓库容量约 15GB（含多套备选模型），但 MinerU 默认仅下载当前流水线实际使用的那一组（约 1GB 左右）。

---

## 十、常见问题

### Q: 更新 MinerU 后模型需要重新下载吗？

看情况。如果表里的模型名称（如 `MinerU2.5-Pro-2604-1.2B`）没变，旧缓存可以直接用。如果 Release Notes 写了模型更新（名字变了），新模型会自动下载，旧的可手动删除。

### Q: 如何同时保留新旧两版模型？

```bash
# 旧版本放在自定义目录
mkdir -p ~/models_local/MinerU2.5-Pro-OLD
# ...复制旧模型文件...

# 需要时切到 local 模式
export MINERU_MODEL_SOURCE=local
# 修改 ~/mineru.json 指向旧版本
```

### Q: 能用符号链接节省空间吗？

可以。如果你有多套 MinerU 环境：

```bash
# 把模型存到公共位置
mkdir -p ~/shared_models
mv ~/.cache/huggingface/hub/models--opendatalab--MinerU2.5-Pro-* ~/shared_models/

# 创建符号链接
ln -s ~/shared_models/models--opendatalab--MinerU2.5-Pro-2604-1.2B \
      ~/.cache/huggingface/hub/models--opendatalab--MinerU2.5-Pro-2604-1.2B
```

### Q: 模型下载一半断了怎么办？

HF 自动支持断点续传——直接重新运行 MinerU 即可，会从断点继续；也可以直接重跑 `huggingface-cli download <模型名>`，已下载的文件会自动跳过。

---

*最后更新: 2026-05-25*
