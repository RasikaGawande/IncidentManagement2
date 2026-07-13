package com.example.incident.service;

import com.example.incident.model.Incident;
import com.example.incident.model.AgentFinding;
import com.example.incident.model.SimilarIncident;
import dev.langchain4j.model.chat.ChatLanguageModel;

import java.util.List;

/** Uses the LLM to validate retrieved history and give a bounded operational recommendation. */
public final class IncidentAdvisor {
    private final ChatLanguageModel chatModel;

    public IncidentAdvisor(ChatLanguageModel chatModel) {
        this.chatModel = chatModel;
    }

    public String recommend(Incident incoming, List<SimilarIncident> matches, List<AgentFinding> findings) {
        StringBuilder history = new StringBuilder();
        for (SimilarIncident match : matches) {
            Incident incident = match.incident();
            history.append("\n- ID: ").append(incident.id())
                    .append("\n  Similarity: ").append(String.format("%.3f", match.similarity()))
                    .append("\n  Details: ").append(incident.searchableText())
                    .append("\n  Root cause: ").append(incident.rootCause())
                    .append("\n  Resolution: ").append(incident.resolution()).append('\n');
        }
        String prompt = "You are an incident commander. Use only the supplied historical incidents and agent evidence. "
                + "Assess whether the matches are relevant, state the likely cause as a hypothesis, and give immediate, safe investigation/remediation steps. "
                + "Say explicitly when evidence is insufficient.\n\nNEW INCIDENT:\n" + incoming.searchableText()
                + "\n\nHISTORICAL INCIDENTS:" + history
                + "\n\nAGENT EVIDENCE:\n" + findings.stream()
                .map(finding -> "- " + finding.agentName() + " [" + finding.status() + "]: "
                        + finding.summary() + " Evidence: " + finding.evidence())
                .reduce("", (left, right) -> left + right + "\n");
        return chatModel.generate(prompt);
    }
}
