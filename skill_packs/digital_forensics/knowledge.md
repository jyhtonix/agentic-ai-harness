# Digital Forensics Knowledge Base

## File Metadata and Timestamps
- **MAC times**: Modified, Accessed, Created (MFT timestamps in NTFS)
- **Tool**: `stat <file>` for POSIX, `icat` + `fls` for deeper analysis
- **Deleted files**: Directory entry still present, data clusters may be intact
- **Tool**: `foremost`, `scalpel`, `photorec` for file carving from unallocated space

## Disk Image Analysis
- **Image types**: raw (.dd, .img), E01 (EnCase), AFF (Advanced Forensic Format)
- **Partition table**: MBR (Master Boot Record) vs GPT (GUID Partition Table)
- **Tool**: `mmls` (list partition layout), `fsstat` (filesystem statistics)
- **Tool**: `fls` (list files), `icat` (extract file by inode)
- **Timeline**: `fls -m / | mactime -b -d` creates body file timeline

## Memory Forensics (Volatility)
- **Image identification**: `volatility imageinfo -f <mem.dmp>`
- **Process list**: `volatility pslist -f <mem.dmp>`, `psscan`, `pstree`
- **Network connections**: `volatility netscan -f <mem.dmp>`
- **DLL injection**: `volatility malfind -f <mem.dmp>` (detect injected code)
- **Registry**: `volatility hivelist`, `printkey -K "Software\Microsoft\Windows\CurrentVersion\Run"`
- **Cmd history**: `volatility cmdscan`, `consoles`

## Evidence Handling
- **Chain of custody**: Document who, when, where, how the evidence was acquired
- **Write blocker**: Always acquire images via hardware/software write blocker
- **Hash verification**: Record MD5 and SHA256 before and after analysis
- **Working copies**: Never analyse original media — always use a forensic copy

## Browser Forensics
- **Chrome**: `History`, `Bookmarks`, `Cookies`, `Login Data` (SQLite databases)
- **Firefox**: `places.sqlite`, `cookies.sqlite`, `logins.json`
- **Downloads**: Download history records source URL, local path, timestamps
- **Cache**: Recovered cached pages may reveal accessed content

## Log Analysis
- **Windows Event Logs**: Security (4624 = logon, 4625 = failed), Sysmon, PowerShell
- **Linux syslog**: `/var/log/auth.log`, `/var/log/syslog`, `/var/log/apache2/access.log`
- **Correlation**: Cross-reference timestamps across multiple log sources
- **Tool**: `grep`, `awk`, `jq` for structured log parsing, `timeline.pl` for event correlation
