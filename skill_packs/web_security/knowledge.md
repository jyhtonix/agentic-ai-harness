# Web Security Knowledge Base

## SQL Injection
- **Detection**: `'`, `"`, `)--`, `' OR '1'='1`, `' UNION SELECT ...`
- **UNION-based**: Match column count with `ORDER BY N` or `UNION SELECT NULL,NULL,...`
- **Blind**: Boolean-based (`' AND 1=1 --` vs `' AND 1=0 --`) or time-based (`' WAITFOR DELAY '0:0:5' --`)
- **Error-based**: Extract data via database error messages
- **Mitigation**: Parameterized queries, input validation, least-privilege DB accounts

## Cross-Site Scripting (XSS)
- **Reflected**: `<script>alert('XSS')</script>`, `<img src=x onerror=alert(1)>`
- **Stored**: Payload persisted on server, affects all visitors
- **DOM-based**: Client-side JS manipulates DOM unsafely: `document.write()`, `innerHTML`
- **Mitigation**: Output encoding, Content-Security-Policy headers, input sanitization

## JWT Attacks
- **None algorithm**: Change `alg` header to `none` and remove signature
- **Weak secret**: Crack HMAC-SHA256 JWT with common secrets via brute force
- **Algorithm confusion**: Trick server into using public key as HMAC secret
- **JWT structure**: `header.payload.signature` (base64url encoded)

## Server-Side Template Injection (SSTI)
- **Detection**: `{{7*7}}` → `49` (Jinja2), `${7*7}` → `49` (Freemarker)
- **Exploitation**: Access config, environment, RCE via template engine internals
- **Common engines**: Jinja2 (Python), Freemarker (Java), Twig (PHP), ERB (Ruby)

## Common OWASP Patterns
- **Broken Access Control**: IDOR (`?user_id=123` → `?user_id=124`), missing role checks
- **Security Misconfiguration**: Default credentials, directory listing, verbose errors
- **SSRF**: Server-side request forgery via `?url=http://internal-service/admin`
- **LFI**: `?file=../../etc/passwd` or PHP wrappers (`php://filter/convert.base64-encode/resource=index`)
