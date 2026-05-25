#!/usr/bin/env python3
"""
MinerU API 命令行工具 — 调用 MinerU 在线 API 解析文档，下载结果 ZIP 包。

支持两种输入模式：
  1. 本地文件  → 批量上传流程  (POST /api/v4/file-urls/batch → PUT → 轮询 → 下载)
  2. URL      → 单任务流程     (POST /api/v4/extract/task → 轮询 → 下载)

用法:
  python mineru_cli.py ./document.pdf
  python mineru_cli.py ./doc1.pdf ./doc2.pdf -o ./output
  python mineru_cli.py https://example.com/doc.pdf
  python mineru_cli.py ./doc.html --model MinerU-HTML

API Key 可通过以下方式提供（优先级从高到低）：
  --api-key 参数 → MINERU_API_KEY 环境变量 → .env 文件
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Optional

import httpx

# ── 常量 ────────────────────────────────────────────────────────
BASE_URL = "https://mineru.net/api/v4"
DEFAULT_MODEL = "vlm"
DEFAULT_POLL_INTERVAL = 5.0
DEFAULT_MAX_WAIT = 600.0

_NETWORK_EXC = (
    httpx.ConnectError,
    httpx.TimeoutException,
    httpx.ReadError,
    httpx.HTTPStatusError,
)
if hasattr(httpx, "NetworkError"):
    _NETWORK_EXC += (httpx.NetworkError,)


# ── API Key 加载 ─────────────────────────────────────────────────
def _load_api_key_from_dotenv() -> Optional[str]:
    """尝试从当前目录及脚本所在目录的 .env 文件中读取 MINERU_API_KEY"""
    search_dirs = [Path.cwd(), Path(__file__).resolve().parent]
    for d in search_dirs:
        env_file = d / ".env"
        if not env_file.exists():
            continue
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("MINERU_API_KEY=") or line.startswith("MINERU_API_KEY ="):
                    value = line.split("=", 1)[1].strip()
                    if value:
                        return value
        except Exception:
            continue
    return None


def resolve_api_key(cli_key: Optional[str]) -> str:
    """解析 API Key，优先级: CLI 参数 > 环境变量 > .env 文件"""
    if cli_key:
        return cli_key
    env_key = os.environ.get("MINERU_API_KEY", "")
    if env_key:
        return env_key
    dotenv_key = _load_api_key_from_dotenv()
    if dotenv_key:
        return dotenv_key
    print("Error: MinerU API Key not provided. Provide it via one of:")
    print("  1. --api-key CLI argument")
    print("  2. MINERU_API_KEY environment variable")
    print("  3. .env file in current or script directory")
    sys.exit(1)


# ── 网络请求封装 ─────────────────────────────────────────────────
def _auth_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


async def _retry(coro_fn, *, max_retries: int = 3, base_delay: float = 2.0):
    """指数退避重试 (2s → 4s → 8s)，仅对瞬时网络故障重试"""
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except _NETWORK_EXC as exc:
            if attempt >= max_retries:
                raise RuntimeError(
                    f"Network error after {max_retries} retries, last error: {exc}"
                ) from exc
            delay = base_delay * (2 ** attempt)
            print(f"  [WARN] Connection failed (attempt {attempt + 1}/{max_retries}), retrying in {delay:.0f}s: {exc}")
            await asyncio.sleep(delay)


# ── 批量本地文件上传流程 ────────────────────────────────────────
async def _request_batch_upload_urls(
    files_info: list[dict], api_key: str, model: str
) -> tuple[str, list[str]]:
    """申请批量预签名上传链接，返回 (batch_id, file_urls)"""
    payload = {"files": files_info, "model_version": model}

    async def _call():
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{BASE_URL}/file-urls/batch",
                headers=_auth_headers(api_key),
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    body = await _retry(_call)
    if body.get("code") != 0:
        raise RuntimeError(f"Failed to request upload URLs: code={body.get('code')}, msg={body.get('msg')}")
    data = body["data"]
    return data["batch_id"], data["file_urls"]


async def _upload_file_to_presigned_url(presigned_url: str, local_path: Path) -> None:
    """将本地文件 PUT 到预签名 URL（流式上传，不设置 Content-Type）

    使用同步 httpx.Client + run_in_executor，避免将整个文件读入内存，
    同时保持 _retry 的重试能力（每次重试重新打开文件）。
    """
    file_size = local_path.stat().st_size

    async def _call():
        loop = asyncio.get_running_loop()

        def _sync_put():
            with open(local_path, "rb") as f:
                with httpx.Client(timeout=180) as client:
                    resp = client.put(presigned_url, content=f)
            if resp.status_code not in (200, 201, 204):
                raise RuntimeError(
                    f"Presigned upload failed {local_path.name}: HTTP {resp.status_code}, body={resp.text[:200]}"
                )
            return resp

        return await loop.run_in_executor(None, _sync_put)

    await _retry(_call)
    print(f"  [OK] Uploaded: {local_path.name} ({file_size:,} bytes)")


async def _poll_batch_results(
    batch_id: str, api_key: str, poll_interval: float, max_wait: float
) -> list[dict]:
    """轮询批量任务直到所有文件达到终态"""
    terminal = {"done", "failed"}
    elapsed = 0.0

    while elapsed < max_wait:

        async def _call():
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{BASE_URL}/extract-results/batch/{batch_id}",
                    headers=_auth_headers(api_key),
                )
                resp.raise_for_status()
                return resp.json()

        body = await _retry(_call)
        if body.get("code") != 0:
            raise RuntimeError(f"Failed to query batch results: {body}")

        results: list[dict] = body["data"].get("extract_result", [])
        states = [r.get("state", "?") for r in results]
        file_names = [r.get("file_name", "?") for r in results]

        # 打印进度（行内刷新）
        status_str = " | ".join(f"{n}:{s}" for n, s in zip(file_names, states))
        print(f"\r  [...] [{elapsed:.0f}s] {status_str}", end="", flush=True)

        if results and all(s in terminal for s in states):
            print()  # 换行
            return results

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    print()  # 换行
    raise TimeoutError(f"Batch task {batch_id} did not complete within {max_wait}s")


async def process_local_files(
    file_paths: list[Path], api_key: str, output_dir: Path, model: str,
    poll_interval: float, max_wait: float,
) -> list[Path]:
    """批量本地文件上传 → 轮询 → 下载 ZIP"""
    files_info = [{"name": p.name} for p in file_paths]

    print(f"Requesting presigned upload URLs ({len(file_paths)} files, model={model})...")
    batch_id, presigned_urls = await _request_batch_upload_urls(files_info, api_key, model)
    print(f"  batch_id: {batch_id}")

    # 上传
    for url, local_path in zip(presigned_urls, file_paths):
        print(f"  Uploading {local_path.name} ...")
        await _upload_file_to_presigned_url(url, local_path)

    # 轮询
    print("  Waiting for parsing to complete...")
    results = await _poll_batch_results(batch_id, api_key, poll_interval, max_wait)

    # 下载
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    for r in results:
        fname = r.get("file_name", "unknown")
        state = r.get("state", "?")
        if state == "done" and r.get("full_zip_url"):
            print(f"  Downloading result for {fname} ...")
            dest = await _download_zip(r["full_zip_url"], output_dir)
            downloaded.append(dest)
        else:
            print(f"  [FAIL] {fname}: state={state}, err_msg={r.get('err_msg', '')}")

    return downloaded


# ── 单文件 URL 解析流程 ─────────────────────────────────────────
async def _submit_single_url_task(file_url: str, api_key: str, model: str) -> str:
    """提交单文件（URL）解析任务，返回 task_id"""
    payload = {"url": file_url, "model_version": model}

    async def _call():
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{BASE_URL}/extract/task",
                headers=_auth_headers(api_key),
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    body = await _retry(_call)
    if body.get("code") != 0:
        raise RuntimeError(f"Failed to submit URL task: code={body.get('code')}, msg={body.get('msg')}")
    return body["data"]["task_id"]


async def _poll_single_task(
    task_id: str, api_key: str, poll_interval: float, max_wait: float
) -> dict:
    """轮询单个任务直到完成"""
    terminal = {"done", "failed"}
    elapsed = 0.0

    while elapsed < max_wait:

        async def _call():
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{BASE_URL}/extract/task/{task_id}",
                    headers=_auth_headers(api_key),
                )
                resp.raise_for_status()
                return resp.json()

        body = await _retry(_call)
        if body.get("code") != 0:
            raise RuntimeError(f"Failed to query task status: {body}")

        data = body["data"]
        state = data.get("state", "")
        progress = data.get("extract_progress", {})
        if progress:
            print(f"\r  [...] [{elapsed:.0f}s] state={state} "
                  f"({progress.get('extracted_pages', '?')}/{progress.get('total_pages', '?')} pages)",
                  end="", flush=True)
        else:
            print(f"\r  [...] [{elapsed:.0f}s] state={state}", end="", flush=True)

        if state in terminal:
            print()
            return data

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    print()
    raise TimeoutError(f"Task {task_id} did not complete within {max_wait}s")


async def process_url(
    file_url: str, api_key: str, output_dir: Path, model: str,
    poll_interval: float, max_wait: float,
) -> Path:
    """单 URL 任务: 提交 → 轮询 → 下载 ZIP"""
    print(f"  Submitting URL task: {file_url} (model={model})")
    task_id = await _submit_single_url_task(file_url, api_key, model)
    print(f"  task_id: {task_id}")

    print("  Waiting for parsing to complete...")
    result = await _poll_single_task(task_id, api_key, poll_interval, max_wait)

    state = result.get("state", "?")
    if state != "done" or not result.get("full_zip_url"):
        raise RuntimeError(f"Parsing failed: state={state}, err_msg={result.get('err_msg', '')}")

    output_dir.mkdir(parents=True, exist_ok=True)
    print("  Downloading ZIP ...")
    dest = await _download_zip(result["full_zip_url"], output_dir)
    return dest


# ── ZIP 下载 ─────────────────────────────────────────────────────
def _filename_from_cd(content_disposition: str | None) -> str | None:
    """从 Content-Disposition 头提取 filename，支持 filename 和 filename* 两种形式"""
    if not content_disposition:
        return None
    # 优先解析 filename*=UTF-8''xxx 格式
    for part in content_disposition.split(";"):
        part = part.strip()
        if part.startswith("filename*="):
            # filename*=UTF-8''encoded_name
            _, _, encoded = part.partition("=")
            encoded = encoded.strip().strip('"')
            if "''" in encoded:
                _, _, name = encoded.partition("''")
                from urllib.parse import unquote
                return unquote(name)
            return encoded
    # 回退到 filename="xxx"
    for part in content_disposition.split(";"):
        part = part.strip()
        if part.startswith("filename="):
            name = part.partition("=")[2].strip().strip('"')
            if name:
                return name
    return None


def _fallback_name(zip_url: str) -> str:
    """从 ZIP URL 路径提取文件名作为兜底"""
    from urllib.parse import urlparse
    path = urlparse(zip_url).path
    name = Path(path).name
    return name if name else "output.zip"


async def _download_zip(zip_url: str, output_dir: Path) -> Path:
    """流式下载 ZIP 到本地，文件名取自服务器返回的 Content-Disposition"""
    output_dir.mkdir(parents=True, exist_ok=True)

    dest_path: Path | None = None

    async def _call():
        nonlocal dest_path
        async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
            async with client.stream("GET", zip_url) as resp:
                resp.raise_for_status()
                cd = resp.headers.get("Content-Disposition", "")
                fname = _filename_from_cd(cd) or _fallback_name(zip_url)
                dest_path = output_dir / fname
                total = 0
                with open(dest_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        f.write(chunk)
                        total += len(chunk)
        return total

    total = await _retry(_call)
    print(f"  [OK] Downloaded: {dest_path} ({total:,} bytes)")
    return dest_path


# ── 判断输入类型 ─────────────────────────────────────────────────
def _is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


# ── CLI 入口 ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="MinerU API CLI - Upload documents to MinerU for parsing, download result ZIP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python mineru_cli.py document.pdf
  python mineru_cli.py doc1.pdf doc2.pdf -o ./output
  python mineru_cli.py https://example.com/document.pdf
  python mineru_cli.py document.html --model MinerU-HTML
  python mineru_cli.py document.pdf --api-key YOUR_KEY --model pipeline
        """,
    )
    parser.add_argument(
        "inputs", nargs="+",
        help="Input file paths or URLs (.pdf/.doc/.docx/.ppt/.pptx/.png/.jpg/.html)",
    )
    parser.add_argument(
        "-o", "--output-dir", default="./mineru_output",
        help="Output directory for ZIP files (default: ./mineru_output)",
    )
    parser.add_argument(
        "--api-key", default=None,
        help="MinerU API Token (or set MINERU_API_KEY env var / .env file)",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        choices=["pipeline", "vlm", "MinerU-HTML"],
        help="Model version (default: vlm; use MinerU-HTML for HTML files)",
    )
    parser.add_argument(
        "--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL,
        help=f"Polling interval in seconds (default: {DEFAULT_POLL_INTERVAL})",
    )
    parser.add_argument(
        "--max-wait", type=float, default=DEFAULT_MAX_WAIT,
        help=f"Maximum wait time in seconds (default: {DEFAULT_MAX_WAIT})",
    )

    args = parser.parse_args()

    # 解析 API Key
    api_key = resolve_api_key(args.api_key)

    # 分类输入: URL vs 本地文件
    urls = [x for x in args.inputs if _is_url(x)]
    local_files = [Path(x) for x in args.inputs if not _is_url(x)]

    # 验证本地文件存在
    for fp in local_files:
        if not fp.exists():
            print(f"Error: file not found - {fp}")
            sys.exit(1)

    output_dir = Path(args.output_dir)

    async def run():
        downloaded: list[Path] = []

        if local_files:
            zips = await process_local_files(
                local_files, api_key, output_dir,
                args.model, args.poll_interval, args.max_wait,
            )
            downloaded.extend(zips)

        for url in urls:
            zip_path = await process_url(
                url, api_key, output_dir,
                args.model, args.poll_interval, args.max_wait,
            )
            downloaded.append(zip_path)

        return downloaded

    start = time.perf_counter()
    downloaded = asyncio.run(run())
    elapsed = time.perf_counter() - start

    print(f"\n[DONE] Completed! {len(downloaded)} file(s), elapsed {elapsed:.1f}s")
    for p in downloaded:
        print(f"   -> {p.resolve()}")


if __name__ == "__main__":
    main()
