import struct

with open(r'C:\Users\Jason\source\agent_harness\challenges\authorize', 'rb') as f:
    data = f.read()

# 64-bit ELF header offsets
# e_ident: 0-15
e_type, e_machine, e_version = struct.unpack_from('<HHI', data, 16)
e_entry, e_phoff, e_shoff = struct.unpack_from('<QQQ', data, 24)  # offsets 24, 32, 40
e_flags = struct.unpack_from('<I', data, 48)[0]
e_ehsize, e_phentsize, e_phnum, e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHHHHH', data, 52)

print(f'e_type={e_type} e_machine={e_machine} e_version={e_version}')
print(f'e_entry=0x{e_entry:x}')
print(f'e_phoff=0x{e_phoff:x} e_phnum={e_phnum} e_phentsize={e_phentsize}')
print(f'e_shoff=0x{e_shoff:x} e_shnum={e_shnum} e_shentsize={e_shentsize}')
print(f'e_flags=0x{e_flags:x} e_ehsize={e_ehsize}')
print(f'e_shstrndx={e_shstrndx}')

# Parse program headers
for i in range(e_phnum):
    phoff = e_phoff + i * e_phentsize
    p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align = struct.unpack_from('<IIQQQQQQ', data, phoff)
    type_names = {1: 'PT_LOAD', 2: 'PT_DYNAMIC', 3: 'PT_INTERP', 4: 'PT_NOTE', 6: 'PT_PHDR', 7: 'PT_TLS', 0x6474e550: 'PT_GNU_EH_FRAME', 0x6474e551: 'PT_GNU_STACK', 0x6474e552: 'PT_GNU_RELRO', 0x6474e553: 'PT_GNU_PROPERTY'}
    tname = type_names.get(p_type, f'0x{p_type:x}')
    print(f'  PH {i}: {tname} flags={p_flags} offset=0x{p_offset:x} vaddr=0x{p_vaddr:x} filesz=0x{p_filesz:x} memsz=0x{p_memsz:x}')

# Parse section headers
if e_shnum > 0:
    print(f'\nSection headers (offset=0x{e_shoff:x}):')
    shstrtab_sec = None
    sections = []
    for i in range(e_shnum):
        shoff = e_shoff + i * e_shentsize
        sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size = struct.unpack_from('<IIQQQQ', data, shoff)
        _link, _info, _addralign, _entsize = struct.unpack_from('<QQII', data, shoff + 40)
        sections.append({'name_idx': sh_name, 'type': sh_type, 'flags': sh_flags, 'addr': sh_addr, 'offset': sh_offset, 'size': sh_size})
    
    shstrtab_sec = sections[e_shstrndx] if e_shstrndx < len(sections) else None
    if shstrtab_sec:
        shstrtab = data[shstrtab_sec['offset']:shstrtab_sec['offset']+shstrtab_sec['size']]
        for i, sec in enumerate(sections):
            if sec['size'] > 0:
                try:
                    name_end = shstrtab.index(b'\x00', sec['name_idx'])
                    name = shstrtab[sec['name_idx']:name_end].decode('ascii', errors='replace')
                except:
                    name = f'idx_{sec["name_idx"]}'
                print(f'  Section {i}: {name} @ 0x{sec["addr"]:x} offset=0x{sec["offset"]:x} size={sec["size"]} flags=0x{sec["flags"]:x}')
