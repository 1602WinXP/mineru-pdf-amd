#!/bin/bash
set -e

# 1. __hip_internal::conditional → std::conditional
find /opt/rocm/include/hip /usr/include/hip -name "*.h" -exec sed -i "s/__hip_internal::conditional/std::conditional/g" {} +

# 2. warpSize = __AMDGCN_WAVEFRONT_SIZE → warpSize = 32
find /opt/rocm/include/hip /usr/include/hip -name "amd_warp_functions.h" -exec sed -i "s/static constexpr int warpSize = __AMDGCN_WAVEFRONT_SIZE;/constexpr int warpSize = 32;/g" {} +

# 3. __activemask() → __builtin_amdgcn_read_exec()
find /opt/rocm/include/hip /usr/include/hip -name "*.h" -exec sed -i "s/__activemask()/__builtin_amdgcn_read_exec()/g" {} +

# 4. __assertfail conflict - delete from system header
python3 -c "
import re
with open('/usr/include/hip/amd_detail/amd_device_functions.h') as f:
    c = f.read()
c2 = re.sub(r'void __assertfail(?:\(\))?\s*\{[^}]*\}', '// __assertfail removed', c, flags=re.DOTALL)
with open('/usr/include/hip/amd_detail/amd_device_functions.h', 'w') as f:
    f.write(c2)
"

# 5. mamba operator+
cd ~/vllm && git checkout csrc/mamba/mamba_ssm/selective_scan.h 2>/dev/null
sed -i '109,121s/^/\/\/ /' csrc/mamba/mamba_ssm/selective_scan.h

echo "All 5 patches applied"
