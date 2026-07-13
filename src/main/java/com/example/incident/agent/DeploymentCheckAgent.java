package com.example.incident.agent;

import com.example.incident.model.AgentFinding;
import com.example.incident.model.DeploymentRecord;
import com.example.incident.model.Incident;
import com.example.incident.repository.DeploymentHistoryRepository;

import java.io.IOException;
import java.time.Instant;
import java.util.Comparator;
import java.util.List;

/** Finds the latest successful deployment for a low-similarity incident's affected service. */
public final class DeploymentCheckAgent {
    private final DeploymentHistoryRepository deploymentHistory;

    public DeploymentCheckAgent(DeploymentHistoryRepository deploymentHistory) {
        this.deploymentHistory = deploymentHistory;
    }

    public AgentFinding investigate(Incident incident) {
        try {
            List<DeploymentRecord> deployments = deploymentHistory.findByService(incident.service());
            return deployments.stream()
                    .filter(deployment -> "SUCCESS".equalsIgnoreCase(deployment.status()))
                    .max(Comparator.comparing(deployment -> Instant.parse(deployment.deployedAt())))
                    .map(this::foundDeployment)
                    .orElseGet(() -> new AgentFinding(
                            "DeploymentCheckAgent", "NO_SUCCESSFUL_DEPLOYMENT_FOUND",
                            "No successful deployment history was found for " + incident.service() + ".",
                            "Check the CI/CD deployment system manually before ruling out a release-related cause."));
        } catch (IOException error) {
            return new AgentFinding("DeploymentCheckAgent", "BACKEND_UNAVAILABLE",
                    "Deployment history could not be read.", error.getMessage());
        }
    }

    private AgentFinding foundDeployment(DeploymentRecord deployment) {
        String evidence = "deploymentId=" + deployment.deploymentId()
                + ", version=" + deployment.version()
                + ", deployedAt=" + deployment.deployedAt()
                + ", deployedBy=" + deployment.deployedBy()
                + ", change=" + deployment.changeSummary();
        return new AgentFinding("DeploymentCheckAgent", "DEPLOYMENT_FOUND",
                "Latest successful deployment for " + deployment.service() + " was " + deployment.version()
                        + " at " + deployment.deployedAt() + ".", evidence);
    }
}
