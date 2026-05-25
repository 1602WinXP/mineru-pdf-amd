# MinerU 速查与运维手册

> 最后一课：所有你日常会用到的命令、判断方法、和踩出来的经验

---

## 一、速查卡片（打印/截图保存）

### WSL2 从零启动

```powershell
# Windows PowerShell
wsl -d Ubuntu-22.04
```

```bash
# 进入后
cd ~/mineru_stable && . .venv/bin/activate
# 环境变量 ~/.bashrc 已自动加载，不需要手动 export
```

### 三句话启动服务

```bash
# CLI 直接解析
mineru -p input.pdf -o output -b hybrid-auto-engine

# WebUI（浏览器拖拽）
mineru-gradio --server-name 0.0.0.0 --server-port 7860

# API 服务（程序调用）
mineru-api --host 0.0.0.0 --port 8000
```

### 三句话验证健康

```bash
# GPU 是否可见
/opt/rocm/bin/rocminfo | grep "Agent 2" -A5

# PyTorch 能否用 GPU
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"

# vllm 平台是否识别
python -c "from vllm.platforms import current_platform; print(current_platform.is_rocm())"
```

---

## 二、不可触碰的红线

| 绝对不能做的事 | 原因 | 如果已经做了 |
|--------------|------|------------|
| `uv pip install mineru[core]` | 覆盖 ROCm PyTorch 为 CUDA 版 | 重装 `torch==2.11.0+rocm7.1` |
| `pip install vllm`（PyPI） | 安装 CUDA 版 vllm，破坏 ROCm 环境 | 卸载后重编译 |
| `pip install torch --upgrade` | 装上 2.12+，WSL2 直接崩溃 | 降回 2.11.0 |
| `sudo apt autoremove` | 可能删除 ROCm 依赖 | 重装被删的包 |
| 删除 `/opt/rocm/` 任何内容 | 破坏 ROCm 运行时 | 重装 ROCm |
| 在 WSL2 中 `rm -rf /` | 不言自明 | 重装一切 |

### 可以做的事

| 操作 | 安全吗 | 备注 |
|------|--------|------|
| `pip install --upgrade mineru[core]` | ✅ | 用 pip 而非 uv pip |
| 删除 `~/.cache/huggingface/hub/` | ✅ | 下次运行重新下载 |
| 删除 `~/.triton/cache/` | ✅ | 下次 JIT 重新编译（慢一次） |
| 删除 `~/.cache/miopen/` | ✅ | 需重新预热 |
| `sudo apt update && sudo apt upgrade` | ⚠️ | 注意不要升级 ROCm 核心包 |
| 重装 WSL2 | ✅ | 按照部署教程重来即可 |

---

## 三、正常 vs 异常：学会看日志

### 首次运行正常的日志

```
VLM model load: 46.04s                    ← 正常，首次加载模型
Triton kernel JIT compilation: ...        ← 正常，首次编译缓存
Two Step Extraction: 100%|...| 7.94s/it   ← 首次慢，后续 2-3s/it
Processing pages: 100%|...| 83it/s        ← 一直这么快就正常
Completed batch 1/1                        ← 成功
```

### 应该警惕的日志

```
Found 0 rocprofiler agents                ← PyTorch 2.12+ 被装上了
Device string must not be empty           ← vllm 没检测到 ROCm
Error code: 34 | DRIVER_NOT_LOADED        ← 出现在非 WSL2 检测环节则正常
Using 'pin_memory=False' as WSL is detected ← 正常，WSL2 限制
```

### 静默降级为 CPU 的特征

```bash
# 如果解析突然变慢（几分钟一页），检查是否在用 CPU
python -c "import torch; print(torch.cuda.is_available())"
# 如果输出 False，PyTorch 被覆盖成了 CPU/CUDA 版
```

---

## 四、WSL2 维护

### 4.1 磁盘空间

