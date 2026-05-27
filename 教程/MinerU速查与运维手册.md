# MinerU 速查与运维手册

> 日常会用到的命令、判断方法和踩出来的经验
> 三轮验证部署累计的踩坑清单已扩展到 32 项

---

## 一、速查卡片（打印 / 截图保存）

### WSL2 从零启动

```powershell
# Windows PowerShell（管理员）
wsl -d Ubuntu-22.04          # 路径 A
# 或
wsl -d Ubuntu-24.04          # 路径 B
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
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"

# vllm 平台是否识别
python -c "from vllm.platforms import current_platform; print(type(current_platform).__name__, current_platform.is_rocm())"
```

理想输出：

```
AMD Radeon RX 9070  (Agent 2 输出节选)
2.11.0+rocm7.1 True AMD Radeon RX 9070
RocmPlatform True
```

---

## 二、建议避免的操作

以下操作在 AMD ROCm / WSL2 环境下可能导致问题：

| 操作 | 后果 | 补救 |
|------|------|------|
| `uv pip install mineru[core]` | 可能覆盖 ROCm PyTorch 为 CUDA 版 | 重装 `torch==2.11.0+rocm7.x` |
| `pip install vllm`（从 PyPI） | 安装 CUDA 版 vllm | 卸载后从源码重编译 |
| `pip install torch --upgrade`（WSL2） | 装上 2.12+，程序崩溃 | 降回 2.11.0 |
| `sudo apt autoremove` | 可能误删 ROCm 依赖 | 重装被误删的包 |
| `sudo snap install cmake`（WSL2） | snapd 阻塞，永远不返回 | 直接用 Kitware 二进制 |
| `pip uninstall triton` 后 `pytorch-triton-rocm` | 共享目录被删，ROCm Triton 丢失 | 必须先 `--force-reinstall pytorch-triton-rocm` 再 uninstall |

### 安全的操作

| 操作 | 备注 |
|------|------|
| `pip install --upgrade mineru[core]` | 用 pip，不要用 uv pip；升级后立即查 PyTorch |
| 删除 `~/.cache/huggingface/hub/` | 下次运行重新下载 |
| 删除 `~/.triton/cache/` | 下次 JIT 重新编译（首次会慢） |
| 删除 `~/.cache/miopen/` | 需要重新预热（按部署教程第十二步） |

---

## 三、正常 vs 异常：学会看日志

### 首次运行正常的日志

```
VLM model load: 46.04s                       ← 正常，首次加载模型
Triton kernel JIT compilation: ...           ← 正常，首次编译缓存
Two Step Extraction: 100%|...| 7.94s/it      ← 首次慢（JIT 编译），后续会快
Processing pages: 100%|...| 83it/s           ← 一直这么快就正常
Completed batch 1/1                          ← 成功
```

### 应该警惕的日志

```
Found 0 rocprofiler agents                       ← PyTorch ≥ 2.12 被装上了
Device string must not be empty                  ← vllm 没检测到 ROCm
NotImplementedError ... UnspecifiedPlatform     ← rocm.py 循环导入坑，补丁 B 未生效
Error code: 34 | DRIVER_NOT_LOADED              ← amdsmi 在 WSL2 启动时无法初始化，属预期现象（已被 vllm patch 兜底）
Using 'pin_memory=False' as WSL is detected     ← 正常，WSL2 限制
ImportError: cannot import name '_ON_GFX942'    ← rocm.py 补丁误删了模块级常量，重新精确打 patch
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

### 4.2 内存与显存管理

hybrid-auto-engine 实测显存占用约 8.3GB（不含系统占用），16GB 和 12GB 卡很从容。8GB 卡需限制 vllm 占用或使用 pipeline 后端：

```bash
# 查看显存使用
python -c "
import torch
print(f'Allocated: {torch.cuda.memory_allocated(0)/1e9:.1f} GB')
print(f'Reserved:  {torch.cuda.memory_reserved(0)/1e9:.1f} GB')
"

