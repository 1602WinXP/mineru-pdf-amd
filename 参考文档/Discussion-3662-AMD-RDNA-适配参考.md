> 本文由 [简悦 SimpRead](http://ksria.com/simpread/) 转码， 原文地址 [github.com](https://github.com/opendatalab/MinerU/discussions/3662)

> (2026.2.5 更新)AMD RDNA ROCm vllm 后端和 pipeline 后端完整适配分享

Discussion options

### Uh oh!

There was an error while loading. Please reload this page.

Quote reply edited

### Uh oh!

There was an error while loading. Please reload this page.

 [![](https://avatars.githubusercontent.com/u/58244022?s=64&v=4) healy-hub](/healy-hub) [Oct 4, 2025](#discussion-8980687) 
---------------------------------------------------------------------------------------------------------------------------

-

<table role="presentation" data-paste-markdown-skip=""><tbody data-target-translation-id="8980687" data-target-translation-type="discussion"><tr><td><h2 dir="auto" id="sr-toc-3">2026.2.12 folk 了几个相关的仓库，准备抽空精简一下教程，直接 clone 我的仓库反而更方便。排查了一下 flash_attn 的 triton 实现，最新的提交实现了 RDNA 上的 flash_attn v3，带了问题是仅推理会导致速度反而不如 v2。另外每个实现都没有做形状的分类归一，导致在 mineru 这种视觉处理上只要有一点点的长度不一样就会导致 triton 重新启用新的 kernel。这些问题均解决了，空了我更新一下教程。另外 triton 后端建议在安装结束后采用一个大的 PDF 文件生成缓存，这是 triton 的特性无解。这个缓存文件一次即可，重启等不会丢失。</h2><h3 dir="auto" id="sr-toc-4">2026.2.5 更新，设置了 flash_attn 仓库回退，最新的 triton 后端合并在 RDNA 3 7900xtx 上的性能回退 30% 左右，回退到 12 月的版本即可，git checkout bba578d43974c1d3ba157ab597124dd0fe2ccdb4, 最新的合并实现了 Fused Bwd，只能说暂时还不好用</h3><h3 dir="auto" id="sr-toc-5">2026.1.31 更新，放弃所有的 triton 实现，难以在不同的 GPU 上都实现最好的性能，因此转向于利用 AMD 优化好的无问题的后端提供适配。目前在 7900xtx 测试下来，300 页的 PDF，vllm 后端的速度大概能跑到 1.8～2.01it/s，pipeline ocr 速度也能到几百 it/s。有些国产 GPU 的 pipeline 后端也许可以参考这个实现，好像有看到过 vllm 后端没问题，但是 pipeline 后端几个模型反而没有实现的。</h3><h4 dir="auto" id="sr-toc-6">吐槽：ROCm 7.2 并没有解决 RDNA 上 3D 卷积，2D 卷积的基数倍数，空洞卷积的问题。。。。绷不住了，真特么幽默的 RDNA CK 后端优化。开始觉得不用自己来 AMD 官方能解决，想多了。</h4><hr class="simpread-hidden"><h4 dir="auto" id="sr-toc-7">在开头先解释一下原因，为什么在 RDNA AMD GPU 上推理速度如此之慢。第一个是 vllm 的 conv3d，torch.Size([56700, 3, 2, 14, 14]) 这种 batch_size 根本找不到 MIOPEN 的 kernel 实现，它回退到了 fp64 的双精度计算，并且搜索 kernel 花了 12s，但是啥也没找到，vllm 后端只有这一个问题。</h4><h4 dir="auto" id="sr-toc-8">接下来是 pipeline 后端，这个问题就多了，首先是第一步 Layout Predict 用的空洞卷积，自定义的 doclayout_yolo/nn/modules/g2l_crm.py 找不到 kernel，回退 + 1。然后是 ocr 部分，这里有两个问题，一个是 conv2d 在 MIOPEN 上，遇到 (1, 3, 544, 672) 这种，后面两个都是 32 的奇数倍数时，每次都会冷启动，导致需要 1s 多搜索最佳 kernel 的时间，另一个问题是 mineru 每次 ocr 的 batch 是 6 个送过去的，到最后一次的时候，很可能不是 6 个，这个时候同时面对 batch 和形状的冷启动，会带来一个 7s 左右的延迟，对，你没听错，是 7s。。。。。。</h4><hr class="simpread-hidden"><p dir="auto"><strong>下面是做的一个适配修改，需要修改的部分比之前多一点，，其实可以写一个脚本自动实现，也不是非要自己手动修改，但是尽可能详细一点：</strong></p><h2 dir="auto" id="sr-toc-9">如果有疏漏，可以在下面评论，看到会解决的</h2><h3 dir="auto" id="sr-toc-10">1. 环境介绍</h3><p dir="auto">System: Ubuntu 24.04.3 Kernel: Linux 6.14.0-37-generic ROCm version: 7.1.1 CPU 13900K 内存 64G 6800MHz ddr5<br>python 环境：<br>python 3.13.8<br>pytorch-triton-rocm 3.6.0+git5261b273<br>torch 2.10.0.dev20251208+rocm7.1<br>torchvision 0.25.0.dev20251209+rocm7.1<br>vllm 0.15.2rc1.dev2+g72bb24e2d.rocm720<br>amd-aiter 0.1.11.dev27+g1f5a39227<br>flash_attn 2.8.3</p><p dir="auto">不同版本无所谓，处理方法是一样的，这个版本的 fp16 和 bf16 矩阵乘能到 104tflops 的结果。新版 AMD 官方的 ROCm 7.2 torch 性能也不错更好，但是 torch 2.10 官方只给了 python 3.12 的，没有 python 3.13，参见 <a href="https://repo.radeon.com/rocm/manylinux/rocm-rel-7.2/" rel="nofollow">https://repo.radeon.com/rocm/manylinux/rocm-rel-7.2/</a> 。Pytorch 这边的 preview 版的暂时没有更新 ROCm 7.2 版的，得等等，参见 <a href="https://pytorch.org/" rel="nofollow">https://pytorch.org/</a> 。</p><hr class="simpread-hidden"><h3 dir="auto" id="sr-toc-11">2. 前置环境安装</h3><p dir="auto"><strong><del>已有完整 python vllm 和 mineru 环境直接跳转第 3 步！！！</del> 建议使用推荐版本的 vllm 和 Torch</strong><br>这里我用的 uv python 环境，conda 等均可，但是切记使用 pip 安装 mineru 而不要使用 uv pip，uv pip 会安装英伟达的 torch 后端等。。。。日志显示 Flash Attention (Triton backend) for ViT model on RDNA。</p><pre class="hljs sql">uv venv --python python3.13
source .venv/bin/activate
uv pip install --pre torch==2.10.0.dev20251208+rocm7.1 torchvision==0.25.0.dev20251209+rocm7.1 pytorch-triton-rocm==3.6.0+git5261b273 --index-url https://download.pytorch.org/whl/nightly/rocm7.1
# 最近的更新里就这附近的版本最猛
uv pip install pip
# 避免覆盖我们本地的pytorch，改用pip而没有继续使用uv pip
pip install -U "mineru[core]" -i https://pypi.mirrors.ustc.edu.cn/simple/</pre><clipboard-copy aria-label="Copy code to clipboard" data-copy-feedback="Copied!" data-tooltip-direction="w" value="uv venv --python python3.13
source .venv/bin/activate
uv pip install --pre torch==2.10.0.dev20251208+rocm7.1 torchvision==0.25.0.dev20251209+rocm7.1 pytorch-triton-rocm==3.6.0+git5261b273 --index-url https://download.pytorch.org/whl/nightly/rocm7.1
# 最近的更新里就这附近的版本最猛
uv pip install pip
# 避免覆盖我们本地的pytorch，改用pip而没有继续使用uv pip
pip install -U &quot;mineru[core]&quot; -i https://pypi.mirrors.ustc.edu.cn/simple/" tabindex="0" role="button"><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"></path></svg></clipboard-copy><p dir="auto">vllm 安装参考官方手册 <a href="https://docs.vllm.com.cn/en/latest/getting_started/installation/gpu.html#amd-rocm" rel="nofollow">Vllm</a></p><pre class="hljs properties">#手动安装aiter，vllm，amd-smi等，自行找一个位置clone，然后进入该目录吧
git clone --recursive https://github.com/ROCm/aiter.git
cd aiter
git submodule sync; git submodule update --init --recursive
python setup.py develop
cd ..
git clone --recursive https://github.com/Dao-AILab/flash-attention.git
cd flash-attention
git checkout bba578d43974c1d3ba157ab597124dd0fe2ccdb4   #一月到二月commi均导致在RDNA 3上的性能回退，尤其是最新的2月rocm改进提交
export FLASH_ATTENTION_TRITON_AMD_ENABLE="TRUE"   
rm -rf ~/.triton/cache   #清理以前的triton缓存
#至关重要，官方FLASH_ATTENTION_TRITON_AMD_ENABLE="TRUE" python setup.py install不大好，而且运行的时候这个环境变量也需要，不如终端设置了。
python setup.py install
cd ..
git clone https://github.com/vllm-project/vllm.git
cd vllm/
cp -r /opt/rocm/share/amd_smi ~/Pytorch/vllm/
pip install amd_smi/
pip install --upgrade numba \
    scipy \
    huggingface-hub[cli,hf_transfer] \
    setuptools_scm
pip install -r requirements/rocm.txt    #如果和mineru的包冲突了，用mineru需要的的版本即可，vllm不挑的，没啥问题
export PYTORCH_ROCM_ARCH="gfx1100"   #根据自己的GPU架构 rocminfo | grep gfx
python setup.py develop</pre><clipboard-copy aria-label="Copy code to clipboard" data-copy-feedback="Copied!" data-tooltip-direction="w" value="#手动安装aiter，vllm，amd-smi等，自行找一个位置clone，然后进入该目录吧
git clone --recursive https://github.com/ROCm/aiter.git
cd aiter
git submodule sync; git submodule update --init --recursive
python setup.py develop
cd ..
git clone --recursive https://github.com/Dao-AILab/flash-attention.git
cd flash-attention
git checkout bba578d43974c1d3ba157ab597124dd0fe2ccdb4   #一月到二月commi均导致在RDNA 3上的性能回退，尤其是最新的2月rocm改进提交
export FLASH_ATTENTION_TRITON_AMD_ENABLE=&quot;TRUE&quot;   
rm -rf ~/.triton/cache   #清理以前的triton缓存
#至关重要，官方FLASH_ATTENTION_TRITON_AMD_ENABLE=&quot;TRUE&quot; python setup.py install不大好，而且运行的时候这个环境变量也需要，不如终端设置了。
python setup.py install
cd ..
git clone https://github.com/vllm-project/vllm.git
cd vllm/
cp -r /opt/rocm/share/amd_smi ~/Pytorch/vllm/
pip install amd_smi/
pip install --upgrade numba \
    scipy \
    huggingface-hub[cli,hf_transfer] \
    setuptools_scm
pip install -r requirements/rocm.txt    #如果和mineru的包冲突了，用mineru需要的的版本即可，vllm不挑的，没啥问题
export PYTORCH_ROCM_ARCH=&quot;gfx1100&quot;   #根据自己的GPU架构 rocminfo | grep gfx
python setup.py develop" tabindex="0" role="button"><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"></path></svg></clipboard-copy><hr class="simpread-hidden"><h3 dir="auto" id="sr-toc-12">3.patch 环节</h3><p dir="auto">mineru 和 doclayoutyolo 两个仓库的改动可以参考我做的 <a href="https://github.com/healy-hub/MinerU-AMD-RDNA">MinerU-AMD-RDNA</a> 和 <a href="https://github.com/healy-hub/DocLayout-YOLO-AMD-RDNA">DocLayout-YOLO-AMD-RDNA</a> 的 commit。下面我还是给出完整的 patch 部分：</p><h4 dir="auto" id="sr-toc-13">3.1 vllm patch 部分</h4><p dir="auto">定位自己 vllm 位置 XXX</p><pre class="hljs nginx">pip show vllm</pre><clipboard-copy aria-label="Copy code to clipboard" data-copy-feedback="Copied!" data-tooltip-direction="w" value="pip show vllm" tabindex="0" role="button"><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"></path></svg></clipboard-copy><p dir="auto"><strong>关键更改</strong><br>XXX/vllm/model_executor/models/qwen2_vl.py 文件：<br>35 行下面增加一个 import：</p><pre class="hljs coffeescript">import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F</pre><clipboard-copy aria-label="Copy code to clipboard" data-copy-feedback="Copied!" data-tooltip-direction="w" value="import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F" tabindex="0" role="button"><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"></path></svg></clipboard-copy><p dir="auto">446 行 class Qwen2VisionPatchEmbed(nn.Module) 函数修改为下面的, 直接用 F.linear 来实现 conv3d，速度极快，拉满 rocblas：</p><pre class="hljs ruby">class Qwen2VisionPatchEmbed(nn.Module):
    def __init__(
        self,
        patch_size: int = 14,
        temporal_patch_size: int = 2,
        in_channels: int = 3,
        embed_dim: int = 1152,
    ) -&gt; None:
        super().__init__()
        self.patch_size = patch_size
        self.temporal_patch_size = temporal_patch_size
        self.embed_dim = embed_dim

        kernel_size = (temporal_patch_size, patch_size, patch_size)

        # 保持 Conv3d 定义，确保加载 Checkpoint 时 key 匹配
        self.proj = nn.Conv3d(
            in_channels,
            embed_dim,
            kernel_size=kernel_size,
            stride=kernel_size,
            bias=False,
        )

        # Conv 权重默认是连续的
        self.flat_weight_shape = (embed_dim, -1)

    def forward(self, x: torch.Tensor) -&gt; torch.Tensor:
        # x shape: (L, Total_Input_Pixels), 例如: (56700, 3 * 2 * 14 * 14) = (56700, 1176)
        # 确保输入内存连续
        if not x.is_contiguous():
            x = x.contiguous()
        weight = self.proj.weight.view(self.flat_weight_shape)
        # 偏差处理 (Bias Handling)
        bias = self.proj.bias
        # Conv3d (stride=k) 等同于将每个 Patch 拉平后与权重矩阵做点积。
        out = F.linear(x, weight, bias)
        return out</pre><clipboard-copy aria-label="Copy code to clipboard" data-copy-feedback="Copied!" data-tooltip-direction="w" value="class Qwen2VisionPatchEmbed(nn.Module):
    def __init__(
        self,
        patch_size: int = 14,
        temporal_patch_size: int = 2,
        in_channels: int = 3,
        embed_dim: int = 1152,
    ) -> None:
        super().__init__()
        self.patch_size = patch_size
        self.temporal_patch_size = temporal_patch_size
        self.embed_dim = embed_dim

        kernel_size = (temporal_patch_size, patch_size, patch_size)

        # 保持 Conv3d 定义，确保加载 Checkpoint 时 key 匹配
        self.proj = nn.Conv3d(
            in_channels,
            embed_dim,
            kernel_size=kernel_size,
            stride=kernel_size,
            bias=False,
        )

        # Conv 权重默认是连续的
        self.flat_weight_shape = (embed_dim, -1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x shape: (L, Total_Input_Pixels), 例如: (56700, 3 * 2 * 14 * 14) = (56700, 1176)
        # 确保输入内存连续
        if not x.is_contiguous():
            x = x.contiguous()
        weight = self.proj.weight.view(self.flat_weight_shape)
        # 偏差处理 (Bias Handling)
        bias = self.proj.bias
        # Conv3d (stride=k) 等同于将每个 Patch 拉平后与权重矩阵做点积。
        out = F.linear(x, weight, bias)
        return out" tabindex="0" role="button"><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"></path></svg></clipboard-copy><h4 dir="auto" id="sr-toc-14">3.2 pipline doclayout_yolo patch 部分</h4><p dir="auto">可以去仓库直接复制该文件：<a href="https://github.com/healy-hub/DocLayout-YOLO-AMD-RDNA">DocLayout-YOLO-AMD-RDNA</a><br>定位自己 doclayout_yolo 位置 XXX</p><pre class="hljs nginx">pip show doclayout_yolo</pre><clipboard-copy aria-label="Copy code to clipboard" data-copy-feedback="Copied!" data-tooltip-direction="w" value="pip show doclayout_yolo" tabindex="0" role="button"><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"></path></svg></clipboard-copy><p dir="auto">修改 XXX/doclayout_yolo/nn/modules/g2l_crm.py，比如我的在 / home/XXX/Pytorch/MinerUvllm/.venv/lib/python3.13/site-packages/doclayout_yolo/nn/modules/g2l_crm.py：<br>代码不长直接替换好了：</p><pre class="hljs python">import torch
from torch import nn, Tensor
import torch.nn.functional as F
from typing import List, Optional

from .conv import Conv
from .block import CIB

class DilatedBlock(nn.Module):
    """
    针对 AMD RDNA、优化的 DilatedBlock。
    针对非整除尺寸的 Padding 对齐逻辑，彻底解决 RuntimeError，蛋疼的RDNA。
    """
    def __init__(self, c, dilation: List[int], k: int, fuse="sum", shortcut=True):
        super().__init__()
        self.dilation = dilation
        self.k = k
        self.fuse = fuse
        self.add = shortcut

        self.cv2 = Conv(c, c, k=1, s=1)
        if fuse == "glu":
            self.conv_gating = Conv(c * len(dilation), c * len(dilation), k=1, s=1, g=c * len(dilation))
            self.conv1x1 = Conv(c * len(dilation), c, k=1, s=1, g=c)
        elif fuse == "sum":
            self.conv1x1 = Conv(c, c, k=1, s=1, g=c)

        # 这里的 dcv 包含 conv, bn, act。将在 _s2b_forward 中复用
        self.dcv = Conv(c, c, k=k, s=1)

    def _s2b_forward(self, x: Tensor, d: int) -&gt; Tensor:
        """
        Space-to-Batch 卷积实现 (Robust Version)。
        自动处理非整除尺寸，避免 RuntimeError。
        """
        if d == 1:
            return self.dcv(x)

        n, c, h, w = x.shape
        conv_mod = self.dcv.conv
        
        # 计算 Padding，base_pad用于模拟相同卷积所需的 padding
        base_pad = d * (self.k // 2)
        
        h_padded_base = h + 2 * base_pad
        w_padded_base = w + 2 * base_pad
        
        pad_h_extra = (d - (h_padded_base % d)) % d
        pad_w_extra = (d - (w_padded_base % d)) % d
        
        # F.pad 参数顺序: (left, right, top, bottom)，额外的 padding 加在右侧和下侧，方便后续裁剪
        x_pad = F.pad(x, (base_pad, base_pad + pad_w_extra, base_pad, base_pad + pad_h_extra))
        
        # Space-to-Batch(S2B)切片
        slices = []
        for i in range(d):
            for j in range(d):
                slices.append(x_pad[:, :, i::d, j::d])
        
        # 堆叠 -&gt; (N * d*d, C, H_sub, W_sub)，extra_pad，此处所有 slice 的 shape 严格一致
        x_batch = torch.cat(slices, dim=0)

        # 标准卷积 (Stride=1, Padding=0)
        # 手动处理过padding，用padding=0的valid conv
        out_batch = F.conv2d(x_batch, conv_mod.weight, conv_mod.bias, stride=1, padding=0)
        
        # 计算子块输出尺寸
        h_sub_out, w_sub_out = out_batch.shape[2], out_batch.shape[3]
        
        # 预分配输出张量 (尺寸可能略大于原图)
        out_temp = torch.empty((n, c, h_sub_out * d, w_sub_out * d), device=x.device, dtype=x.dtype)
        
        out_chunks = torch.tensor_split(out_batch, d*d, dim=0)
        
        idx = 0
        for i in range(d):
            for j in range(d):
                # 并行写入显存，还原空间位置
                out_temp[:, :, i::d, j::d] = out_chunks[idx]
                idx += 1

        # 输出 (N, C, H, W)，由于padding存在，out_temp会略大，问题不大
        if out_temp.shape[2] != h or out_temp.shape[3] != w:
            out = out_temp[:, :, :h, :w]
        else:
            out = out_temp

        return self.dcv.act(self.dcv.bn(out))

    def forward(self, x: Tensor) -&gt; Tensor:
        # 确保内存连续，防止 AMD GPU 上的 stride 异常
        if not x.is_contiguous():
            x = x.contiguous()

        if self.fuse == "sum":
            dx_accum = None
            for d in self.dilation:
                # 使用 S2B 优化的卷积
                current = self.cv2(self._s2b_forward(x, d))
                if dx_accum is None:
                    dx_accum = current
                else:
                    dx_accum = dx_accum + current
            dx = self.conv1x1(dx_accum)
            
        elif self.fuse == "glu":
            dx_list = [self.cv2(self._s2b_forward(x, d)) for d in self.dilation]
            dx = torch.cat(dx_list, dim=1)
            g = torch.sigmoid(self.conv_gating(dx))
            dx = self.conv1x1(dx * g)

        return (x + dx if self.add else dx)

class DilatedBottleneck(nn.Module):
    # 标准空洞卷积瓶颈模块
    def __init__(self, c1, c2, shortcut=True, dilation=[1,2,3], block_k=3, fuse="sum", g=1, k=(3, 3), e=0.5):
        super().__init__()
        c_ = int(c2 * e)
        self.cv1 = Conv(c1, c_, k[0], 1)
        self.cv2 = Conv(c_, c2, k[1], 1, g=g)
        self.dilated_block = DilatedBlock(c_, dilation, block_k, fuse)
        self.add = shortcut and c1 == c2

    def forward(self, x):
        return x + self.cv2(self.dilated_block(self.cv1(x))) if self.add else self.cv2(self.dilated_block(self.cv1(x)))

class G2L_CRM(nn.Module):
    # 使用2个卷积层更快地实现CSP瓶颈问题。
    def __init__(self, c1, c2, n=1, shortcut=False, use_dilated=False, dilation=[1,2,3], block_k=3, fuse="sum", g=1, e=0.5):
        super().__init__()
        self.c = int(c2 * e)
        self.cv1 = Conv(c1, 2 * self.c, 1, 1)
        self.cv2 = Conv((2 + n) * self.c, c2, 1)
        if use_dilated:
            self.m = nn.ModuleList(DilatedBottleneck(
                self.c, self.c, shortcut, dilation, block_k, fuse, g, k=((3, 3), (3, 3)), e=1.0
            ) for _ in range(n))
        else:
            self.m = nn.ModuleList(CIB(self.c, self.c, shortcut, e=1.0) for _ in range(n))

    def forward(self, x):
        y = list(self.cv1(x).chunk(2, 1))
        for m in self.m:
            y.append(m(y[-1]))
        return self.cv2(torch.cat(y, 1))

    def forward_split(self, x):
        y = list(self.cv1(x).split((self.c, self.c), 1))
        for m in self.m:
            y.append(m(y[-1]))
        return self.cv2(torch.cat(y, 1))</pre><clipboard-copy aria-label="Copy code to clipboard" data-copy-feedback="Copied!" data-tooltip-direction="w" value="import torch
from torch import nn, Tensor
import torch.nn.functional as F
from typing import List, Optional

from .conv import Conv
from .block import CIB

class DilatedBlock(nn.Module):
    &quot;&quot;&quot;
    针对 AMD RDNA、优化的 DilatedBlock。
    针对非整除尺寸的 Padding 对齐逻辑，彻底解决 RuntimeError，蛋疼的RDNA。
    &quot;&quot;&quot;
    def __init__(self, c, dilation: List[int], k: int, fuse=&quot;sum&quot;, shortcut=True):
        super().__init__()
        self.dilation = dilation
        self.k = k
        self.fuse = fuse
        self.add = shortcut

        self.cv2 = Conv(c, c, k=1, s=1)
        if fuse == &quot;glu&quot;:
            self.conv_gating = Conv(c * len(dilation), c * len(dilation), k=1, s=1, g=c * len(dilation))
            self.conv1x1 = Conv(c * len(dilation), c, k=1, s=1, g=c)
        elif fuse == &quot;sum&quot;:
            self.conv1x1 = Conv(c, c, k=1, s=1, g=c)

        # 这里的 dcv 包含 conv, bn, act。将在 _s2b_forward 中复用
        self.dcv = Conv(c, c, k=k, s=1)

    def _s2b_forward(self, x: Tensor, d: int) -> Tensor:
        &quot;&quot;&quot;
        Space-to-Batch 卷积实现 (Robust Version)。
        自动处理非整除尺寸，避免 RuntimeError。
        &quot;&quot;&quot;
        if d == 1:
            return self.dcv(x)

        n, c, h, w = x.shape
        conv_mod = self.dcv.conv
        
        # 计算 Padding，base_pad用于模拟相同卷积所需的 padding
        base_pad = d * (self.k // 2)
        
        h_padded_base = h + 2 * base_pad
        w_padded_base = w + 2 * base_pad
        
        pad_h_extra = (d - (h_padded_base % d)) % d
        pad_w_extra = (d - (w_padded_base % d)) % d
        
        # F.pad 参数顺序: (left, right, top, bottom)，额外的 padding 加在右侧和下侧，方便后续裁剪
        x_pad = F.pad(x, (base_pad, base_pad + pad_w_extra, base_pad, base_pad + pad_h_extra))
        
        # Space-to-Batch(S2B)切片
        slices = []
        for i in range(d):
            for j in range(d):
                slices.append(x_pad[:, :, i::d, j::d])
        
        # 堆叠 -> (N * d*d, C, H_sub, W_sub)，extra_pad，此处所有 slice 的 shape 严格一致
        x_batch = torch.cat(slices, dim=0)

        # 标准卷积 (Stride=1, Padding=0)
        # 手动处理过padding，用padding=0的valid conv
        out_batch = F.conv2d(x_batch, conv_mod.weight, conv_mod.bias, stride=1, padding=0)
        
        # 计算子块输出尺寸
        h_sub_out, w_sub_out = out_batch.shape[2], out_batch.shape[3]
        
        # 预分配输出张量 (尺寸可能略大于原图)
        out_temp = torch.empty((n, c, h_sub_out * d, w_sub_out * d), device=x.device, dtype=x.dtype)
        
        out_chunks = torch.tensor_split(out_batch, d*d, dim=0)
        
        idx = 0
        for i in range(d):
            for j in range(d):
                # 并行写入显存，还原空间位置
                out_temp[:, :, i::d, j::d] = out_chunks[idx]
                idx += 1

        # 输出 (N, C, H, W)，由于padding存在，out_temp会略大，问题不大
        if out_temp.shape[2] != h or out_temp.shape[3] != w:
            out = out_temp[:, :, :h, :w]
        else:
            out = out_temp

        return self.dcv.act(self.dcv.bn(out))

    def forward(self, x: Tensor) -> Tensor:
        # 确保内存连续，防止 AMD GPU 上的 stride 异常
        if not x.is_contiguous():
            x = x.contiguous()

        if self.fuse == &quot;sum&quot;:
            dx_accum = None
            for d in self.dilation:
                # 使用 S2B 优化的卷积
                current = self.cv2(self._s2b_forward(x, d))
                if dx_accum is None:
                    dx_accum = current
                else:
                    dx_accum = dx_accum + current
            dx = self.conv1x1(dx_accum)
            
        elif self.fuse == &quot;glu&quot;:
            dx_list = [self.cv2(self._s2b_forward(x, d)) for d in self.dilation]
            dx = torch.cat(dx_list, dim=1)
            g = torch.sigmoid(self.conv_gating(dx))
            dx = self.conv1x1(dx * g)

        return (x + dx if self.add else dx)

class DilatedBottleneck(nn.Module):
    # 标准空洞卷积瓶颈模块
    def __init__(self, c1, c2, shortcut=True, dilation=[1,2,3], block_k=3, fuse=&quot;sum&quot;, g=1, k=(3, 3), e=0.5):
        super().__init__()
        c_ = int(c2 * e)
        self.cv1 = Conv(c1, c_, k[0], 1)
        self.cv2 = Conv(c_, c2, k[1], 1, g=g)
        self.dilated_block = DilatedBlock(c_, dilation, block_k, fuse)
        self.add = shortcut and c1 == c2

    def forward(self, x):
        return x + self.cv2(self.dilated_block(self.cv1(x))) if self.add else self.cv2(self.dilated_block(self.cv1(x)))

class G2L_CRM(nn.Module):
    # 使用2个卷积层更快地实现CSP瓶颈问题。
    def __init__(self, c1, c2, n=1, shortcut=False, use_dilated=False, dilation=[1,2,3], block_k=3, fuse=&quot;sum&quot;, g=1, e=0.5):
        super().__init__()
        self.c = int(c2 * e)
        self.cv1 = Conv(c1, 2 * self.c, 1, 1)
        self.cv2 = Conv((2 + n) * self.c, c2, 1)
        if use_dilated:
            self.m = nn.ModuleList(DilatedBottleneck(
                self.c, self.c, shortcut, dilation, block_k, fuse, g, k=((3, 3), (3, 3)), e=1.0
            ) for _ in range(n))
        else:
            self.m = nn.ModuleList(CIB(self.c, self.c, shortcut, e=1.0) for _ in range(n))

    def forward(self, x):
        y = list(self.cv1(x).chunk(2, 1))
        for m in self.m:
            y.append(m(y[-1]))
        return self.cv2(torch.cat(y, 1))

    def forward_split(self, x):
        y = list(self.cv1(x).split((self.c, self.c), 1))
        for m in self.m:
            y.append(m(y[-1]))
        return self.cv2(torch.cat(y, 1))" tabindex="0" role="button"><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"></path></svg></clipboard-copy><h4 dir="auto" id="sr-toc-15">3.3 pipline mineru patch 部分</h4><p dir="auto">可以去仓库直接复制对应文件，<a href="https://github.com/healy-hub/MinerU-AMD-RDNA">MinerU-AMD-RDNA</a> ：<br>定位自己 mineru 位置 XXX</p><pre class="hljs nginx">pip show mineru</pre><clipboard-copy aria-label="Copy code to clipboard" data-copy-feedback="Copied!" data-tooltip-direction="w" value="pip show mineru" tabindex="0" role="button"><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"></path></svg></clipboard-copy><p dir="auto">XXX/mineru/model/utils/tools/infer/predict_rec.py 的 136 行下面增加将 imgW 对齐到 32：</p><pre class="hljs properties">max_wh_ratio = max(max_wh_ratio, imgW / imgH)
        imgW = int(imgH * max_wh_ratio)
        imgW = max(min(imgW, self.limited_max_width), self.limited_min_width)
        # 将 imgW 对齐到 32，以避免任意宽度图像的 ROCm MIOpen JIT 开销。
        imgW = math.ceil(imgW / 32) * 32</pre><clipboard-copy aria-label="Copy code to clipboard" data-copy-feedback="Copied!" data-tooltip-direction="w" value="        max_wh_ratio = max(max_wh_ratio, imgW / imgH)
        imgW = int(imgH * max_wh_ratio)
        imgW = max(min(imgW, self.limited_max_width), self.limited_min_width)
        # 将 imgW 对齐到 32，以避免任意宽度图像的 ROCm MIOpen JIT 开销。
        imgW = math.ceil(imgW / 32) * 32" tabindex="0" role="button"><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"></path></svg></clipboard-copy><p dir="auto">XXX/mineru/model/utils/tools/infer/predict_rec.py 的 355 行下面增加</p><pre class="hljs properties">norm_img = norm_img[np.newaxis, :]
                        norm_img_batch.append(norm_img)
                # 增加下面内容，将批次填充到固定大小（self.rec_batch_num），以避免 MIOpen 重新编译。避免最后一个部分批次7秒以上的延迟问题。
                actual_batch_size = len(norm_img_batch)
                if actual_batch_size &lt; batch_num:
                    pad_size = batch_num - actual_batch_size
                    pad_img = np.zeros_like(norm_img_batch[0])
                    for _ in range(pad_size):
                        norm_img_batch.append(pad_img)
                # 改动结束
                norm_img_batch = np.concatenate(norm_img_batch)
                norm_img_batch = norm_img_batch.copy()</pre><clipboard-copy aria-label="Copy code to clipboard" data-copy-feedback="Copied!" data-tooltip-direction="w" value="                        norm_img = norm_img[np.newaxis, :]
                        norm_img_batch.append(norm_img)
                # 增加下面内容，将批次填充到固定大小（self.rec_batch_num），以避免 MIOpen 重新编译。避免最后一个部分批次7秒以上的延迟问题。
                actual_batch_size = len(norm_img_batch)
                if actual_batch_size < batch_num:
                    pad_size = batch_num - actual_batch_size
                    pad_img = np.zeros_like(norm_img_batch[0])
                    for _ in range(pad_size):
                        norm_img_batch.append(pad_img)
                # 改动结束
                norm_img_batch = np.concatenate(norm_img_batch)
                norm_img_batch = norm_img_batch.copy()" tabindex="0" role="button"><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"></path></svg></clipboard-copy><p dir="auto">XXX/mineru/model/utils/tools/infer/predict_rec.py 的 433 行附近修改 for rno in range(len(rec_result)) 为 for rno in range(actual_batch_size)：</p><pre class="hljs cs"># 只处理实际图像，忽略填充。
                for rno in range(actual_batch_size):
                    rec_res[indices[beg_img_no + rno]] = rec_result[rno]
                elapse += time.time() - starttime</pre><clipboard-copy aria-label="Copy code to clipboard" data-copy-feedback="Copied!" data-tooltip-direction="w" value="                # 只处理实际图像，忽略填充。
                for rno in range(actual_batch_size):
                    rec_res[indices[beg_img_no + rno]] = rec_result[rno]
                elapse += time.time() - starttime" tabindex="0" role="button"><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"></path></svg></clipboard-copy><p dir="auto">XXX/mineru/model/utils/tools/infer/predict_det.py 312 行下面增加两行形式检查，是否连续：</p><pre class="hljs properties">inp = torch.from_numpy(img)
            inp = inp.to(self.device)
            # Check format
            if not inp.is_contiguous():
                inp = inp.contiguous()
            outputs = self.net(inp)</pre><clipboard-copy aria-label="Copy code to clipboard" data-copy-feedback="Copied!" data-tooltip-direction="w" value="            inp = torch.from_numpy(img)
            inp = inp.to(self.device)
            # Check format
            if not inp.is_contiguous():
                inp = inp.contiguous()
            outputs = self.net(inp)" tabindex="0" role="button"><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"></path></svg></clipboard-copy><p dir="auto">差不多就这么多，仓库里我额外改了两个文件，只是为了修复一个 warming 的，不重要</p><hr class="simpread-hidden"><h3 dir="auto" id="sr-toc-16">4. 运行一个预热脚本，在这个环境提前存好所有的 MIOPEN conv2d 的 kernel 缓存，避免用的时候寻找。</h3><p dir="auto">抓取模型运行时的张量形状得到的问题形状，冷启动需要 1s 搜索的，就是后两个都是 32 的奇数次时：</p><markdown-accessiblity-table data-catalyst=""><table role="table"><thead><tr><th>序号</th><th>输入形状 (Shape)</th><th>Net Forward Time (ms)</th></tr></thead><tbody><tr><td>1</td><td>(1, 3, 544, 672)</td><td>1320.09</td></tr><tr><td>2</td><td>(1, 3, 416, 704)</td><td>1133.11</td></tr><tr><td>3</td><td>(1, 3, 288, 736)</td><td>982.78</td></tr><tr><td>4</td><td>(1, 3, 448, 736)</td><td>1202.01</td></tr><tr><td>5</td><td>(1, 3, 512, 672)</td><td>1236.20</td></tr><tr><td>6</td><td>(1, 3, 352, 736)</td><td>1076.65</td></tr><tr><td>7</td><td>(1, 3, 480, 672)</td><td>1207.67</td></tr><tr><td>8</td><td>(1, 3, 288, 544)</td><td>906.87</td></tr></tbody></table></markdown-accessiblity-table><p dir="auto">让 AI 帮我重新写了一个预热脚本，我自己是通过加载模型预热过的，但是每个人电脑模型存储位置可能不一样，那还是预热形状吧。建一个 cache_warmer.py 直接运行就行。</p><pre class="hljs python">import os
import argparse
import torch
import torch.nn as nn
import torch.nn.functional as F
from tqdm import tqdm

def get_args():
    parser = argparse.ArgumentParser(description="ROCm MIOpen Cache Warmer (No Model File Required)")
    parser.add_argument("--device", type=str, default="cuda", help="Device to run on")
    parser.add_argument("--max_side", type=int, default=960, help="Max image side length")
    parser.add_argument("--step", type=int, default=32, help="Step size for resolution grid")
    return parser.parse_args()

class MockOCRModel(nn.Module):
    """
    一个模拟 PP-OCR/DBNet 结构的代理模型。
    它不需要通过训练，包含了 MobileNetV3 和 DBHead 中涉及的所有关键卷积算子类型：
    1. Standard Conv 3x3, stride 1 &amp; 2
    2. Pointwise Conv 1x1
    3. Depthwise Conv 3x3
    4. Depthwise Conv 5x5 (MobileNetV3 特有)
    5. Upsampling / Fusion
    """
    def __init__(self, in_channels=3):
        super().__init__()
        
        # 1. Stem (Standard 3x3, stride 2)
        self.stem = nn.Conv2d(in_channels, 16, kernel_size=3, stride=2, padding=1)
        
        # 2. Depthwise Separable Blocks (模拟 MobileNetV3 的核心算子)
        # Block 1: 3x3 Depthwise
        self.dw_3x3 = nn.Conv2d(16, 16, kernel_size=3, stride=1, padding=1, groups=16)
        self.pw_1 = nn.Conv2d(16, 64, kernel_size=1, stride=1)
        
        # Block 2: 5x5 Depthwise (关键！很多缓存缺失是因为没覆盖 k=5)
        self.dw_5x5 = nn.Conv2d(64, 64, kernel_size=5, stride=2, padding=2, groups=64)
        self.pw_2 = nn.Conv2d(64, 128, kernel_size=1, stride=1)
        
        # Block 3: Larger stride/channel
        self.dw_3x3_s2 = nn.Conv2d(128, 128, kernel_size=3, stride=2, padding=1, groups=128)
        self.pw_3 = nn.Conv2d(128, 256, kernel_size=1, stride=1)

        # 3. Neck/Head (FPN + DBHead Simulation)
        # 模拟特征融合和输出层的 1x1 卷积与上采样
        self.out_conv = nn.Conv2d(256, 64, kernel_size=1)
        self.binarize_conv = nn.Conv2d(64, 1, kernel_size=3, stride=1, padding=1) # Standard 3x3 for head
        
        # 激活函数也会影响某些融合算子的编译
        self.act = nn.ReLU()

    def forward(self, x):
        # 模拟前向传播路径，确保所有算子被执行
        x = self.stem(x)
        x = self.act(x)
        
        x = self.dw_3x3(x)
        x = self.pw_1(x)
        
        x = self.dw_5x5(x)
        x = self.act(x)
        x = self.pw_2(x)
        
        x = self.dw_3x3_s2(x)
        x = self.pw_3(x)
        
        # 模拟 Head 部分的上采样和输出
        x = self.out_conv(x)
        x = F.interpolate(x, scale_factor=2, mode='bilinear', align_corners=True)
        x = self.binarize_conv(x)
        return x

def main():
    args = get_args()

    if not torch.cuda.is_available():
        print("Error: CUDA/ROCm is not available. This script requires a GPU.")
        return

    device = torch.device(args.device)
    
    print("="*80)
    print("ROCm MIOpen Cache Warmer (Standalone Version)")
    print("="*80)
    print("Initializing Proxy Model (matches PP-OCR architecture structure)...")
    
    # 初始化模型并放入 GPU (随机权重即可，不需要加载真实模型)
    model = MockOCRModel().to(device)
    model.eval()

    # 生成分辨率列表
    # PP-OCR 默认限制通常在 960 左右，且必须是 32 的倍数
    min_side = 64 # 这里的最小尺寸不需要太小，常用范围即可
    heights = range(min_side, args.max_side + 1, args.step)
    widths = range(min_side, args.max_side + 1, args.step)
    
    combinations = []
    for h in heights:
        for w in widths:
            combinations.append((h, w))

    print(f"Plan to warm up {len(combinations)} shape combinations...")
    print(f"Range: {min_side}x{min_side} to {args.max_side}x{args.max_side}, Step: {args.step}")

    # 开始预热
    pbar = tqdm(combinations)
    success_count = 0
    
    # 只需要做一次 forward 就可以触发编译
    with torch.no_grad():
        for h, w in pbar:
            pbar.set_description(f"Warming {h}x{w}")
            try:
                # 构造输入 Tensor (B=1, C=3, H, W)
                # 使用 float32，因为这是推理时的默认精度
                dummy_input = torch.zeros((1, 3, h, w), device=device, dtype=torch.float32)
                
                # 执行推理
                model(dummy_input)
                success_count += 1
                
            except RuntimeError as e:
                if "out of memory" in str(e):
                    pbar.write(f"Skipping {h}x{w} due to OOM")
                    torch.cuda.empty_cache()
                else:
                    pbar.write(f"Failed {h}x{w}: {e}")
            except Exception as e:
                pbar.write(f"Unexpected error at {h}x{w}: {e}")

    print("\n" + "="*80)
    print(f"WARMUP COMPLETE! ({success_count}/{len(combinations)} shapes processed)")
    print("MIOpen kernels for MobileNetV3/DBNet architectures have been cached.")
    print("Location: ~/.cache/miopen/ (or system default)")
    print("="*80)

if __name__ == "__main__":
    main()</pre><clipboard-copy aria-label="Copy code to clipboard" data-copy-feedback="Copied!" data-tooltip-direction="w" value="import os
import argparse
import torch
import torch.nn as nn
import torch.nn.functional as F
from tqdm import tqdm

def get_args():
    parser = argparse.ArgumentParser(description=&quot;ROCm MIOpen Cache Warmer (No Model File Required)&quot;)
    parser.add_argument(&quot;--device&quot;, type=str, default=&quot;cuda&quot;, help=&quot;Device to run on&quot;)
    parser.add_argument(&quot;--max_side&quot;, type=int, default=960, help=&quot;Max image side length&quot;)
    parser.add_argument(&quot;--step&quot;, type=int, default=32, help=&quot;Step size for resolution grid&quot;)
    return parser.parse_args()

class MockOCRModel(nn.Module):
    &quot;&quot;&quot;
    一个模拟 PP-OCR/DBNet 结构的代理模型。
    它不需要通过训练，包含了 MobileNetV3 和 DBHead 中涉及的所有关键卷积算子类型：
    1. Standard Conv 3x3, stride 1 &amp; 2
    2. Pointwise Conv 1x1
    3. Depthwise Conv 3x3
    4. Depthwise Conv 5x5 (MobileNetV3 特有)
    5. Upsampling / Fusion
    &quot;&quot;&quot;
    def __init__(self, in_channels=3):
        super().__init__()
        
        # 1. Stem (Standard 3x3, stride 2)
        self.stem = nn.Conv2d(in_channels, 16, kernel_size=3, stride=2, padding=1)
        
        # 2. Depthwise Separable Blocks (模拟 MobileNetV3 的核心算子)
        # Block 1: 3x3 Depthwise
        self.dw_3x3 = nn.Conv2d(16, 16, kernel_size=3, stride=1, padding=1, groups=16)
        self.pw_1 = nn.Conv2d(16, 64, kernel_size=1, stride=1)
        
        # Block 2: 5x5 Depthwise (关键！很多缓存缺失是因为没覆盖 k=5)
        self.dw_5x5 = nn.Conv2d(64, 64, kernel_size=5, stride=2, padding=2, groups=64)
        self.pw_2 = nn.Conv2d(64, 128, kernel_size=1, stride=1)
        
        # Block 3: Larger stride/channel
        self.dw_3x3_s2 = nn.Conv2d(128, 128, kernel_size=3, stride=2, padding=1, groups=128)
        self.pw_3 = nn.Conv2d(128, 256, kernel_size=1, stride=1)

        # 3. Neck/Head (FPN + DBHead Simulation)
        # 模拟特征融合和输出层的 1x1 卷积与上采样
        self.out_conv = nn.Conv2d(256, 64, kernel_size=1)
        self.binarize_conv = nn.Conv2d(64, 1, kernel_size=3, stride=1, padding=1) # Standard 3x3 for head
        
        # 激活函数也会影响某些融合算子的编译
        self.act = nn.ReLU()

    def forward(self, x):
        # 模拟前向传播路径，确保所有算子被执行
        x = self.stem(x)
        x = self.act(x)
        
        x = self.dw_3x3(x)
        x = self.pw_1(x)
        
        x = self.dw_5x5(x)
        x = self.act(x)
        x = self.pw_2(x)
        
        x = self.dw_3x3_s2(x)
        x = self.pw_3(x)
        
        # 模拟 Head 部分的上采样和输出
        x = self.out_conv(x)
        x = F.interpolate(x, scale_factor=2, mode='bilinear', align_corners=True)
        x = self.binarize_conv(x)
        return x

def main():
    args = get_args()

    if not torch.cuda.is_available():
        print(&quot;Error: CUDA/ROCm is not available. This script requires a GPU.&quot;)
        return

    device = torch.device(args.device)
    
    print(&quot;=&quot;*80)
    print(&quot;ROCm MIOpen Cache Warmer (Standalone Version)&quot;)
    print(&quot;=&quot;*80)
    print(&quot;Initializing Proxy Model (matches PP-OCR architecture structure)...&quot;)
    
    # 初始化模型并放入 GPU (随机权重即可，不需要加载真实模型)
    model = MockOCRModel().to(device)
    model.eval()

    # 生成分辨率列表
    # PP-OCR 默认限制通常在 960 左右，且必须是 32 的倍数
    min_side = 64 # 这里的最小尺寸不需要太小，常用范围即可
    heights = range(min_side, args.max_side + 1, args.step)
    widths = range(min_side, args.max_side + 1, args.step)
    
    combinations = []
    for h in heights:
        for w in widths:
            combinations.append((h, w))

    print(f&quot;Plan to warm up {len(combinations)} shape combinations...&quot;)
    print(f&quot;Range: {min_side}x{min_side} to {args.max_side}x{args.max_side}, Step: {args.step}&quot;)

    # 开始预热
    pbar = tqdm(combinations)
    success_count = 0
    
    # 只需要做一次 forward 就可以触发编译
    with torch.no_grad():
        for h, w in pbar:
            pbar.set_description(f&quot;Warming {h}x{w}&quot;)
            try:
                # 构造输入 Tensor (B=1, C=3, H, W)
                # 使用 float32，因为这是推理时的默认精度
                dummy_input = torch.zeros((1, 3, h, w), device=device, dtype=torch.float32)
                
                # 执行推理
                model(dummy_input)
                success_count += 1
                
            except RuntimeError as e:
                if &quot;out of memory&quot; in str(e):
                    pbar.write(f&quot;Skipping {h}x{w} due to OOM&quot;)
                    torch.cuda.empty_cache()
                else:
                    pbar.write(f&quot;Failed {h}x{w}: {e}&quot;)
            except Exception as e:
                pbar.write(f&quot;Unexpected error at {h}x{w}: {e}&quot;)

    print(&quot;\n&quot; + &quot;=&quot;*80)
    print(f&quot;WARMUP COMPLETE! ({success_count}/{len(combinations)} shapes processed)&quot;)
    print(&quot;MIOpen kernels for MobileNetV3/DBNet architectures have been cached.&quot;)
    print(&quot;Location: ~/.cache/miopen/ (or system default)&quot;)
    print(&quot;=&quot;*80)

if __name__ == &quot;__main__&quot;:
    main()" tabindex="0" role="button"><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"></path></svg></clipboard-copy><hr class="simpread-hidden"><h3 dir="auto" id="sr-toc-17">5.<strong> 最后整三个环境变量后愉快玩耍即可</strong></h3><pre class="hljs bash">export MINERU_MODEL_SOURCE=modelscope
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
export FLASH_ATTENTION_TRITON_AMD_ENABLE="TRUE"  #使用时也需要，否则flash_attn不识别
mineru-gradio --server-name 0.0.0.0 --server-port 7860</pre><clipboard-copy aria-label="Copy code to clipboard" data-copy-feedback="Copied!" data-tooltip-direction="w" value="export MINERU_MODEL_SOURCE=modelscope
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=&quot;TRUE&quot;  #使用时也需要，否则flash_attn不识别
mineru-gradio --server-name 0.0.0.0 --server-port 7860 " tabindex="0" role="button"><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"></path></svg></clipboard-copy><hr class="simpread-hidden"><h3 dir="auto" id="sr-toc-18">6. 运行结果</h3><pre class="hljs apache">Layout Predict: 100%|█████████████████████████████████| 200/200 [00:10&lt;00:00, 18.81it/s]
MFD Predict: 100%|██████████████████████████████████| 200/200 [00:09&lt;00:00, 21.82it/s]
MFR Predict: 100%|██████████████████████████████████| 430/430 [00:04&lt;00:00, 106.36it/s]
Table-ocr det: 100%|█████████████████████████████████| 142/142 [00:01&lt;00:00, 127.44it/s]
Table-ocr rec ch: 100%|███████████████████████████████| 881/881 [00:02&lt;00:00, 409.11it/s]
Table-wireless Predict: 100%|████████████████████████████| 141/141 [00:01&lt;00:00, 71.38it/s]
Table-wired Predict: 100%|████████████████████████████| 117/117 [00:03&lt;00:00, 30.32it/s]
OCR-det Predict: 100%|██████████████████████████████| 200/200 [00:14&lt;00:00, 14.22it/s]
Processing pages: 100%|█████████████████████████████| 200/200 [00:08&lt;00:00, 24.86it/s]
OCR-rec Predict: 100%|██████████████████████████████| 20/20 [00:00&lt;00:00, 422.94it/s]</pre><clipboard-copy aria-label="Copy code to clipboard" data-copy-feedback="Copied!" data-tooltip-direction="w" value="Layout Predict: 100%|█████████████████████████████████| 200/200 [00:10<00:00, 18.81it/s]
MFD Predict: 100%|██████████████████████████████████| 200/200 [00:09<00:00, 21.82it/s]
MFR Predict: 100%|██████████████████████████████████| 430/430 [00:04<00:00, 106.36it/s]
Table-ocr det: 100%|█████████████████████████████████| 142/142 [00:01<00:00, 127.44it/s]
Table-ocr rec ch: 100%|███████████████████████████████| 881/881 [00:02<00:00, 409.11it/s]
Table-wireless Predict: 100%|████████████████████████████| 141/141 [00:01<00:00, 71.38it/s]
Table-wired Predict: 100%|████████████████████████████| 117/117 [00:03<00:00, 30.32it/s]
OCR-det Predict: 100%|██████████████████████████████| 200/200 [00:14<00:00, 14.22it/s]
Processing pages: 100%|█████████████████████████████| 200/200 [00:08<00:00, 24.86it/s]
OCR-rec Predict: 100%|██████████████████████████████| 20/20 [00:00<00:00, 422.94it/s]" tabindex="0" role="button"><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"></path></svg></clipboard-copy><p dir="auto">下面 vllm 的 PDF 来自 <a href="https://github.com/krahets/hello-algo/releases/tag/1.3.0">https://github.com/krahets/hello-algo/releases/tag/1.3.0</a> 中文 python 版</p><pre class="hljs cs">mineru.utils.engine_utils:get_vlm_engine:32 - Using vllm-async-engine as the inference engine for VLM.
Two Step Extraction: 100%|█████████████████████████████| 348/348 [02:53&lt;00:00,  2.01it/s]</pre><clipboard-copy aria-label="Copy code to clipboard" data-copy-feedback="Copied!" data-tooltip-direction="w" value="mineru.utils.engine_utils:get_vlm_engine:32 - Using vllm-async-engine as the inference engine for VLM.
Two Step Extraction: 100%|█████████████████████████████| 348/348 [02:53<00:00,  2.01it/s]" tabindex="0" role="button"><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg><svg aria-hidden="true" data-component="Octicon" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"></path></svg></clipboard-copy><hr class="simpread-hidden"><p dir="auto">PS：mineru 保存的 jpg 图片很不清晰，并且命名也不是序号来的，我自用版本改成了 webp 格式图片，并且按照真实顺序保存的，方便使用，300dpi 压缩 95% 的 webp 图像就非常清晰了，而且每张图体积也非常小。所以其实推荐使用这个格式来保存图片。</p></td></tr></tbody></table>

Beta Was this translation helpful? [Give feedback.](#)

3 You must be logged in to vote All reactions

Replies: 4 comments · 8 replies
-------------------------------

*   [Oldest](/opendatalab/MinerU/discussions/3662?sort=old)
*   [Newest](/opendatalab/MinerU/discussions/3662?sort=new)
*   [Top](/opendatalab/MinerU/discussions/3662?sort=top)

Comment options

### Uh oh!

There was an error while loading. Please reload this page.

Quote reply

###  [![](https://avatars.githubusercontent.com/u/99164808?s=64&v=4) tinafengfun](/tinafengfun) [Nov 23, 2025](#discussioncomment-15050131) 

-

<table role="presentation" data-paste-markdown-skip=""><tbody data-target-translation-id="15050131" data-target-translation-type="comment"><tr><td><p dir="auto">非常赞的 patch，能详细说说为啥 7900 要这样手动调的原因？--- 针对 7900xtx 的手动调优配置，其他 GPU 的最优组合可能需要自行寻找，AMD 的 autotune 效果就是没有效果</p></td></tr></tbody></table>

Beta Was this translation helpful? [Give feedback.](#)

1 You must be logged in to vote All reactions

6 replies

   Show 1 previous reply 

[![](https://avatars.githubusercontent.com/u/58244022?s=60&v=4)](/healy-hub)

Comment options

### Uh oh!

There was an error while loading. Please reload this page.

Quote reply

#### [healy-hub](/healy-hub) [Jan 26, 2026](#discussioncomment-15602671) Author

-

<table role="presentation" data-paste-markdown-skip=""><tbody data-target-translation-id="15602671" data-target-translation-type="comment"><tr><td><blockquote><p dir="auto">非常赞的 patch，能详细说说为啥 7900 要这样手动调的原因？--- 针对 7900xtx 的手动调优配置，其他 GPU 的最优组合可能需要自行寻找，AMD 的 autotune 效果就是没有效果</p></blockquote><p dir="auto">这个 triton 实现比较麻烦，我放弃了 triton 有一个优雅点的通解了，回头整理一下更新，现在还很混乱。AMD 的 vllm 要么 docker，要么自行编译，感觉没法写一个 pr 合并进这个仓库。但是 pipeline 后端的加速方案，我猜国产基于 rocm 改的 GPU 可以参考。</p></td></tr></tbody></table>

Beta Was this translation helpful? [Give feedback.](#)

All reactions

[![](https://avatars.githubusercontent.com/u/11393164?s=60&v=4)](/myhloli)

Comment options

### Uh oh!

There was an error while loading. Please reload this page.

Quote reply

#### [myhloli](/myhloli) [Jan 26, 2026](#discussioncomment-15604645) Maintainer

-

<table role="presentation" data-paste-markdown-skip=""><tbody data-target-translation-id="15604645" data-target-translation-type="comment"><tr><td><blockquote><blockquote><p dir="auto">非常赞的 patch，能详细说说为啥 7900 要这样手动调的原因？--- 针对 7900xtx 的手动调优配置，其他 GPU 的最优组合可能需要自行寻找，AMD 的 autotune 效果就是没有效果</p></blockquote><p dir="auto">这个 triton 实现比较麻烦，我放弃了 triton 有一个优雅点的通解了，回头整理一下更新，现在还很混乱。AMD 的 vllm 要么 docker，要么自行编译，感觉没法写一个 pr 合并进这个仓库。但是 pipeline 后端的加速方案，我猜国产基于 rocm 改的 GPU 可以参考。</p></blockquote><p dir="auto">我们在国产的海光 dcu 上进行过测试，没有遇到 amd 上这么明显的性能 bug，速度比较符合预期。</p></td></tr></tbody></table>

Beta Was this translation helpful? [Give feedback.](#)

All reactions

[![](https://avatars.githubusercontent.com/u/58244022?s=60&v=4)](/healy-hub)

Comment options

### Uh oh!

There was an error while loading. Please reload this page.

Quote reply

#### [healy-hub](/healy-hub) [Jan 26, 2026](#discussioncomment-15604733) Author

-

<table role="presentation" data-paste-markdown-skip=""><tbody data-target-translation-id="15604733" data-target-translation-type="comment"><tr><td><blockquote><blockquote><blockquote><p dir="auto">非常赞的 patch，能详细说说为啥 7900 要这样手动调的原因？--- 针对 7900xtx 的手动调优配置，其他 GPU 的最优组合可能需要自行寻找，AMD 的 autotune 效果就是没有效果</p></blockquote><p dir="auto">这个 triton 实现比较麻烦，我放弃了 triton 有一个优雅点的通解了，回头整理一下更新，现在还很混乱。AMD 的 vllm 要么 docker，要么自行编译，感觉没法写一个 pr 合并进这个仓库。但是 pipeline 后端的加速方案，我猜国产基于 rocm 改的 GPU 可以参考。</p></blockquote><p dir="auto">我们在国产的海光 dcu 上进行过测试，没有遇到 amd 上这么明显的性能 bug，速度比较符合预期。</p></blockquote><p dir="auto">原来如此，看来他们应该用的有 tensor 的 CDNA 架构，就没什么问题。消费级 AMD 这边用的 RDNA 架构，真的一言难尽，很多算子支持都有奇葩回退，一个超大尺寸的 conv3d 能寻找 12s 的 kernel，空洞卷积每次找 1s，conv2d 出现双 32 的奇数倍丢失 kernel。。。。我做了一些改动，新的教程我需要整理一下再发在评论区。另外用户 patch 其实比较麻烦，我考虑做一个仓库方便大家。</p></td></tr></tbody></table>

Beta Was this translation helpful? [Give feedback.](#)

All reactions

[![](https://avatars.githubusercontent.com/u/99164808?s=60&v=4)](/tinafengfun)

Comment options

### Uh oh!

There was an error while loading. Please reload this page.

Quote reply

#### [tinafengfun](/tinafengfun) [Jan 27, 2026](#discussioncomment-15612849)

-

<table role="presentation" data-paste-markdown-skip=""><tbody data-target-translation-id="15612849" data-target-translation-type="comment"><tr><td><p dir="auto">可以试试 flag gemm 那边搞的一个自动生成 triton 的项目，<a href="https://github.com/flagos-ai/KernelGen">https://github.com/flagos-ai/KernelGen</a> 不知道怎么样，再手工调调看。 哎，手搓真的不容易，心痛各位一下下。最近工程界弄了不少 ai 生成 kernel 的项目，可能能解决点痛点。</p></td></tr></tbody></table>

Beta Was this translation helpful? [Give feedback.](#)

All reactions

[![](https://avatars.githubusercontent.com/u/58244022?s=60&v=4)](/healy-hub)

Comment options

### Uh oh!

There was an error while loading. Please reload this page.

Quote reply

#### [healy-hub](/healy-hub) [Jan 27, 2026](#discussioncomment-15612913) Author

-

<table role="presentation" data-paste-markdown-skip=""><tbody data-target-translation-id="15612913" data-target-translation-type="comment"><tr><td><blockquote><p dir="auto">可以试试 flag gemm 那边搞的一个自动生成 triton 的项目，<a href="https://github.com/flagos-ai/KernelGen">https://github.com/flagos-ai/KernelGen</a> 不知道怎么样，再手工调调看。 哎，手搓真的不容易，心痛各位一下下。最近工程界弄了不少 ai 生成 kernel 的项目，可能能解决点痛点。</p></blockquote><p dir="auto">可以的，谢谢，我学习了解一下。<br>这个项目的适配我暂时放弃 Triton 了，空洞卷积那个可以直接填充到标准卷积，OCR 批处理不满足 6 batch 的也填充到到 6patch，避免任何非官方 kernel 的寻找，速度就挺快的。我正在整理文档，为了测试改动的位置有点混乱。。。<br>目前 vllm 大概在 1.84-2.01it/s（300 页的编程 pdf 测试），pipeline 后端的 ocr 也可以到几百 it/s 了。</p></td></tr></tbody></table>

Beta Was this translation helpful? [Give feedback.](#)

All reactions

Comment options

### Uh oh!

There was an error while loading. Please reload this page.

Quote reply

###  [![](https://avatars.githubusercontent.com/u/72428523?s=64&v=4) ChenxiWu-Lab](/ChenxiWu-Lab) [Jan 31, 2026](#discussioncomment-15656143) 

-

<table role="presentation" data-paste-markdown-skip=""><tbody data-target-translation-id="15656143" data-target-translation-type="comment"><tr><td><p dir="auto">大佬啥时候更新呀~</p></td></tr></tbody></table>

Beta Was this translation helpful? [Give feedback.](#)

1 You must be logged in to vote All reactions

2 replies [![](https://avatars.githubusercontent.com/u/58244022?s=60&v=4)](/healy-hub)

Comment options

### Uh oh!

There was an error while loading. Please reload this page.

Quote reply

#### [healy-hub](/healy-hub) [Jan 31, 2026](#discussioncomment-15656881) Author

-

<table role="presentation" data-paste-markdown-skip=""><tbody data-target-translation-id="15656881" data-target-translation-type="comment"><tr><td><blockquote><p dir="auto">大佬啥时候更新呀~</p></blockquote><p dir="auto">稍等，下午或者晚上应该就发了，这几天事情太多了</p></td></tr></tbody></table>

Beta Was this translation helpful? [Give feedback.](#)

All reactions

[![](https://avatars.githubusercontent.com/u/58244022?s=60&v=4)](/healy-hub)

Comment options

### Uh oh!

There was an error while loading. Please reload this page.

Quote reply

#### [healy-hub](/healy-hub) [Jan 31, 2026](#discussioncomment-15658222) Author

-

<table role="presentation" data-paste-markdown-skip=""><tbody data-target-translation-id="15658222" data-target-translation-type="comment"><tr><td><blockquote><p dir="auto">大佬啥时候更新呀~</p></blockquote><p dir="auto">已更新</p></td></tr></tbody></table>

Beta Was this translation helpful? [Give feedback.](#)

👍 1 All reactions

*   👍 1

Comment options

### Uh oh!

There was an error while loading. Please reload this page.

Quote reply

###  [![](https://avatars.githubusercontent.com/u/2101082?s=64&v=4) vjeson](/vjeson) [Apr 3, 2026](#discussioncomment-16432254) 

-

<table role="presentation" data-paste-markdown-skip=""><tbody data-target-translation-id="16432254" data-target-translation-type="comment"><tr><td><p dir="auto">大佬是否支持 mineru 3.x 版本？</p></td></tr></tbody></table>

Beta Was this translation helpful? [Give feedback.](#)

1 You must be logged in to vote All reactions

0 replies

Comment options

### Uh oh!

There was an error while loading. Please reload this page.

Quote reply

###  [![](https://avatars.githubusercontent.com/u/99164808?s=64&v=4) tinafengfun](/tinafengfun) [Apr 3, 2026](#discussioncomment-16435523) 

-

<table role="presentation" data-paste-markdown-skip=""><tbody data-target-translation-id="16435523" data-target-translation-type="comment"><tr><td><p dir="auto">有兴趣去参加 AMD 的模型优化比赛吗？用上 AI 会更厉害，大牛加油，可以转奖金呀 <a href="https://marketing.csdn.net/questions/Q2603192021352912290?utm_source=dx&amp;utm_medium=distribute.app_sms.1093755.nonecase&amp;csdn_tiny_tail=%7B%22ext%22%3A%221c4f62c151001033%22,%22phone%22%3A%2213466334563%22,%22distribute_task_id%22%3A%221093755%22,%22taskId%22%3A%221093755%22,%22smsOperator%22%3A%22mengwang%22%7D%EF%BC%8C" rel="nofollow">https://marketing.csdn.net/questions/Q2603192021352912290?utm_source=dx&amp;utm_medium=distribute.app_sms.1093755.nonecase&amp;csdn_tiny_tail=%7B%22ext%22%3A%221c4f62c151001033%22,%22phone%22%3A%2213466334563%22,%22distribute_task_id%22%3A%221093755%22,%22taskId%22%3A%221093755%22,%22smsOperator%22%3A%22mengwang%22%7D，</a> 我不是广告，我是在做 AI 算子优化的同学</p></td></tr></tbody></table>

Beta Was this translation helpful? [Give feedback.](#)

1 You must be logged in to vote All reactions

0 replies

 

[Sign up for free](/join?source=comment-repo) **to join this conversation on GitHub**. Already have an account? [Sign in to comment](/login?return_to=https%3A%2F%2Fgithub.com%2Fopendatalab%2FMinerU%2Fdiscussions%2F3662)