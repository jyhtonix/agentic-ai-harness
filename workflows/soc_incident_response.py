"""
SOC Incident Response Workflow.

Purpose: End-to-end SOC workflow demonstrating all four SOC agents
coordinated through the Supervisor. Handles an incident from initial
alert triage through to remediation planning.

Workflow:
  1. Alert Analyst    — triage the SIEM alert
  2. Threat Hunter    — hunt for related IOCs and suspicious activity
  3. Malware Analyst  — analyse any malware samples found
  4. Incident Responder — produce containment and remediation plan
  5. Supervisor       — synthesise final incident report

Usage:
    from workflows.soc_incident_response import run_soc_incident_response
    result = await run_soc_incident_response(supervisor, alert_data)
"""

import logging

from agents.supervisor import SupervisorAgent

logger = logging.getLogger("workflow.soc_incident")


SOC_INCIDENT_REQUEST = """Investigate the following security incident.

Incident data:
{alert_data}

Follow the SOC incident response process:
1. Triage the alert and assess severity
2. Hunt for IOCs and correlate with logs
3. Analyse any malware or suspicious artefacts
4. Produce containment and remediation plan
5. Provide a final synthesised incident report

Map findings to MITRE ATT&CK, NIST CSF, and the Cyber Kill Chain."""


async def run_soc_incident_response(
    supervisor: SupervisorAgent,
    alert_data: str,
) -> dict:
    """
    Run a complete SOC incident response workflow through the Supervisor.

    Args:
        supervisor: Initialized SupervisorAgent with registry containing
                    alert_analyst, threat_hunter, malware_analyst, and
                    incident_responder.
        alert_data: The SIEM alert or incident data to investigate.

    Returns:
        Dict with plan, agent results, and final incident report.
    """
    request = SOC_INCIDENT_REQUEST.format(alert_data=alert_data)
    logger.info("Starting SOC incident response workflow")

    result = await supervisor.run(request)

    logger.info(
        "SOC incident response complete | agents=%d final_report_length=%d",
        len(result.get("agent_results", [])),
        len(result.get("final_response", "")),
    )
    return result
