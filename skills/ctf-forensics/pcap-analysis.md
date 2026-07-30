## PCAP Analysis (challenge02_pcap_analysis)

When analysing `.pcap` or `.pcapng` files:

### Initial Recon

```bash
# Get capture statistics
capinfos capture.pcapng

# List all protocols
tshark -r capture.pcapng -z io,phs

# Extract all HTTP objects
tshark -r capture.pcapng --export-objects http,/tmp/http_extract/

# Follow TCP streams
tshark -r capture.pcapng -z follow,tcp,ascii,0
```

### Flag Discovery

```bash
# Search for flag patterns
strings capture.pcapng | grep -iE "flag|ctf|secret"

# Examine DNS queries (common exfiltration channel)
tshark -r capture.pcapng -Y "dns" -T fields -e dns.qry.name

# Extract credentials from protocols
tshark -r capture.pcapng -Y "http.request.method == POST" -T fields -e http.file_data

# Reconstruct files from raw data
tshark -r capture.pcapng -Y "data" -T fields -e data.data | xxd -r -p > extracted.bin
```

**Key insight:** PCAP flags are often found in plaintext protocols (HTTP, FTP, SMTP) or encoded in DNS query subdomains.
