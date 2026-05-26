# MinerU 本地使用指南

> 如何在 Windows 上启动 MinerU 服务（CLI / WebUI / API），以及如何从局域网或公网远程调用。输出对标官网精准解析 API 的 zip 包。

---

## 一、快速启动（从 Windows 终端）

### 1.1 一键进入 WSL 环境

在 Windows PowerShell 或终端中：

```powershell
wsl -d Ubuntu-22.04
```

进入后激活环境：

```bash
cd ~/mineru_stable && . .venv/bin/activate
export HSA_ENABLE_DXG_DETECTION=1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE
export MINERU_MODEL_SOURCE=huggingface
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
```

> 这些环境变量已写入 `~/.bashrc`，新终端会自动加载。

### 1.2 四种使用方式

| 方式 | 命令 | 适用场景 |
|------|------|---------|
| CLI 命令行 | `mineru -p <文件> -o <输出>` | 批量处理、脚本集成 |
| WebUI 界面 | `mineru-gradio --server-name 0.0.0.0` | 拖拽上传、可视化 |
| API 服务 | `mineru-api --host 0.0.0.0` | 程序调用、远程访问 |
| OpenAI 兼容 | `mineru-openai-server --port 30000` | 接入 OpenAI 协议生态 |

---

## 二、CLI 命令行

### 2.1 基本用法

```bash
cd ~/mineru_stable && . .venv/bin/activate
export HSA_ENABLE_DXG_DETECTION=1 FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE MINERU_MODEL_SOURCE=huggingface

# 解析单个 PDF（hybrid-auto-engine，质量最高）
mineru -p /path/to/input.pdf -o /path/to/output -b hybrid-auto-engine

# 解析整个目录
mineru -p /path/to/docs/ -o /path/to/output -b hybrid-auto-engine

# 中文文档指定语言（提升 OCR 精度）
mineru -p input.pdf -o output -b hybrid-auto-engine -l ch
```

### 2.2 从 Windows 直接调用

在 Windows PowerShell 中一行搞定：

```powershell
wsl -d Ubuntu-22.04 -- bash -c "cd ~/mineru_stable && . .venv/bin/activate && export HSA_ENABLE_DXG_DETECTION=1 MINERU_MODEL_SOURCE=huggingface && mineru -p ~/input.pdf -o ~/output -b hybrid-auto-engine"
```

### 2.3 输出文件

解析完成后，`output_dir/<文件名>/hybrid_auto/` 下包含：

| 文件 | 说明 |
|------|------|
| `<name>.md` | Markdown 正文（可直接阅读） |
| `<name>_content_list.json` | 结构化内容列表 |
| `<name>_middle.json` | 中间处理结果 |
| `<name>_model.json` | 模型原始输出 |
| `<name>_layout.pdf` | 版面分析标注 |
| `images/` | 提取的图片 |

---

## 三、WebUI（图形界面）

### 3.1 启动

```bash
cd ~/mineru_stable && . .venv/bin/activate
export HSA_ENABLE_DXG_DETECTION=1 FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE MINERU_MODEL_SOURCE=huggingface

mineru-gradio --server-name 0.0.0.0 --server-port 7860

# 启动时预加载 VLM 模型（可选，避免首次请求等待）
mineru-gradio --server-name 0.0.0.0 --server-port 7860 --enable-vlm-preload true
```

### 3.2 访问

浏览器打开 `http://localhost:7860`，拖拽 PDF 即可解析。

> WSL2 的端口会自动转发到 Windows 的 localhost，无需额外配置。

---

## 四、OpenAI 兼容服务器

如果已有 vllm 环境，可以启动 OpenAI 兼容 API：

```bash
cd ~/mineru_stable && . .venv/bin/activate
export HSA_ENABLE_DXG_DETECTION=1 FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE MINERU_MODEL_SOURCE=huggingface

# 启动 OpenAI 兼容服务器
mineru-openai-server --port 30000
```

然后用 http-client 模式调用：