```bash
# WSL2 虚拟磁盘会膨胀，定期检查
du -sh ~/mineru_stable ~/.cache

# 清理 pip 缓存
pip cache purge

# 清理 apt 缓存
sudo apt clean

# WSL2 磁盘 compact（在 Windows PowerShell 中，先 shutdown WSL）
# wsl --shutdown
# diskpart → select vdisk file="..." → compact vdisk
```

### 4.2 内存管理

RX 9070 只有 16GB 显存，hybrid-auto-engine 加载 VLM 模型后约占用 10-12GB：

```bash
# 查看显存使用
python -c "
import torch
print(f'Allocated: {torch.cuda.memory_allocated(0)/1e9:.1f} GB')
print(f'Reserved:  {torch.cuda.memory_reserved(0)/1e9:.1f} GB')
"

# 如果 API 服务 OOM，降低并发
export MINERU_MAX_CONCURRENT_REQUESTS=1
```

### 4.3 WSL2 配置文件

创建 `C:\Users\<用户名>\.wslconfig`（Windows 侧）：

```ini
[wsl2]
memory=12GB          # 限制 WSL2 内存使用（你有 16GB 总内存）
processors=8        # 限制 CPU 核心数
swap=4GB            # 交换空间
```

> 配置后需要 `wsl --shutdown` 再重启生效。

### 4.4 DNS 修复（每次 wsl --shutdown 后）

```bash
# 如果 ping 外网不通
sudo rm -f /etc/resolv.conf
sudo sh -c 'echo -e "nameserver 8.8.8.8\nnameserver 114.114.114.114" > /etc/resolv.conf'
```

> 加到 `~/.bashrc` 的末尾可以自动执行：
> ```bash
> echo 'sudo rm -f /etc/resolv.conf && sudo sh -c "echo -e \"nameserver 8.8.8.8\nnameserver 114.114.114.114\" > /etc/resolv.conf" 2>/dev/null' >> ~/.bashrc
> ```
> 但这会让每次打开终端都要求 sudo 密码。建议手动执行。

---

## 五、服务管理

### 5.1 优雅关闭

```bash
# mineru-api 和 mineru-gradio 按 Ctrl+C 即可
# 如果有残留进程
pkill -f mineru
```

### 5.2 后台运行

```bash
# 让 API 服务在后台持续运行
nohup mineru-api --host 0.0.0.0 --port 8000 > ~/mineru_api.log 2>&1 &

# 查看日志
tail -f ~/mineru_api.log

# 停止
pkill -f mineru-api
```

### 5.3 开机自启

编辑 `/etc/wsl.conf`：

```bash
sudo sh -c 'cat > /etc/wsl.conf << EOF
[boot]
command = /bin/su - dev -c "cd /home/dev/mineru_stable && .venv/bin/nohup mineru-api --host 0.0.0.0 --port 8000 > /home/dev/mineru_api.log 2>&1 &"
EOF'
```

---

## 六、性能诊断

### 6.1 速度突然变慢？

排查顺序：
1. **是不是重启了？** → 首次运行有 JIT 编译，正常
2. **是不是换了 PDF？** → 不同 PDF 的页面复杂度影响 OCR 时间
3. **是不是 Triton 缓存在重建？** → `ls ~/.triton/cache/` 看数量
4. **是不是掉到 CPU 了？** → 检查 `torch.cuda.is_available()`
5. **是不是 ROCm 升级了？** → MIOpen 缓存失效

### 6.2 基准性能

在 RX 9070 上，hybrid-auto-engine 预热后的正常速度：

| 阶段 | 正常 | 偏慢 | 严重问题 |
|------|------|------|---------|
| VLM 模型加载 | 3-5s | 10-20s | >60s（可能磁盘慢） |
| Two Step Extraction | 2-4s/it | 5-8s/it | >10s/it（可能 CPU fallback） |
| Processing pages | 60-100 it/s | 30-60 it/s | <20 it/s（可能 CPU fallback） |
| 1 页 PDF 总耗时 | 5-15s | 15-30s | >60s |

### 6.3 用 nvitop 替代品监控 GPU

