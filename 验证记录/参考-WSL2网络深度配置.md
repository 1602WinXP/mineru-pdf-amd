# WSL2 网络深度配置（TUN 代理 + 镜像网络）

> 融合三轮实际部署验证 + 社区资料搜索核实。适用于使用 Clash Verge Rev 等 TUN 模式代理的 WSL2 用户。

---

## 一、为什么需要特殊配置

WSL2 默认 NAT 模式使虚拟机与宿主机处于不同网段，TUN 虚拟网卡的流量无法自动穿透。镜像网络（Mirrored）模式让 WSL2 共享 Windows 网络栈，TUN 代理可直接接管 WSL2 流量。但有三道坎要迈：

1. **路由表不同步**：WSL2 启动时抓取 Windows 路由表快照。如果先启 WSL 后开 TUN，WSL 看不到 TUN 网卡
2. **MTU 巨型帧冲突**：TUN 默认 MTU 9000，WSL2 网卡 MTU 1500，大包被静默丢弃
3. **Hyper-V 防火墙**：mirrored 模式下防火墙默认拦截入站

---

## 二、最终配置（已验证通过）

### 2.1 Windows 端（`%USERPROFILE%\.wslconfig`）

```ini
[wsl2]
networkingMode=mirrored      # 让 WSL2 共享 Windows 网卡和 IP
dnsTunneling=true            # DNS 通过虚拟化通道代理解析
firewall=true                # 同步 Windows 防火墙规则
autoProxy=true               # 自动注入宿主机代理环境变量
hostAddressLoopback=true     # Windows 宿主机可通过 LAN IP 访问 WSL2 服务
memory=12GB
processors=8
swap=4GB
```

修改后必须执行 `wsl --shutdown` 才能生效。

### 2.2 Clash Verge Rev 端

| 参数 | 推荐值 | 原理 |
|------|--------|------|
| TUN 模式 | 开启 | 全局接管流量 |
| Fake-IP | 开启 | 减少 DNS 延迟 |
| **TUN MTU** | **1500** | 最关键！默认 9000 巨型帧在 WSL2 被丢弃 |
| **TUN Stack** | **System** | gVisor 在长连接下不如系统协议栈稳定 |
| IPv6 全局接管 | 开启 | 防止物理网卡 IPv6 直连泄漏 |
| DNS IPv6 解析 | 关闭 | 多数代理节点不支持 IPv6 |

### 2.3 WSL2 内（`/etc/wsl.conf`）

```ini
[boot]
systemd=true
[network]
generateResolvConf = false
[user]
default=dev
```

### 2.4 WSL2 内 DNS（`/etc/resolv.conf`）

```bash
# Ubuntu 24.04 用 systemd-resolved，resolv.conf 指向 127.0.0.53
# 需手动覆盖：
sudo rm -f /etc/resolv.conf
echo 'nameserver 223.5.5.5' | sudo tee /etc/resolv.conf
```

> 每次 `wsl --shutdown` 后 DNS 可能重置，需重新设置。

---

## 三、必须避开的 7 个坑

### 坑一：Hyper-V 防火墙拦截入站（⚠️ 最易忽略）

`firewall=true` 时 Hyper-V 防火墙**默认阻止所有进入 WSL2 的入站连接**。这导致：
- vllm engine 子进程间 IPC 通信被阻断
- Windows 浏览器无法访问 WSL 内 Web 服务

**修复**（管理员 PowerShell）：
```powershell
Set-NetFirewallHyperVVMSetting -Name '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -DefaultInboundAction Allow
```
GUID `{40E0AC32-...}` 是 WSL2 的 VMCreatorId。

也可以创建精细端口规则（替代全局 Allow）：
```powershell
New-NetFirewallHyperVRule -Name "WSL2" -DisplayName "WSL2 Services" `
  -Direction Inbound -VMCreatorId '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' `
  -Protocol TCP -LocalPorts 80,443,3000,8000,8080
```

### 坑二：启动顺序

**永远先开 Clash TUN，再启 WSL2**。镜像网络在 WSL 启动瞬间抓取 Windows 路由表。如果顺序反了，WSL 看不到 `198.18.0.0/16` 路由，Fake-IP 全部变成死 IP。中途切换代理后需 `wsl --shutdown`。

### 坑三：MTU 黑洞

TUN 默认 MTU 9000 的巨型帧在 WSL2 网卡（MTU 1500）中直接被丢弃，无任何报错。现象：`ping` 能通（小包），但 `curl`/`git clone` 在 TLS 握手后卡死。如果 1500 仍有偶发卡死，可尝试 1492 或 1360（特别是套了 PPPoE 或企业 VPN 时）。

### 坑四：sudo 环境下代理变量丢失

`autoProxy=true` 仅为当前用户注入代理环境变量。执行 `sudo` 时变量被清空。

**修复**：`sudo visudo` 添加：
```
Defaults env_keep += "http_proxy https_proxy ftp_proxy all_proxy no_proxy"
```

### 坑五：历史代理配置导致流量循环

`.bashrc` 中手写的 `export http_proxy=...` 与 `autoProxy=true` 会叠加导致流量无限回环。配置镜像网络 + TUN 后，**应清理所有手写代理环境变量**。

### 坑六：Docker Desktop 与镜像网络冲突

Docker Desktop 的 `vpnkit` 后端代理与 WSL 镜像模式端口转发机制冲突。容器端口映射可能静默失效（容器运行中但宿主机 `localhost:8080` 不通）。

**修复**：在 WSL2 内直接安装原生 `docker-ce`，或使用 `--network host`。

### 坑七：mDNS（`.local` 域名）解析失效

`dnsTunneling=true` 时 mDNS 多播请求无法正确转发，导致局域网内 `.local` 设备名无法解析。如依赖此类功能：

```bash
sudo apt install libnss-mdns
# 在 /etc/nsswitch.conf 中的 hosts 行添加：
# hosts: files mdns_minimal [NOTFOUND=return] dns
```

---

## 四、验证命令

```bash
# 确认镜像网络已生效
wslinfo --networking-mode          # 期望：mirrored

# 确认 TUN 路由存在
ip route                            # 应有 198.18.x.x 路由

# 测试 TCP 连接（勿用 ping，Fake-IP 下 ping 不可靠）
curl -I https://github.com         # 期望：HTTP/2 200

# 如果 GitHub 连不上但百度能通 → Clash 节点问题，换节点
# 如果全部不通 → 检查 TUN 是否在 WSL 之前启动，执行 wsl --shutdown 重试
```