# 告诉 MinerU 显存上限（GB 为单位，8GB 显卡推荐）
export MINERU_VIRTUAL_VRAM_SIZE=6

# 如果 API 服务 OOM，降低并发
export MINERU_API_MAX_CONCURRENT_REQUESTS=1
```

### 4.3 `.wslconfig` 关键参数

`C:\Users\<用户名>\.wslconfig`（Windows 侧）：

```ini
[wsl2]
memory=12GB                  # WSL2 内存上限（16GB 物理内存时推荐）
processors=8
swap=4GB
networkingMode=mirrored      # 让 WSL2 共享 Windows 网卡
dnsTunneling=true            # DNS 走虚拟化通道
firewall=true                # 同步 Windows 防火墙规则
autoProxy=true               # 自动注入宿主机代理变量
hostAddressLoopback=true     # Windows 可通过 LAN IP 访问 WSL2 服务
```

修改后必须 `wsl --shutdown` 才生效。

### 4.4 Hyper-V 防火墙放行（启用 `firewall=true` 后必须做）

否则 vllm engine 子进程间 IPC 通信被阻断，浏览器也无法访问 WSL 内服务。

```powershell
# Windows PowerShell（管理员）
Set-NetFirewallHyperVVMSetting -Name '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -DefaultInboundAction Allow
```

或者只放行你需要的端口：

```powershell
New-NetFirewallHyperVRule -Name "WSL2" -DisplayName "WSL2 Services" `
  -Direction Inbound -VMCreatorId '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' `
  -Protocol TCP -LocalPorts 80,443,3000,7860,8000,8080
```

### 4.5 DNS 修复（每次 `wsl --shutdown` 后检查）

systemd-resolved 可能把 `/etc/resolv.conf` 重置为 `127.0.0.53`，导致内网外网都通不了。

```bash
cat /etc/resolv.conf
# 如果只看到 nameserver 127.0.0.53：
sudo rm -f /etc/resolv.conf
echo 'nameserver 223.5.5.5' | sudo tee /etc/resolv.conf
```

> 加到 `~/.bashrc` 末尾可以自动执行（但会每次问 sudo 密码，不推荐）：
> ```bash
> echo 'sudo rm -f /etc/resolv.conf && echo "nameserver 223.5.5.5" | sudo tee /etc/resolv.conf 2>/dev/null' >> ~/.bashrc
> ```

### 4.6 Clash TUN 启动顺序

**永远先开 Clash TUN，再启 WSL2**。镜像网络在 WSL 启动瞬间抓取 Windows 路由表快照——如果顺序反了，WSL 看不到 TUN 网卡，所有 Fake-IP 全变成死 IP。

中途切换代理后需 `wsl --shutdown` 重启 WSL。

---

## 五、服务管理

### 5.1 优雅关闭

```bash
# mineru-api / mineru-gradio：按 Ctrl+C
# 残留进程：
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

编辑 `/etc/wsl.conf`（注意：`boot.command` 以 root 运行，`$USER` 在 root 环境下未定义，需要把用户名写死）：

```bash
sudo tee /etc/wsl.conf > /dev/null << EOF
[boot]
systemd=true
command = /bin/su - $USER -c "cd \$HOME/mineru_stable && nohup .venv/bin/mineru-api --host 0.0.0.0 --port 8000 > \$HOME/mineru_api.log 2>&1 &"
EOF
```

> 上面利用外层 shell 在写入文件时把 `$USER` 替换为当前用户名；`\$HOME` 保留字面，留到 `su -` 启动子 shell 时再展开。

---

## 六、性能诊断

### 6.1 速度突然变慢？

排查顺序：

1. **是不是重启了？** → 首次运行有 JIT 编译，正常
2. **是不是换了 PDF？** → 不同 PDF 的页面复杂度影响 OCR 时间
3. **是不是 Triton 缓存在重建？** → `ls ~/.triton/cache/` 看数量
4. **是不是掉到 CPU 了？** → 检查 `torch.cuda.is_available()`
5. **是不是 ROCm 升级了？** → MIOpen 缓存失效，重新预热