```bash
mineru -p input.pdf -o output -b hybrid-http-client -u http://127.0.0.1:30000
```

---

## 五、API 服务

### 5.1 启动 API 服务

```bash
cd ~/mineru_stable && . .venv/bin/activate
export HSA_ENABLE_DXG_DETECTION=1 FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE MINERU_MODEL_SOURCE=huggingface

# 基础启动
mineru-api --host 0.0.0.0 --port 8000

# 启动时预加载 VLM 模型（推荐，避免首次请求等待 ~46s）
mineru-api --host 0.0.0.0 --port 8000 --enable-vlm-preload true
```

启动后：
- API 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

### 5.2 API 端点一览

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/file_parse` | 同步解析，等待完成后直接返回结果 |
| `POST` | `/tasks` | 异步提交任务，返回 task_id |
| `GET` | `/tasks/{task_id}` | 查询任务状态 |
| `GET` | `/tasks/{task_id}/result` | 获取解析结果（支持 zip） |
| `GET` | `/health` | 健康检查 |

### 5.3 调用示例：异步任务 + 获取 zip 包（对标官网精准解析 API）

#### 步骤 1：提交解析任务

```python
import requests

# ===== 本地 API 地址 =====
BASE_URL = "http://localhost:8000"

# ===== 方式 A：上传本地文件 =====
with open("example.pdf", "rb") as f:
    resp = requests.post(
        f"{BASE_URL}/tasks",
        files={"files": ("example.pdf", f, "application/pdf")},
        data={
            "backend": "hybrid-auto-engine",  # 最高精度
            "parse_method": "auto",
            "lang_list": "ch",                 # 中文文档
            "response_format_zip": True,       # 返回 zip 包
            "return_md": True,
            "return_content_list": True,
            "return_images": True,
        },
    )

# ===== 方式 B：提交公网 URL =====
resp = requests.post(
    f"{BASE_URL}/tasks",
    data={
        "server_url": "https://example.com/document.pdf",
        "backend": "hybrid-auto-engine",
        "response_format_zip": True,
        "return_md": True,
        "return_content_list": True,
        "return_images": True,
    },
)

task = resp.json()
task_id = task["task_id"]  # 响应是扁平 JSON，task_id 在根级
print(f"任务已提交: {task_id}")
```

#### 步骤 2：轮询任务状态

```python
import time

while True:
    status_resp = requests.get(f"{BASE_URL}/tasks/{task_id}")
    status = status_resp.json()
    task_status = status["status"]  # 扁平 JSON

    if task_status == "completed":
        print("解析完成！")
        break
    elif task_status == "failed":
        print(f"解析失败: {status.get('error', '未知错误')}")
        exit(1)
    else:
        print(f"状态: {task_status}，等待中...")
        time.sleep(3)
```

#### 步骤 3：下载 zip 结果

```python
result = requests.get(f"{BASE_URL}/tasks/{task_id}/result")

# 保存 zip 文件
with open(f"{task_id}.zip", "wb") as f:
    f.write(result.content)

print(f"结果已保存: {task_id}.zip")
```

#### 完整脚本

```python
"""
MinerU 本地 API 调用脚本
对标官网 https://mineru.net/api/v4/extract/task 的行为
"""
import time
import requests

BASE_URL = "http://localhost:8000"

def parse_pdf(file_path: str, lang: str = "ch") -> str:
    """解析 PDF 并返回 zip 文件路径"""
    # 1. 提交任务
    with open(file_path, "rb") as f:
        resp = requests.post(
            f"{BASE_URL}/tasks",
            files={"files": (file_path, f, "application/pdf")},
            data={
                "backend": "hybrid-auto-engine",
                "parse_method": "auto",
                "lang_list": lang,
                "response_format_zip": "true",
                "return_md": "true",
                "return_content_list": "true",
                "return_images": "true",
            },
        )
    task = resp.json()
    task_id = task["task_id"]
    print(f"[{task_id}] 任务已提交")

    # 2. 轮询等待
    while True:
        status = requests.get(f"{BASE_URL}/tasks/{task_id}").json()
        s = status["status"]
        if s == "completed":
            break
        elif s == "failed":
            raise RuntimeError(f"解析失败: {status.get('error', '未知错误')}")
        print(f"[{task_id}] {s}...")
        time.sleep(3)

    # 3. 下载 zip
    result = requests.get(f"{BASE_URL}/tasks/{task_id}/result")
    zip_path = f"{task_id}.zip"
    with open(zip_path, "wb") as f:
        f.write(result.content)
    print(f"[{task_id}] 完成 → {zip_path}")
    return zip_path


