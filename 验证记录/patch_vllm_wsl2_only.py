#!/usr/bin/env python3
"""Apply ONLY the WSL2 rocm fallback to __init__.py, no placeholder"""
with open("/home/dev/vllm/vllm/platforms/__init__.py") as f:
    content = f.read()

old = '    return "vllm.platforms.rocm.RocmPlatform" if is_rocm else None'
new = """    # WSL2 fallback: amdsmi may fail, check torch.version.hip
    if not is_rocm:
        try:
            import torch
            if torch.version.hip is not None:
                is_rocm = True
        except Exception:
            pass
    return "vllm.platforms.rocm.RocmPlatform" if is_rocm else None"""

if old in content:
    content = content.replace(old, new)
    with open("/home/dev/vllm/vllm/platforms/__init__.py", "w") as f:
        f.write(content)
    print("Applied: WSL2 fallback only")
else:
    print("Pattern not found!")
