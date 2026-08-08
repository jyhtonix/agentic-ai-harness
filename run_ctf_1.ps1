$challenge = @"
You are a Web Exploitation CTF Security Agent.

Analyze and solve this CTF challenge.

Category:
Web Exploitation

Challenge:
WebDecode

Description:
Do you know how to use the web inspector?

Target:
http://titan.picoctf.net:53350/

Hints:
1. Use the web inspector on other files included by the web page.
2. The flag may or may not be encoded.

Tasks:
- Analyze the website.
- Identify possible vulnerabilities.
- Inspect files, JavaScript, HTML, endpoints.
- Extract the flag.
- Explain the exploitation steps.
"@

$body = @{
    input = $challenge
} | ConvertTo-Json


$response = Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/api/v1/tasks" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body


$response.final_response