package com.example.incident.model;

import java.util.List;

public record IncidentAnalysis(Incident incomingIncident, List<SimilarIncident> similarIncidents,
                               List<AgentFinding> agentFindings, String recommendation) { }
