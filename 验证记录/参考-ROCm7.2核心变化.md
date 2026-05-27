# ROCm 7.2 相比于 7.1 的核心变化

> 整合 AMD 官方 Release Notes、社区实测、外部资料搜索验证。帮助读者理解为什么推荐 7.2 而非 7.1。
>
> ROCm 7.2 于 **2026-01-21** 正式发布。

---

## 一、硬件与架构支持大幅扩展

### 1.1 RDNA 4 正式支持（7.2 最大卖点）

ROCm 7.2 是**首个正式支持 RDNA 4 架构的版本**。此前 7.1 对 RX 9070 等 RDNA 4 显卡只有实验性支持。

| GPU | 架构 | LLVM Target | 7.1 状态 | 7.2 状态 |
|-----|------|-------------|:---:|:---:|
| RX 9070 / 9070 XT / 9070 GRE | RDNA 4 | **gfx1201** | 实验性 | ✅ 正式 |
| RX 9060 XT / 9060 XT LP | RDNA 4 | gfx1200 | 不支持 | ✅ 正式 |
| Radeon AI PRO R9700 / R9600D | RDNA 4 | gfx1201/gfx1200 | 不支持 | ✅ 正式 |

### 1.2 RDNA 3 中端卡补全

ROCm 7.1 遗漏了 RX 7700 系列（gfx1101），7.2 终于官方列入支持。

### 1.3 Ryzen AI APU（RDNA 3.5 核显）Preview 支持

Strix Halo / Strix Point 等搭载 RDNA 3.5 核显的 APU（gfx1150/gfx1151）获得 Preview 阶段支持。可在 BIOS 中调整 Reserved Video Memory 为最小值（512MB），配合 Grub 参数 `amdgpu.gttsize` 实现共享内存优化。

### 1.4 数据中心：SR-IOV / Bad Page Avoidance

Instinct MI350X/MI355X 获得 SR-IOV 虚拟化和 RAS 增强。Bad Page Avoidance 功能在内存故障时自动隔离坏页，提高多租户 GPU 可用性。

---

## 二、WSL2 / Windows 支持（史诗级增强）

这是 7.2 相比 7.1 变化最大的领域，也是我们在 24.04 上选择 7.2 而非 7.1 的关键原因之一。

### 2.1 librocdxg 生产级（7.2.1 + Adrenalin 26.2.2）

| 维度 | 7.1 | 7.2.1 |
|------|-----|-------|
| 状态 | 实验性引入 | ✅ **生产级** |
| 与驱动耦合 | 绑定 ROCm 版本 | ✅ **三方解耦**（Windows 驱动、ROCm 版本、librocdxg 独立更新） |
| WSL2 GPU 穿透 | 不稳定 | ✅ 官方验证 |

librocdxg 作为 Linux ROCm 运行时与 Windows GPU 驱动栈之间的翻译层，在 7.2.1 中被正式标记为生产级组件。其架构重新设计为与 Windows 显示驱动和 ROCm 版本**三方解耦**——升级显卡驱动或 ROCm 都不会破坏 WSL2 GPU 计算环境。

### 2.2 WSL2 首次支持核显 AI

得益于 librocdxg 的成熟，7.2 首次在 WSL 中官方支持了 Ryzen Strix 和 Strix Halo 核显处理器，让没有独显的笔记本也能在 WSL2 里跑 AI 推理。

### 2.3 Windows 原生 PyTorch

AMD 发布了 **"PyTorch on Windows Edition 7.2"**（基于 ROCm 7.2.1 核心组件），可直接在 Windows 11 上为 Radeon 7000/9000 系列及 Ryzen AI NPU 提供原生 ML 支持。这对不想折腾 WSL2 的用户来说是个替代方案。

---

## 三、核心库性能优化

| 库 | 7.1 | 7.2 变化 |
|----|-----|---------|
| **hipBLASLt** | 基础 GEMM | Swizzle A/B 内存访问优化 + 在线 GEMM 调优（Qwen3-30B 实测提升 **106%**）+ restore-from-log 重现 |
| **rocMLIR** | — | FP8/FP4 精度原生支持（为 MI350 NPI 准备） |
| **MIGraphX** | — | FP8/FP4 支持 + Gather 算子重写（embedding 模型性能大幅提升） |
| **RCCL** | 基础多卡 | 拓扑感知通信调度（GDA 集成），更低延迟、更高吞吐 |
| **ONNX Runtime** | — | 外部流（external stream）支持，多流推理可靠性提升 |
| **vLLM profiler** | 时间线有空洞 bug | **7.2.3 修复**（2026-05-04） |

---

## 四、开发者工具变化

### 4.1 ROCm Optiq（全新）

随 7.2 发布（Beta 0.3.0，2026-03-26）。图形化 GPU 内核调度可视化工具，跨平台（Win 11 + Ubuntu 22.04/24.04），**独立运行**不依赖完整 ROCm 栈。功能包括：
- Timeline View（CPU/GPU 活动时间线）
- Roofline Chart（算力/带宽上限分析）
- Memory Chart（各级缓存吞吐量）
- System Speed-of-Light（关键指标峰值百分比）

### 4.2 旧工具废弃（Q2 2026）

| 废弃 | 替代 |
|------|------|
| ROCTracer、ROCProfiler | ROCprofiler-SDK（`rocprofv3`） |
| `rocprof`、`rocprofv2` | `rocprofv3` |
| ROCm SMI（`rocm-smi`） | AMD SMI（`amd-smi`） |
| `roc-obj-*` 系列 | `llvm-objdump --offloading` |

---

## 五、LLVM 版本变化

| ROCm 版本 | Ubuntu 22.04 (jammy) | Ubuntu 24.04 (noble) |
|-----------|---------------------|---------------------|
| 7.1.1 | LLVM 17 | LLVM 20 |
| 7.2.1 | — | **LLVM 22** |

这是 24.04 + 7.1.1 不兼容的根因：LLVM 20 的语法收紧导致 ROCm 头文件多处报错。7.2.1 升级到 LLVM 22 并修复了大部分兼容性问题。

---

## 六、社区实测性能数据

- **ComfyUI**（AMD CES 2026 官方基准，7.x vs 6.4.4）：
  - SDXL：**2.6x** 加速
  - Flux S：**5.2x** 加速
  - WAN 14b（视频生成）：**5.4x** 加速
- 多 GPU RCCL：更低延迟、更高吞吐
- Linux 端大模型推理稳定性明显改善

---

## 七、对我们部署的结论

1. **24.04 必须用 7.2**：7.1 的 noble 包有 LLVM 20 头文件适配问题，7.2 修复了大部分
2. **librocdxg 在 7.2 是生产级**：我们是 librocdxg 生产级状态的受益者
3. **vllm 最新 main + 7.2 是目前唯一可行组合**（24.04 上）
4. **如果追求 profiler 精度**，可等 7.2.3 的修复
