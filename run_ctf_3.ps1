$prompt = @'
@binary_expert.md
@binary_reverse_expert.md
@ctf_security_agent.md
@forensics_expert.md
@malware_expert.md
@pwn_expert.md

You are an autonomous CTF investigation agent.

Analyze the supplied CTF challenge systematically.

Binary Exploitation - format string 0

Can you use your knowledge of format strings to make the customers happy?

Download the binary here.
./challenges/challenge26_binary_formatString/format-string-0

Download the source here.
./challenges/challenge26_binary_formatString/format-string-0.c

Connect with the challenge instance here:
nc mimas.picoctf.net 57282

Hints
1. This is an introduction of format string vulnerabilities. Look up "format specifiers" if you have never seen them before.
2. Just try out the different options

IMPORTANT RULES:

1. Do NOT guess the flag.
2. Do NOT present hypothetical source code as confirmed evidence.
3. Clearly distinguish:
   - CONFIRMED: directly observed evidence
   - HYPOTHESIS: reasonable but unverified interpretation
   - UNVERIFIED: information that still requires testing
4. Before proposing an exploitation technique, establish the actual program behaviour from the available source, binary, or service.
5. When source code is available, quote only the relevant short code fragment and explain exactly why it is vulnerable.
6. When a remote service is provided, interact with it when authorized and collect actual output.
7. After every investigation step, evaluate the evidence and determine the next appropriate step.
8. Do not invent tool output, file contents, addresses, offsets, or flags.
9. The final flag must only be reported if it was actually recovered or independently verified.
10. If the flag cannot be confirmed, explicitly state:
   "FLAG NOT VERIFIED."

Required final report:

## 1. Challenge Classification

## 2. Confirmed Evidence

## 3. Vulnerability Analysis

## 4. Investigation Performed

For every step include:
- Action
- Tool/agent used
- Actual result
- Interpretation

## 5. Exploitation / Solution

Only describe techniques supported by the evidence.

## 6. Flag

Either:
- VERIFIED: picoCTF{...}
or:
- FLAG NOT VERIFIED

## 7. Confidence

State:
- High
- Medium
- Low

and explain why.

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