### 6.2 参考耗时（RX 9070 实测）

`example.pdf` (13 页) 在 RX 9070 上连续运行三次的稳定状态：

| 阶段 | 路径 A (22.04+7.1.1) | 路径 B (24.04+7.2.1) |
|------|---------|---------|
| VLM 推理 (Two Step Extraction) | ~6s (1.98 it/s) | ~5s |
| 版面与 OCR (Processing pages) | <1s (61 it/s) | <1s (65-71 it/s) |
| 13 页总耗时 | 6-7s | 5-7s |

如果你的速度远慢于这个数量级（比如 Two Step Extraction 只有 0.1 it/s），先检查是否掉到了 CPU：
```bash
python -c "import torch; print(torch.cuda.is_available())"
```

### 6.3 GPU 监控（AMD 版的 nvidia-smi）

```bash
# AMD GPU 没有 nvidia-smi / nvitop，用 rocm-smi 和 radeontop
/opt/rocm/bin/rocm-smi --showuse

# 或监控显存
watch -n 1 '/opt/rocm/bin/rocm-smi --showmemuse'
```

> WSL2 中 `rocm-smi` 依赖 KFD，可能报错。`/opt/rocm/bin/rocminfo` 总是可用，可以替代查 GPU 状态。

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

建议备份以下文件（加起来不到 1MB），省得重装后手动改：

```bash
# 备份到 Windows 桌面
mkdir -p /mnt/c/Users/<用户名>/Desktop/mineru_backup

# 配置文件
cp ~/mineru.json /mnt/c/Users/<用户名>/Desktop/mineru_backup/ 2>/dev/null
cp ~/.bashrc /mnt/c/Users/<用户名>/Desktop/mineru_backup/bashrc_backup

# Patch 后的文件（避免重新手动改）
PYVER=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
mkdir -p /mnt/c/Users/<用户名>/Desktop/mineru_backup/patches
cp ~/mineru_stable/.venv/lib/python${PYVER}/site-packages/mineru/model/utils/tools/infer/predict_rec.py \
   /mnt/c/Users/<用户名>/Desktop/mineru_backup/patches/
cp ~/mineru_stable/.venv/lib/python${PYVER}/site-packages/mineru/model/utils/tools/infer/predict_det.py \
   /mnt/c/Users/<用户名>/Desktop/mineru_backup/patches/
cp ~/vllm/vllm/platforms/__init__.py /mnt/c/Users/<用户名>/Desktop/mineru_backup/patches/vllm_init.py
cp ~/vllm/vllm/platforms/rocm.py     /mnt/c/Users/<用户名>/Desktop/mineru_backup/patches/vllm_rocm.py
```

### 8.2 完整备份（虚拟环境）

```bash
# 打包整个虚拟环境（约 15GB）
cd ~ && tar -czf mineru_env_backup.tar.gz mineru_stable/

# 复制到 Windows
cp ~/mineru_env_backup.tar.gz /mnt/c/Users/<用户名>/Desktop/
```

### 8.3 整体 WSL 备份（推荐）

```powershell
# Windows PowerShell（管理员）
wsl --export Ubuntu-22.04 D:\WSL\ubuntu-22.04-mineru.tar
# 大小约 60-80GB，时间约 5-10 分钟
```

恢复：

```powershell
wsl --import Ubuntu-22.04 C:\WSL\Ubuntu-22.04 D:\WSL\ubuntu-22.04-mineru.tar
```

---

## 九、本次部署的核心经验

### 为什么这套环境能跑而之前的不行

