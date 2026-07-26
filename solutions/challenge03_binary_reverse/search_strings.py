import re

with open(r'C:\Users\Jason\source\agent_harness\challenges\authorize', 'rb') as f:
    data = f.read()

# Search for flag patterns
patterns_to_find = [b'THC', b'FLAG', b'flag', b'ctf', b'CTF', b'secret', b'SECRET']
for pattern in patterns_to_find:
    matches = [m.start() for m in re.finditer(pattern, data)]
    if matches:
        for m in matches:
            context = data[max(0,m-10):m+50]
            print(f'{pattern.decode()} at offset 0x{m:x}: {context}')
    else:
        print(f'{pattern.decode()}: not found')

# All printable strings >= 4 chars
strings = re.findall(rb'[\x20-\x7e]{4,}', data)
print('\nAll strings:')
for s in sorted(set(strings)):
    try:
        print(f'  {s.decode("ascii")}')
    except:
        pass
