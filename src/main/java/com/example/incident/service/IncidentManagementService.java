package com.example.incident.service;

import com.example.incident.agent.DeploymentCheckAgent;
import com.example.incident.model.AgentFinding;
import com.example.incident.model.Incident;
import com.example.incident.model.IncidentAnalysis;
import com.example.incident.model.SimilarIncident;
import com.example.incident.vector.InMemoryIncidentVectorStore;

import java.util.List;

/** Coordinates similarity search and LLM verification for one incoming incident. */
public final class IncidentManagementService {
    private final InMemoryIncidentVectorStore vectorStore;
    private final IncidentAdvisor advisor;
    private final DeploymentCheckAgent deploymentCheckAgent;

    public IncidentManagementService(InMemoryIncidentVectorStore vectorStore, IncidentAdvisor advisor,
                                     DeploymentCheckAgent deploymentCheckAgent) {
        this.vectorStore = vectorStore;
        this.advisor = advisor;
        this.deploymentCheckAgent = deploymentCheckAgent;
    }

    public IncidentAnalysis analyze(Incident incomingIncident) {
        List<SimilarIncident> matches = vectorStore.search(incomingIncident, 3);
        List<AgentFinding> findings = hasStrongHistoricalMatch(matches)
                ? List.of()
                : List.of(deploymentCheckAgent.investigate(incomingIncident));
        return new IncidentAnalysis(incomingIncident, matches, findings,
                advisor.recommend(incomingIncident, matches, findings));
    }

    private boolean hasStrongHistoricalMatch(List<SimilarIncident> matches) {
        return !matches.isEmpty() && matches.get(0).similarity() >= 0.85;
    }
}
