import struct

with open(r'C:\Users\Jason\source\agent_harness\challenges\binary1', 'rb') as f:
    data = f.read()

# Parse verify_password expected values
# At 0x1228: movabs rax, 0x673a257671212f28
# At 0x1232: movabs rdx, 0x3131122d140d2d2d
expected = struct.pack('<Q', 0x673a257671212f28) + struct.pack('<Q', 0x3131122d140d2d2d)
print('Expected bytes:', expected.hex())
print('Expected len:', len(expected))

# Password = expected[i] ^ 0x42
password = bytes([b ^ 0x42 for b in expected])
print(f'Password: {password.decode("ascii")}')

# Key at .rodata+0x2010
rodata = data[0x2000:0x2000+159]
key = rodata[0x10:0x14]  # 4 bytes at offset 0x10 from rodata start
print(f'Key: {key.hex()}')

# Encrypted flag at .rodata+0x2024 (31 bytes for i=0..0x1e)
enc_flag_offset = 0x24
enc_flag = rodata[enc_flag_offset:enc_flag_offset + 31]
print(f'Encrypted flag ({len(enc_flag)} bytes): {enc_flag.hex()}')

# Decrypt
flag = []
for i, b in enumerate(enc_flag):
    dec = b ^ key[i % 4]
    flag.append(dec)
print(f'Decrypted flag bytes: {bytes(flag)}')
print(f'Decrypted flag: {"".join(chr(b) if 32 <= b < 127 else f"\\x{b:02x}" for b in flag)}')