1. **Ubuntu 22.04 + ROCm 7.1.1 是稳定路径**：LLVM 17 + ROCm 头文件天然匹配，零额外补丁
2. **Ubuntu 24.04 必须配 ROCm 7.2.1**：7.1.1 在 24.04 上的 LLVM 20 兼容问题无法绕过
3. **pip 而非 uv pip**：uv pip 依赖解析太激进，会主动替换 ROCm PyTorch
4. **hipblas-dev 装真头文件而非创建符号链接**：符号链接会导致 `internal/` include 路径丢失
5. **`hipsparselt-dev` 是必装项**：PyTorch ROCm 版的 `Caffe2Targets.cmake` 硬编码引用
6. **`pytorch-triton-rocm` 与 `triton` 共享目录**：恢复顺序错了会自毁
7. **vllm 用最新 main 而非旧 commit**：旧 commit 357fddf61 有 PEP 639 与 rocm.py 循环导入双重坑
8. **rocm.py 的 `logger.warning_once` 是循环导入元凶**：必须替换，单纯改 `__init__.py` 不够
9. **cmake 4.0 不能用 hipcc 包装器**：要求底层 clang，并需要 `CMAKE_HIP_ARCHITECTURES`
10. **Hyper-V 防火墙默认拦截入站**：vllm 子进程通信会被切

### 如果一切重来，最快的路径是什么

1. 按 [MinerU本地部署教程.md](MinerU本地部署教程.md) 路径 A 一步不跳地走完
2. 遇到报错，查本文第十一节的完整踩坑清单，按关键字搜索
3. 部署完跑一次 MIOpen 预热
4. 第一次跑 PDF 时喝杯咖啡等 JIT 编译
5. 之后每次都是一行命令

### 最可能踩的坑 Top 5

| # | 现象 | 一秒定位 |
|---|------|---------|
| 1 | `import torch` 后 GPU 不可用 | `python -c "import torch; print('rocm' in torch.__version__)"` → False 说明 PyTorch 被覆盖 |
| 2 | vllm 报 "Device string must not be empty" | vllm 平台检测失败，检查两个 patch 是否还在 |
| 3 | vllm `NotImplementedError ... UnspecifiedPlatform` | rocm.py 循环导入未修，补丁 B 没生效 |
| 4 | 第一次解析极慢（>2min/页） | 正常！第二次就好了 |
| 5 | `curl https://github.com` 卡死 / `rocminfo` 只显示 CPU | TUN MTU 没改为 1500 / Hyper-V 防火墙没放行 / `HSA_ENABLE_DXG_DETECTION` 没设 |

---

## 十、文档导航

### 我们写的教程

