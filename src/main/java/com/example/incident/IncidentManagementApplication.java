package com.example.incident;

import com.example.incident.config.OllamaConfiguration;
import com.example.incident.agent.DeploymentCheckAgent;
import com.example.incident.model.IncidentAnalysis;
import com.example.incident.repository.IncidentJsonRepository;
import com.example.incident.repository.DeploymentHistoryRepository;
import com.example.incident.service.IncidentAdvisor;
import com.example.incident.service.IncidentManagementService;
import com.example.incident.vector.InMemoryIncidentVectorStore;

import java.util.List;

/** Application entry point. */
public final class IncidentManagementApplication {
    public static void main(String[] args) throws Exception {
        OllamaConfiguration ollama = new OllamaConfiguration();
        IncidentJsonRepository repository = new IncidentJsonRepository();

        System.out.println("Building in-memory vector store using " + ollama.embeddingModelName() + "...");
        InMemoryIncidentVectorStore store = InMemoryIncidentVectorStore.from(
                repository.loadHistoricalIncidents(), ollama.embeddingModel());
        IncidentManagementService service = new IncidentManagementService(store, new IncidentAdvisor(ollama.chatModel()),
                new DeploymentCheckAgent(new DeploymentHistoryRepository()));
        List<IncidentAnalysis> results = repository.loadNewIncidents().stream().map(service::analyze).toList();

        for (IncidentAnalysis result : results) {
            System.out.println("\n============================================================");
            System.out.println("New incident: " + result.incomingIncident().id() + " - " + result.incomingIncident().title());
            System.out.println("\nMost similar historical incidents:");
            result.similarIncidents().forEach(match -> System.out.printf("- %s (similarity %.3f): %s%n",
                    match.incident().id(), match.similarity(), match.incident().title()));
            if (!result.agentFindings().isEmpty()) {
                System.out.println("\nAgent findings (top similarity below 85%):");
                result.agentFindings().forEach(finding -> System.out.println("- " + finding.summary()
                        + " [" + finding.status() + "]\n  " + finding.evidence()));
            }
            System.out.println("\nMistral verification and recommended response:\n" + result.recommendation());
        }
    }
}
