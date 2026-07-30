---
name: ctf-forensics
description: >-
  Digital forensics techniques for CTF challenges. Covers PCAP analysis,
  steganography, file carving, metadata extraction, log analysis, and
  hidden data discovery in files.
domain: ctf
subdomain: forensics
category: forensics
tags: [forensics, pcap, stego, metadata, carving, analysis]
version: "1.0"
author: "agent-harness"
allowed-tools: [Bash, Read, Write, Grep, Glob, Task, WebSearch]
requires: []
user_invocable: false
token_budget:
  frontmatter: 150
  full_content: 1500
---

## When to Use

When a challenge involves data files: PCAP/PCAPNG captures, images (JPG, PNG, BMP), audio files, documents, or raw binary data.

## Prerequisites

- Read access to challenge files
- Binwalk, foremost, or strings for file analysis
- Python for steganography extraction

## Common Challenge Patterns

### PCAP Analysis (challenges/challenge02_pcap_analysis/)

```
strings capture.pcapng | grep -i flag
tshark -r capture.pcapng -Y "http.request" -T fields -e http.host -e http.request.uri
tshark -r capture.pcapng -Y "data" -T fields -e data.data
```

Look for:
- HTTP requests containing credentials or flags
- DNS queries encoding exfiltrated data (subdomain strings)
- TCP streams with plaintext protocols
- Objects exported via HTTP/SMB

### Steganography (challenges/challenge04_StegoRSA/)

For images with hidden data:
```
strings image.jpg | tail
binwalk -e image.jpg
```

RSA-encrypted flags (`flag.enc` + `image.jpg`):
- Extract metadata from the image (EXIF)
- Look for embedded private keys or hints in the image
- Decrypt with OpenSSL: `openssl rsautl -decrypt -in flag.enc -inkey key.pem`

### File Metadata

```
exiftool image.jpg
xxd image.jpg | head -20  # Check for appended data
```

### Log Analysis

Parse auth logs, web server logs, or system logs for:
- Failed login patterns
- Suspicious IP addresses
- Timestamp-based correlations

## Verification

- Hidden data successfully extracted
- Decryption produces readable flag
- PCAP analysis reveals flag in network stream