| 我想... | 看这个 |
|---------|--------|
| 从头部署（推荐路径） | [MinerU本地部署教程.md](MinerU本地部署教程.md) |
| 24.04 + 较新 ROCm 部署 | [ROCm7.2升级指南.md](ROCm7.2升级指南.md) |
| 日常使用 | [MinerU本地使用指南.md](MinerU本地使用指南.md) |
| 更新 MinerU | [MinerU本地更新指南.md](MinerU本地更新指南.md) |
| 管理 / 替换模型 | [MinerU模型管理指南.md](MinerU模型管理指南.md) |
| N 卡云端部署对照 | [N卡部署教程.md](N卡部署教程.md) |
| 出问题排查 + 速查 | 本文 第三、四、六、九、十一节 |
| 搜具体报错关键字 | 本文 [附录：完整踩坑清单](#十一附录完整踩坑清单32-项) |

### 官方参考文档（在 `../参考文档/` 下）

| 文档 | 来源 |
|------|------|
| [MinerU命令行工具参考.md](../参考文档/MinerU命令行工具参考.md) | 官方 CLI 完整帮助 + 环境变量列表 |
| [MinerU进阶参数参考.md](../参考文档/MinerU进阶参数参考.md) | 官方 vllm/lmdeploy 参数透传 + GPU 选择 |
| [MinerU模型源配置参考.md](../参考文档/MinerU模型源配置参考.md) | 官方模型源切换 + models-download 说明 |
| [MinerU扩展模块安装参考.md](../参考文档/MinerU扩展模块安装参考.md) | 官方 core/vllm/lmdeploy/pipeline 安装变体 |
| [WSL2-依赖库补充.md](../参考文档/WSL2-依赖库补充.md) | WSL2 上 libGL.so.1 缺失的解决方案 |
| [基础使用 - MinerU.md](../参考文档/基础使用%20-%20MinerU.md) | 官方快速入门 |
| [MinerU API 文档（新的）.md](../参考文档/MinerU%20API%20文档（新的）.md) | 官网 API 开发者文档 |
| [README_zh-CN.md](../参考文档/README_zh-CN.md) | MinerU 官方 README |
| [Discussion-3662-AMD-RDNA-适配参考.md](../参考文档/Discussion-3662-AMD-RDNA-适配参考.md) | 社区 AMD 适配讨论原文 |

---

## 十一、附录：完整踩坑清单（32 项）

> 从这里直接搜报错关键字，快速定位解决方案。

### 网络与 WSL 基础（1-7）

| # | 问题 | 原因 / 解决 |
|---|------|------------|
| 1 | `curl https://...` 在 TLS 握手后卡死 | Clash TUN MTU 默认 9000 在 WSL2 网卡（MTU 1500）被丢；改 TUN MTU 为 1500 |
| 2 | WSL2 看不到 TUN 路由（`ip route` 没有 198.18.x.x） | 启动顺序错了：永远先开 Clash TUN 再启 WSL；中途切代理后 `wsl --shutdown` |
| 3 | `ping` 外网不通 | systemd-resolved 把 resolv.conf 指向 127.0.0.53，按 4.5 节修复 |
| 4 | `sudo apt update` 绕开代理失败 | `Defaults env_keep += "http_proxy https_proxy ..."` 加到 sudoers |
| 5 | 浏览器访问 WSL 的 7860 / 8000 端口超时 | Hyper-V 防火墙拦截入站，按 4.4 节放行 |
| 6 | vllm engine 子进程 IPC 报错 | 同上，Hyper-V 防火墙阻断 |
| 7 | mDNS / `.local` 域名解析失败 | `dnsTunneling=true` 不转发多播；装 `libnss-mdns` 并配 nsswitch |

### ROCm 与底层依赖（8-13）

| # | 问题 | 原因 / 解决 |
|---|------|------------|
| 8 | librocdxg 报 `ntstatus.h: No such file or directory` | WIN_SDK 必须指向 `shared/` 子目录而非 SDK 根目录 |
| 9 | rocminfo 显示 "ROCk module NOT loaded" | Ubuntu 自带 rocminfo 太旧不识别 librocdxg，用 `--allow-downgrades` 装 ROCm 版 |
| 10 | ldconfig 加载旧版 libhsa-runtime64 | `echo /opt/rocm/lib > /etc/ld.so.conf.d/rocm.conf && ldconfig` |
| 11 | rocminfo 只显示 CPU 没 GPU | `HSA_ENABLE_DXG_DETECTION=1` 没设、`/dev/dxg` 不存在、AMD 驱动没装 |
| 12 | `sudo snap install cmake` 永远阻塞 | snapd 在 WSL2 无 systemd mount namespace；改用 Kitware 二进制 |
| 13 | ROCm 仓库用了 jammy 在 noble 上（或反之） | Ubuntu 22.04 是 jammy，24.04 是 noble，不能混 |

### PyTorch 与 Triton（14-17）

| # | 问题 | 原因 / 解决 |
|---|------|------------|
| 14 | PyTorch 启动崩溃 "Found 0 rocprofiler agents" | PyTorch ≥ 2.12 在 WSL2 无 KFD 拓扑，必须用 2.11.x |
| 15 | mineru[core] / flash_attn / vllm 装完后 GPU 不能用 | `uv pip` 或依赖解析覆盖 PyTorch 为 CUDA 版；按 [部署教程 8.3](MinerU本地部署教程.md#83-立即验证-pytorch-是否被覆盖) 顺序恢复 |
| 16 | `pip install vllm`（PyPI）破坏 ROCm 环境 | PyPI 上 vllm 只有 CUDA wheel，必须从源码编译 |
| 17 | `import triton` 报 `no attribute 'language'` 或目录文件丢失 | `pytorch-triton-rocm` 与 `triton` 共享 `triton/` 目录；正确顺序：**先 `--force-reinstall pytorch-triton-rocm` 再 `uninstall triton triton-rocm`** |

### vllm 编译（18-23）

| # | 问题 | 原因 / 解决 |
|---|------|------------|
| 18 | cmake 报版本太旧 | Ubuntu 自带 cmake 不够 4.0；用 Kitware 二进制 |
| 19 | cmake 报 "Failed to find ROCm root directory" | PATH 没包含 `/opt/rocm/bin`，cmake 找不到 hipconfig |
| 20 | cmake 报 "Failed to find a default HIP architecture" | WSL2 中 `rocm_agent_enumerator` 失效，必须显式 `-DCMAKE_HIP_ARCHITECTURES=gfxXXXX` |
| 21 | cmake 报 `CMAKE_HIP_COMPILER ... refusing` | 不能设 `-DCMAKE_HIP_COMPILER=hipcc`；CMake 4.0 拒绝 Perl 包装器，要求底层 Clang |
| 22 | cmake 报 `roc::hipsparselt target not found` | 漏装 `hipsparselt-dev` |
| 23 | cmake 报 `hiprand not found` 之类 | 多见于 ROCm 7.2；按 [部署教程 9.5](MinerU本地部署教程.md#95-rocm-711-下的-cmake-别名多数情况不需要) 创建别名 |

### vllm pip 安装与运行（24-27）

| # | 问题 | 原因 / 解决 |
|---|------|------------|
| 24 | `pip install -e .` 报缺少 wheel / setuptools_rust / setuptools_scm | 装 `setuptools>=77.0.3 setuptools_scm setuptools_rust wheel` |
| 25 | vllm pyproject.toml 报 `license-files` 错误 | 旧 commit 357fddf61 的 PEP 639 写法；改用 vllm main 或升级 setuptools |
| 26 | vllm 报 "Device string must not be empty" | 平台检测 fallback 到 UnspecifiedPlatform；按部署教程 9.10 补丁 A |
| 27 | vllm 报 `NotImplementedError` 来自 `UnspecifiedPlatform.check_if_supports_dtype` | `rocm.py` 的 `logger.warning_once` 触发循环导入，按部署教程 9.10 补丁 B |

### MinerU & RDNA 适配（28-30）

| # | 问题 | 原因 / 解决 |
|---|------|------------|
| 28 | rocm.py patch 后报 `ImportError: cannot import name '_ON_GFX942'` | 旧补丁正则匹配过宽误删常量；按部署教程 9.10 精确替换 except 块 |
| 29 | OCR 阶段偶尔 7 秒延迟 | MIOpen conv2d 冷启动；按部署教程 10.3 应用 RDNA 补丁 + 跑 cache_warmer.py |
| 30 | 升级 MinerU 后 RDNA 补丁位置找不到 | 不同版本行号会变；按更新指南用 grep 重新定位关键行 |

### 编译资源与琐碎（31-32）

| # | 问题 | 原因 / 解决 |
|---|------|------------|
| 31 | ninja 编译时 OOM 被 kill（exit 137） | 16GB 内存不能全开并行，`ninja -j4` 限制；或加大 `.wslconfig` 的 memory |
| 32 | `python3.13` 命令不存在（22.04） | `add-apt-repository ppa:deadsnakes/ppa` 后再装。24.04 默认 3.12，路径 B 不需要 3.13 |

---

*文档最后更新: 2026-05-27*
*这套环境能跑，参考第十一节避坑清单，别再从头来了。*
