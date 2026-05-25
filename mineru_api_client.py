#!/usr/bin/env python3
"""
MinerU 精准解析 API 客户端
对标 https://mineru.net/api/v4/extract/task — 提交文件→轮询→下载 zip

用法:
    python mineru_api_client.py example.pdf                 # 本地 API
    python mineru_api_client.py example.pdf -o result.zip   # 指定输出
    python mineru_api_client.py example.pdf --base-url https://xxxx.ngrok-free.app  # 远程
    python mineru_api_client.py example.pdf -o out.zip --extract   # 下载后自动解压
    python mineru_api_client.py --status <task_id>          # 查询状态
    python mineru_api_client.py --status <task_id> --download result.zip  # 下载
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from typing import Optional

import requests


def _submit_file_with_curl(url: str, file_path: str, data: dict, mime: str, timeout: int) -> dict:
    """使用 curl 提交 multipart 请求，避免 requests 在本地环境中的传输问题。"""
    curl = shutil.which("curl") or shutil.which("curl.exe")
    if not curl:
        raise RuntimeError("未找到 curl，无法上传文件")

    command = [curl, "-sS", "-X", "POST", url, "-o", "-", "-w", "\n%{http_code}"]

    for key, value in data.items():
        command.extend(["-F", f"{key}={value}"])

    command.extend(["-F", f"files=@{file_path};type={mime}"])

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    output = completed.stdout.strip()
    if not output:
        raise RuntimeError(completed.stderr.strip() or "curl 上传失败")

    lines = output.splitlines()
    status_text = lines[-1]
    body = "\n".join(lines[:-1]).strip()

    if not status_text.isdigit():
        raise RuntimeError(body or output)

    status_code = int(status_text)
    if status_code != 202:
        detail = body or completed.stderr.strip() or "上传失败"
        try:
            detail = json.loads(body).get("detail", detail)
        except Exception:
            pass
        raise RuntimeError(f"提交失败 (HTTP {status_code}): {detail}")

    try:
        return json.loads(body)
    except Exception as exc:
        raise RuntimeError(f"提交成功但返回内容无法解析: {body}") from exc


def submit_file(
    base_url: str,
    file_path: str,
    backend: str = "hybrid-auto-engine",
    parse_method: str = "auto",
    lang: str = "ch",
    response_format_zip: bool = True,
    return_md: bool = True,
    return_content_list: bool = True,
    return_images: bool = True,
    return_middle_json: bool = False,
    return_model_output: bool = False,
    return_original_file: bool = False,
    formula_enable: bool = True,
    table_enable: bool = True,
    start_page: Optional[int] = None,
    end_page: Optional[int] = None,
    timeout: int = 30,
) -> dict:
    """提交本地文件到解析任务，返回 task 信息"""
    url = f"{base_url.rstrip('/')}/tasks"

    # 表单字段 — 布尔值用字符串 "true"/"false"（multipart/form-data 要求）
    data = {
        "backend": backend,
        "parse_method": parse_method,
        "lang_list": lang,
        "response_format_zip": "true" if response_format_zip else "false",
        "return_md": "true" if return_md else "false",
        "return_content_list": "true" if return_content_list else "false",
        "return_images": "true" if return_images else "false",
        "return_middle_json": "true" if return_middle_json else "false",
        "return_model_output": "true" if return_model_output else "false",
        "return_original_file": "true" if return_original_file else "false",
        "formula_enable": "true" if formula_enable else "false",
        "table_enable": "true" if table_enable else "false",
    }
    if start_page is not None:
        data["start_page_id"] = str(start_page)
    if end_page is not None:
        data["end_page_id"] = str(end_page)

    filename = os.path.basename(file_path)
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    mime_map = {
        "pdf": "application/pdf",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    mime = mime_map.get(ext, "application/octet-stream")

    print(f"📤 上传: {filename} ({os.path.getsize(file_path) / 1024 / 1024:.1f} MB)")
    try:
        return _submit_file_with_curl(url, file_path, data, mime, timeout)
    except Exception:
        with open(file_path, "rb") as f:
            resp = requests.post(
                url,
                files={"files": (filename, f, mime)},   # ← 字段名必须是 "files"
                data=data,
                timeout=timeout,
            )

        if resp.status_code != 202:
            detail = resp.text
            try:
                detail = resp.json().get("detail", detail)
            except Exception:
                pass
            raise RuntimeError(f"提交失败 (HTTP {resp.status_code}): {detail}")
        return resp.json()  # 响应是扁平 JSON，task_id 在根级


def get_status(base_url: str, task_id: str, timeout: int = 10) -> dict:
    """查询任务状态"""
    url = f"{base_url.rstrip('/')}/tasks/{task_id}"
    resp = requests.get(url, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"查询失败 (HTTP {resp.status_code}): {resp.text}")
    return resp.json()  # 扁平 JSON


def download_result(
    base_url: str, task_id: str, output_path: str, timeout: int = 120
) -> str:
    """下载 zip 结果，返回保存路径"""
    url = f"{base_url.rstrip('/')}/tasks/{task_id}/result"
    resp = requests.get(url, timeout=timeout)

    if resp.status_code == 202:
        raise RuntimeError("任务尚未完成，请等待后重试")
    if resp.status_code != 200:
        raise RuntimeError(f"下载失败 (HTTP {resp.status_code}): {resp.text}")

    if not output_path.endswith(".zip"):
        output_path += ".zip"

    with open(output_path, "wb") as f:
        f.write(resp.content)
    return output_path


def poll_until_done(
    base_url: str,
    task_id: str,
    poll_interval: int = 3,
    max_wait: int = 1800,
) -> dict:
    """轮询等待任务完成，返回最终状态"""
    start = time.time()
    dots = 0

    while True:
        elapsed = time.time() - start
        if elapsed > max_wait:
            raise TimeoutError(f"任务 {task_id} 超过 {max_wait}s ({max_wait // 60} 分钟) 未完成")

        status = get_status(base_url, task_id)
        s = status["status"]

        if s == "completed":
            print(f"\r✅ 解析完成 ({elapsed:.0f}s){' ' * 20}")
            return status
        elif s == "failed":
            error = status.get("error", "未知错误")
            raise RuntimeError(f"任务失败: {error}")

        dots = (dots + 1) % 4
        bar = "." * dots + " " * (3 - dots)
        print(f"\r⏳ {s}{bar} ({elapsed:.0f}s)  ", end="", flush=True)
        time.sleep(poll_interval)


def show_status(base_url: str, task_id: str):
    """显示任务详情"""
    s = get_status(base_url, task_id)
    print(f"Task ID:      {task_id}")
    print(f"Status:       {s['status']}")
    print(f"Backend:      {s.get('backend', '-')}")
    print(f"File(s):      {', '.join(s.get('file_names', ['-']))}")
    print(f"Created:      {s.get('created_at', '-')}")
    if s.get("completed_at"):
        print(f"Completed:    {s['completed_at']}")
    if s.get("error"):
        print(f"Error:        {s['error']}")
    if s.get("queued_ahead") is not None:
        print(f"Queued ahead: {s['queued_ahead']}")


def extract_zip(zip_path: str, extract_to: Optional[str] = None):
    """解压 zip 文件"""
    if extract_to is None:
        extract_to = os.path.splitext(zip_path)[0]
    os.makedirs(extract_to, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)
    print(f"📂 解压到: {extract_to}")
    for name in sorted(zf.namelist())[:10]:
        print(f"   {name}")
    if len(zf.namelist()) > 10:
        print(f"   ... 共 {len(zf.namelist())} 个文件")


def main():
    parser = argparse.ArgumentParser(
        description="MinerU 精准解析 API 客户端 — 提交文件 → 轮询 → 下载 zip",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s example.pdf                              # 本地 API
  %(prog)s example.pdf -o result.zip --extract      # 指定输出 + 解压
  %(prog)s example.pdf --base-url https://xxx.com   # 远程 API
  %(prog)s --status <task_id>                       # 查询状态
  %(prog)s --status <task_id> --download result.zip # 下载结果
        """,
    )

    parser.add_argument("file", nargs="?", help="要解析的文件路径")
    parser.add_argument("-o", "--output", help="输出 zip 路径（默认: <task_id>.zip）")
    parser.add_argument("--extract", action="store_true", help="下载后自动解压")

    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API 地址（默认: http://localhost:8000）",
    )
    parser.add_argument(
        "-b", "--backend",
        default="hybrid-auto-engine",
        choices=["hybrid-auto-engine", "vlm-auto-engine", "pipeline"],
        help="解析后端（默认: hybrid-auto-engine）",
    )
    parser.add_argument(
        "-m", "--method",
        default="auto",
        choices=["auto", "txt", "ocr"],
        help="解析方法（默认: auto）",
    )
    parser.add_argument("-l", "--lang", default="ch", help="文档语言（默认: ch）")

    parser.add_argument("--no-zip", action="store_true", help="不打包 zip")
    parser.add_argument("--no-md", action="store_true", help="不返回 Markdown")
    parser.add_argument("--no-content-list", action="store_true", help="不返回 content_list JSON")
    parser.add_argument("--no-images", action="store_true", help="不返回图片")
    parser.add_argument("--middle-json", action="store_true", help="返回中间 JSON")
    parser.add_argument("--model-output", action="store_true", help="返回模型原始输出")
    parser.add_argument("--original-file", action="store_true", help="返回原始文件")
    parser.add_argument("--no-formula", action="store_true", help="禁用公式识别")
    parser.add_argument("--no-table", action="store_true", help="禁用表格识别")
    parser.add_argument("--full", action="store_true",
                        help="返回全部文件（对标官网 API 输出，含 model.json / origin.pdf 等）")

    parser.add_argument("--start-page", type=int, help="起始页（0-based）")
    parser.add_argument("--end-page", type=int, help="结束页（0-based）")
    parser.add_argument("--poll-interval", type=int, default=3, help="轮询间隔秒（默认: 3）")
    parser.add_argument("--max-wait", type=int, default=1800, help="最大等待秒（默认: 1800）")

    parser.add_argument("--status", help="查询指定 task_id 的状态")
    parser.add_argument("--download", help="配合 --status，下载已完成任务的结果")

    parser.add_argument("--timeout", type=int, default=30, help="HTTP 请求超时秒（默认: 30）")

    args = parser.parse_args()

    # ---- 模式：查询 / 下载已有任务 ----
    if args.status:
        if args.download:
            output = args.download
            print(f"⬇️  下载 {args.status} → {output}")
            path = download_result(args.base_url, args.status, output, args.timeout)
            print(f"✅ 已保存: {path} ({os.path.getsize(path) / 1024:.1f} KB)")
            if args.extract:
                extract_zip(path)
        else:
            show_status(args.base_url, args.status)
        return

    # ---- 模式：提交新任务 ----
    if not args.file:
        parser.error("需要提供文件路径")

    if not os.path.exists(args.file):
        print(f"❌ 文件不存在: {args.file}")
        sys.exit(1)

    # --full 标志：返回全部输出文件（对标官网 API）
    full_output = args.full

    try:
        task = submit_file(
            args.base_url, args.file,
            backend=args.backend,
            parse_method=args.method,
            lang=args.lang,
            response_format_zip=not args.no_zip,
            return_md=not args.no_md,
            return_content_list=(not args.no_content_list) or full_output,
            return_images=(not args.no_images) or full_output,
            return_middle_json=args.middle_json or full_output,
            return_model_output=args.model_output or full_output,
            return_original_file=args.original_file or full_output,
            formula_enable=not args.no_formula,
            table_enable=not args.no_table,
            start_page=args.start_page,
            end_page=args.end_page,
            timeout=args.timeout,
        )

        task_id = task["task_id"]
        status_url = f"{args.base_url.rstrip('/')}/tasks/{task_id}"
        print(f"✅ 任务已提交: {task_id}")
        print(f"🔗 状态查询: {status_url}")

        final = poll_until_done(args.base_url, task_id, args.poll_interval, args.max_wait)

        if args.no_zip:
            print("ℹ️  未启用 zip，请手动获取结果")
        else:
            output = args.output or f"{task_id}.zip"
            print(f"⬇️  下载结果...")
            path = download_result(args.base_url, task_id, output, args.timeout)
            size_kb = os.path.getsize(path) / 1024
            print(f"✅ 已保存: {path} ({size_kb:.1f} KB)")
            if args.extract:
                extract_zip(path)

    except requests.exceptions.ConnectionError:
        print(f"❌ 无法连接到 {args.base_url}")
        print("   确保 API 已启动: mineru-api --host 0.0.0.0 --port 8000")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print(f"❌ 请求超时")
        sys.exit(1)
    except RuntimeError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n⚠️  已中断（任务 {task_id} 仍在后台运行）")
        print(f"   查询状态: python {sys.argv[0]} --status {task_id}")
        sys.exit(130)


if __name__ == "__main__":
    main()
