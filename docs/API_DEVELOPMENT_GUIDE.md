# CTF Platform API Development Guide

## Overview

The CTF Platform API provides RESTful access to challenge discovery, execution, session management, and learning report retrieval. It follows a clean separation between API layer, service layer, and the underlying agentic engine.

### Architecture

```
HTTP Client
    |
    v
API Layer (FastAPI routes + Pydantic schemas)
    |
    v
Service Layer (SessionManager, AuthProvider)
    |
    v
Engine Layer (ChallengeLoader, SupervisorAgent, FlagVerifier, etc.)
```

### Separation of Concerns

- **API Layer** (`api/routes/`): HTTP concerns — request parsing, response formatting, status codes
- **Service Layer** (`api/session_manager.py`, `api/auth.py`): Orchestration — session lifecycle, auth
- **Engine Layer** (existing): Business logic — challenge loading, agent execution, verification

Route handlers import and call services; services call engine components. Routes never contain orchestration logic.

## Endpoint Reference

### Health

```
GET /health
```

Returns API status and version.

```json
{"status": "ok", "version": "0.3.5"}
```

### Challenges

#### List Challenges

```
GET /api/v1/challenges
```

Optional query parameters: `category`, `difficulty`, `skill`

```json
[
  {
    "id": "stego_basic_001",
    "name": "Stego Basic",
    "category": "steganography",
    "difficulty": "beginner",
    "description": "A steganography challenge..."
  }
]
```

#### Run Challenge

```
POST /api/v1/challenges/run
```

Non-blocking: creates a session and kicks off execution in a background task.

```json
{"challenge_id": "stego_basic_001", "user_prompt": "Optional custom prompt"}
```

Response (201):

```json
{"session_id": "a1b2c3d4e5f6", "status": "running"}
```

### Sessions

#### Get Session Status

```
GET /api/v1/sessions/{session_id}
```

```json
{
  "session_id": "a1b2c3d4e5f6",
  "status": "COMPLETED",
  "challenge": "stego_basic_001",
  "flag_status": "PASS",
  "error": null
}
```

Session states: `CREATED` → `RUNNING` → `COMPLETED` / `FAILED`

### Reports

#### Get Learning Report

```
GET /api/v1/reports/{session_id}
```

Returns the complete learning report for a completed session.

```json
{
  "session_id": "a1b2c3d4e5f6",
  "challenge": "stego_basic_001",
  "skills_used": [{"name": "steganography-basics", ...}],
  "tools_used": ["strings", "exiftool"],
  "flag_result": "PASS",
  "recommendations": ["Keep practicing"],
  "student_report": "=== LEARNING REPORT ===...",
  "instructor_summary": "=== INSTRUCTOR SUMMARY ===..."
}
```

## Session Lifecycle

```
POST /api/v1/challenges/run
    |
    v
Session created (CREATED)
    |
    v
Background task starts supervisor.run()
    |
    v
Session updated to RUNNING
    |
    v
Execution completes or fails
    |
    v
Session updated to COMPLETED or FAILED
    |
    v
Client polls GET /api/v1/sessions/{id}
    |
    v
Client retrieves GET /api/v1/reports/{id}
```

## Authentication

### Anonymous Mode (Development)

No authentication required. Suitable for local development and testing.

```python
AuthProvider(mode="anonymous")
```

### API Key Mode (Production)

Requires `X-API-Key` header matching the configured key.

```python
AuthProvider(mode="api_key", api_key="your-secret-key")
```

### Future Authentication

The `AuthProvider` interface supports extension for:

- University SSO (SAML/OIDC)
- LMS integration (LTI 1.3)
- JWT-based token authentication
- OAuth2 with scoped access

To implement a new auth mode:

```python
class CustomAuthProvider(AuthProvider):
    async def authenticate(self, token: str) -> tuple[bool, str]:
        # Custom logic
        return True, "user_id"
```

## Integration Examples

### Python Client

```python
import httpx

BASE = "http://localhost:8000"

# List challenges
challenges = httpx.get(f"{BASE}/api/v1/challenges?category=malware").json()

# Run a challenge
run = httpx.post(f"{BASE}/api/v1/challenges/run", json={
    "challenge_id": "stego_basic_001",
}).json()
session_id = run["session_id"]

# Poll for completion
while True:
    status = httpx.get(f"{BASE}/api/v1/sessions/{session_id}").json()
    if status["status"] in ("COMPLETED", "FAILED"):
        break

# Get report
report = httpx.get(f"{BASE}/api/v1/reports/{session_id}").json()
```

### curl

```bash
# Health check
curl http://localhost:8000/health

# List challenges
curl "http://localhost:8000/api/v1/challenges?category=steganography"

# Run challenge
curl -X POST http://localhost:8000/api/v1/challenges/run \
  -H "Content-Type: application/json" \
  -d '{"challenge_id": "stego_basic_001"}'

# Check session
curl http://localhost:8000/api/v1/sessions/<session_id>

# Get report
curl http://localhost:8000/api/v1/reports/<session_id>
```