```bash
# AMD GPU 没有 nvidia-smi，用 rocm-smi 和 radeontop
/opt/rocm/bin/rocm-smi --showuse

# 或监控显存
watch -n 1 '/opt/rocm/bin/rocm-smi --showmemuse'
```

---

## 七、输出质量自查

### 7.1 快速判断解析是否正常

```bash
# 查看输出的 Markdown 文件
cat output/<文件名>/hybrid_auto/<文件名>.md

# 正常输出应该有：标题层级、段落文字、表格（如有）
# 异常特征：全空、乱码、只有图片路径、大量重复字符
```

### 7.2 质量不如预期时

1. **中文识别不准** → 加 `-l ch` 参数
2. **表格漏了** → 确保用了 `hybrid-auto-engine` 而非 `pipeline`
3. **公式乱码** → pipeline 后端对公式支持弱于 vlm 后端
4. **扫描件效果差** → 试试 `-m ocr` 强制 OCR 模式
5. **输出太多噪声** → 检查 PDF 本身质量（水印、背景纹理等）

---

## 八、备份策略

### 8.1 最小备份

以下是你绝对不能丢的东西（加起来不到 1MB）：

```bash
# 备份到 Windows 桌面
mkdir -p /mnt/c/Users/14044/Desktop/mineru_backup

# 配置文件
cp ~/mineru.json /mnt/c/Users/14044/Desktop/mineru_backup/ 2>/dev/null
cp ~/.bashrc /mnt/c/Users/14044/Desktop/mineru_backup/bashrc_backup

# Patch 后的文件（避免重新手动改）
mkdir -p /mnt/c/Users/14044/Desktop/mineru_backup/patches
cp ~/mineru_stable/.venv/lib/python3.13/site-packages/mineru/model/utils/tools/infer/predict_rec.py \
   /mnt/c/Users/14044/Desktop/mineru_backup/patches/
cp ~/mineru_stable/.venv/lib/python3.13/site-packages/mineru/model/utils/tools/infer/predict_det.py \
   /mnt/c/Users/14044/Desktop/mineru_backup/patches/
cp ~/vllm/vllm/platforms/__init__.py /mnt/c/Users/14044/Desktop/mineru_backup/patches/vllm_init.py
cp ~/vllm/vllm/platforms/rocm.py /mnt/c/Users/14044/Desktop/mineru_backup/patches/vllm_rocm.py
```

### 8.2 完整备份（虚拟环境）

```bash
# 打包整个虚拟环境（约 15GB，很大）
cd ~ && tar -czf mineru_env_backup.tar.gz mineru_stable/

# 复制到 Windows
cp ~/mineru_env_backup.tar.gz /mnt/c/Users/14044/Desktop/
```

### 8.3 恢复

```bash
# 最小恢复：重跑部署教程（1-2小时）
# 备份恢复：
cd ~ && tar -xzf ~/mineru_env_backup.tar.gz
```

---

## 九、本次部署的核心经验

### 为什么这个环境能跑而之前的不行

1. **Ubuntu 22.04 而非 24.04**：22.04 能用 snap 装 cmake 4.x，24.04 的 cmake 3.28 太旧
2. **ROCm 7.1.1 而非 7.2.1**：cmake 包名兼容性更好，社区验证充分
3. **pip 而非 uv pip**：uv pip 的依赖解析太激进，会主动替换 ROCm PyTorch
4. **hipblas-dev 装真头文件而非创建符号链接**：符号链接会导致 `internal/` include 路径丢失
5. **pytorch-triton-rocm 是完整版 triton**：274MB 不是虚包，不能和 triton-rocm 共存
6. **vllm WSL2 平台检测需要 patch**：amdsmi 在 WSL2 无法初始化是硬伤，必须绕过
7. **vllm 0.21 已有 conv3d F.linear 优化**：不需要 Discussion #3662 的 vllm patch

### 如果一切重来，最快的路径是什么