if __name__ == "__main__":
    parse_pdf("example.pdf")
```

### 5.4 curl 调用示例

```bash
# 提交任务（上传文件）
curl -X POST http://localhost:8000/tasks \
  -F "files=@example.pdf;type=application/pdf" \
  -F "backend=hybrid-auto-engine" \
  -F "response_format_zip=true" \
  -F "return_md=true" \
  -F "return_images=true" \
  -F "lang_list=ch"

# 返回示例:
# {"task_id":"a6e47eff-da08-4163-9520-05f0339aab4f", "status": "pending", "message": "Task submitted successfully"}

# 查询状态
curl http://localhost:8000/tasks/a6e47eff-da08-4163-9520-05f0339aab4f

# 下载结果
curl -o result.zip http://localhost:8000/tasks/a6e47eff-da08-4163-9520-05f0339aab4f/result
```

### 5.5 请求参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `files` | file | 是* | 上传文件（与 server_url 二选一） |
| `server_url` | string | 是* | 公网文件 URL（与 files 二选一） |
| `backend` | string | 否 | `hybrid-auto-engine`（默认，最高精度）/ `vlm-auto-engine` / `pipeline` |
| `parse_method` | string | 否 | `auto`（默认）/ `txt` / `ocr` |
| `lang_list` | string | 否 | 语言代码：`ch`/`en`/`japan`/`korean` 等 |
| `response_format_zip` | bool | 否 | 设为 `true` 返回 zip 包（对标官网 API） |
| `return_md` | bool | 否 | 返回 Markdown |
| `return_content_list` | bool | 否 | 返回结构化 JSON |
| `return_images` | bool | 否 | 返回提取的图片 |
| `return_middle_json` | bool | 否 | 返回中间处理 JSON |
| `return_model_output` | bool | 否 | 返回模型原始输出 |
| `start_page_id` | int | 否 | 起始页（0-based） |
| `end_page_id` | int | 否 | 结束页 |
| `formula_enable` | bool | 否 | 启用公式识别 |
| `table_enable` | bool | 否 | 启用表格识别 |

---

## 六、局域网内其他电脑访问

WSL2 默认使用 NAT 网络，只有 Windows 本机可以通过 `localhost` 访问。局域网内其他设备需要额外配置。

### 6.1 方案 A：Windows 端口转发（推荐）

在 **Windows PowerShell（管理员）** 中：

```powershell
# 添加端口转发规则
# 把本机 8000 端口的流量转发到 WSL2
netsh interface portproxy add v4tov4 `
    listenport=8000 `
    listenaddress=0.0.0.0 `
    connectport=8000 `
    connectaddress=(wsl -d Ubuntu-22.04 -- bash -c "hostname -I | awk '{print \$1}'")

# 开放 Windows 防火墙
netsh advfirewall firewall add rule `
    name="MinerU API" `
    dir=in action=allow `
    protocol=TCP `
    localport=8000
```

> 注意：WSL2 重启后 IP 会变，需要重新设置 `connectaddress`。可以把以上命令写成脚本。

现在局域网内其他设备可以通过 `http://<你的Windows_IP>:8000` 访问。

### 6.2 方案 B：WSL2 镜像网络模式（Windows 11 22H2+）

如果你用的是 Windows 11 22H2（Build 22621）或更高版本，并且 WSL 版本 ≥ 2.0.9，可以在用户目录 `C:\Users\<用户名>\.wslconfig` 中配置：

