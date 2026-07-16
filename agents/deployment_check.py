"""Agent that checks deployments when incident history is inconclusive."""
from domain.models import AgentFinding, Incident
from repositories.json_repository import DeploymentHistoryRepository

class DeploymentCheckAgent:
    def __init__(self, deployment_history: DeploymentHistoryRepository) -> None:
        self._deployment_history = deployment_history
    def investigate(self, incident: Incident) -> AgentFinding:
        try:
            deployments = self._deployment_history.find_by_service(incident.service)
        except RuntimeError as error:
            return AgentFinding(agentName="DeploymentCheckAgent", status="BACKEND_UNAVAILABLE", summary="Deployment history could not be read.", evidence=str(error))
        successful = [deployment for deployment in deployments if deployment.status.casefold() == "success"]
        if not successful:
            return AgentFinding(agentName="DeploymentCheckAgent", status="NO_SUCCESSFUL_DEPLOYMENT_FOUND", summary=f"No successful deployment history was found for {incident.service}.", evidence="Check the CI/CD deployment system manually before ruling out a release-related cause.")
        deployment = max(successful, key=lambda record: record.deployed_at)
        evidence = f"deploymentId={deployment.deployment_id}, version={deployment.version}, deployedAt={deployment.deployed_at.isoformat()}, deployedBy={deployment.deployed_by}, change={deployment.change_summary}"
        return AgentFinding(agentName="DeploymentCheckAgent", status="DEPLOYMENT_FOUND", summary=f"Latest successful deployment for {deployment.service} was {deployment.version} at {deployment.deployed_at.isoformat()}.", evidence=evidence)
