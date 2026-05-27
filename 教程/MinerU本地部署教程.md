# MinerU AMD GPU 本地部署教程

> 在 AMD 显卡上部署 MinerU 3.x + vllm + hybrid-auto-engine
> 我们实际跑通了 RX 9070（gfx1201），其他 RDNA2/3/4 显卡可按相同流程套用
> **推荐组合**：Ubuntu 22.04 + ROCm 7.1.1 + PyTorch 2.11.0+rocm7.1 + vllm main + MinerU 3.2.0

本教程参考了 [Discussion #3662](https://github.com/opendatalab/MinerU/discussions/3662)、[AMD WSL2 官方指南](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installrad/wsl/howto_wsl.html) 和 [librocdxg](https://github.com/ROCm/librocdxg)。每一步都在 RX 9070 (gfx1201) + Windows 11 Pro WSL2 上**实际验证过**（首版 2026-05-25，三轮验证修订于 2026-05-27）。

**两条已验证的部署路径**：

| 路径 | 系统 | ROCm | 适用场景 |
|------|------|------|---------|
| **A（推荐）** | Ubuntu 22.04 (jammy) | 7.1.1 | 稳定优先，社区验证最充分 |
| **B（较新）** | Ubuntu 24.04 (noble) | 7.2.1 | 需要最新内核 / 想体验 RDNA4 正式支持 |

⚠️ **明确不可行**：Ubuntu 24.04 + ROCm 7.1.1。Ubuntu 24.04 上的 ROCm 7.1.1 用 LLVM 20，但 ROCm 头文件没适配，编译 vllm 时会撞上无法绕过的 FP8 类型错误。详见 [ROCm7.2升级指南.md](ROCm7.2升级指南.md)。

**本文重点描述路径 A**。如果你打算走路径 B，先读完本文（许多坑两条路径都会踩），再跳到 [ROCm7.2升级指南.md](ROCm7.2升级指南.md) 看 24.04 特有的补丁。

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
| RX 9070 XT / 9070 / 9070 GRE | gfx1201 | `gfx1201` | 不需要 | 我们实测通过（ROCm 7.2.1 起官方正式支持） |
| RX 9060 XT / 9060 XT LP | gfx1200 | `gfx1200` | 不需要 | RDNA4，ROCm 7.2 起官方支持 |
| RX 7900 XTX / XT / GRE | gfx1100 | `gfx1100` | 不需要 | 旗舰卡，ROCm 原生支持 |
| RX 7800 XT / 7700 XT | gfx1101 | `gfx1101` | 不需要 | Navi 32，ROCm 较新版已原生支持 |
| RX 7600 XT | gfx1102 | `gfx1102` | 如果 rocminfo 不识别则加 `11.0.0` | Navi 33，vllm 编译支持，但 ROCm 运行时官方未必收录 |
| RX 7600 | gfx1102 | `gfx1102` | 同上 | 8GB 显存，勉强能跑但不宽裕 |
| RX 6950 / 6900 / 6800 XT / 6800 | gfx1030 | `gfx1030` | 不需要 | Navi 21，16GB 版显存安全，未实测 |
| RX 6750 XT / 6700 XT / 6700 | gfx1031 | `gfx1030`（伪装编译） | 需要 `10.3.0` | Navi 22，vllm 官方未列 gfx1031，编译时按 gfx1030 + 运行时伪装即可；12GB 够用 |

**明确不支持的**：
- RDNA1 全系（RX 5700/5700 XT/5600 XT 为 gfx1010；RX 5500/5500 XT 为 gfx1012）——vllm 不支持此架构
- RX 6650 / 6600 XT / 6600（gfx1032，Navi 23）——vllm 未包含此变体，需要 `HSA_OVERRIDE_GFX_VERSION=10.3.0` 伪装为 gfx1030 试试，但不一定能跑通
- RX 6500 XT / 6400（gfx1034，Navi 24）——计算单元和显存都太少，ROCm 也不支持
- 集成显卡（APU / 核显）——WSL2 下共享显存机制容易出问题，未测试

**关于 `HSA_OVERRIDE_GFX_VERSION`**：

ROCm 编译时（vllm 的 `PYTORCH_ROCM_ARCH`）和运行时（rocminfo 识别）是两套机制。某些中端卡的架构代码虽然在 vllm 编译列表中，但 ROCm 运行时可能不主动识别它们。

如果 `rocminfo` 看不到你的显卡，或者运行时 MIOpen 报 "no kernel found"，在 `~/.bashrc` 中加一行：

```bash
# RX 7600 / 7600 XT（gfx1102）伪装成 7900 XTX（gfx1100，同是 RDNA3，架构兼容）
export HSA_OVERRIDE_GFX_VERSION=11.0.0

# RX 6700 系 / 6600 系（gfx1031 / gfx1032）伪装成 6900 XT（gfx1030）
export HSA_OVERRIDE_GFX_VERSION=10.3.0
```

然后 `source ~/.bashrc` 生效。这不会影响性能——同代架构内部是兼容的。

**8GB 显存遇到 OOM 怎么办**：

12GB 和 16GB 卡实测不会爆显存。8GB 卡如果遇到 `hipErrorOutOfMemory`：

1. 告诉 MinerU 显存上限（以 GB 为单位，触发更保守的并发 / KV cache 分配策略）：
   ```bash
   export MINERU_VIRTUAL_VRAM_SIZE=6
   ```
2. 或者换 pipeline 后端（不需要 vllm，显存占用低很多）：
   ```bash
   mineru -p input.pdf -o output -b pipeline -l ch
   ```

### 0.1 系统要求

| 项目 | 要求 |
|------|------|
| 系统 | Windows 11 (WSL2) 或 原生 Linux (Ubuntu 22.04/24.04) |
| 内存 | ≥ 16GB |
| 显存 | ≥ 8GB（推荐 16GB+，否则调低并发或换 pipeline 后端） |
| 磁盘 | ≥ 50GB |

如果你是原生 Linux（不是 WSL2），部署会简单不少——跳过第四步（librocdxg 编译），amdsmi 也能正常工作，vllm 不需要 patch。

### 0.2 为什么选这些版本

| 组件 | 推荐版本（路径 A） | 说明 |
|------|------|------|
| Ubuntu | 22.04 (jammy) | vllm 编译需要 cmake ≥ 4.0；社区验证最充分 |
| ROCm | 7.1.1 | 与 22.04 仓库（LLVM 17）完美匹配，是目前最稳定的组合 |
| Python | 3.13 | 与 PyTorch ROCm 7.1 nightly wheel 完全匹配；3.12 也可以 |
| PyTorch | 2.11.0+rocm7.1 | WSL2 必须锁定，详见下方 |
| vllm | 最新 main | PyPI 只有 CUDA 版，需从源码编译；旧 commit `357fddf61` 有过时的 PEP 639 问题 |
| MinerU | 3.2.0 | 当前 PyPI 最新版，对应 VLM 模型 `MinerU2.5-Pro-2605-1.2B` |

**关于 PyTorch 2.11.0**：如果你用 WSL2，必须锁定这个版本。原因如下：

ROCm 版 PyTorch 从 2.12 开始，官方把 rocprofiler 这个性能分析工具默认集成进去了——程序一启动就会自动调用它。但 rocprofiler 依赖 KFD（AMD 显卡在原生 Linux 里的底层驱动），WSL2 里并没有 KFD——WSL2 通过微软的 librocdxg 借用了 Windows 的显卡驱动。新版 PyTorch 启动时找不到 KFD，直接报错退出（`Found 0 rocprofiler agents`）。

如果你用的是原生 Linux（不是 WSL2），这个限制就不存在，可以用更新的 PyTorch。

**关于路径 B（Ubuntu 24.04 + ROCm 7.2.1）**：

ROCm 7.2 在 2026-01-21 发布，7.2.1 修订版在 2026-03-26 跟进——这是首个正式将 RX 9070 等 RDNA4 显卡列入支持名单的版本系列，librocdxg 也在该版本中被标记为生产级组件。但 24.04 默认 Python 是 3.12（不是 3.13）、需要在 vllm 源码和 ROCm 头文件上多打 5-6 个补丁。如果你坚持要走这条路，全部细节都在 [ROCm7.2升级指南.md](ROCm7.2升级指南.md)。

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

应该能看到 AMD 显卡的名称和驱动版本。如果显示的是其他厂商，先去[官网](https://www.amd.com/zh-cn/support)装好最新的 Adrenalin 驱动再继续。

### 1.3 配置 WSL2 资源（强烈建议）

在用户目录创建 `C:\Users\<你的用户名>\.wslconfig`：

```ini
[wsl2]
memory=12GB                  # 限制 WSL2 内存使用（你有 16GB 物理内存的话）
processors=8
swap=4GB
networkingMode=mirrored      # 让 WSL2 共享 Windows 网卡和 IP（Windows 11 22H2+）
dnsTunneling=true            # DNS 通过虚拟化通道转发
firewall=true                # 同步 Windows 防火墙规则
autoProxy=true               # 自动注入宿主机代理环境变量
hostAddressLoopback=true     # Windows 宿主机可通过 LAN IP 访问 WSL2 服务
```

修改后必须执行 `wsl --shutdown` 才能生效。

### 1.4 进入 WSL2 并更新系统

```bash
wsl -d Ubuntu-22.04
sudo apt update && sudo apt upgrade -y
```

---

## 第二步：网络与代理配置（国内用户重点）

这一节是新增的——验证部署中发现，国内用户最容易卡在网络问题上。后续步骤会下载 ROCm 仓库（约 3GB）、PyTorch wheel（约 3GB）、HuggingFace 模型（约 2.3GB）、vllm 源码与依赖。如果网络不通，后面寸步难行。

如果你能直连国外网络（公司专线、海外服务器），可以快速浏览跳过本节。**家庭宽带 + Clash 用户务必读完本节。**

### 2.1 Clash 端配置（如果你用 Clash Verge Rev / Mihomo）

| 参数 | 推荐值 | 原因 |
|------|--------|------|
| TUN 模式 | 开启 | 全局接管流量，无需配 `http_proxy` |
| Fake-IP | 开启 | 减少 DNS 解析延迟 |
| **TUN MTU** | **1500** | 关键！默认 9000 巨型帧在 WSL2 网卡（MTU 1500）被丢弃，TLS 握手会卡死 |
| **TUN Stack** | **System** | gVisor 在长连接下不如系统协议栈稳定 |
| IPv6 全局接管 | 开启 | 防止物理网卡 IPv6 直连泄漏 |
| IPv6 DNS 解析 | 关闭 | 多数代理节点不支持 IPv6 |

**启动顺序**：永远先开 Clash TUN，再启 WSL2。镜像网络在 WSL 启动瞬间抓取 Windows 路由表快照，如果 WSL 先启就看不到 TUN 网卡，Fake-IP 全变成死 IP。中途切换代理后需 `wsl --shutdown` 重启 WSL。

### 2.2 放行 Hyper-V 防火墙（最易忽略的坑）

第 1.3 节启用 `firewall=true` 后，Hyper-V 防火墙**默认阻止所有进入 WSL2 的入站连接**。这会导致：
- vllm engine 子进程间 IPC 通信被阻断
- Windows 浏览器无法访问 WSL 内的 WebUI/API

以**管理员身份**打开 PowerShell，执行：

```powershell
Set-NetFirewallHyperVVMSetting -Name '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -DefaultInboundAction Allow
```

GUID `{40E0AC32-...}` 是微软为 WSL2 分配的固定 VMCreatorId。

如果嫌全局 Allow 太开放，可以改为精细端口规则：

```powershell
New-NetFirewallHyperVRule -Name "WSL2" -DisplayName "WSL2 Services" `
  -Direction Inbound -VMCreatorId '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' `
  -Protocol TCP -LocalPorts 80,443,3000,7860,8000,8080
```

### 2.3 WSL2 内的 DNS 与 sudo 环境

进入 WSL2，编辑 `/etc/wsl.conf`：

```bash
sudo tee /etc/wsl.conf > /dev/null << 'EOF'
[boot]
systemd=true
[network]
generateResolvConf = false
[user]
default=$USER
EOF
```

> 注意：上面把 `default=$USER` 写入文件时，shell 会先把 `$USER` 替换成你当前的用户名（如 `dev`）。如果想保留字面 `$USER`，把 `'EOF'` 改成 `\EOF` 或预先记下用户名手填。

然后手动指定 DNS（绕过 systemd-resolved 的 `127.0.0.53`）：

```bash
sudo rm -f /etc/resolv.conf
echo 'nameserver 223.5.5.5' | sudo tee /etc/resolv.conf
```

让 sudo 保留代理变量（否则 `sudo apt` 在 TUN 模式下绕开代理直连失败）：

```bash
echo 'Defaults env_keep += "http_proxy https_proxy ftp_proxy all_proxy no_proxy"' | \
    sudo tee /etc/sudoers.d/keep-proxy
```

退出后 `wsl --shutdown` 再进入，让上面所有更改生效。

### 2.4 验证

```bash
# 期望：mirrored
wslinfo --networking-mode

# 期望：HTTP/2 200
curl -I https://github.com
curl -I https://pypi.org
```

如果两个 curl 都返回 200，网络层就准备好了。如果 GitHub 通但 HuggingFace 不通，是节点问题，换 Clash 节点。如果全不通，先检查 TUN 是否在 WSL 之前启动，再 `wsl --shutdown` 重试。

---

## 第三步：基础工具与 CMake

### 3.1 编译工具链

```bash
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y build-essential git wget curl \
    python3.13 python3.13-venv python3.13-dev \
    libnuma-dev libdrm2 libhwloc-dev ninja-build \
    pkg-config libgl1-mesa-glx
```

> Ubuntu 22.04 自带 Python 3.10，所以需要 deadsnakes PPA 才能装 3.13。
> 24.04 用户的对应包名是 `libgl1`（不是 `libgl1-mesa-glx`，后者在 noble 中已移除）。

### 3.2 安装最新 CMake（直接装二进制包，不要用 snap）

vllm 编译需要 cmake ≥ 4.0，Ubuntu 22.04 自带的是 3.22，24.04 是 3.28，都不够。

⚠️ **不要用 `sudo snap install cmake --classic`**：snapd 依赖 systemd 的 mount namespace，WSL2 内核中受限，命令会永久阻塞。第一轮验证就被这一步浪费了很久。

直接从 Kitware GitHub 下载预编译二进制：

```bash
cd /tmp
wget https://github.com/Kitware/CMake/releases/download/v4.0.0/cmake-4.0.0-linux-x86_64.tar.gz
tar -xzf cmake-4.0.0-linux-x86_64.tar.gz
sudo cp -r cmake-4.0.0-linux-x86_64/bin/* /usr/local/bin/
sudo cp -r cmake-4.0.0-linux-x86_64/share/* /usr/local/share/
cmake --version  # 期望: 4.0.0
```

如果原生 Linux 上 snap 工作正常，`sudo snap install cmake --classic` 也行——这个坑只影响 WSL2。

### 3.3 Windows SDK（仅 WSL2 用户）

编译 librocdxg 需要 Windows SDK 的 `ntstatus.h` 等头文件。

1. 下载 [Windows SDK](https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/)
2. 安装后确认 `shared/` 子目录存在（版本号会因 SDK 版本不同而变）：
   ```
   C:\Program Files (x86)\Windows Kits\10\Include\10.0.<XXXXX>.0\shared\
   ```
   里面应该有 `ntstatus.h`（约 700KB）。后面 cmake 命令里的版本号要与你实际安装的对应。

---

## 第四步：安装 ROCm 7.1.1

### 4.1 添加 ROCm 仓库

```bash
wget https://repo.radeon.com/rocm/rocm.gpg.key -O - | \
    sudo gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/rocm.gpg > /dev/null

# Ubuntu 22.04 代号是 jammy。24.04 是 noble，不能混用
echo 'deb [arch=amd64] https://repo.radeon.com/rocm/apt/7.1.1 jammy main' | \
    sudo tee /etc/apt/sources.list.d/rocm.list

sudo apt update
```

### 4.2 安装基础组件

```bash
sudo apt install -y rocminfo hip-dev miopen-hip
```

约 96 个包，3GB 左右，需要几分钟。

### 4.3 修复 rocminfo / rocm-device-libs 版本

Ubuntu 软件源自带的 `rocminfo`（22.04 是 5.0.0，24.04 是 5.7.1）远早于 librocdxg 架构，不包含 WSL2 GPU 虚拟化检测逻辑——继续用旧版会报 "ROCk module NOT loaded"。必须替换为 ROCm 仓库的版本：

```bash
sudo apt install -y --allow-downgrades \
    rocminfo=1.0.0.70101-38~22.04 \
    rocm-device-libs=1.0.0.70101-38~22.04
```

**关于"降级"两个字**：表面上 ROCm 版的版本号 `1.0.0.70101` 比 Ubuntu 的 `5.0.0` 小，APT 因此认为是"降级"。但实际上 ROCm 在自己的仓库中重启了 `1.0.0.xxxxx` 版本号方案，**代码反而比 Ubuntu 自带的 5.x 更新**。Ubuntu 沿用旧命名是历史遗留问题。`--allow-downgrades` 只是为了骗过 APT 的版本比较，操作本身是用新代码替换旧代码。

**APT Pinning 替代方案**：如果不想每次都写 `--allow-downgrades`，可以创建 `/etc/apt/preferences.d/rocm-pin-600`：

```text
Package: *
Pin: release o=repo.radeon.com
Pin-Priority: 600
```

之后 `apt install rocminfo` 会自动选 AMD 版。

---

## 第五步：编译 librocdxg（仅 WSL2 用户）

原生 Linux 用户请跳过这一步。

### 5.1 这是什么

WSL2 没有原生 Linux 的 KFD 驱动，GPU 无法被 ROCm 直接访问。librocdxg 是 AMD 提供的桥接层——通过 Windows 的 DXCore 接口让 ROCm 运行时间接操作 GPU。

### 5.2 编译

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

把上面的 `10.0.28000.0` 替换为你实际安装的 SDK 版本号（去 `C:\Program Files (x86)\Windows Kits\10\Include\` 看一眼）。

### 5.3 安装

```bash
sudo make install
sudo sh -c 'echo /opt/rocm/lib > /etc/ld.so.conf.d/rocm.conf'
sudo ldconfig
sudo usermod -a -G render,video $USER
```

### 5.4 环境变量

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

各变量的含义：

| 变量 | 作用 |
|------|------|
| `HSA_ENABLE_DXG_DETECTION` | 让 ROCm 走 librocdxg 桥接，否则在 WSL2 中检测不到 GPU |
| `FLASH_ATTENTION_TRITON_AMD_ENABLE` | 启用 flash_attn 的 Triton 后端（ROCm 没有官方 CUDA flash_attn） |
| `MINERU_MODEL_SOURCE` | 默认从 HuggingFace 拉模型；国内可改 `modelscope` |
| `TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL` | 启用 PyTorch 实验性 AOTriton 后端，对 SDPA 等算子有提速 |

### 5.5 重启 WSL 并验证

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
/opt/rocm/bin/rocminfo | grep -A5 "Agent 2"
```

应该能看到你的 AMD 显卡信息。如果只看到 CPU 没有 GPU：
- 检查 `/dev/dxg` 是否存在
- 确认 `HSA_ENABLE_DXG_DETECTION=1` 已设置
- 确认 Windows AMD 驱动已安装
- 试试 `newgrp video` 或重新登录

---

## 第六步：Python 虚拟环境 + PyTorch

### 6.1 创建虚拟环境

```bash
mkdir -p ~/mineru_stable && cd ~/mineru_stable
python3.13 -m venv .venv
```

### 6.2 安装 PyTorch（ROCm 版）

```bash
.venv/bin/pip install --pre \
    torch==2.11.0+rocm7.1 \
    torchvision \
    pytorch-triton-rocm \
    --index-url https://download.pytorch.org/whl/rocm7.1
```

如果你用的是原生 Linux（不是 WSL2），可以试试更新的 PyTorch 版本。但 WSL2 用户请锁定 2.11.0，原因在 0.2 节解释过了。

### 6.3 验证

```bash
.venv/bin/python -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'ROCm:    {torch.version.hip}')
print(f'GPU:     {torch.cuda.is_available()}')
print(f'Name:    {torch.cuda.get_device_name(0)}')
x = torch.randn(100, 100).cuda()
print(f'Test:    {(x @ x).shape} — PASS')
"
```

期望输出 `PyTorch: 2.11.0+rocm7.1` + `GPU: True` + `Test: ... — PASS`。

---

## 第七步：安装 ROCm 开发包

这些是 vllm 编译需要的头文件和库。

注意 `hipblas-dev` 和 `hiprand-dev` 必须装真正的包——之前我们试过手动创建符号链接 `hipblas.h → rocblas.h`，结果 rocblas.h 内部有 `#include "internal/rocblas-auxiliary.h"` 这样的相对路径引用，编译器从符号链接目录查不到 internal 子目录。

```bash
sudo DEBIAN_FRONTEND=noninteractive apt install -y \
    hipblas-dev \
    hiprand-dev \
    hipsparse-dev \
    hipsparselt-dev \
    hipsolver-dev \
    hipcub-dev \
    rocprim-dev \
    rocthrust-dev \
    rocblas-dev \
    rocrand-dev \
    hipfft-dev \
    hipblaslt
```

⚠️ **`hipsparselt-dev` 是验证部署中新发现的必需包**。原始教程漏掉了它，结果 cmake 配置时报 `roc::hipsparselt target not found`——PyTorch ROCm 版在 `Caffe2Targets.cmake` 中硬编码了对 `roc::hipsparselt`（AMD 的稀疏矩阵加速库）的依赖。

---

## 第八步：安装 amd-aiter 和 flash_attn

### 8.1 amd-aiter

```bash
cd ~
git clone --recursive https://github.com/ROCm/aiter.git
cd ~/mineru_stable
.venv/bin/pip install -e ~/aiter
```

### 8.2 flash_attn（Triton AMD 后端）

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

更新的 commit 不一定有问题，但这是我们验证过的版本。如果想试新版，可以跳过 checkout 这一步。

### 8.3 ⚠️ 立即验证 PyTorch 是否被覆盖

`flash_attn` 的依赖解析可能拉一个 CUDA 版的 `torch` 覆盖掉刚刚装好的 ROCm 版。**每次安装大依赖（flash_attn、mineru[core]、vllm）之后都必须复查一次**。

```bash
.venv/bin/python -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"
```

如果第一行**不含** `+rocm7.1`（如显示 `2.11.0+cu130`），说明 PyTorch 被覆盖了。**按正确顺序**修复：

```bash
# 1. 先强制重装 ROCm PyTorch + pytorch-triton-rocm
.venv/bin/pip install --force-reinstall \
    torch==2.11.0+rocm7.1 torchvision pytorch-triton-rocm \
    --index-url https://download.pytorch.org/whl/rocm7.1

# 2. 再清理 CUDA 版的 triton 元数据（不会删共享文件）
.venv/bin/pip uninstall -y triton triton-rocm
```

⚠️ **顺序重要**：`pytorch-triton-rocm`（ROCm 版 Triton）和 `triton`（CUDA 版）在 `site-packages` 中的物理文件夹**都叫 `triton/`**。两个不同的 pip 包写同一个目录，必然相互覆盖。如果先 `uninstall triton` 再 `force-reinstall pytorch-triton-rocm`，会把刚装好的 ROCm 版 `.so` 文件一起删掉。**必须先重装、后卸载**。

---

## 第九步：编译 vllm

这是整个部署里最耗时的一步，大概 30-60 分钟。

### 9.1 准备源码

```bash
cd ~
git clone https://github.com/vllm-project/vllm.git
cd vllm
# 直接用 main 最新版。旧 commit 357fddf61 的 pyproject.toml 有过时的 PEP 639 写法，
# 而最新 main 已经原生支持，且 _get_gcn_arch() 自带 torch.cuda 回退（少打一个补丁）
```

### 9.2 准备 build 依赖与 setuptools

vllm 的 `pyproject.toml` 用了 PEP 639 写法（`license = "Apache-2.0"` + 单独的 `license-files`），需要 `setuptools >= 77.0.3` 才支持。同时 vllm 源码安装还需要几个旧版 setuptools 没拉进来的工具：

```bash
~/mineru_stable/.venv/bin/pip install -U \
    "setuptools>=77.0.3" setuptools_scm setuptools_rust wheel
```

> 如果你坚持用旧 commit `357fddf61` 并保留旧 setuptools，必须手动改 `vllm/pyproject.toml`：把 `license = "Apache-2.0"` 改回 `license = {text = "Apache-2.0"}`，并删除 `license-files = ["LICENSE"]` 这行。**推荐升级 setuptools 而不是改源码**。

### 9.3 检查 Caffe2Targets.cmake

ROCm 7.x 改了一些 cmake 包名。PyTorch 的 cmake 配置文件可能引用旧名称，先确认一下：

```bash
grep "INTERFACE_LINK_LIBRARIES.*c10_hip" \
    ~/mineru_stable/.venv/lib/python3.13/site-packages/torch/share/cmake/Caffe2/Caffe2Targets.cmake
```

该行应该包含 `roc::rocblas`, `roc::rocrand`, `roc::hipsparse`, `roc::rocsolver`, `roc::hipsparselt` 等名称。在 ROCm 7.1.1 上正常情况下不需要改这个文件。

### 9.4 cmake 配置

```bash
mkdir -p ~/vllm_build

# 这两个 export 是必要的：cmake 内部要调 hipconfig，必须能找到它
export PATH=/opt/rocm/bin:/opt/rocm/llvm/bin:$PATH
export PYTORCH_ROCM_ARCH=gfx1201   # 替换成你的 gfx 代号（见 0.0 节表格）

cmake -S ~/vllm -B ~/vllm_build -G Ninja \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DVLLM_TARGET_DEVICE=rocm \
    -DVLLM_PYTHON_EXECUTABLE=/home/$USER/mineru_stable/.venv/bin/python \
    -DHIP_ROOT_DIR=/opt/rocm \
    -DROCM_PATH=/opt/rocm \
    -DCMAKE_HIP_ARCHITECTURES=gfx1201 \
    -DCMAKE_PREFIX_PATH="/home/$USER/mineru_stable/.venv/lib/python3.13/site-packages/torch/share/cmake"
```

三处关键细节（验证部署中踩过的坑）：

| 细节 | 原因 |
|------|------|
| `PATH` 包含 `/opt/rocm/bin` | CMake 内部要调 `hipconfig --rocmpath` 探测 ROCm 路径，WSL2 默认 PATH 不含该目录，否则报 "Failed to find ROCm root directory" |
| `-DCMAKE_HIP_ARCHITECTURES=gfx1201` | 实体 Linux 上 CMake 通过 `rocm_agent_enumerator` 自动探测 GPU 架构，WSL2 虚拟化下该工具经常失效；显式指定避免 "Failed to find a default HIP architecture" |
| **不要设** `-DCMAKE_HIP_COMPILER=hipcc` | CMake 4.0 的 `CMakeDetermineHIPCompiler.cmake` 检测到编译器名含 `hipcc` 时直接 `FATAL_ERROR`——现代 CMake 拒绝通过 Perl 包装器套娃，要求直接用底层 Clang。这与 `hipcc` 本身好坏无关 |

如果 cmake 报错找不到某个包，先回到第七步看是不是漏装了什么，再考虑 9.5 节的别名兜底。

### 9.5 ROCm 7.1.1 下的 cmake 别名（多数情况不需要）

ROCm 7.1.1 + 22.04 路径下，所有 cmake 包名都齐全，**通常不需要这一步**。仅在 cmake 报 "hiprand not found" 或类似时才创建：

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

### 9.6 编译

```bash
cd ~/vllm_build
PYTORCH_ROCM_ARCH=gfx1201 ninja -j4
```

`-j4` 是限制并行编译数为 4。我们 16GB 内存的机器开 `-j20` 会 OOM 被系统 kill（exit 137）。内存更大可以适当调高，32GB 试试 `-j8`。

编译成功后 `~/vllm_build/` 下会有几个 `.abi3.so` 文件。

### 9.7 安装 vllm

```bash
cp ~/vllm_build/*.abi3.so ~/vllm/vllm/

cd ~/vllm
VLLM_TARGET_DEVICE=rocm PYTORCH_ROCM_ARCH=gfx1201 \
    ~/mineru_stable/.venv/bin/pip install -e . --no-build-isolation
```

> **不要加 `--no-deps`**：vllm 0.21+ 依赖很多 Python 包（`compressed_tensors`、`partial_json_parser`、`xgrammar`、`mistral_common` 等），手动逐个装会非常痛苦。让 pip 完整解析依赖，再走 9.8 把可能被覆盖的 ROCm PyTorch 装回来。
>
> 如果遇到 `amd-quark>=0.8.99` 找不到 Python 3.13 wheel 的报错，可以加 `--no-deps` 安装后再手动补充 `compressed_tensors` 等关键包；但**不推荐**——首选是用 vllm 最新 main，它的依赖列表已经清理过。

### 9.8 再次验证 PyTorch 没有被覆盖

```bash
~/mineru_stable/.venv/bin/python -c "import torch; print(torch.__version__)"
```

如果显示 `+cu130` 之类，按 8.3 节的恢复顺序处理。

### 9.9 amdsmi（可选）

```bash
cp -r /opt/rocm/share/amd_smi ~/amd_smi 2>/dev/null && \
cd ~/amd_smi && \
~/mineru_stable/.venv/bin/pip install . --no-build-isolation
```

> **WSL2 中 amdsmi 永远不可用**：它依赖 Linux 原生 KFD 驱动和 `/dev/kfd` 设备节点，WSL2 通过 librocdxg 桥接走的是另一条路。原生 Linux 用户应该装；WSL2 用户即使装上也只是放在那里不工作，**整步可以跳过**。`/opt/rocm/share/amd_smi/` 目录不存在也不影响后续步骤。

### 9.10 vllm 平台检测补丁（仅 WSL2 用户）

原生 Linux 用户跳过本节。

vllm 在子进程初始化时通过 `current_platform` 探测平台类型。检测路径上有两个独立问题，分别需要打一个补丁：

**问题 1：amdsmi 在 WSL2 失败 → vllm 误判没有 GPU**
**问题 2：`rocm.py` 中 `logger.warning_once()` 触发循环导入 → `current_platform` 被设为 `UnspecifiedPlatform`**

任一问题没修都会导致 `AsyncLLM` 启动时报 `Device string must not be empty` 或 `NotImplementedError`。

#### 补丁 A：`~/vllm/vllm/platforms/__init__.py`

找到 `rocm_platform_plugin()` 函数，把结尾：
```python
    return "vllm.platforms.rocm.RocmPlatform" if is_rocm else None
```
替换为：
```python
    # WSL2 fallback: amdsmi doesn't work, check torch.version.hip
    if not is_rocm:
        try:
            import torch
            if torch.version.hip is not None:
                is_rocm = True
        except Exception:
            pass
    return "vllm.platforms.rocm.RocmPlatform" if is_rocm else None
```

#### 补丁 B：`~/vllm/vllm/platforms/rocm.py`

找到 `_get_gcn_arch()` 函数里 `except Exception as e:` 那一段——目前长这样：

```python
    except Exception as e:
        logger.debug("Failed to get GCN arch via amdsmi: %s", e)
        logger.warning_once(
            "Failed to get GCN arch via amdsmi, falling back to torch.cuda. "
            "This will initialize CUDA and may cause "
            "issues if CUDA_VISIBLE_DEVICES is not set yet."
        )
```

替换为：

```python
    except Exception as e:
        import sys as _sys
        _sys.stderr.write("WSL2: amdsmi unavailable, using torch.cuda for GPU detection\n")
```

**为什么必须替换 `logger.warning_once()`**：这个 logger 内部会触发 `from vllm.distributed.parallel_state import is_local_first_rank`，进而 `from vllm.platforms import current_platform`——形成循环导入。子进程（EngineCore）加载到一半时 `current_platform` 还没就绪，被设为 `UnspecifiedPlatform()`，之后所有调用都会 `NotImplementedError`。

> ⚠️ **不要做整段函数替换或正则匹配**：原教程的旧补丁用宽松正则会把后续的模块级常量（`_GCN_ARCH = _get_gcn_arch()`、`_ON_GFX942 = ...`、`_ON_GFX12X = ...` 等）一并吃掉，导致 `ImportError: cannot import name '_ON_GFX942'`。正确做法是只替换 except 块内的几行。

最新 vllm main 已经把 `_get_gcn_arch()` 改造为自带 `torch.cuda` 回退——如果你看到函数体的开头已经是 `try: return torch.cuda.get_device_properties("cuda").gcnArchName`，那么平台识别本身不需要再补丁，但**`logger.warning_once()` 仍需替换**以断开循环导入。

### 9.11 验证 vllm

```bash
~/mineru_stable/.venv/bin/python -c "
from vllm.platforms import current_platform
print('Platform:', type(current_platform).__name__)
print('is_rocm:', current_platform.is_rocm())
print('device_type:', current_platform.device_type)
"
```

期望 `Platform: RocmPlatform` + `is_rocm: True` + `device_type: cuda`（ROCm 沿用 CUDA device 类型字符串，正常现象）。

---

## 第十步：安装 MinerU + RDNA 适配

### 10.1 安装 MinerU

```bash
cd ~/mineru_stable
# ⚠️ 用 pip 而非 uv pip
# uv pip 的依赖解析比较激进，会主动把已安装的 ROCm PyTorch 替换成 CUDA 版
.venv/bin/pip install 'mineru[core]' -i https://pypi.mirrors.ustc.edu.cn/simple/
```

### 10.2 第三次验证 PyTorch 没有被覆盖

```bash
.venv/bin/python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

如果不含 `+rocm7.1`，按 8.3 节顺序修复。

### 10.3 应用 RDNA 适配补丁

AMD RDNA 架构上 MIOpen 遇到新的卷积尺寸组合时需要搜索最优 kernel（冷启动），每次可能花 1-7 秒。以下补丁来自 Discussion #3662 作者，作用是规避容易触发冷启动的输入尺寸。

先确认 mineru 包路径（不同 Python 版本目录名不同）：

```bash
PYVER=$(.venv/bin/python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
MINERU_INFER_DIR="$HOME/mineru_stable/.venv/lib/python${PYVER}/site-packages/mineru/model/utils/tools/infer"
echo $MINERU_INFER_DIR
ls $MINERU_INFER_DIR
```

后续 patch 文件路径都是 `$MINERU_INFER_DIR/predict_rec.py` 等。

**Patch A — `predict_rec.py` imgW 对齐到 32**

找到 `imgW = max(min(imgW, self.limited_max_width), self.limited_min_width)`，在它**下一行**加：
```python
        imgW = math.ceil(imgW / 32) * 32
```
注意保持与上一行相同的缩进（一般是 8 个空格）。

**Patch B — `predict_rec.py` 批次填充**

在 `norm_img_batch = np.concatenate(norm_img_batch)` 之前插入：
```python
                actual_batch_size = len(norm_img_batch)
                if actual_batch_size < batch_num:
                    pad_size = batch_num - actual_batch_size
                    pad_img = np.zeros_like(norm_img_batch[0])
                    for _ in range(pad_size):
                        norm_img_batch.append(pad_img)
```

然后把同一函数里 `for rno in range(len(rec_result)):` 改为：
```python
                for rno in range(actual_batch_size):
```

**Patch C — `predict_det.py` 内存连续性检查**

在 `inp = inp.to(self.device)` 之后加：
```python
            if not inp.is_contiguous():
                inp = inp.contiguous()
```

### 10.4 不需要改的

| 原本 Discussion #3662 提到的 | 现状 |
|:--|:--|
| vllm qwen2_vl.py 的 conv3d 改 F.linear | vllm 0.21+ 已经自带等价优化 |
| doclayout_yolo g2l_crm.py 的空洞卷积改造 | MinerU 3.x 已经移除了 doclayout_yolo |

---

## 第十一步：下载模型并测试

### 11.1 DNS 检查（WSL2 常见问题）

WSL2 每次 `wsl --shutdown` 后 systemd-resolved 可能会把 `/etc/resolv.conf` 重置成 `127.0.0.53`。在跑下面命令前确认一下：

```bash
cat /etc/resolv.conf
# 期望看到 nameserver 223.5.5.5 或你在第 2.3 节配的 DNS
```

如果被覆盖了，重新执行第 2.3 节的 `sudo tee /etc/resolv.conf` 命令。

### 11.2 首次运行

```bash
cd ~/mineru_stable && . .venv/bin/activate
# 环境变量已在 ~/.bashrc 配好，新终端自动加载；这里 source 一次保险
source ~/.bashrc

# 随便放一个 PDF 到 ~/test.pdf，也可以用本仓库根目录的 example.pdf
mineru -p ~/test.pdf -o ~/output -b hybrid-auto-engine
```

首次运行会自动从 HuggingFace 下载约 2.3GB 的模型（`MinerU2.5-Pro-2605-1.2B` + `PDF-Extract-Kit-1.0`）。VLM 模型首次加载约 46 秒，Triton 首次编译 kernel 约 7 秒——这些都是一次性的，后续会快很多。

如果 HuggingFace 连不上，改用 ModelScope：
```bash
export MINERU_MODEL_SOURCE=modelscope
```

---

## 第十二步：MIOpen 缓存预热

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
python cache_warmer.py --device cuda --max_side 960 --step 32
```

约 841 个尺寸组合，3-4 分钟。

---

## 第十三步：日常使用

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

更详细的用法见 [MinerU本地使用指南.md](MinerU本地使用指南.md)。

---

## 性能参考

`example.pdf`（13 页）在 RX 9070 上连续运行三次实测（预热后稳定状态）：

| 阶段 | 耗时 / 速度 |
|:-----|:-----------|
| VLM 推理 (Two Step Extraction) | 约 6 秒 (1.98 it/s) |
| 版面与 OCR (Processing pages) | < 1 秒 (61.13 it/s) |
| 13 页总耗时 | **6-7 秒** |

得益于 RX 9070 的 640 GB/s 高显存带宽，MinerU 在 Pipeline (版面与 OCR) 阶段的处理速度极快。你的实际耗时取决于 PDF 的页数和复杂程度。

路径 B（Ubuntu 24.04 + ROCm 7.2.1）实测 Processing pages 速度可达 65-71 it/s，略快于路径 A——但代价是多打几个补丁，详见 [ROCm7.2升级指南.md](ROCm7.2升级指南.md)。

---

## 常见问题

**Q: rocminfo 显示 "ROCk module is NOT loaded"**
检查 rocminfo 版本是 ROCm 版的（`dpkg -l | grep rocminfo` 应显示 `1.0.0.70101`），并且 `HSA_ENABLE_DXG_DETECTION=1` 已设置、`/dev/dxg` 存在。

**Q: PyTorch 报 "Found 0 rocprofiler agents"**
大概率是 PyTorch ≥ 2.12 被装上了。降回 2.11.0+rocm7.1（见第六步）。原生 Linux 不会有这个问题。

**Q: vllm 报 "Device string must not be empty"**
vllm 没检测到 ROCm 平台。确认 9.10 节的两个 patch（`__init__.py` 和 `rocm.py`）都应用了。

**Q: vllm 报 `NotImplementedError`，提示来自 `UnspecifiedPlatform.check_if_supports_dtype`**
循环导入导致 `current_platform` 被设成 `UnspecifiedPlatform`。检查 9.10 节补丁 B（`rocm.py` 的 `logger.warning_once` 替换）是否生效。

**Q: cmake 报 "Failed to find a default HIP architecture" 或 "Failed to find ROCm root directory"**
9.4 节的 `PATH=/opt/rocm/bin:...` 和 `-DCMAKE_HIP_ARCHITECTURES=gfx1201` 没设。

**Q: cmake 报 `roc::hipsparselt target not found`**
第七步没装 `hipsparselt-dev`，回去补一下。

**Q: cmake 报 "hiprand not found" 或类似**
ROCm 7.1.1 一般不会出，多见于 ROCm 7.2。回到 9.5 节创建别名兜底，或直接换路径 B（[ROCm7.2升级指南.md](ROCm7.2升级指南.md)）。

**Q: 安装 mineru/flash_attn/vllm 后 GPU 不能用了**
ROCm PyTorch 被覆盖。按 8.3 节顺序（先 `--force-reinstall pytorch-triton-rocm` 后 `uninstall triton triton-rocm`）修复。

**Q: WSL2 重启后 GPU 不工作**
依次检查：DNS 是否被 systemd-resolved 重置（2.3 节）→ `/dev/dxg` 是否存在 → `HSA_ENABLE_DXG_DETECTION=1` 是否设置 → `rocminfo` 看 GPU → `torch.cuda.is_available()` 验证。

**Q: ninja 编译中途被 kill（exit 137）**
内存爆了。把 `ninja -j4` 降为 `-j2`，或加大 `.wslconfig` 的 `memory` 上限。

---

## 改动清单（升级或重装时回查）

升级 MinerU、vllm 或 ROCm 后，以下改动需要重新应用：

| 文件 | 改了什么 | 谁需要 |
|:-----|:--------|:------|
| `~/vllm/vllm/platforms/__init__.py` | rocm_platform_plugin() 加 torch.version.hip 回退 | WSL2 用户 |
| `~/vllm/vllm/platforms/rocm.py` | _get_gcn_arch() 的 except 块去掉 logger.warning_once | WSL2 用户 |
| `.venv/.../mineru/.../predict_rec.py` | imgW 32 对齐 + batch padding | 所有 AMD 用户 |
| `.venv/.../mineru/.../predict_det.py` | contiguous 检查 | 所有 AMD 用户 |
| `/etc/apt/preferences.d/rocm-pin-600`（可选） | 让 AMD 仓库的 rocminfo 优先 | 不想每次写 `--allow-downgrades` 的人 |

升级时的具体步骤见 [MinerU本地更新指南.md](MinerU本地更新指南.md)。

---

*文档最后更新: 2026-05-27*
*实测环境：Windows 11 Pro + WSL2 Ubuntu 22.04 + AMD RX 9070 + ROCm 7.1.1 + PyTorch 2.11.0+rocm7.1 + vllm main + MinerU 3.2.0*
