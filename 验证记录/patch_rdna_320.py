#!/usr/bin/env python3
"""Apply RDNA MIOpen patches to MinerU 3.2.0"""

# Patch A+B: predict_rec.py
f = "/home/dev/mineru_stable/.venv/lib/python3.12/site-packages/mineru/model/utils/tools/infer/predict_rec.py"
with open(f) as fp:
    lines = fp.readlines()

# A: imgW 32-align (line 137, 0-indexed)
for i, line in enumerate(lines):
    if "imgW = max(min(imgW, self.limited_max_width), self.limited_min_width)" in line:
        indent = line[:len(line) - len(line.lstrip())]
        lines.insert(i + 1, f"{indent}imgW = math.ceil(imgW / 32) * 32\n")
        print(f"Patch A: imgW 32-align at line {i+1}")
        break

# B: batch padding (before line 355)
for i, line in enumerate(lines):
    if line.strip() == "norm_img_batch = np.concatenate(norm_img_batch)":
        indent = line[:len(line) - len(line.lstrip())]
        padding_code = f"""{indent}actual_batch_size = len(norm_img_batch)
{indent}if actual_batch_size < batch_num:
{indent}    pad_size = batch_num - actual_batch_size
{indent}    pad_img = np.zeros_like(norm_img_batch[0])
{indent}    for _ in range(pad_size):
{indent}        norm_img_batch.append(pad_img)
"""
        lines.insert(i, padding_code)
        print(f"Patch B: batch padding before line {i+1}")
        break

# B2: fix rec_result loop
for i, line in enumerate(lines):
    if "for rno in range(len(rec_result)):" in line:
        lines[i] = line.replace("for rno in range(len(rec_result)):", "for rno in range(actual_batch_size):")
        print(f"Patch B2: rec_result loop at line {i+1}")
        break

with open(f, "w") as fp:
    fp.writelines(lines)

# Patch C: predict_det.py
f2 = "/home/dev/mineru_stable/.venv/lib/python3.12/site-packages/mineru/model/utils/tools/infer/predict_det.py"
with open(f2) as fp:
    lines = fp.readlines()

# Find first inp = inp.to(self.device) in predict method (line ~186)
for i, line in enumerate(lines):
    if line.strip() == "inp = inp.to(self.device)":
        indent = line[:len(line) - len(line.lstrip())]
        lines.insert(i + 1, f"{indent}if not inp.is_contiguous():\n{indent}    inp = inp.contiguous()\n")
        print(f"Patch C: contiguous check at line {i+1}")
        break

with open(f2, "w") as fp:
    fp.writelines(lines)

print("All RDNA patches applied!")
