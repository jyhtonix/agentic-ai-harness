$prompt = @'
@binary_expert.md
@binary_reverse_expert.md
@ctf_security_agent.md
@forensics_expert.md
@malware_expert.md
@pwn_expert.md

You are the Cyber Security Capture The Flag Expert!

Binary Exploitation - format string 0

Can you use your knowledge of format strings to make the customers happy?

Download the binary here:
@challenges/challenge26_binary_formatString/format-string-0

Download the source here:
@challenges/challenge26_binary_formatString/format-string-0.c

Connect with the challenge instance here:
nc mimas.picoctf.net 58912

Hints:
1. This is an introduction of format string vulnerabilities. Look up "format specifiers" if you have never seen them before.
2. Just try out the different options.

Your task:
Analyze this CTF challenge systematically.

1. Identify the vulnerability.
2. Explain what the program is likely doing.
3. Determine what information we need from the binary and source code.
4. Give me the exact commands I should run in Kali Linux.
5. Analyze the output I provide.
6. Continue iteratively based on evidence.
7. Do not guess the flag.

Start with the initial analysis.
'@

$body = @{
    input = $prompt
} | ConvertTo-Json -Depth 10

Write-Host "Sending CTF challenge to AI Agent Harness..." -ForegroundColor Cyan

$response = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/v1/tasks" -Method POST -ContentType "application/json" -Body $body

Write-Host ""
Write-Host "========== AGENT RESPONSE ==========" -ForegroundColor Green
$response.final_response
Write-Host "====================================" -ForegroundColor Green

