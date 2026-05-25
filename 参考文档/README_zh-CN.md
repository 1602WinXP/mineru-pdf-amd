<div align="center" xmlns="http://www.w3.org/1999/html">
<!-- logo -->
<p align="center">
  <img src="https://gcore.jsdelivr.net/gh/opendatalab/MinerU@master/docs/images/MinerU-logo.png" width="300px" style="vertical-align:middle;">
</p>

<!-- icon -->

[![stars](https://img.shields.io/github/stars/opendatalab/MinerU.svg)](https://github.com/opendatalab/MinerU)
[![forks](https://img.shields.io/github/forks/opendatalab/MinerU.svg)](https://github.com/opendatalab/MinerU)
[![open issues](https://img.shields.io/github/issues-raw/opendatalab/MinerU)](https://github.com/opendatalab/MinerU/issues)
[![issue resolution](https://img.shields.io/github/issues-closed-raw/opendatalab/MinerU)](https://github.com/opendatalab/MinerU/issues)
[![PyPI version](https://img.shields.io/pypi/v/mineru)](https://pypi.org/project/mineru/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/mineru)](https://pypi.org/project/mineru/)
[![Downloads](https://static.pepy.tech/badge/mineru)](https://pepy.tech/project/mineru)
[![Downloads](https://static.pepy.tech/badge/mineru/month)](https://pepy.tech/project/mineru)
[OpenDataLab](https://mineru.net/OpenSourceTools/Extractor?source=github)
[ModelScope](https://www.modelscope.cn/studios/OpenDataLab/MinerU)
[HuggingFace](https://huggingface.co/spaces/opendatalab/MinerU)
[![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/gist/myhloli/a3cb16570ab3cfeadf9d8f0ac91b4fca/mineru_demo.ipynb)
[![arXiv](https://img.shields.io/badge/MinerU-Technical%20Report-b31b1b.svg?logo=arXiv)](https://arxiv.org/abs/2409.18839)
[![arXiv](https://img.shields.io/badge/MinerU2.5-Technical%20Report-b31b1b.svg?logo=arXiv)](https://arxiv.org/abs/2509.22186)
[![arXiv](https://img.shields.io/badge/MinerU2.5%20Pro-Technical%20Report-b31b1b.svg?logo=arXiv)](https://arxiv.org/abs/2604.04771)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/opendatalab/MinerU)


<a href="https://trendshift.io/repositories/11174" target="_blank"><img src="https://trendshift.io/api/badge/repositories/11174" alt="opendatalab%2FMinerU | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>

<!-- language -->

[English](README.md) | [简体中文](README_zh-CN.md)

<!-- hot link -->

<p align="center">
🚀<a href="https://mineru.net/?source=github">MinerU 官网入口→✅ 免装在线版 ✅ 全功能客户端 ✅ 开发者API在线调用，省去部署麻烦，多种产品形态一键get，速冲！</a>
</p>

<!-- join us -->

<p align="center">
    👋 join us on <a href="https://discord.gg/Tdedn9GTXq" target="_blank">Discord</a> and <a href="https://mineru.net/community-portal/?aliasId=3c430f94" target="_blank">WeChat</a>
</p>

</div>

<details>
<summary>MinerU — 专为 LLM · RAG · Agent 场景构建的高精度文档解析引擎 </summary>
将 PDF · DOCX · PPTX · XLSX · 图片 · 网页转为结构化 Markdown / JSON · VLM+OCR 双引擎 · 109 种语言 <br>
MCP Server · LangChain / Dify / FastGPT 原生集成 · 10+ 国产算力适配 <br>

**🔍 核心解析能力**
- 原生支持 `DOCX`、`PPTX`、`XLSX` 解析
- 公式 → LaTeX · 表格 → HTML，精准还原复杂版面
- 支持扫描件、手写体、多栏布局、跨页表格合并
- 输出符合人类阅读顺序，自动去除页眉页脚
- VLM + OCR 双引擎，支持 109 种语言识别

**🔌 接入方式**

| 场景 | 方案 |
|------|------|
| AI 编程工具 | MCP Server — Cursor · Claude Desktop · Windsurf |
| RAG 框架 | LangChain · LlamaIndex · RAGFlow · RAG-Anything · Flowise · Dify · FastGPT |
| 开发集成 | Python / Go / TypeScript SDK · CLI · REST API · Docker |
| 零代码 | mineru.net 在线版 · Gradio WebUI · 桌面客户端 |

**🖥️ 部署生态（支持私有化 · 完全离线）**

| 推理后端         | 适用场景                        |
|--------------|-----------------------------|
| pipeline     | 快速稳定，无幻觉，CPU / GPU 均可运行     |
| vlm-engine   | 高精度，支持 vLLM / LMdeploy / mlx 生态 |
| hybrid-engine| 高精度，原生文本提取，低幻觉              |

国产算力：昇腾 · 寒武纪 · 燧原 · 沐曦 · 摩尔线程 · 昆仑芯 · 天数智芯 · 瀚博 · 太初元碁 · 海光 · 平头哥

</details>

# 更新记录

- 2026/04/18 3.1.0 发布

  本次版本更新聚焦于**许可协议开放性、解析精度提升与全格式原生支持**。主要更新内容包括：

  - 许可协议升级
    - MinerU 已正式从 `AGPLv3` 切换至基于 `Apache 2.0` 的 [MinerU 开源许可证](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md)。
    - 新的许可方式在兼顾开源协作与商业落地的同时，进一步降低了社区使用和商业化接入门槛，让 MinerU 更容易融入真实业务流程。
  - VLM 主模型升级
    - VLM 主模型正式切换为 `MinerU2.5-Pro-2604-1.2B`，整体解析精度提升至业内领先水平。
    - 新模型现已支持子图切分合并、图像与图表解析、截断段落合并、跨页面表格合并以及表格内图像识别，复杂版面场景下的解析能力进一步增强。
  - 全格式原生解析支持
    - 新增 `PPTX` 与 `XLSX` 原生解析能力。
    - 至此，MinerU 已完整支持图片、`PDF`、`DOCX`、`PPTX`、`XLSX` 全格式解析，为多类型文档统一处理提供了更完整的能力闭环。

  通过 3.1.0 版本，MinerU 在开放性、解析精度和落地能力上进一步提升。新的许可协议降低了社区使用和商业接入门槛，`MinerU2.5-Pro-2604-1.2B` 提升了复杂内容的解析质量，而 `PPTX` 与 `XLSX` 原生解析的补齐，也让 MinerU 完成了主流文档格式的端到端覆盖。

- 2026/03/29 3.0.0 发布

  本次版本更新围绕**解析能力、系统架构与工程可用性**进行了系统升级。主要更新内容包括：
  
  - `DOCX` 原生解析
    - 正式支持 `DOCX` 原生解析，在无幻觉前提下实现高精度解析。
    - 相较于“先将 `DOCX` 转为 `PDF` 再解析”的传统流程，端到端速度提升数十倍以上，更适合对精度与吞吐均有要求的场景。
  - `pipeline` 后端升级
    - `pipeline` 后端在 OmniDocBench (v1.5) 上取得 `86.2` 分，精度超过上一代主流 VLM `MinerU2.0-2505-0.9B`。
    - 新增表格内图片/公式解析、印章文字识别、竖排文本支持、行间公式序号识别等能力，持续提升复杂文档场景下的解析效果。
    - 在保持高精度的同时，资源占用极低，并继续支持纯 CPU 环境推理。
  - `API / CLI / Router` 编排升级
    - `mineru` 现作为基于 `mineru-api` 的编排客户端运行；在未传入 `--api-url` 时，会自动拉起本地临时服务。
    - `mineru-api` 新增异步任务接口 `POST /tasks`，支持任务提交、状态查询与结果获取；同时保留同步解析接口 `POST /file_parse`，以兼容老版本插件。
    - 新增 `mineru-router`，适用于多服务、多 GPU 的统一入口部署与任务路由；其接口与 `mineru-api` 完全兼容，并支持任务自动负载均衡。
  - 部署与使用体验优化
    - 解决了 `torch >= 2.8` 的兼容问题，基础镜像升级为 `vllm0.11.2 + torch2.9.0`，统一了不同 Compute Capability 的安装路径。
    - 通过滑动窗口优化解析链路，显著降低长文档场景下的内存峰值占用，上万页文档解析不再需要手动拆分。
    - `pipeline` 的 batch 推理支持流式落盘，已完成的解析结果可及时写出，进一步提升长任务处理体验。
    - 完成线程安全优化，全面支持多线程并发推理；配合 `mineru-router`，可一键实现多卡部署，轻松构建高并发、高吞吐解析系统。
    - 完全移除了两个 AGPLv3 模型（`doclayoutyolo` 和 `mfd_yolov8`）以及一个 CC-BY-NC-SA 4.0 模型（`layoutreader`）的使用。  
  
  本次更新不仅是若干功能点的补强，更是 MinerU 在系统能力上的一次关键跃迁。我们重点解决了长文档解析过程中的内存峰值占用问题，通过滑动窗口、流式落盘等链路优化，让超长文档解析从“需要手动拆分、谨慎处理”走向“稳定可跑、规模可扩展”。同时，我们完成了线程安全优化，全面支持多线程并发推理，进一步提升了单机资源利用率与高并发场景下的运行稳定性。在此基础上，基于 mineru-router 与全新的 API / CLI 编排体系，MinerU 已具备一键多卡部署、多服务统一接入、任务自动负载均衡的能力，显著降低了大规模部署难度。至此，MinerU 正在从单一的数据生产工具，进一步演进为面向高并发、高吞吐场景的大规模文档解析基座，为企业级文档数据处理提供更稳定、更高效、更易扩展的基础设施能力。

> 📝 查看完整的 [更新日志](https://opendatalab.github.io/MinerU/zh/reference/changelog/) 了解更多历史版本信息

# MinerU

## 项目简介

MinerU 是一款文档解析工具，可将 `PDF`、图片以及 `DOCX`、`PPTX`、`XLSX` 转化为机器可读格式（如 Markdown、JSON），便于后续检索、抽取与二次处理。
MinerU诞生于[书生-浦语](https://github.com/InternLM/InternLM)的预训练过程中，我们将会集中精力解决科技文献中的符号转化问题，希望在大模型时代为科技发展做出贡献。
相比国内外知名商用产品MinerU还很年轻，如果遇到问题或者结果不及预期请到[issue](https://github.com/opendatalab/MinerU/issues)提交问题，同时**附上相关文档或样例文件**。

https://github.com/user-attachments/assets/4bea02c9-6d54-4cd6-97ed-dff14340982c

## 主要功能

- 支持 `PDF`、图片与 `DOCX`、`PPTX`、`XLSX` 输入
- 删除页眉、页脚、脚注、页码等元素，确保语义连贯
- 输出符合人类阅读顺序的文本，适用于单栏、多栏及复杂排版
- 保留原文档的结构，包括标题、段落、列表等
- 提取图像、图片描述、表格、表格标题及脚注
- 自动识别并转换文档中的公式为LaTeX格式
- 自动识别并转换文档中的表格为HTML格式
- 自动检测扫描版PDF和乱码PDF，并启用OCR功能
- OCR支持109种语言的检测与识别
- 支持多种输出格式，如多模态与NLP的Markdown、按阅读顺序排序的JSON、含有丰富信息的中间格式等
- 支持多种可视化结果，包括layout可视化、span可视化等，便于高效确认输出效果与质检
- 内置命令行、FastAPI、Gradio WebUI，支持本地编排和多服务部署
- 支持纯CPU环境运行，并支持 GPU/MPS加速，以及十余款国产算力平台的推理加速
- 兼容Windows、Linux和Mac平台

# 快速开始

文档解析是困难且复杂的任务，尤其是对于复杂版面、扫描件、手写体等场景，解析结果可能不尽如人意。我们建议您先使用在线体验评估 MinerU 的解析效果和适用性，再根据实际需求选择合适的部署方式。
如果您有解析效果不佳的**文档**样例，欢迎提交上传到 [issue](https://github.com/opendatalab/MinerU/issues)，我们会持续优化解析能力。
如果安装或使用中遇到任何问题，请先查询 <a href="#faq">FAQ</a> 

## 在线体验

### 官网在线应用
官网在线版功能与客户端一致，界面美观，功能丰富，需要登录使用  
   
- [OpenDataLab](https://mineru.net/OpenSourceTools/Extractor?source=github)

### 基于Gradio的在线demo
基于gradio开发的webui，界面简洁，仅包含核心解析功能，免登录

- [ModelScope](https://www.modelscope.cn/studios/OpenDataLab/MinerU)
- [HuggingFace](https://huggingface.co/spaces/opendatalab/MinerU)

## 本地部署

> [!WARNING]
> **安装前必看——软硬件环境支持说明**
> 
> 为了确保项目的稳定性和可靠性，我们在开发过程中仅对特定的软硬件环境进行优化和测试。这样当用户在推荐的系统配置上部署和运行项目时，能够获得最佳的性能表现和最少的兼容性问题。
>
> 通过集中资源和精力于主线环境，我们团队能够更高效地解决潜在的BUG，及时开发新功能。
>
> 在非主线环境中，由于硬件、软件配置的多样性，以及第三方依赖项的兼容性问题，我们无法100%保证项目的完全可用性。因此，对于希望在非推荐环境中使用本项目的用户，我们建议先仔细阅读文档以及FAQ，大多数问题已经在FAQ中有对应的解决方案，除此之外我们鼓励社区反馈问题，以便我们能够逐步扩大支持范围。

<table>
  <thead>
    <tr>
      <th rowspan="2">解析后端</th>
      <th rowspan="2">pipeline</th>
      <th colspan="2">*-auto-engine</th>
      <th colspan="2">*-http-client</th>
    </tr>
    <tr>
      <th>hybrid</th>
      <th>vlm</th>
      <th>hybrid</th>
      <th>vlm</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>后端特性</th>
      <td >兼容性好</td>
      <td colspan="2">硬件配置要求较高</td>
      <td colspan="2">适用于OpenAI兼容服务器<sup>2</sup></td>
    </tr> 
    <tr>
      <th>精度指标<sup>1</sup></th>
      <td style="text-align:center;">85+</td>
      <td colspan="4" style="text-align:center;">95+</td>
    </tr>
    <tr>
      <th>操作系统</th>
      <td colspan="5" style="text-align:center;">Linux<sup>3</sup> / Windows<sup>4</sup> / macOS<sup>5</sup></td>
    </tr>
    <tr>
      <th>纯CPU平台支持</th>
      <td style="text-align:center;">✅</td>
      <td colspan="2" style="text-align:center;">❌</td>
      <td colspan="2" style="text-align:center;">✅</td>
    </tr>
        <tr>
      <th>GPU加速支持</th>
      <td colspan="4" style="text-align:center;">Volta及以后架构GPU或Apple Silicon</td>
      <td rowspan="2">不需要</td>
    </tr>
    <tr>
      <th>显存最低要求</th>
      <td style="text-align:center;">4GB</td>
      <td style="text-align:center;">8GB</td>
      <td style="text-align:center;">8GB</td>
      <td style="text-align:center;">2GB</td>
    </tr>
    <tr>
      <th>内存要求</th>
      <td colspan="3" style="text-align:center;">最低16GB以上,推荐32GB以上</td>
      <td colspan="2" style="text-align:center;">最低16GB</td>
    </tr>
    <tr>
      <th>磁盘空间要求</th>
      <td colspan="3" style="text-align:center;">20GB以上,推荐使用SSD</td>
      <td colspan="2" style="text-align:center;">至少2GB</td>
    </tr>
    <tr>
      <th>python版本</th>
      <td colspan="5" style="text-align:center;">3.10-3.13</td>
    </tr>
  </tbody>
</table>

<sup>1</sup> 精度指标为OmniDocBench (v1.6)的End-to-End Evaluation Overall分数，基于`MinerU`最新版本测试  
<sup>2</sup> 兼容OpenAI API的服务器，如通过`vLLM`/`SGLang`/`LMDeploy`等推理框架部署的本地模型服务器或远程模型服务  
<sup>3</sup> Linux仅支持2019年及以后发行版  
<sup>4</sup> 由于关键依赖`ray`未能在windows平台支持Python 3.13，故仅支持至3.10~3.12版本  
<sup>5</sup> macOS 需使用14.0以上版本  

> [!TIP]
> - 除以上主流环境与平台外，我们也收录了一些社区用户反馈的其他平台支持情况，详情请参考[其他加速卡适配](https://opendatalab.github.io/MinerU/zh/usage/)。  
> - 如果您有意将自己的环境适配经验分享给社区，欢迎通过[show-and-tell](https://github.com/opendatalab/MinerU/discussions/categories/show-and-tell)提交或提交PR至[其他加速卡适配](https://github.com/opendatalab/MinerU/tree/master/docs/zh/usage/acceleration_cards)文档。

### 安装 MinerU

#### 使用pip或uv安装MinerU
```bash
pip install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple
pip install uv -i https://mirrors.aliyun.com/pypi/simple
uv pip install -U "mineru[all]" -i https://mirrors.aliyun.com/pypi/simple 
```

#### 通过源码安装MinerU
```bash
git clone https://github.com/opendatalab/MinerU.git
cd MinerU
uv pip install -e .[all] -i https://mirrors.aliyun.com/pypi/simple
```

> [!TIP]
> - `mineru[all]`包含所有核心功能，兼容Windows / Linux / macOS系统，适合绝大多数用户。
> - 如果您在 Windows 上安装后无法使用 CUDA 加速，请参考 [Windows CUDA 加速 FAQ](https://opendatalab.github.io/MinerU/zh/faq/#windows-cuda-acceleration)。
> - 如果您需要指定vlm模型的推理框架，或是仅准备在边缘设备安装轻量版client端，可以参考文档[扩展模块安装指南](https://opendatalab.github.io/MinerU/zh/quick_start/extension_modules/)。

---
 
#### 使用docker部署Mineru
MinerU提供了便捷的docker部署方式，这有助于快速搭建环境并解决一些棘手的环境兼容问题。

> [!TIP]
> - Docker 部署仅适用于 Linux，以及支持 WSL2 的 Windows 环境；
> - macOS 用户请直接参考前面两种方式部署安装，不要使用 Docker 部署。

您可以在文档中获取[Docker部署说明](https://opendatalab.github.io/MinerU/zh/quick_start/docker_deployment/)。

---

### 使用 MinerU

>[!TIP]
>默认使用托管在`huggingface`的模型进行解析，首次使用时会自动下载所需模型文件，后续使用将直接加载本地缓存的模型。如果您无法访问`huggingface`，可以通过以下命令切换至国内镜像源:
>```bash
>export MINERU_MODEL_SOURCE=modelscope
>```

如果您的设备满足上表中GPU加速的条件，可以使用简单的命令行进行文档解析:
```bash
mineru -p <input_path> -o <output_path>
```
如果您的设备不满足GPU加速条件，可以指定后端为`pipeline`，以在纯CPU环境下运行:
```bash
mineru -p <input_path> -o <output_path> -b pipeline
```

当前 `mineru` 支持本地 `PDF / 图片 / DOCX / PPTX / XLSX` 文件或目录输入，并可通过命令行、API、WebUI、`mineru-router` 等多种方式进行文档解析，具体使用方法请参考[使用指南](https://opendatalab.github.io/MinerU/zh/usage/)。


# FAQ
 
- 如果您在使用过程中遇到问题，可以先查看[常见问题](https://opendatalab.github.io/MinerU/zh/faq/)是否有解答。  
- 如果未能解决您的问题，您也可以使用[DeepWiki](https://deepwiki.com/opendatalab/MinerU)与AI助手交流，这可以解决大部分常见问题。  
- 如果您仍然无法解决问题，您可通过[Discord](https://discord.gg/Tdedn9GTXq)或[WeChat](https://mineru.net/community-portal/?aliasId=3c430f94)加入社区，与其他用户和开发者交流。

# All Thanks To Our Contributors

<a href="https://github.com/opendatalab/MinerU/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=opendatalab/MinerU" />
</a>

# License Information

本仓库采用 [MinerU 开源许可证](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md) 进行许可，基于 Apache 2.0 并附带额外条款。

# Acknowledgments

- [UniMERNet](https://github.com/opendatalab/UniMERNet)
- [TableStructureRec](https://github.com/RapidAI/TableStructureRec)
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- [PaddleOCR2Pytorch](https://github.com/frotms/PaddleOCR2Pytorch)
- [fast-langdetect](https://github.com/LlmKira/fast-langdetect)
- [pypdfium2](https://github.com/pypdfium2-team/pypdfium2)
- [pdftext](https://github.com/datalab-to/pdftext)
- [pdfminer.six](https://github.com/pdfminer/pdfminer.six)
- [pypdf](https://github.com/py-pdf/pypdf)
- [magika](https://github.com/google/magika)
- [vLLM](https://github.com/vllm-project/vllm)
- [LMDeploy](https://github.com/InternLM/lmdeploy)

# Citation

```bibtex
@article{wang2026mineru2,
  title={MinerU2. 5-Pro: Pushing the Limits of Data-Centric Document Parsing at Scale},
  author={Wang, Bin and He, Tianyao and Ouyang, Linke and Wu, Fan and Zhao, Zhiyuan and Chu, Tao and Qu, Yuan and Jin, Zhenjiang and Zeng, Weijun and Miao, Ziyang and others},
  journal={arXiv preprint arXiv:2604.04771},
  year={2026}
}

@article{dong2026minerudiffusion,
  title={MinerU-Diffusion: Rethinking Document OCR as Inverse Rendering via Diffusion Decoding},
  author={Dong, Hejun and Niu, Junbo and Wang, Bin and Zeng, Weijun and Zhang, Wentao and He, Conghui},
  journal={arXiv preprint arXiv:2603.22458},
  year={2026}
}

@article{niu2025mineru2,
  title={Mineru2. 5: A decoupled vision-language model for efficient high-resolution document parsing},
  author={Niu, Junbo and Liu, Zheng and Gu, Zhuangcheng and Wang, Bin and Ouyang, Linke and Zhao, Zhiyuan and Chu, Tao and He, Tianyao and Wu, Fan and Zhang, Qintong and others},
  journal={arXiv preprint arXiv:2509.22186},
  year={2025}
}

@article{wang2024mineru,
  title={Mineru: An open-source solution for precise document content extraction},
  author={Wang, Bin and Xu, Chao and Zhao, Xiaomeng and Ouyang, Linke and Wu, Fan and Zhao, Zhiyuan and Xu, Rui and Liu, Kaiwen and Qu, Yuan and Shang, Fukai and others},
  journal={arXiv preprint arXiv:2409.18839},
  year={2024}
}

@article{he2024opendatalab,
  title={Opendatalab: Empowering general artificial intelligence with open datasets},
  author={He, Conghui and Li, Wei and Jin, Zhenjiang and Xu, Chao and Wang, Bin and Lin, Dahua},
  journal={arXiv preprint arXiv:2407.13773},
  year={2024}
}
```

# Star History

<a>
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=opendatalab/MinerU&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=opendatalab/MinerU&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=opendatalab/MinerU&type=Date" />
 </picture>
</a>


# Links
- [Easy Data Preparation with latest LLMs-based Operators and Pipelines](https://github.com/OpenDCAI/DataFlow)
- [Vis3 (OSS browser based on s3)](https://github.com/opendatalab/Vis3)
- [LabelU (A Lightweight Multi-modal Data Annotation Tool)](https://github.com/opendatalab/labelU)
- [LabelLLM (An Open-source LLM Dialogue Annotation Platform)](https://github.com/opendatalab/LabelLLM)
- [PDF-Extract-Kit (A Comprehensive Toolkit for High-Quality PDF Content Extraction)](https://github.com/opendatalab/PDF-Extract-Kit)
- [OmniDocBench (A Comprehensive Benchmark for Document Parsing and Evaluation)](https://github.com/opendatalab/OmniDocBench)
- [Magic-HTML (Mixed web page extraction tool)](https://github.com/opendatalab/magic-html)
- [Magic-Doc (Fast speed ppt/pptx/doc/docx/pdf extraction tool)](https://github.com/InternLM/magic-doc) 
- [Dingo: A Comprehensive AI Data Quality Evaluation Tool](https://github.com/MigoXLab/dingo)
