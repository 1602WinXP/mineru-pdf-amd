#!/usr/bin/env python3
"""Fix rocm.py circular import: replace logger.warning_once with stderr"""
with open("/home/dev/vllm/vllm/platforms/rocm.py") as f:
    content = f.read()

old = '''    except Exception as e:
        logger.debug("Failed to get GCN arch via amdsmi: %s", e)
        logger.warning_once(
            "Failed to get GCN arch via amdsmi, falling back to torch.cuda. "
            "This will initialize CUDA and may cause "
            "issues if CUDA_VISIBLE_DEVICES is not set yet."
        )'''

new = '''    except Exception as e:
        import sys as _sys
        _sys.stderr.write("WSL2: amdsmi unavailable, using torch.cuda for GPU detection\\n")'''

if old in content:
    content = content.replace(old, new)
    with open("/home/dev/vllm/vllm/platforms/rocm.py", "w") as f:
        f.write(content)
    print("rocm.py: logger circular import chain broken")
else:
    print("Pattern not found in rocm.py")
