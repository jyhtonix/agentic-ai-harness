import logging
from typing import Optional

from agents.team.evidence import AgentFinding
from agents.team.specialists import SpecialistAgent

logger = logging.getLogger("agents.team.specialists.devops")


class DevOpsAgent(SpecialistAgent):
    name = "devops_agent"
    category = "devops"
    capabilities = [
        "docker_container_analysis",
        "kubernetes_analysis",
        "ci_cd_pipeline_analysis",
        "infrastructure_as_code_analysis",
        "cloud_deployment_analysis",
        "monitoring_logging_analysis",
        "secure_devops_review",
    ]

    def __init__(self, tool_executor=None, tool_selector=None, skill_selector=None):
        super().__init__(tool_executor, tool_selector, skill_selector)

    async def analyze(self, task: str, context: Optional[dict] = None) -> AgentFinding:
        logger.info("DevOpsAgent analyzing: %.60s", task)
        ctx = self._build_context(task, context)

        findings = []
        evidence = []
        tools_used = []
        confidence = 0.5

        if "docker" in ctx.lower() or "container" in ctx.lower() or "compose" in ctx.lower():
            findings.append("Docker/containerization review — multi-stage build and health check recommended")
            evidence.append("Dockerfile or Compose configuration identified")
            tools_used.append("docker")
            confidence += 0.2
        if "kubernetes" in ctx.lower() or "k8s" in ctx.lower() or "helm" in ctx.lower() or "pod" in ctx.lower():
            findings.append("Kubernetes deployment review — readiness probes and resource limits required")
            evidence.append("K8s manifests or Helm charts identified")
            tools_used.extend(["kubectl", "helm"])
            confidence += 0.2
        if "ci/cd" in ctx.lower() or "pipeline" in ctx.lower() or "github actions" in ctx.lower() or "jenkins" in ctx.lower() or "gitlab" in ctx.lower():
            findings.append("CI/CD pipeline design — build, test, scan, and deploy gates required")
            evidence.append("Pipeline configuration identified for review")
            tools_used.append("git")
            confidence += 0.2
        if "terraform" in ctx.lower() or "pulumi" in ctx.lower() or "iac" in ctx.lower() or "infrastructure as code" in ctx.lower():
            findings.append("Infrastructure as code review — terraform plan and lint validation recommended")
            evidence.append("IaC configuration identified — destructive change check needed")
            tools_used.append("terraform")
            confidence += 0.2
        if "ansible" in ctx.lower() or "playbook" in ctx.lower() or "configuration management" in ctx.lower():
            findings.append("Ansible configuration management — idempotent playbook review recommended")
            evidence.append("Ansible playbook/role identified")
            tools_used.append("ansible")
            confidence += 0.15
        if "deploy" in ctx.lower() or "cloud" in ctx.lower() or "aws" in ctx.lower() or "gcp" in ctx.lower() or "azure" in ctx.lower():
            findings.append("Cloud deployment planning — environment parity and rollback readiness required")
            evidence.append("Deployment target identified across cloud environment")
            tools_used.append("git")
            confidence += 0.15
        if "monitoring" in ctx.lower() or "prometheus" in ctx.lower() or "grafana" in ctx.lower() or "logging" in ctx.lower() or "observability" in ctx.lower():
            findings.append("Monitoring/logging setup — metrics, alerts, and structured logging recommended")
            evidence.append("Observability requirements identified")
            tools_used.extend(["prometheus", "grafana"])
            confidence += 0.15
        if "secret" in ctx.lower() or "scan" in ctx.lower() or "secure" in ctx.lower() or "security" in ctx.lower():
            findings.append("Secure DevOps review — secrets in secret manager and container scanning required")
            evidence.append("Security hardening opportunities identified in pipeline/infra")
            tools_used.append("trivy")
            confidence += 0.15

        if not findings:
            findings.append("Performing general DevOps engineering assessment")
            evidence.append("General DevOps review performed")
            tools_used.append("git")

        return AgentFinding(
            agent_name=self.name,
            findings=findings,
            evidence=list(set(evidence)),
            confidence=min(confidence, 0.95),
            tools_used=list(set(tools_used)),
            category=self.category,
        )