```ini
[wsl2]
networkingMode=mirrored
```

配置后 `wsl --shutdown` 再重启，WSL2 将共享 Windows 的网络，无需端口转发。但 mirror 模式可能与某些 VPN 冲突。

---

## 七、公网访问

让外网也能调用你的本地 MinerU API。

### 7.1 方案 A：ngrok（最简单，适合临时使用）

```powershell
# 1. 下载 ngrok（https://ngrok.com/download）
# 2. 注册获取 authtoken
ngrok config add-authtoken <你的token>

# 3. 启动隧道（MinerU API 在 WSL2 的 8000 端口）
ngrok http 8000
```

会得到一个公网 URL 如 `https://xxxx.ngrok-free.app`，外网可直接调用：

```python
resp = requests.post(
    "https://xxxx.ngrok-free.app/tasks",
    files={"files": open("example.pdf", "rb")},
    data={"response_format_zip": True},
)
```

### 7.2 方案 B：frp 内网穿透（适合长期使用）

在有一台公网服务器的情况下，用 frp 建立稳定的反向代理。

### 7.3 方案 C：Cloudflare Tunnel

免费且不需要公网服务器，但需要有自己的域名。

### 7.4 方案 D：纯 IPv6 服务器

如果你的服务器只有公网 IPv6（很多国内云服务器默认只给 IPv6），需要在启动 API 时同时监听 IPv4 和 IPv6：

```bash
# 启动时绑定所有接口（IPv4 + IPv6）
mineru-api --host :: --port 8000
```

客户端调用时，IPv6 地址必须用方括号包裹：

```bash
# curl
curl -X POST "http://[2408:xxxx:xxxx:xxxx::1]:8000/tasks" \
  -F "files=@example.pdf;type=application/pdf" \
  -F "response_format_zip=true"

# Python
resp = requests.post("http://[2408:xxxx:xxxx:xxxx::1]:8000/tasks",
    files={"files": open("example.pdf", "rb")},
    data={"response_format_zip": "true"})
```

用项目自带客户端：

```bash
uv run mineru_api_client.py example.pdf \
  --base-url "http://[2408:xxxx:xxxx:xxxx::1]:8000"
```

> Windows 本地调用远程 IPv6 服务器无需额外配置。浏览器访问同理：`http://[<ipv6地址>]:8000/docs`

---

## 八、开机自启

### 8.1 创建启动脚本

在 WSL2 中创建 `~/start_mineru_api.sh`：

```bash
#!/bin/bash
cd ~/mineru_stable && . .venv/bin/activate
export HSA_ENABLE_DXG_DETECTION=1
export FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE
export MINERU_MODEL_SOURCE=huggingface
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
mineru-api --host 0.0.0.0 --port 8000
```

```bash
chmod +x ~/start_mineru_api.sh
```

### 8.2 Windows 开机自动启动 WSL2 服务

在 Windows 中创建计划任务或使用 `wsl.conf`：

```bash
# WSL2 内编辑 /etc/wsl.conf
sudo sh -c 'cat > /etc/wsl.conf << EOF
[boot]
command = ~/start_mineru_api.sh
EOF'
```

> 注意：`wsl.conf` 的 boot 命令以 root 运行，如需以普通用户运行请使用 `su - $USER -c "~/start_mineru_api.sh"`。

---

## 九、输出格式与转换

### 9.1 两种 Markdown 模式

MinerU 内部有两种 Markdown 生成模式：

| 模式 | 代码名 | 特点 | 本地 API | 官网云 API | 官网 Web 端 |
|------|--------|------|:--:|:--:|:--:|
| 普通输出 | `MM_MD` | 含 `<details>` 图像描述块 | ✅ 默认 | ✅ (full.md) | ✅ |
| 输出为Markdown | `NLP_MD` | 纯文本，无视觉描述 | ❌ 未暴露参数 | ❌ 也没有 | ✅ 专有 |

