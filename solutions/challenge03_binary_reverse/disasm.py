from capstone import Cs, CS_ARCH_X86, CS_MODE_64
import struct

with open(r'C:\Users\Jason\source\agent_harness\challenges\authorize', 'rb') as f:
    data = f.read()

# .text at offset 0x10a0, vaddr 0x10a0, size 867
text_offset = 0x10a0
text_size = 867
text_data = data[text_offset:text_offset + text_size]

md = Cs(CS_ARCH_X86, CS_MODE_64)
print("=== .text disassembly ===")
for insn in md.disasm(text_data, text_offset):
    print(f"0x{insn.address:x}:\t{insn.mnemonic}\t{insn.op_str}")

print("\n=== .rodata dump ===")
rodata_offset = 0x2000
rodata_size = 127
rodata = data[rodata_offset:rodata_offset + rodata_size]
# Print with ASCII
for i in range(0, len(rodata), 16):
    hex_part = ' '.join(f'{b:02x}' for b in rodata[i:i+16])
    ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in rodata[i:i+16])
    print(f"  0x{rodata_offset+i:04x}: {hex_part}  {ascii_part}")
