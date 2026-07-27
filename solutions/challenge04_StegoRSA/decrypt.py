import sys
sys.stdout.reconfigure(encoding='utf-8')

from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

with open('C:\\Users\\Jason\\source\\agent_harness\\challenges\\challenge04_StegoRSA\\private_key.pem', 'rb') as f:
    pem_data = f.read()

key = serialization.load_pem_private_key(pem_data, password=None, backend=default_backend())

if isinstance(key, rsa.RSAPrivateKey):
    numbers = key.private_numbers()
    pub_numbers = key.public_key().public_numbers()
    n = numbers.p * numbers.q
    
    print('=== RSA PRIVATE KEY PARAMETERS ===')
    print(f'n bit length: {n.bit_length()}')
    print(f'n hex: {hex(n)}')
    print(f'p hex: {hex(numbers.p)}')
    print(f'q hex: {hex(numbers.q)}')
    print(f'd hex: {hex(numbers.d)}')
    print(f'e: {pub_numbers.e}')
    
    with open('C:\\Users\\Jason\\source\\agent_harness\\challenges\\challenge04_StegoRSA\\flag.enc', 'rb') as f:
        flag_enc = f.read()
    
    print(f'\nEncrypted flag: {len(flag_enc)} bytes')
    c = int.from_bytes(flag_enc, 'big')
    print(f'c hex: {hex(c)}')
    
    # Try raw RSA (textbook)
    m = pow(c, numbers.d, n)
    m_bytes = m.to_bytes((m.bit_length() + 7) // 8, 'big')
    print(f'\n=== RAW RSA DECRYPTION ===')
    print(f'm hex: {hex(m)}')
    print(f'm bytes ({len(m_bytes)}): {m_bytes}')
    try:
        print(f'm as text: {m_bytes.decode("utf-8")}')
    except:
        print(f'm as latin-1: {m_bytes.decode("latin-1")}')
    
    # Try PKCS1v15
    try:
        pt = key.decrypt(flag_enc, padding.PKCS1v15())
        print(f'\n=== PKCS1v15 DECRYPTION ===')
        print(f'Plaintext: {pt}')
        print(f'As text: {pt.decode("utf-8", errors="replace")}')
    except Exception as e:
        print(f'\nPKCS1v15 failed: {e}')
    
    # Try OAEP SHA1
    try:
        pt = key.decrypt(flag_enc, padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA1()),
            algorithm=hashes.SHA1(),
            label=None))
        print(f'\n=== OAEP-SHA1 DECRYPTION ===')
        print(f'Plaintext: {pt}')
        print(f'As text: {pt.decode("utf-8", errors="replace")}')
    except Exception as e:
        print(f'\nOAEP-SHA1 failed: {e}')
    
    # Try OAEP SHA256
    try:
        pt = key.decrypt(flag_enc, padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None))
        print(f'\n=== OAEP-SHA256 DECRYPTION ===')
        print(f'Plaintext: {pt}')
        print(f'As text: {pt.decode("utf-8", errors="replace")}')
    except Exception as e:
        print(f'\nOAEP-SHA256 failed: {e}')
