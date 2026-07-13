package com.example.incident.model;

/** A deployment event returned by the deployment-history backend. */
public record DeploymentRecord(String deploymentId, String service, String version, String deployedAt,
                               String deployedBy, String changeSummary, String status) { }
