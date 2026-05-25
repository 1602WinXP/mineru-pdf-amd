# MinerU NVIDIA GPU 云端部署教程

> 适用于 Ubuntu + NVIDIA GPU (A10/A100/4090 等) 的远程服务器部署
> 与 AMD RX 9070 本地部署可对照参考 [MinerU本地部署教程.md](MinerU本地部署教程.md)

---

## 一、环境要求

| 项目 | 要求 |
|------|------|
| GPU | NVIDIA Volta 架构及以上（A10/A100/4090 等），显存 ≥ 8GB |
| CUDA | ≥ 12.4 |
| 系统 | Ubuntu 20.04 / 22.04 / 24.04 |
| 磁盘 | ≥ 30GB（模型约 2.5GB + 虚拟环境约 10GB） |

通过 `nvidia-smi` 确认 GPU 可见：

```bash
nvidia-smi
# 应显示 GPU 型号、CUDA 版本、显存信息
```

---

## 二、部署步骤

### 2.1 创建虚拟环境

```bash
python3 -m venv ~/mineru_env
source ~/mineru_env/bin/activate
```

### 2.2 安装 PyTorch（CUDA 版）

```bash
# CUDA 12.4 版
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124

# 验证
python -c "import torch; print('GPU:', torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

### 2.3 安装 MinerU

NVIDIA 环境下 `mineru[all]` 可直接安装（已包含 vllm）：

```bash
pip install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple
pip install uv -i https://mirrors.aliyun.com/pypi/simple
uv pip install -U "mineru[all]" -i https://mirrors.aliyun.com/pypi/simple
```

> NVIDIA 环境下 `uv pip` 是安全的——官方推荐方式，vllm 可直接从 PyPI 安装 CUDA 版 wheel。

### 2.4 配置模型源（国内服务器建议用 ModelScope）

```bash
echo 'export MINERU_MODEL_SOURCE=modelscope' >> ~/.bashrc
source ~/.bashrc
source ~/mineru_env/bin/activate   # source .bashrc 后需重新激活
```

如果服务器在海外，默认 HuggingFace 更快，无需此步。

---

## 三、启动服务

### 3.1 后台启动 API（推荐）

```bash
source ~/mineru_env/bin/activate

# 有公网 IPv4 时
nohup mineru-api --host 0.0.0.0 --port 8000 --enable-vlm-preload true \
    > ~/mineru_api.log 2>&1 &

# 只有公网 IPv6 时（很多国内云服务器默认只给 IPv6）
nohup mineru-api --host :: --port 8000 --enable-vlm-preload true \
    > ~/mineru_api.log 2>&1 &
```

> `--host ::` 同时监听 IPv4 和 IPv6。客户端用 `http://[<ipv6地址>]:8000` 访问。

# 查看启动日志
tail -f ~/mineru_api.log
# 看到 "Uvicorn running on http://0.0.0.0:8000" 即启动完成
# 按 Ctrl+C 退出日志查看（不关闭服务）
```

### 3.2 启动 WebUI

```bash
source ~/mineru_env/bin/activate
nohup mineru-gradio --server-name 0.0.0.0 --server-port 7860 --enable-vlm-preload true \
    > ~/mineru_gradio.log 2>&1 &
```

浏览器访问：`http://<服务器公网IP>:7860`

### 3.3 停止服务

```bash
pkill -f mineru-api
pkill -f mineru-gradio
```

---

## 四、调用 API

### 4.1 用项目自带的客户端（推荐）

```bash
# 本地服务器
uv run mineru_api_client.py example.pdf --base-url http://127.0.0.1:8000

# 远程服务器（从本地电脑调用）
uv run mineru_api_client.py example.pdf --base-url http://<服务器公网IP>:8000

# 返回完整输出（对标官网 API zip 内容）
uv run mineru_api_client.py example.pdf --base-url http://127.0.0.1:8000 --full
```

### 4.2 curl 快速测试

```bash
# 提交异步任务
curl -X POST http://127.0.0.1:8000/tasks \
  -F "files=@example.pdf;type=application/pdf" \
  -F "backend=hybrid-auto-engine" \
  -F "response_format_zip=true" \
  -F "return_md=true" \
  -F "lang_list=ch"

# 返回 {"task_id": "xxx", "status": "pending", ...}

# 查询状态
curl http://127.0.0.1:8000/tasks/<task_id>

# 下载结果 zip
curl -o result.zip http://127.0.0.1:8000/tasks/<task_id>/result
```

### 4.3 Python 代码调用

```python
import time, requests

API = "http://127.0.0.1:8000"

# 提交
with open("example.pdf", "rb") as f:
    resp = requests.post(f"{API}/tasks",
        files={"files": ("example.pdf", f, "application/pdf")},
        data={"backend": "hybrid-auto-engine", "lang_list": "ch",
              "response_format_zip": "true", "return_md": "true"})

task_id = resp.json()["task_id"]

# 轮询
while True:
    s = requests.get(f"{API}/tasks/{task_id}").json()
    if s["status"] == "completed": break
    if s["status"] == "failed": raise RuntimeError(s.get("error"))
    time.sleep(3)

# 下载 zip
with open(f"{task_id}.zip", "wb") as f:
    f.write(requests.get(f"{API}/tasks/{task_id}/result").content)
print("Done")
```

> `POST /file_parse` 是同步接口——等待完成后直接返回结果。但 zip 下载场景推荐用 `POST /tasks` 异步+轮询，可控性更好。

---

## 五、GPU 监控

```bash
# 实时查看 GPU 使用情况
watch -n 1 nvidia-smi

# 或只看显存
nvidia-smi --query-gpu=memory.used,memory.total --format=csv
```

---

## 六、环境变量参考

```bash
MINERU_MODEL_SOURCE=modelscope   # 模型源（huggingface / modelscope / local）
MINERU_API_MAX_CONCURRENT_REQUESTS=3  # 最大并发（A10 24GB 可设 3，显存不足降为 1）
MINERU_PROCESSING_WINDOW_SIZE=64     # 处理窗口大小，大文档可调大
MINERU_PDF_RENDER_THREADS=4          # PDF 渲染线程数
```

写入 `~/.bashrc` 持久化：

```bash
echo 'export MINERU_MODEL_SOURCE=modelscope' >> ~/.bashrc
echo 'export MINERU_API_MAX_CONCURRENT_REQUESTS=2' >> ~/.bashrc
```

---

## 七、与 AMD 本地部署的关键差异

| 项目 | NVIDIA（本文） | AMD RX 9070（本地教程） |
|------|--------------|---------------------|
| vllm 安装 | `mineru[all]` 一键安装 | 必须从源码编译 |
| PyTorch | `pip install torch --index-url cu124` | `pip install torch==2.11.0+rocm7.1 --index-url rocm7.1` |
| 平台检测 | 原生支持，无需 patch | 需 patch vllm 两个文件 |
| MIOpen 预热 | 不需要 | 建议运行 cache_warmer.py |
| cuDNN vs MIOpen | cuDNN 优化更成熟 | MIOpen 有冷启动问题 |
| 安装复杂度 | ~10 分钟 | ~2 小时（含 vllm 编译） |
| **输出质量** | **相同** | **相同**（同为 hybrid-auto-engine + 同一 VLM 模型） |

---

*最后更新: 2026-05-25*