> "输出为Markdown"是官网 Web 端**独有功能**，连他们的云 API 都没有这个参数。NLP_MD 代码内置在 MinerU 里，只是 CLI/API 没暴露。

用 `mineru_md_clean.py` 做后处理即可达到同样效果：

```bash
uv run mineru_md_clean.py full.md -o clean.md
```

完整流程（API → zip → 解压 → 清理）：

```bash
uv run mineru_api_client.py example.pdf --full
unzip -q <task_id>.zip
uv run mineru_md_clean.py <name>/hybrid_auto/<name>.md -o output_clean.md
```

### 9.2 导出 docx / html / LaTeX

官网云 API 通过 `extra_formats: ["docx", "html", "latex"]` 参数支持格式转换，但**本地 API 没有此功能**。

替代方案是用 `pandoc` 从 Markdown 转换：

```bash
# 安装 pandoc
sudo apt install pandoc

# Markdown → DOCX
pandoc full.md -o output.docx

# Markdown → HTML
pandoc full.md -o output.html --standalone

# Markdown → LaTeX
pandoc full.md -o output.tex

# 指定中文 PDF 引擎
pandoc full.md -o output.pdf --pdf-engine=xelatex -V mainfont="SimSun"
```

> pandoc 转换的 docx/html/latex 质量取决于源 Markdown 的结构化程度。MinerU 输出已含标题层级和表格，转换效果通常不错。

---

## 十、常用技巧

### 10.1 查看 GPU 状态

```bash
watch -n 1 /opt/rocm/bin/rocminfo
# 或
.venv/bin/python -c "import torch; print(torch.cuda.memory_allocated()/1e9, 'GB used')"
```

### 10.2 并发限制

`mineru-api` 默认最大并发 3 个任务（VLM 显存占用大）。如需修改，设置环境变量：

```bash
export MINERU_API_MAX_CONCURRENT_REQUESTS=1  # 16GB 显存建议 1-2
```

### 10.3 指定模型本地路径

```bash
export MINERU_MODEL_SOURCE=huggingface
export HF_HOME=/path/to/models  # 自定义模型缓存位置
```

### 10.4 加速模型下载

```bash
# 使用 hf_transfer 加速
.venv/bin/pip install huggingface-hub[hf_transfer]
export HF_HUB_ENABLE_HF_TRANSFER=1
```

---

## 附录：API 响应格式

### 成功响应（POST /tasks）

```json
{
  "task_id": "a6e47eff-da08-4163-9520-05f0339aab4f",
  "status": "pending",
  "backend": "hybrid-auto-engine",
  "file_names": ["test"],
  "created_at": "2026-05-24T14:03:55.681455+00:00",
  "status_url": "http://localhost:8000/tasks/a6e47eff...",
  "result_url": "http://localhost:8000/tasks/a6e47eff.../result",
  "queued_ahead": 0,
  "message": "Task submitted successfully"
}
```

### 任务状态（GET /tasks/{task_id}）

```json
{
  "task_id": "a6e47eff-da08-4163-9520-05f0339aab4f",
  "status": "completed",
  "backend": "hybrid-auto-engine",
  "file_names": ["test"],
  "created_at": "2026-05-24T14:03:55.681455+00:00",
  "started_at": "2026-05-24T14:03:56.000000+00:00",
  "completed_at": "2026-05-24T14:05:32.779444+00:00"
}
```

状态值：`pending` → `processing` → `completed` / `failed`

### 结果响应（GET /tasks/{task_id}/result）

当 `response_format_zip=true` 时，直接返回 zip 二进制流（Content-Type: `application/zip`）。解压后包含：

```
<task_id>.zip
├── example.md              # Markdown 正文
├── example_content_list.json  # 结构化 JSON（含段落、表格、公式位置）
├── example_model.json      # 模型原始输出
├── example_middle.json     # 中间处理结果
├── example_layout.pdf      # 版面分析标注
└── images/                 # 提取的图片
```

> 这和官网精准解析 API 的 zip 包结构完全一致。

---

*最后更新: 2026-05-25*
