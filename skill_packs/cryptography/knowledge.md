# Cryptography Knowledge Base

## Encoding Detection
- **Base64**: Alphanumeric + `+/` + `=` padding, length multiple of 4
- **Hex**: Characters `0-9a-f` only, even length
- **Base32**: Uppercase A-Z + 2-7 + `=` padding
- **Binary**: Only `0` and `1`, length multiple of 8
- **ROT**: Shifted alphabet, frequency analysis reveals pattern

## RSA Basics
- `n = p * q` (modulus), `e` (public exponent), `d` (private exponent)
- Encryption: `c = m^e mod n`, Decryption: `m = c^d mod n`
- **Small e attack** (e=3): If `m^3 < n`, take integer cube root
- **Wiener attack**: When `d < n^0.25`, use continued fractions on `e/n`
- **Common modulus**: Same `n`, two `e` values → extended Euclidean algorithm
- **Broadcast**: Same `e` and `m`, different `n` → Chinese Remainder Theorem

## Hash Identification
- **MD5**: 32 hex characters, always starts with letters
- **SHA1**: 40 hex characters
- **SHA256**: 64 hex characters
- **bcrypt**: Starts with `$2a$`, `$2b$`, or `$2y$`
- **LM/NTLM**: Windows password hashes (LM splits into two 7-char halves)

## Weak Cryptography Patterns
- **ECB mode**: Identical plaintext blocks produce identical ciphertext blocks
- **Fixed IV**: Repeated use of same initialization vector leaks patterns
- **Custom crypto**: Homebrew algorithms are almost always breakable
- **Weak PRNG**: `rand()` without proper seeding produces predictable output
- **Key reuse**: One-time pad with reused key → XOR ciphertexts together

## Padding Oracle Attack
- Service reveals whether padding is valid (via error message or timing)
- Decrypt ciphertext block-by-block by manipulating padding byte
- Requires: ability to submit modified ciphertext and observe padding validity