1. 按 [MinerU本地部署教程.md](MinerU本地部署教程.md) 一步不跳地走完
2. 遇到报错，查本文附录（26项踩坑清单），按关键字搜索
3. 部署完跑一次 MIOpen 预热
4. 第一次跑 PDF 时喝杯咖啡等 JIT 编译
5. 之后每次都是一行命令

### 最可能踩的坑 Top 5

| # | 现象 | 一秒定位 |
|---|------|---------|
| 1 | `import torch` 后 GPU 不可用 | `python -c "import torch; print('rocm' in torch.__version__)"` → False 说明 PyTorch 被覆盖 |
| 2 | vllm 报 "Device string must not be empty" | vllm 平台检测失败，检查 patch 是否还在 |
| 3 | 第一次解析极慢（>2min/页） | 正常！第二次就好了 |
| 4 | `ping huggingface.co` 不通 | DNS 掉了，修复 /etc/resolv.conf |
| 5 | `rocminfo` 只显示 CPU | `HSA_ENABLE_DXG_DETECTION` 没设，或 /dev/dxg 不存在 |

---

## 十、文档导航

### 我们写的教程

| 我想... | 看这个 |
|---------|--------|
| 从头部署 | [MinerU本地部署教程.md](MinerU本地部署教程.md) |
| 日常使用 | [MinerU本地使用指南.md](MinerU本地使用指南.md) |
| 更新 MinerU | [MinerU本地更新指南.md](MinerU本地更新指南.md) |
| 管理/替换模型 | [MinerU模型管理指南.md](MinerU模型管理指南.md) |
| 升级 ROCm | [ROCm7.2升级指南.md](ROCm7.2升级指南.md) |
| 出问题排查 + 速查 | 本文 第三、四、五、九节 |
| 搜具体报错 | 本文 [附录：完整踩坑清单](#十一附录完整踩坑清单26-项) |

### 官方参考文档（在 `../参考文档/` 下）

| 文档 | 来源 |
|------|------|
| [MinerU命令行工具参考.md](../参考文档/MinerU命令行工具参考.md) | 官方 CLI 完整帮助 + 环境变量列表 |
| [MinerU进阶参数参考.md](../参考文档/MinerU进阶参数参考.md) | 官方 vllm/lmdeploy 参数透传 + GPU 选择 |
| [MinerU模型源配置参考.md](../参考文档/MinerU模型源配置参考.md) | 官方模型源切换 + models-download 说明 |
| [MinerU扩展模块安装参考.md](../参考文档/MinerU扩展模块安装参考.md) | 官方 core/vllm/lmdeploy/pipeline 安装变体 |
| [WSL2-依赖库补充.md](../参考文档/WSL2-依赖库补充.md) | WSL2 上 libGL.so.1 缺失的解决方案 |
| [基础使用 - MinerU.md](../参考文档/基础使用 - MinerU.md) | 官方快速入门 |
| [MinerU API 文档（新的）.md](../参考文档/MinerU%20API%20文档（新的）.md) | 官网 API 开发者文档 |
| [README_zh-CN.md](../参考文档/README_zh-CN.md) | MinerU 官方 README |
| [Discussion-3662-AMD-RDNA-适配参考.md](../参考文档/Discussion-3662-AMD-RDNA-适配参考.md) | 社区 AMD 适配讨论 |

---

## 十一、附录：完整踩坑清单（26 项）

> 从这里直接搜报错关键字，快速定位解决方案。

| # | 问题 | 原因 / 解决 |
|---|------|------------|
| 1 | librocdxg 报 `ntstatus.h` 找不到 | WIN_SDK 必须指向 `shared/` 子目录而非 SDK 根目录 |
| 2 | rocminfo 显示 "ROCk module NOT loaded" | Ubuntu 自带 rocminfo 5.7.1 不认识 librocdxg，必须用 `--allow-downgrades` 装 ROCm 版 |
| 3 | ldconfig 加载旧版 libhsa-runtime64 | 需 `echo /opt/rocm/lib > /etc/ld.so.conf.d/rocm.conf && ldconfig` |
| 4 | PyTorch 启动崩溃 "Found 0 rocprofiler agents" | PyTorch 2.12+ 在 WSL2 无 KFD 拓扑，必须用 2.11.x |
| 5 | mineru[core] 安装后 GPU 不能用 | `uv pip` 覆盖 PyTorch 为 CUDA 版；用 `pip` 装 mineru，或立即重装 ROCm PyTorch |
| 6 | `pip install vllm` 破坏 ROCm 环境 | PyPI 上 vllm 只有 CUDA 版，必须从源码编译 |
| 7 | `ping` 外网不通 | WSL2 systemd-resolved 不完善，需手动写 `/etc/resolv.conf`（每次 `wsl --shutdown` 后） |
| 8 | ROCm 仓库用了 jammy 在 noble 上 | Ubuntu 24.04 是 noble，Ubuntu 22.04 是 jammy，不能混用 |
| 9 | cmake 报版本太旧 | Ubuntu 22.04 自带 cmake 3.22，vllm 需要 4.x；用 `snap install cmake --classic` |
| 10 | cmake 报 `hiprand` not found | ROCm 7.x 重命名为 `rocrand`，需创建 cmake alias wrapper |
| 11 | 编译报 `internal/rocblas-auxiliary.h` 找不到 | 符号链接 `hipblas.h → rocblas.h` 不够，rocblas.h 内部有相对 include 引用 |
| 12 | 同上 | 必须 `apt install hipblas-dev` 获取真实的 1.4MB hipblas.h（含完整兼容层） |
| 13 | 同上 | 必须 `apt install hiprand-dev` 同理 |
| 14 | cmake 报 "No GPU arch specified" | `-DPYTORCH_ROCM_ARCH=gfx1201` 不生效，必须 `export` 为环境变量 |
| 15 | ninja 编译时 OOM 被 kill（exit 137） | 16GB 内存不能全开并行，`ninja -j4` 限制 |
| 16 | `import triton` 报 `no attribute 'language'` | `pytorch-triton-rocm` 3.5.1（274MB）是完整版，不可与 `triton-rocm` 3.6.0 共存 |
| 17 | `python setup.py develop` 报 "CUDA_HOME is not set" | 需要 `VLLM_TARGET_DEVICE=rocm PYTORCH_ROCM_ARCH=gfx1201` 环境变量 |
| 18 | amdsmi 初始化失败 `AMDSMI_STATUS_DRIVER_NOT_LOADED` | WSL2 无 Linux KFD 驱动，amdsmi 无法工作（需要在 WSL2 中绕过） |
| 19 | vllm 报 "Device string must not be empty" | vllm 平台检测 fallback 到 UnspecifiedPlatform；需 patch 两个文件用 torch.version.hip 回退 |
| 20 | Discussion #3662 vllm patch 还需要吗 | 不需要 — vllm 0.21 内置 `Conv3dLayer._forward_mulmat()` 已实现 F.linear 优化 |
| 21 | Discussion #3662 doclayout_yolo patch 还需要吗 | 不适用 — MinerU 3.x 已移除 doclayout_yolo |
| 22 | `pip install amd_smi/` 报权限错误 | `/opt/rocm` 只读；需 `cp -r` 到用户目录再安装，加 `--no-build-isolation` |
| 23 | OCR 阶段偶尔 7 秒延迟 | MIOpen conv2d 冷启动 — predict_rec.py / predict_det.py 的 patch 仍需手动应用 |
| 24 | pip install 各种超时 | 加 `-i https://pypi.mirrors.ustc.edu.cn/simple/` 用国内镜像 |
| 25 | `python3.13` 命令不存在 | Ubuntu 22.04 默认无 Python 3.13，需 `add-apt-repository ppa:deadsnakes/ppa` |
| 26 | cmake 输出 "Timeout querying rocminfo" | 无害警告，可忽略 |

---

*最后更新: 2026-05-24*
*这环境能跑，别再从头来了。*
