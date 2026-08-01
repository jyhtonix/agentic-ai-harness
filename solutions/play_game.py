import socket
import time
import re
import sys

HOST = 'aureolin-pixie.cylabacademy.net'
PORT = 64974

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(10)
s.connect((HOST, PORT))

all_text = b""

def send_line(text):
    s.sendall((text + '\n').encode())

def recv_some(timeout=2):
    s.settimeout(timeout)
    data = b""
    while True:
        try:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
            sys.stdout.buffer.write(chunk)
            sys.stdout.flush()
        except socket.timeout:
            break
    return data

# Question-answer pairs for the ethics game
# The game "Trust But Verify" - answers should be about verification
qa = iter([
    'b',  # Scene 1: Ask for source link (verify)
    'b',  # Continue verifying
    'c',  # Look it up independently
    'b',  # Choose verification
    'b',  # Choose verification
    'b',  # Choose verification
    'b',  # Choose verification
    'b',  # Choose verification
    'b',  # Choose verification
    'b',  # Choose verification
    'b',  # Choose verification
    'b',  # Choose verification
])

for i in range(500):
    data = recv_some(2)
    if not data:
        break
    all_text += data
    text = all_text.decode('utf-8', errors='replace')

    # Check for flag
    matches = re.findall(r'[A-Za-z0-9_]+\{[^}]+\}', text)
    if matches:
        print(f"\n\n=== FLAG FOUND: {matches} ===")
        break

    # Determine what to send
    last_200 = text[-200:] if len(text) > 200 else text

    if '>' in last_200:
        try:
            ans = next(qa)
            print(f"[Sending: {ans}]")
            send_line(ans)
        except StopIteration:
            send_line('a')
    elif 'continue' in text.lower() and '(Press Enter to continue...)' in text:
        send_line('')
    elif text.strip().endswith(':'):
        send_line('')
    elif text.strip().endswith('?'):
        send_line('')
    else:
        send_line('')

s.close()

final = all_text.decode('utf-8', errors='replace')
matches = re.findall(r'[A-Za-z0-9_]+\{[^}]+\}', final)
if matches:
    print(f"\n\nFLAG: {matches}")
else:
    print(f"\n\nNo flag. Saving to game_output.txt")
    with open('game_output.txt', 'w', encoding='utf-8') as f:
        f.write(final)
