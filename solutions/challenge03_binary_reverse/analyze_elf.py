import struct

with open(r'C:\Users\Jason\source\agent_harness\challenges\authorize', 'rb') as f:
    data = f.read()

e_ident = data[:16]
ei_class = e_ident[4]
ei_data = e_ident[5]
print(f'Class: {"64-bit" if ei_class == 2 else "32-bit"}')
print(f'Endian: {"Little" if ei_data == 1 else "Big"}')

e_type, e_machine, e_version, e_entry, e_phoff, e_shoff = struct.unpack_from('<HHIQQQ', data, 16)
e_flags, e_ehsize, e_phentsize, e_phnum, e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<IHHHHHH', data, 36)

print(f'Entry: 0x{e_entry:x}')
print(f'Section headers offset: {e_shoff}, count: {e_shnum}')

sections = []
for i in range(e_shnum):
    shoff = e_shoff + i * e_shentsize
    sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size = struct.unpack_from('<IIQQQQ', data, shoff)
    _link, _info, _addralign, _entsize = struct.unpack_from('<QQII', data, shoff + 40)
    sections.append({
        'name_idx': sh_name,
        'type': sh_type,
        'flags': sh_flags,
        'addr': sh_addr,
        'offset': sh_offset,
        'size': sh_size
    })

shstrtab_sec = sections[e_shstrndx]
shstrtab = data[shstrtab_sec['offset']:shstrtab_sec['offset']+shstrtab_sec['size']]

for i, sec in enumerate(sections):
    name_end = shstrtab.index(b'\x00', sec['name_idx'])
    name = shstrtab[sec['name_idx']:name_end].decode('ascii', errors='replace')
    if name:
        print(f'  Section {i}: {name} @ 0x{sec["addr"]:x} offset=0x{sec["offset"]:x} size={sec["size"]} flags=0x{sec["flags"]:x}')
