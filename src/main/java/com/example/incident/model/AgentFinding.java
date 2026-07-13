package com.example.incident.model;

/** Evidence gathered by one investigation agent before the LLM is asked to advise. */
public record AgentFinding(String agentName, String status, String summary, String evidence) { }
