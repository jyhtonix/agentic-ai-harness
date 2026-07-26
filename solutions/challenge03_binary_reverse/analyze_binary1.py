from capstone import Cs, CS_ARCH_X86, CS_MODE_64
import struct

with open(r'C:\Users\Jason\source\agent_harness\challenges\binary1', 'rb') as f:
    data = f.read()

e_ident = data[:16]
ei_class = e_ident[4]
print(f'Class: {"64-bit" if ei_class == 2 else "32-bit"}')

e_type, e_machine, e_version, e_entry, e_phoff, e_shoff = struct.unpack_from('<HHIQQQ', data, 16)
e_flags, e_ehsize, e_phentsize, e_phnum, e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<IHHHHHH', data, 48)

print(f'Entry: 0x{e_entry:x}')
print(f'Sec headers offset: {e_shoff}, count: {e_shnum}')

sections = []
for i in range(e_shnum):
    shoff = e_shoff + i * e_shentsize
    sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size = struct.unpack_from('<IIQQQQ', data, shoff)
    _link, _info, _addralign, _entsize = struct.unpack_from('<QQII', data, shoff + 40)
    sections.append({
        'name_idx': sh_name, 'type': sh_type, 'flags': sh_flags,
        'addr': sh_addr, 'offset': sh_offset, 'size': sh_size
    })

s = sections[e_shstrndx]
shstrtab = data[s['offset']:s['offset']+s['size']]

for i, sec in enumerate(sections):
    if sec['size'] > 0:
        name_end = shstrtab.index(b'\x00', sec['name_idx'])
        name = shstrtab[sec['name_idx']:name_end].decode('ascii', errors='replace')
        print(f'  {name}: addr=0x{sec["addr"]:x} offset=0x{sec["offset"]:x} size={sec["size"]} flags=0x{sec["flags"]:x}')
        if name == '.text':
            text_off = sec['offset']
            text_addr = sec['addr']
            text_size = sec['size']
        if name == '.rodata':
            rodata_off = sec['offset']
            rodata_addr = sec['addr']
            rodata_size = sec['size']
        if name == '.data':
            data_off = sec['offset']
            data_addr = sec['addr']
            data_size = sec['size']

print(f'\n=== .text disassembly ===')
text_data = data[text_off:text_off + text_size]
md = Cs(CS_ARCH_X86, CS_MODE_64)
for insn in md.disasm(text_data, text_addr):
    print(f'0x{insn.address:x}: {insn.mnemonic} {insn.op_str}')
