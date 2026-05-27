#!/usr/bin/env python3
import re
with open("/home/dev/vllm/pyproject.toml") as f:
    c = f.read()
c = c.replace('license = "Apache-2.0"', 'license = {text = "Apache-2.0"}')
c = re.sub(r'license-files.*\n', '', c)
with open("/home/dev/vllm/pyproject.toml", "w") as f:
    f.write(c)
print("pyproject.toml fixed")
