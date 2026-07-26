import struct

with open(r'C:\Users\Jason\source\agent_harness\challenges\authorize', 'rb') as f:
    data = f.read()

e_ident = data[:16]

e_type, e_machine, e_version, e_entry, e_phoff, e_shoff = struct.unpack_from('<HHIQQQ', data, 16)
e_flags, e_ehsize, e_phentsize, e_phnum, e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<IHHHHHH', data, 36)

print(f'Entry: 0x{e_entry:x}')
print(f'Program headers at {e_phoff}, count={e_phnum}, entsize={e_phentsize}')
print(f'Sec headers at {e_shoff}, count={e_shnum}, shentsize={e_shentsize}')

# Dump program headers
for i in range(e_phnum):
    phoff = e_phoff + i * e_phentsize
    p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align = struct.unpack_from('<IIQQQQQQ', data, phoff)
    type_names = {1: 'PT_LOAD', 2: 'PT_DYNAMIC', 3: 'PT_INTERP', 4: 'PT_NOTE', 6: 'PT_PHDR', 7: 'PT_TLS', 0x6474e550: 'PT_GNU_EH_FRAME', 0x6474e551: 'PT_GNU_STACK', 0x6474e552: 'PT_GNU_RELRO', 0x6474e553: 'PT_GNU_PROPERTY'}
    tname = type_names.get(p_type, f'0x{p_type:x}')
    print(f'  PH {i}: {tname} flags={p_flags} offset=0x{p_offset:x} vaddr=0x{p_vaddr:x} filesz=0x{p_filesz:x} memsz=0x{p_memsz:x}')
