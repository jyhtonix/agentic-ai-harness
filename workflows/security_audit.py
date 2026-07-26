"""
Security Audit Workflow.

Purpose: Demonstrates the multi-agent Supervisor pattern for a
real-world use case — analysing a web application's security posture.

Workflow:
  1. Supervisor receives: "Analyze my web application security"
  2. Supervisor plans the dispatch:
     a. Research Agent → gather latest threat intelligence
     b. Coding Agent → review application code patterns
     c. Security Agent → perform vulnerability analysis
     d. QA Agent → verify findings and test coverage
  3. Supervisor collects all results
  4. Supervisor synthesises final security report

Usage:
    from workflows.security_audit import run_security_audit
    result = await run_security_audit(supervisor, code_snippet)
"""

import logging

from agents.supervisor import SupervisorAgent

logger = logging.getLogger("workflow.security_audit")

SECURITY_AUDIT_REQUEST = """Analyze the security of my web application.

Application type: {app_type}
Code to review:
```python
{code}
```

Please identify vulnerabilities, assess risk levels, and provide
remediation recommendations. Check for:
- Injection flaws (SQL, XSS, command injection)
- Authentication and authorisation issues
- Sensitive data exposure
- Security misconfiguration
- Insecure deserialization
- Known dependency vulnerabilities"""


async def run_security_audit(
    supervisor: SupervisorAgent,
    code: str,
    app_type: str = "FastAPI web application",
) -> dict:
    """
    Run a complete security audit workflow through the Supervisor.

    Args:
        supervisor: Initialized SupervisorAgent with registry.
        code: The application source code to analyse.
        app_type: Description of the application type.

    Returns:
        Dict with plan, agent results, and final report.
    """
    request = SECURITY_AUDIT_REQUEST.format(app_type=app_type, code=code)
    logger.info("Starting security audit workflow")

    result = await supervisor.run(request)

    logger.info(
        "Security audit complete | agents=%d final_response_length=%d",
        len(result.get("agent_results", [])),
        len(result.get("final_response", "")),
    )
    return result


# Example usage (requires configured LLM and registry):
#
# from models.llm import OpenAILLM
# from agents.registry import AgentRegistry
# from agents.researcher import ResearchAgent
# from agents.coder import CodingAgent
# from agents.security import SecurityAgent
# from agents.qa import QAAgent
# from agents.supervisor import SupervisorAgent
# from workflows.security_audit import run_security_audit
#
# llm = OpenAILLM()
# registry = AgentRegistry()
# registry.register(ResearchAgent(llm))
# registry.register(CodingAgent(llm))
# registry.register(SecurityAgent(llm))
# registry.register(QAAgent(llm))
# supervisor = SupervisorAgent(llm, registry)
#
# code = '''
# from flask import Flask, request
# app = Flask(__name__)
# @app.route("/login")
# def login():
#     username = request.args.get("username")
#     password = request.args.get("password")
#     query = f"SELECT * FROM users WHERE
#               username='{username}' AND password='{password}'"
#     # ... execute query
# '''
#
# result = await run_security_audit(supervisor, code)
# print(result["final_response"])
